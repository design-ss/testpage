import hashlib
import html
import io
import zipfile

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


SMALL_SOURCE_SIZE = (960, 640)
LARGE_SOURCE_SIZE = (1920, 1280)
SMALL_OUTPUT_SIZE = (100, 100)
LARGE_OUTPUT_SIZE = (640, 640)
INITIAL_LARGE_SCALES = (1.0, 0.95, 0.90, 0.85, 0.80)
ADDITIONAL_LARGE_SCALES = tuple(value / 100 for value in range(75, 0, -5))


def safe_name(name):
    return (name or "image.png").replace("\\", "_").replace("/", "_")


def uploaded_file_to_data(uploaded_file):
    return safe_name(uploaded_file.name), uploaded_file.getvalue()


def open_rgba(file_data, size=None):
    if file_data is None:
        if size is None:
            raise ValueError("空画像にはサイズが必要です。")
        return Image.new("RGBA", size, (0, 0, 0, 0))

    with Image.open(io.BytesIO(file_data[1])) as image:
        image = image.convert("RGBA")
        if size is not None and image.size != size:
            image = image.resize(size)
        return image.copy()


def image_to_png_bytes(image):
    with io.BytesIO() as buffer:
        image.save(buffer, format="PNG")
        return buffer.getvalue()


def png_bytes_to_image(image_bytes):
    with Image.open(io.BytesIO(image_bytes)) as image:
        return image.convert("RGBA").copy()


@st.cache_data(show_spinner=False)
def build_small_base(front_data, back_data, center_data):
    image_back = open_rgba(back_data, SMALL_SOURCE_SIZE)
    image_center = open_rgba(center_data, SMALL_SOURCE_SIZE)
    image_front = open_rgba(front_data, SMALL_SOURCE_SIZE)
    combined = Image.alpha_composite(image_back, image_center)
    combined = Image.alpha_composite(combined, image_front)
    return image_to_png_bytes(combined)


@st.cache_data(show_spinner=False)
def build_large_base(front_data, back_data, center_data):
    image_back = open_rgba(back_data, LARGE_SOURCE_SIZE)
    image_center = open_rgba(center_data, LARGE_SOURCE_SIZE)
    image_front = open_rgba(front_data, LARGE_SOURCE_SIZE)
    combined = Image.alpha_composite(image_back, image_center)
    combined = Image.alpha_composite(combined, image_front)
    return image_to_png_bytes(combined)


def scaled_content_bounds(content_bounds, scale):
    left, upper, right, lower = content_bounds
    paste_x = 320 - round(990 * scale)
    paste_y = 320 - round(260 * scale)
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
def calculate_default_large_transform(base_image_bytes):
    image = png_bytes_to_image(base_image_bytes)
    # ほぼ透明なノイズを除き、実際に見えるパーツ範囲を判定する。
    alpha_mask = image.getchannel("A").point(lambda alpha: 255 if alpha > 1 else 0)
    content_bounds = alpha_mask.getbbox()
    if content_bounds is None:
        return 1.0, 0, 0

    # 1. 基準位置のまま、5％刻みで最大20％縮小する。
    for scale in INITIAL_LARGE_SCALES:
        bounds = scaled_content_bounds(content_bounds, scale)
        if bounds_fit_canvas(bounds):
            return scale, 0, 0

    # 2. 20％縮小した状態で、必要最小限の上下左右移動を行う。
    scale = INITIAL_LARGE_SCALES[-1]
    bounds = scaled_content_bounds(content_bounds, scale)
    shift_x = required_axis_shift(bounds[0], bounds[2], LARGE_OUTPUT_SIZE[0])
    shift_y = required_axis_shift(bounds[1], bounds[3], LARGE_OUTPUT_SIZE[1])
    if bounds_fit_canvas(bounds, shift_x, shift_y):
        return scale, shift_x, shift_y

    # 3. 移動しても収まらない場合だけ、5％刻みでさらに縮小する。
    for scale in ADDITIONAL_LARGE_SCALES:
        bounds = scaled_content_bounds(content_bounds, scale)
        shift_x = required_axis_shift(bounds[0], bounds[2], LARGE_OUTPUT_SIZE[0])
        shift_y = required_axis_shift(bounds[1], bounds[3], LARGE_OUTPUT_SIZE[1])
        if bounds_fit_canvas(bounds, shift_x, shift_y):
            return scale, shift_x, shift_y

    return ADDITIONAL_LARGE_SCALES[-1], shift_x, shift_y


