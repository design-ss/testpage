import hashlib
import html
import io
import zipfile

import numpy as np
import streamlit as st
from PIL import Image, ImageDraw


def render_preview_filename(container, file_name):
    escaped_name = html.escape(str(file_name), quote=True)
    container.markdown(
        f'<div title="{escaped_name}" style="height:1.25rem; line-height:1.25rem; '
        'overflow:hidden; text-overflow:ellipsis; white-space:nowrap; '
        'font-size:0.875rem; opacity:0.6;">'
        f'{escaped_name}</div>',
        unsafe_allow_html=True,
    )


SOURCE_OUTPUT_SIZE = (960, 640)
SMALL_OUTPUT_SIZE = (100, 100)
LARGE_OUTPUT_SIZE = (640, 640)
INITIAL_LARGE_SCALES = (1.0, 0.95, 0.90, 0.85, 0.80)
ADDITIONAL_LARGE_SCALES = tuple(value / 100 for value in range(75, 0, -5))


def safe_name(name):
    normalized = (name or "image.png").replace("\\", "/")
    return normalized.rsplit("/", 1)[-1] or "image.png"


def uploaded_file_to_data(uploaded_file):
    return safe_name(uploaded_file.name), uploaded_file.getvalue()


def open_rgba(file_data):
    with Image.open(io.BytesIO(file_data[1])) as image:
        return image.convert("RGBA").copy()


def image_to_png_bytes(image):
    with io.BytesIO() as buffer:
        image.save(buffer, format="PNG")
        return buffer.getvalue()


def png_bytes_to_image(image_bytes):
    with Image.open(io.BytesIO(image_bytes)) as image:
        return image.convert("RGBA").copy()


def visible_crop(image):
    bounds = image.getbbox()
    if bounds is None:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    return image.crop(bounds)


def image_weight_array(image):
    # 従来どおり輝度を中心計算に使用し、真っ黒な画像だけアルファへ切り替える。
    weights = np.asarray(image.convert("L"), dtype=np.float64)
    if weights.sum() == 0:
        weights = np.asarray(image.getchannel("A"), dtype=np.float64)
    return weights


def weighted_center(weights):
    total = weights.sum()
    if total == 0:
        height, width = weights.shape
        return width / 2, height / 2

    x_weights = weights.sum(axis=0)
    y_weights = weights.sum(axis=1)
    center_x = np.dot(
        np.arange(weights.shape[1], dtype=np.float64),
        x_weights,
    ) / total
    center_y = np.dot(
        np.arange(weights.shape[0], dtype=np.float64),
        y_weights,
    ) / total
    return float(center_x), float(center_y)


def resize_small_base(image):
    width, height = image.size
    if width < height:
        if width > 100 and height / width > 1.7:
            new_width = 70
            new_height = max(1, int(height * 70 / width))
        else:
            new_width = max(1, int(width * 100 / height))
            new_height = 100
    else:
        if height > 100 and width / height > 1.7:
            new_width = max(1, int(width * 70 / height))
            new_height = 70
        else:
            new_width = 100
            new_height = max(1, int(height * 100 / width))
    return image.resize((new_width, new_height))


@st.cache_data(show_spinner=False)
def generate_small_png(
    file_data,
    scale_100,
    horizontal_shift_100,
    vertical_shift_100,
):
    image = visible_crop(open_rgba(file_data))
    image = resize_small_base(image)

    # 標準UIの0.75を、従来の初期倍率0.7へ対応させる。
    effective_scale = scale_100 * (0.7 / 0.75)
    new_width = max(1, int(image.width * effective_scale))
    new_height = max(1, int(image.height * effective_scale))
    image = image.resize((new_width, new_height))

    weights = image_weight_array(image)
    center_x, center_y = weighted_center(weights)
    center_x = int(center_x)
    center_y = int(center_y)

    paste_x = 50 - center_x + horizontal_shift_100
    paste_y = 50 - center_y - vertical_shift_100
    output = Image.new("RGBA", SMALL_OUTPUT_SIZE, (0, 0, 0, 0))
    output.alpha_composite(image, dest=(paste_x, paste_y))
    return image_to_png_bytes(output)


@st.cache_data(show_spinner=False)
def prepare_large_base(file_data):
    image = visible_crop(open_rgba(file_data))
    weights = image_weight_array(image)
    center_x, _ = weighted_center(weights)
    center_x = int(center_x)

    nonzero_rows = np.nonzero(weights)[0]
    if len(nonzero_rows) == 0:
        bottom_y = image.height - 1
    else:
        bottom_y = int(nonzero_rows.max())

    # 従来処理と同じく、表示パーツの最下部を下端から15pxに配置する。
    anchor_y = bottom_y - 305
    return image_to_png_bytes(image), center_x, anchor_y


