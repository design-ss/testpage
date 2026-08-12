import hashlib
import html
import io
import zipfile

import numpy as np
import streamlit as st
from PIL import Image, ImageDraw, ImageOps


def render_preview_filename(container, file_name):
    escaped_name = html.escape(str(file_name), quote=True)
    container.markdown(
        f'<div title="{escaped_name}" style="height:1.25rem; line-height:1.25rem; '
        'overflow:hidden; text-overflow:ellipsis; white-space:nowrap; '
        'font-size:0.875rem; opacity:0.6;">'
        f'{escaped_name}</div>',
        unsafe_allow_html=True,
    )


SOURCE_SIZE = (960, 640)
SMALL_SIZE = (100, 100)
LARGE_SIZE = (640, 640)


def safe_name(name):
    normalized = (name or "image.png").replace("\\", "/")
    return normalized.rsplit("/", 1)[-1] or "image.png"


def uploaded_file_to_data(uploaded_file):
    if uploaded_file is None:
        return None
    return safe_name(uploaded_file.name), uploaded_file.getvalue()


def open_rgba(file_data, size=None):
    if file_data is None:
        output_size = size or SOURCE_SIZE
        return Image.new("RGBA", output_size, (0, 0, 0, 0))

    _, image_bytes = file_data
    with Image.open(io.BytesIO(image_bytes)) as image:
        rgba = image.convert("RGBA")

    if size is not None:
        rgba = rgba.resize(size, Image.Resampling.LANCZOS)
    return rgba