@st.cache_data(show_spinner=False)
def generate_small_png(
    front_data,
    back_data,
    center_data,
    attribution_data,
    scale_100,
    horizontal_shift_100,
    vertical_shift_100,
):
    image = png_bytes_to_image(build_small_base(front_data, back_data, center_data))

    # 従来の初期倍率0.4を、標準UIの初期値0.75へ対応させる。
    effective_scale = scale_100 * (0.4 / 0.75)
    new_width = max(1, round(image.width * effective_scale))
    new_height = max(1, round(image.height * effective_scale))
    image = image.resize((new_width, new_height))

    # 従来の基準点(490, 120)を100×100の中央へ配置する。
    paste_x = 50 - round(490 * effective_scale) + horizontal_shift_100
    paste_y = 50 - round(120 * effective_scale) - vertical_shift_100
    output = Image.new("RGBA", SMALL_OUTPUT_SIZE, (0, 0, 0, 0))
    output.alpha_composite(image, dest=(paste_x, paste_y))

    attribution = open_rgba(attribution_data, SMALL_OUTPUT_SIZE)
    output = Image.alpha_composite(output, attribution)
    return image_to_png_bytes(output)


@st.cache_data(show_spinner=False)
def generate_large_png(
    front_data,
    back_data,
    center_data,
    scale_640,
    horizontal_shift_640,
    vertical_shift_640,
):
    base_image_bytes = build_large_base(front_data, back_data, center_data)
    image = png_bytes_to_image(base_image_bytes)
    default_scale, default_shift_x, default_shift_y = calculate_default_large_transform(
        base_image_bytes
    )
    effective_scale = default_scale * scale_640
    new_width = max(1, round(image.width * effective_scale))
    new_height = max(1, round(image.height * effective_scale))
    image = image.resize((new_width, new_height))

    # 全体画像を保持したまま配置し、640×640キャンバスの外側だけを落とす。
    # 自動調整後の位置を基準に、スライダーの調整値を加える。
    paste_x = (
        320
        - round(990 * effective_scale)
        + default_shift_x
        + horizontal_shift_640
    )
    paste_y = (
        320
        - round(260 * effective_scale)
        + default_shift_y
        - vertical_shift_640
    )
    output = Image.new("RGBA", LARGE_OUTPUT_SIZE, (0, 0, 0, 0))
    output.alpha_composite(image, dest=(paste_x, paste_y))
    return image_to_png_bytes(output)


@st.cache_data(show_spinner=False)
def resize_png(image_bytes, size):
    image = png_bytes_to_image(image_bytes)
    image = image.resize(size)
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


def output_name(front_data, back_data):
    if front_data is not None:
        return front_data[0]
    return back_data[0]


def pad_pairs(front_files, back_files):
    pair_count = max(len(front_files), len(back_files))
    padded_front = list(front_files) + [None] * (pair_count - len(front_files))
    padded_back = list(back_files) + [None] * (pair_count - len(back_files))
    return tuple(zip(padded_front, padded_back))


def pair_token(index, pair):
    digest = hashlib.sha1()
    digest.update(str(index).encode("utf-8"))
    for file_data in pair:
        if file_data is not None:
            digest.update(file_data[0].encode("utf-8"))
            digest.update(file_data[1])
    return digest.hexdigest()[:12]


def data_digest(file_data):
    if file_data is None:
        return ""
    return hashlib.sha256(file_data[1]).hexdigest()


def sync_selection_checkbox(source_key, target_key, canonical_key):
    selected = bool(st.session_state[source_key])
    st.session_state[target_key] = selected
    st.session_state[canonical_key] = selected


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
    pairs,
    center_data,
    attribution_data,
    scale_100,
    horizontal_shift_100,
    vertical_shift_100,
    scale_640,
    horizontal_shift_640,
    vertical_shift_640,
    selected_indices,
):
    with io.BytesIO() as buffer:
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for index in selected_indices:
                front_data, back_data = pairs[index]
                file_name = output_name(front_data, back_data)

                image_100 = generate_small_png(
                    front_data,
                    back_data,
                    center_data,
                    attribution_data,
                    scale_100,
                    horizontal_shift_100,
                    vertical_shift_100,
                )
                image_640 = generate_large_png(
                    front_data,
                    back_data,
                    center_data,
                    scale_640,
                    horizontal_shift_640,
                    vertical_shift_640,
                )

                archive.writestr(f"100x100/{file_name}", image_100)
                archive.writestr(f"50x50/{file_name}", resize_png(image_100, (50, 50)))
                archive.writestr(f"640x640/{file_name}", image_640)
                archive.writestr(f"320x320/{file_name}", resize_png(image_640, (320, 320)))

                if front_data is not None:
                    front_image = open_rgba(front_data, SMALL_SOURCE_SIZE)
                    archive.writestr(
                        f"960x640/{front_data[0]}",
                        image_to_png_bytes(front_image),
                    )
                if back_data is not None:
                    back_image = open_rgba(back_data, SMALL_SOURCE_SIZE)
                    archive.writestr(
                        f"960x640/{back_data[0]}",
                        image_to_png_bytes(back_image),
                    )
        return buffer.getvalue()