def scaled_content_bounds(content_bounds, scale, anchor_x, anchor_y):
    left, upper, right, lower = content_bounds
    paste_x = 320 - round(anchor_x * scale)
    paste_y = 320 - round(anchor_y * scale)
    return (
        paste_x + round(left * scale),
        paste_y + round(upper * scale),
        paste_x + round(right * scale),
        paste_y + round(lower * scale),
    )


def bounds_fit_canvas(bounds, shift_x=0, shift_y=0):
    left, upper, right, lower = bounds
    return (
        left + shift_x >= 0
        and upper + shift_y >= 0
        and right + shift_x <= LARGE_OUTPUT_SIZE[0]
        and lower + shift_y <= LARGE_OUTPUT_SIZE[1]
    )


def required_axis_shift(start, end, canvas_size):
    content_size = end - start
    if content_size > canvas_size:
        return round((canvas_size - start - end) / 2)
    if start < 0:
        return -start
    if end > canvas_size:
        return canvas_size - end
    return 0


@st.cache_data(show_spinner=False)
def calculate_default_large_transform(image_bytes, anchor_x, anchor_y):
    image = png_bytes_to_image(image_bytes)
    alpha_mask = image.getchannel("A").point(
        lambda alpha: 255 if alpha > 1 else 0
    )
    content_bounds = alpha_mask.getbbox()
    if content_bounds is None:
        return 1.0, 0, 0

    # 1. 従来位置のまま、5％刻みで最大20％縮小する。
    for scale in INITIAL_LARGE_SCALES:
        bounds = scaled_content_bounds(
            content_bounds,
            scale,
            anchor_x,
            anchor_y,
        )
        if bounds_fit_canvas(bounds):
            return scale, 0, 0

    # 2. 20％縮小した状態で、必要最小限の上下左右移動を行う。
    scale = INITIAL_LARGE_SCALES[-1]
    bounds = scaled_content_bounds(
        content_bounds,
        scale,
        anchor_x,
        anchor_y,
    )
    shift_x = required_axis_shift(bounds[0], bounds[2], LARGE_OUTPUT_SIZE[0])
    shift_y = required_axis_shift(bounds[1], bounds[3], LARGE_OUTPUT_SIZE[1])
    if bounds_fit_canvas(bounds, shift_x, shift_y):
        return scale, shift_x, shift_y

    # 3. 移動しても収まらない場合だけ、5％刻みでさらに縮小する。
    for scale in ADDITIONAL_LARGE_SCALES:
        bounds = scaled_content_bounds(
            content_bounds,
            scale,
            anchor_x,
            anchor_y,
        )
        shift_x = required_axis_shift(
            bounds[0],
            bounds[2],
            LARGE_OUTPUT_SIZE[0],
        )
        shift_y = required_axis_shift(
            bounds[1],
            bounds[3],
            LARGE_OUTPUT_SIZE[1],
        )
        if bounds_fit_canvas(bounds, shift_x, shift_y):
            return scale, shift_x, shift_y

    return ADDITIONAL_LARGE_SCALES[-1], shift_x, shift_y


@st.cache_data(show_spinner=False)
def generate_large_png(
    file_data,
    scale_640,
    horizontal_shift_640,
    vertical_shift_640,
):
    image_bytes, anchor_x, anchor_y = prepare_large_base(file_data)
    image = png_bytes_to_image(image_bytes)
    default_scale, default_shift_x, default_shift_y = (
        calculate_default_large_transform(
            image_bytes,
            anchor_x,
            anchor_y,
        )
    )
    effective_scale = default_scale * scale_640
    new_width = max(1, round(image.width * effective_scale))
    new_height = max(1, round(image.height * effective_scale))
    image = image.resize((new_width, new_height))

    # 全体画像を保持して配置し、640×640キャンバスの外側だけを落とす。
    paste_x = (
        320
        - round(anchor_x * effective_scale)
        + default_shift_x
        + horizontal_shift_640
    )
    paste_y = (
        320
        - round(anchor_y * effective_scale)
        + default_shift_y
        - vertical_shift_640
    )
    output = Image.new("RGBA", LARGE_OUTPUT_SIZE, (0, 0, 0, 0))
    output.alpha_composite(image, dest=(paste_x, paste_y))
    return image_to_png_bytes(output)