def image_to_png_bytes(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def png_bytes_to_image(image_bytes):
    with Image.open(io.BytesIO(image_bytes)) as image:
        return image.convert("RGBA")


def visible_crop(image):
    bbox = image.getbbox()
    if bbox is None:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    return image.crop(bbox)


def image_weight_array(image):
    # 旧処理の見た目中心を維持するため輝度を優先し、
    # 真っ黒な画像ではアルファを使用する。
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
    center_x = float(
        np.dot(np.arange(weights.shape[1], dtype=np.float64), x_weights)
        / total
    )
    center_y = float(
        np.dot(np.arange(weights.shape[0], dtype=np.float64), y_weights)
        / total
    )
    return center_x, center_y


def resize_small_base(image):
    width, height = image.size

    if width < height:
        if width > 100 and height / width > 1.7:
            new_width = 70
            new_height = max(1, round(height * 70 / width))
        else:
            new_height = 100
            new_width = max(1, round(width * 100 / height))
    else:
        if height > 100 and width / height > 1.7:
            new_height = 70
            new_width = max(1, round(width * 70 / height))
        else:
            new_width = 100
            new_height = max(1, round(height * 100 / width))

    return image.resize(
        (new_width, new_height), Image.Resampling.LANCZOS
    )


@st.cache_data(show_spinner=False)
def generate_small_png(
    file_data,
    attribution_bytes,
    vertical_shift,
    horizontal_shift,
    scale,
):
    image = visible_crop(open_rgba(file_data))
    base = resize_small_base(image)

    # 標準初期値0.75で、旧アプリの初期倍率0.7を再現する。
    effective_scale = scale * (0.7 / 0.75)
    new_width = max(1, round(base.width * effective_scale))
    new_height = max(1, round(base.height * effective_scale))
    resized = base.resize(
        (new_width, new_height), Image.Resampling.LANCZOS
    )

    weights = image_weight_array(resized)
    center_x, center_y = weighted_center(weights)

    paste_x = round(50 - center_x + horizontal_shift)
    paste_y = round(50 - center_y - vertical_shift)
    output = Image.new("RGBA", SMALL_SIZE, (0, 0, 0, 0))
    output.alpha_composite(resized, (paste_x, paste_y))

    with Image.open(io.BytesIO(attribution_bytes)) as attribution:
        attribution_rgba = attribution.convert("RGBA").resize(
            SMALL_SIZE, Image.Resampling.LANCZOS
        )
    output.alpha_composite(attribution_rgba)
    return image_to_png_bytes(output)


@st.cache_data(show_spinner=False)
def generate_large_png(
    file_data,
    vertical_shift,
    horizontal_shift,
    scale,
):
    image = visible_crop(open_rgba(file_data, SOURCE_SIZE))
    weights = image_weight_array(image)
    center_x, _ = weighted_center(weights)

    nonzero_rows = np.nonzero(weights)[0]
    if len(nonzero_rows) == 0:
        bottom_y = image.height - 1
    else:
        bottom_y = int(nonzero_rows.max())

    # 旧処理は下端が出力の約595px位置になるよう配置していた。
    anchor_y = bottom_y - 275

    new_width = max(1, round(image.width * scale))
    new_height = max(1, round(image.height * scale))
    resized = image.resize(
        (new_width, new_height), Image.Resampling.LANCZOS
    )

    # 拡大後の全画像を保持したまま配置し、最後に640x640枠で切り取る。
    paste_x = round(320 - center_x * scale + horizontal_shift)
    paste_y = round(320 - anchor_y * scale - vertical_shift)
    output = Image.new("RGBA", LARGE_SIZE, (0, 0, 0, 0))
    output.alpha_composite(resized, (paste_x, paste_y))
    return image_to_png_bytes(output)


def make_preview_image(image_bytes, preview_size):
    preview = png_bytes_to_image(image_bytes)
    if preview.size != preview_size:
        preview = preview.resize(preview_size, Image.Resampling.LANCZOS)

    draw = ImageDraw.Draw(preview)
    center_x = preview.width // 2
    center_y = preview.height // 2
    draw.line(
        (center_x, 0, center_x, preview.height),
        fill="red",
        width=1,
    )
    draw.line(
        (0, center_y, preview.width, center_y),
        fill="red",
        width=1,
    )
    return ImageOps.expand(preview, border=1, fill="red")


def resize_png(image_bytes, size):
    image = png_bytes_to_image(image_bytes)
    return image_to_png_bytes(
        image.resize(size, Image.Resampling.LANCZOS)
    )


def original_960_png(file_data):
    return image_to_png_bytes(open_rgba(file_data, SOURCE_SIZE))


def selection_checkbox_keys(index, file_name):
    suffix = f"{index}_{file_name}"
    return f"pet_select_100_{suffix}", f"pet_select_640_{suffix}"


def sync_selection_checkbox(source_key, target_key):
    st.session_state[target_key] = st.session_state[source_key]


def file_signature(file_data):
    if file_data is None:
        return None
    name, image_bytes = file_data
    return name, hashlib.sha256(image_bytes).hexdigest()


@st.cache_data(show_spinner=False)
def build_zip(
    file_data_items,
    attribution_bytes,
    small_vertical_shift,
    small_horizontal_shift,
    small_scale,
    large_vertical_shift,
    large_horizontal_shift,
    large_scale,
    selected_indices,
):
    outputs = {}

    for index in selected_indices:
        file_data = file_data_items[index]
        file_name = file_data[0]

        small_png = generate_small_png(
            file_data,
            attribution_bytes,
            small_vertical_shift,
            small_horizontal_shift,
            small_scale,
        )
        large_png = generate_large_png(
            file_data,
            large_vertical_shift,
            large_horizontal_shift,
            large_scale,
        )

        outputs[f"100x100/{file_name}"] = small_png
        outputs[f"50x50/{file_name}"] = resize_png(
            small_png, (50, 50)
        )
        outputs[f"640x640/{file_name}"] = large_png
        outputs[f"320x320/{file_name}"] = resize_png(
            large_png, (320, 320)
        )
        outputs[f"960x640/{file_name}"] = original_960_png(file_data)

    buffer = io.BytesIO()
    with zipfile.ZipFile(
        buffer, "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        for path, image_bytes in outputs.items():
            archive.writestr(path, image_bytes)
    return buffer.getvalue()


@st.fragment
def render_adjustment_and_export(file_data_items, attribution_bytes):
    st.markdown("---")

    small_vertical_shift = st.slider(
        "100×100：下移動 ⇔ 上移動",
        min_value=-150,
        max_value=150,
        value=0,
        key="pet_small_vertical_shift",
    )
    small_horizontal_shift = st.slider(
        "100×100：左移動 ⇔ 右移動",
        min_value=-150,
        max_value=150,
        value=0,
        key="pet_small_horizontal_shift",
    )
    small_scale = st.slider(
        "100×100：縮小 ⇔ 拡大（デフォルトは0.75）",
        min_value=0.5,
        max_value=1.5,
        value=0.75,
        step=0.01,
        key="pet_small_scale",
    )

    st.write("**100×100プレビュー**")
    small_columns = st.columns(4)
    with st.spinner("100×100プレビュー画像を生成中です..."):
        for index, file_data in enumerate(file_data_items):
            file_name = file_data[0]
            preview_png = generate_small_png(
                file_data,
                attribution_bytes,
                small_vertical_shift,
                small_horizontal_shift,
                small_scale,
            )
            column = small_columns[index % 4]
            render_preview_filename(column, file_name)
            column.image(
                make_preview_image(preview_png, SMALL_SIZE),
                width="content",
            )
            small_key, large_key = selection_checkbox_keys(
                index, file_name
            )
            column.checkbox(
                "個別書き出し",
                key=small_key,
                label_visibility="collapsed",
                on_change=sync_selection_checkbox,
                args=(small_key, large_key),
            )

    st.markdown("---")

    large_vertical_shift = st.slider(
        "640×640：下移動 ⇔ 上移動",
        min_value=-150,
        max_value=150,
        value=0,
        key="pet_large_vertical_shift",
    )
    large_horizontal_shift = st.slider(
        "640×640：左移動 ⇔ 右移動",
        min_value=-150,
        max_value=150,
        value=0,
        key="pet_large_horizontal_shift",
    )
    large_scale = st.slider(
        "640×640：縮小 ⇔ 拡大（デフォルトは1.0）",
        min_value=0.5,
        max_value=1.5,
        value=1.0,
        step=0.01,
        key="pet_large_scale",
    )

    st.write("**640×640プレビュー**")
    large_columns = st.columns(4)
    with st.spinner("640×640プレビュー画像を生成中です..."):
        for index, file_data in enumerate(file_data_items):
            file_name = file_data[0]
            preview_png = generate_large_png(
                file_data,
                large_vertical_shift,
                large_horizontal_shift,
                large_scale,
            )
            column = large_columns[index % 4]
            render_preview_filename(column, file_name)
            column.image(
                make_preview_image(preview_png, (200, 200)),
                width="content",
            )
            small_key, large_key = selection_checkbox_keys(
                index, file_name
            )
            column.checkbox(
                "個別書き出し",
                key=large_key,
                label_visibility="collapsed",
                on_change=sync_selection_checkbox,
                args=(large_key, small_key),
            )

    selected_indices = [
        index
        for index, file_data in enumerate(file_data_items)
        if st.session_state.get(
            selection_checkbox_keys(index, file_data[0])[0],
            False,
        )
    ]

    current_config = (
        tuple(file_signature(item) for item in file_data_items),
        hashlib.sha256(attribution_bytes).hexdigest(),
        small_vertical_shift,
        small_horizontal_shift,
        small_scale,
        large_vertical_shift,
        large_horizontal_shift,
        large_scale,
        tuple(selected_indices),
    )
    saved_result = st.session_state.get("pet_generated_zip")
    if saved_result and saved_result["config"] != current_config:
        del st.session_state["pet_generated_zip"]

    st.markdown("---")
    all_column, selected_column = st.columns(2)

    with all_column:
        if st.button(
            "一括書き出し",
            key="pet_export_all",
            width="stretch",
        ):
            with st.spinner("ZIPを生成中です..."):
                zip_bytes = build_zip(
                    file_data_items,
                    attribution_bytes,
                    small_vertical_shift,
                    small_horizontal_shift,
                    small_scale,
                    large_vertical_shift,
                    large_horizontal_shift,
                    large_scale,
                    tuple(range(len(file_data_items))),
                )
            st.session_state["pet_generated_zip"] = {
                "config": current_config,
                "name": "mc_pet1.zip",
                "bytes": zip_bytes,
                "key": "pet_download_all",
            }
        st.write("全てのファイルを書き出します。")

    with selected_column:
        if st.button(
            "個別書き出し",
            key="pet_export_selected",
            width="stretch",
        ):
            if not selected_indices:
                st.warning("書き出すファイルを1件以上選択してください。")
            else:
                with st.spinner("ZIPを生成中です..."):
                    zip_bytes = build_zip(
                        file_data_items,
                        attribution_bytes,
                        small_vertical_shift,
                        small_horizontal_shift,
                        small_scale,
                        large_vertical_shift,
                        large_horizontal_shift,
                        large_scale,
                        tuple(selected_indices),
                    )
                st.session_state["pet_generated_zip"] = {
                    "config": current_config,
                    "name": "mc_pet2.zip",
                    "bytes": zip_bytes,
                    "key": "pet_download_selected",
                }
        st.write("チェックを入れたファイルを書き出します。")

    generated_zip = st.session_state.get("pet_generated_zip")
    if generated_zip:
        st.success("書き出しが完了しました。")
        st.download_button(
            label=f"{generated_zip['name']}をダウンロード",
            data=generated_zip["bytes"],
            file_name=generated_zip["name"],
            mime="application/zip",
            key=generated_zip["key"],
            on_click="ignore",
        )


def main():
    st.set_page_config(page_title="mcペット書き出し")
    st.title("mcペット書き出し")
    st.write(
        '<span style="color:red;">※未圧縮データを使ってください！</span>',
        unsafe_allow_html=True,
    )

    export_files = st.file_uploader(
        "**ペット**",
        type="png",
        accept_multiple_files=True,
        key="export_files",
    )
    export_files = sorted(
        export_files, key=lambda uploaded_file: uploaded_file.name
    )

    st.write(
        '**属性**<span style="color:red; font-size: 80%;">　※必須</span>',
        unsafe_allow_html=True,
    )
    attribution_file = st.file_uploader(
        "選択",
        type="png",
        accept_multiple_files=False,
        key="attribution_file",
    )
    if attribution_file is None:
        st.write(
            '<span style="color:red;">未選択です。属性画像をアップロード'
            "してください。</span>",
            unsafe_allow_html=True,
        )

    if not export_files or attribution_file is None:
        return

    file_data_items = tuple(
        uploaded_file_to_data(uploaded_file)
        for uploaded_file in export_files
    )
    render_adjustment_and_export(
        file_data_items,
        attribution_file.getvalue(),
    )


if __name__ == "__main__":
    main()