def export_config(
    pairs,
    center_data,
    attribution_data,
    adjustment_values,
    selected_indices,
):
    file_hashes = []
    for front_data, back_data in pairs:
        file_hashes.extend((data_digest(front_data), data_digest(back_data)))
    return (
        tuple(file_hashes),
        data_digest(center_data),
        data_digest(attribution_data),
        adjustment_values,
        selected_indices,
    )


@st.fragment
def render_adjustment_and_export(pairs, center_data, attribution_data):
    vertical_shift_100 = st.slider(
        "100×100：下移動 ⇔ 上移動",
        min_value=-150,
        max_value=150,
        value=0,
        step=1,
        key="head_vertical_shift_100",
    )
    horizontal_shift_100 = st.slider(
        "100×100：左移動 ⇔ 右移動",
        min_value=-150,
        max_value=150,
        value=0,
        step=1,
        key="head_horizontal_shift_100",
    )
    scale_100 = st.slider(
        "100×100：縮小 ⇔ 拡大（デフォルトは0.75）",
        min_value=0.5,
        max_value=1.5,
        value=0.75,
        step=0.01,
        key="head_scale_100",
    )

    pair_keys = []
    columns_100 = st.columns(4)
    for index, pair in enumerate(pairs):
        front_data, back_data = pair
        file_name = output_name(front_data, back_data)
        token = pair_token(index, pair)
        key_100 = f"head_select_100_{token}"
        key_640 = f"head_select_640_{token}"
        canonical_key = f"head_selected_{token}"
        pair_keys.append((key_100, key_640, canonical_key))

        selected = bool(st.session_state.get(canonical_key, False))
        st.session_state.setdefault(key_100, selected)
        st.session_state.setdefault(key_640, selected)

        image_100 = generate_small_png(
            front_data,
            back_data,
            center_data,
            attribution_data,
            scale_100,
            horizontal_shift_100,
            vertical_shift_100,
        )
        preview = make_preview_png(image_100, SMALL_OUTPUT_SIZE)
        with columns_100[index % 4]:
            render_preview_filename(st, file_name)
            st.image(preview, width=102)
            st.checkbox(
                f"{file_name}を選択",
                key=key_100,
                label_visibility="collapsed",
                on_change=sync_selection_checkbox,
                args=(key_100, key_640, canonical_key),
            )

    st.divider()

    vertical_shift_640 = st.slider(
        "640×640：下移動 ⇔ 上移動",
        min_value=-150,
        max_value=150,
        value=0,
        step=1,
        key="head_vertical_shift_640",
    )
    horizontal_shift_640 = st.slider(
        "640×640：左移動 ⇔ 右移動",
        min_value=-150,
        max_value=150,
        value=0,
        step=1,
        key="head_horizontal_shift_640",
    )
    scale_640 = st.slider(
        "640×640：縮小 ⇔ 拡大（デフォルトは1.0）",
        min_value=0.5,
        max_value=1.5,
        value=1.0,
        step=0.01,
        key="head_scale_640",
    )

    columns_640 = st.columns(4)
    for index, pair in enumerate(pairs):
        front_data, back_data = pair
        file_name = output_name(front_data, back_data)
        key_100, key_640, canonical_key = pair_keys[index]
        image_640 = generate_large_png(
            front_data,
            back_data,
            center_data,
            scale_640,
            horizontal_shift_640,
            vertical_shift_640,
        )
        preview = make_preview_png(image_640, (200, 200))
        with columns_640[index % 4]:
            render_preview_filename(st, file_name)
            st.image(preview, width=202)
            st.checkbox(
                f"{file_name}を選択",
                key=key_640,
                label_visibility="collapsed",
                on_change=sync_selection_checkbox,
                args=(key_640, key_100, canonical_key),
            )

    selected_indices = tuple(
        index
        for index, (_, _, canonical_key) in enumerate(pair_keys)
        if st.session_state.get(canonical_key, False)
    )
    adjustment_values = (
        vertical_shift_100,
        horizontal_shift_100,
        scale_100,
        vertical_shift_640,
        horizontal_shift_640,
        scale_640,
    )
    current_config = export_config(
        pairs,
        center_data,
        attribution_data,
        adjustment_values,
        selected_indices,
    )
    stored_download = st.session_state.get("head_generated_zip")
    if stored_download and stored_download["config"] != current_config:
        del st.session_state["head_generated_zip"]

    st.divider()
    export_all_column, export_selected_column = st.columns(2)
    with export_all_column:
        if st.button("一括書き出し", use_container_width=True):
            with st.spinner("画像生成中です..."):
                zip_data = build_zip(
                    pairs,
                    center_data,
                    attribution_data,
                    scale_100,
                    horizontal_shift_100,
                    vertical_shift_100,
                    scale_640,
                    horizontal_shift_640,
                    vertical_shift_640,
                    tuple(range(len(pairs))),
                )
            st.session_state["head_generated_zip"] = {
                "config": current_config,
                "file_name": "mc_head1.zip",
                "data": zip_data,
                "key": "head_download_all",
            }

    with export_selected_column:
        if st.button("個別書き出し", use_container_width=True):
            if not selected_indices:
                st.warning("書き出す画像にチェックを入れてください。")
            else:
                with st.spinner("画像生成中です..."):
                    zip_data = build_zip(
                        pairs,
                        center_data,
                        attribution_data,
                        scale_100,
                        horizontal_shift_100,
                        vertical_shift_100,
                        scale_640,
                        horizontal_shift_640,
                        vertical_shift_640,
                        selected_indices,
                    )
                st.session_state["head_generated_zip"] = {
                    "config": current_config,
                    "file_name": "mc_head2.zip",
                    "data": zip_data,
                    "key": "head_download_selected",
                }

    stored_download = st.session_state.get("head_generated_zip")
    if stored_download:
        st.success("書き出しが完了しました。")
        show_download(
            stored_download["file_name"],
            stored_download["data"],
            stored_download.get("key", "head_download"),
        )