@st.cache_data(show_spinner=False)
def resize_png(image_bytes, size):
    image = png_bytes_to_image(image_bytes)
    return image_to_png_bytes(image.resize(size))


@st.cache_data(show_spinner=False)
def original_960_png(file_data):
    image = open_rgba(file_data).resize(SOURCE_OUTPUT_SIZE)
    return image_to_png_bytes(image)


@st.cache_data(show_spinner=False)
def make_preview_png(image_bytes, preview_size):
    image = png_bytes_to_image(image_bytes)
    if image.size != preview_size:
        image = image.resize(preview_size)

    draw = ImageDraw.Draw(image)
    width, height = image.size
    draw.rectangle((0, 0, width - 1, height - 1), outline="red", width=1)
    draw.line((width // 2, 0, width // 2, height - 1), fill="red", width=1)
    draw.line((0, height // 2, width - 1, height // 2), fill="red", width=1)
    return image_to_png_bytes(image)


def selection_checkbox_keys(index, file_name):
    digest = hashlib.sha1(file_name.encode("utf-8")).hexdigest()[:10]
    return (
        f"mm_pet_select_100_{index}_{digest}",
        f"mm_pet_select_640_{index}_{digest}",
    )


def sync_selection_checkbox(source_key, target_key):
    st.session_state[target_key] = st.session_state[source_key]


def file_signature(file_data):
    return file_data[0], hashlib.sha256(file_data[1]).hexdigest()


def show_download(zip_name, zip_bytes, key):
    st.download_button(
        label=f"{zip_name}をダウンロード",
        data=zip_bytes,
        file_name=zip_name,
        mime="application/zip",
        key=key,
        on_click="ignore",
    )


@st.cache_data(show_spinner=False)
def build_zip(
    file_data_items,
    scale_100,
    horizontal_shift_100,
    vertical_shift_100,
    scale_640,
    horizontal_shift_640,
    vertical_shift_640,
    selected_indices,
):
    outputs = {}
    for index in selected_indices:
        file_data = file_data_items[index]
        file_name = file_data[0]
        image_100 = generate_small_png(
            file_data,
            scale_100,
            horizontal_shift_100,
            vertical_shift_100,
        )
        image_640 = generate_large_png(
            file_data,
            scale_640,
            horizontal_shift_640,
            vertical_shift_640,
        )
        outputs[f"100x100/{file_name}"] = image_100
        outputs[f"50x50/{file_name}"] = resize_png(image_100, (50, 50))
        outputs[f"640x640/{file_name}"] = image_640
        outputs[f"320x320/{file_name}"] = resize_png(image_640, (320, 320))
        outputs[f"960x640/{file_name}"] = original_960_png(file_data)

    with io.BytesIO() as buffer:
        with zipfile.ZipFile(
            buffer,
            "w",
            compression=zipfile.ZIP_DEFLATED,
        ) as archive:
            for path, image_bytes in outputs.items():
                archive.writestr(path, image_bytes)
        return buffer.getvalue()


@st.fragment
def render_adjustment_and_export(file_data_items):
    st.divider()

    vertical_shift_100 = st.slider(
        "100×100：下移動 ⇔ 上移動",
        min_value=-150,
        max_value=150,
        value=0,
        step=1,
        key="mm_pet_vertical_shift_100",
    )
    horizontal_shift_100 = st.slider(
        "100×100：左移動 ⇔ 右移動",
        min_value=-150,
        max_value=150,
        value=0,
        step=1,
        key="mm_pet_horizontal_shift_100",
    )
    scale_100 = st.slider(
        "100×100：縮小 ⇔ 拡大（デフォルトは0.75）",
        min_value=0.5,
        max_value=1.5,
        value=0.75,
        step=0.01,
        key="mm_pet_scale_100",
    )

    columns_100 = st.columns(4)
    for index, file_data in enumerate(file_data_items):
        file_name = file_data[0]
        image_100 = generate_small_png(
            file_data,
            scale_100,
            horizontal_shift_100,
            vertical_shift_100,
        )
        key_100, key_640 = selection_checkbox_keys(index, file_name)
        column = columns_100[index % 4]
        render_preview_filename(column, file_name)
        column.image(make_preview_png(image_100, SMALL_OUTPUT_SIZE), width=102)
        column.checkbox(
            f"{file_name}を選択",
            key=key_100,
            label_visibility="collapsed",
            on_change=sync_selection_checkbox,
            args=(key_100, key_640),
        )

    st.divider()

    vertical_shift_640 = st.slider(
        "640×640：下移動 ⇔ 上移動",
        min_value=-150,
        max_value=150,
        value=0,
        step=1,
        key="mm_pet_vertical_shift_640",
    )
    horizontal_shift_640 = st.slider(
        "640×640：左移動 ⇔ 右移動",
        min_value=-150,
        max_value=150,
        value=0,
        step=1,
        key="mm_pet_horizontal_shift_640",
    )
    scale_640 = st.slider(
        "640×640：縮小 ⇔ 拡大（デフォルトは1.0）",
        min_value=0.5,
        max_value=1.5,
        value=1.0,
        step=0.01,
        key="mm_pet_scale_640",
    )

    columns_640 = st.columns(4)
    for index, file_data in enumerate(file_data_items):
        file_name = file_data[0]
        image_640 = generate_large_png(
            file_data,
            scale_640,
            horizontal_shift_640,
            vertical_shift_640,
        )
        key_100, key_640 = selection_checkbox_keys(index, file_name)
        column = columns_640[index % 4]
        render_preview_filename(column, file_name)
        column.image(make_preview_png(image_640, (200, 200)), width=202)
        column.checkbox(
            f"{file_name}を選択",
            key=key_640,
            label_visibility="collapsed",
            on_change=sync_selection_checkbox,
            args=(key_640, key_100),
        )

    selected_indices = tuple(
        index
        for index, file_data in enumerate(file_data_items)
        if st.session_state.get(
            selection_checkbox_keys(index, file_data[0])[0],
            False,
        )
    )
    current_config = (
        tuple(file_signature(item) for item in file_data_items),
        vertical_shift_100,
        horizontal_shift_100,
        scale_100,
        vertical_shift_640,
        horizontal_shift_640,
        scale_640,
        selected_indices,
    )
    stored_download = st.session_state.get("mm_pet_generated_zip")
    if stored_download and stored_download["config"] != current_config:
        del st.session_state["mm_pet_generated_zip"]

    st.divider()
    export_all_column, export_selected_column = st.columns(2)
    with export_all_column:
        if st.button(
            "一括書き出し",
            key="mm_pet_export_all",
            use_container_width=True,
        ):
            with st.spinner("ZIPを生成中です..."):
                zip_bytes = build_zip(
                    file_data_items,
                    scale_100,
                    horizontal_shift_100,
                    vertical_shift_100,
                    scale_640,
                    horizontal_shift_640,
                    vertical_shift_640,
                    tuple(range(len(file_data_items))),
                )
            st.session_state["mm_pet_generated_zip"] = {
                "config": current_config,
                "name": "mm_pet1.zip",
                "bytes": zip_bytes,
                "key": "mm_pet_download_all",
            }
        st.write("全てのファイルを書き出します。")

    with export_selected_column:
        if st.button(
            "個別書き出し",
            key="mm_pet_export_selected",
            use_container_width=True,
        ):
            if not selected_indices:
                st.warning("書き出すファイルを1件以上選択してください。")
            else:
                with st.spinner("ZIPを生成中です..."):
                    zip_bytes = build_zip(
                        file_data_items,
                        scale_100,
                        horizontal_shift_100,
                        vertical_shift_100,
                        scale_640,
                        horizontal_shift_640,
                        vertical_shift_640,
                        selected_indices,
                    )
                st.session_state["mm_pet_generated_zip"] = {
                    "config": current_config,
                    "name": "mm_pet2.zip",
                    "bytes": zip_bytes,
                    "key": "mm_pet_download_selected",
                }
        st.write("チェックを入れたファイルを書き出します。")

    stored_download = st.session_state.get("mm_pet_generated_zip")
    if stored_download:
        st.success("書き出しが完了しました。")
        show_download(
            stored_download["name"],
            stored_download["bytes"],
            stored_download.get("key", "mm_pet_download"),
        )


def main():
    st.set_page_config(page_title="mmペット書き出し")
    st.title("mmペット書き出し")
    st.markdown(
        '<span style="color:red;">※未圧縮データを使ってください！</span>',
        unsafe_allow_html=True,
    )

    export_files = st.file_uploader(
        "ファイルを選択",
        type="png",
        accept_multiple_files=True,
        key="export_files",
    )
    export_files = sorted(
        export_files or [],
        key=lambda uploaded_file: uploaded_file.name,
    )
    if not export_files:
        return

    file_data_items = tuple(
        uploaded_file_to_data(uploaded_file)
        for uploaded_file in export_files
    )
    render_adjustment_and_export(file_data_items)


if __name__ == "__main__":
    main()