def main():
    st.set_page_config(page_title="mc頭・髪書き出し")
    st.title("mc頭・髪書き出し")

    front_column, back_column = st.columns(2)
    with front_column:
        export_files_front = st.file_uploader(
            "頭_前ファイルを選択",
            type="png",
            accept_multiple_files=True,
            key="export_files_front",
        )
    with back_column:
        export_files_back = st.file_uploader(
            "頭_後ろファイルを選択",
            type="png",
            accept_multiple_files=True,
            key="export_files_back",
        )

    center_column, attribution_column = st.columns(2)
    with center_column:
        st.markdown("**mc_白黒頭素体** <span style='color:red'>※必須</span>", unsafe_allow_html=True)
        st.caption("「mc_w_head.png」をアップロードしてください。")
        export_files_center = st.file_uploader(
            "mc_白黒頭素体を選択",
            type="png",
            accept_multiple_files=True,
            key="export_files_center",
            label_visibility="collapsed",
        )
        if not export_files_center:
            st.markdown(
                '<span style="color:red;">未選択です。「mc_w_head.png」をアップロードしてください。</span>',
                unsafe_allow_html=True,
            )
    with attribution_column:
        st.markdown("**属性** <span style='color:red'>※必須</span>", unsafe_allow_html=True)
        st.caption("属性画像をアップロードしてください。")
        attribution_file = st.file_uploader(
            "属性画像を選択",
            type="png",
            key="attribution_file",
            label_visibility="collapsed",
        )
        if attribution_file is None:
            st.markdown(
                '<span style="color:red;">未選択です。属性画像をアップロードしてください。</span>',
                unsafe_allow_html=True,
            )

    front_files = sorted(export_files_front or [], key=lambda file: file.name)
    back_files = sorted(export_files_back or [], key=lambda file: file.name)
    center_files = sorted(export_files_center or [], key=lambda file: file.name)

    if not front_files and not back_files:
        return
    if not center_files or attribution_file is None:
        return
    if len(center_files) > 1:
        st.info("頭素体はファイル名順の先頭1件を使用します。")

    front_data = tuple(uploaded_file_to_data(file) for file in front_files)
    back_data = tuple(uploaded_file_to_data(file) for file in back_files)
    center_data = uploaded_file_to_data(center_files[0])
    attribution_data = uploaded_file_to_data(attribution_file)
    pairs = pad_pairs(front_data, back_data)

    render_adjustment_and_export(pairs, center_data, attribution_data)


if __name__ == "__main__":
    main()
