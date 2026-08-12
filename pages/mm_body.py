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
SMALL_OUTPUT_SIZE = (100, 100)
LARGE_OUTPUT_SIZE = (640, 640)
INITIAL_LARGE_SCALES = (1.0, 0.95, 0.90, 0.85, 0.80)
ADDITIONAL_LARGE_SCALES = tuple(value / 100 for value in range(75, 0, -5))
EXCLUDED_BACK_NAMES = {"素体_男.png", "素体_女.png"}


def safe_name(name):
    normalized = (name or "image.png").replace("\\", "/")
    return normalized.rsplit("/", 1)[-1] or "image.png"


def uploaded_file_to_data(uploaded_file):
    if uploaded_file is None:
        return None
    return safe_name(uploaded_file.name), uploaded_file.getvalue()


def open_rgba(file_data, size=None):
    if file_data is None:
        return Image.new("RGBA", size or SOURCE_SIZE, (0, 0, 0, 0))

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


def apply_face_mask(image_center, mask_data):
    if mask_data is None:
        return image_center

    with Image.open(io.BytesIO(mask_data[1])) as mask:
        mask = mask.convert("L")
        if mask.size != image_center.size:
            mask = mask.resize(image_center.size)
        mask_array = np.asarray(mask, dtype=np.float64)

    image_array = np.asarray(image_center).copy()
    image_array[:, :, 3] = (
        (1.0 - mask_array / 255.0) * image_array[:, :, 3]
    ).astype(np.uint8)
    return Image.fromarray(image_array, mode="RGBA")


@st.cache_data(show_spinner=False)
def masked_center_png(center_data, mask_data):
    image_center = open_rgba(center_data, SOURCE_SIZE)
    image_center = apply_face_mask(image_center, mask_data)
    return image_to_png_bytes(image_center)


@st.cache_data(show_spinner=False)
def build_composite(front_data, center_data, back_data, mask_data):
    image_front = open_rgba(front_data, SOURCE_SIZE)
    image_center = png_bytes_to_image(
        masked_center_png(center_data, mask_data)
    )
    image_back = open_rgba(back_data, SOURCE_SIZE)
    combined = Image.alpha_composite(image_back, image_center)
    combined = Image.alpha_composite(combined, image_front)
    return image_to_png_bytes(combined)


def centered_scaled_image(image, scale):
    width, height = image.size
    new_width = max(1, int(width * scale))
    new_height = max(1, int(height * scale))
    resized = image.resize(
        (new_width, new_height),
        Image.Resampling.BILINEAR,
    )

    x1, y1 = width // 2, height // 2
    x2, y2 = int(x1 * scale), int(y1 * scale)
    delta_x = (width / 2 - x1) - (new_width / 2 - x2)
    delta_y = (height / 2 - y1) - (new_height / 2 - y2)
    frame_height = max(height, int(height * scale * 2))
    frame_width = max(width, int(width * scale * 2))
    framed = Image.new("RGBA", (frame_width, frame_height), (0, 0, 0, 0))
    paste_x = int(-delta_x + frame_width / 2 - new_width / 2)
    paste_y = int(-delta_y + frame_height / 2 - new_height / 2)
    framed.paste(resized, (paste_x, paste_y))
    crop_left = int(frame_width / 2 - width / 2)
    crop_top = int(frame_height / 2 - height / 2)
    return framed.crop(
        (
            crop_left,
            crop_top,
            crop_left + width,
            crop_top + height,
        )
    )


@st.cache_data(show_spinner=False)
def generate_small_png(
    front_data,
    center_data,
    back_data,
    mask_data,
    playmark_data,
    scale_100,
    horizontal_shift_100,
    vertical_shift_100,
):
    image = png_bytes_to_image(
        build_composite(front_data, center_data, back_data, mask_data)
    )

    # 標準UIの0.75を、従来の初期倍率0.96へ対応させる。
    effective_scale = scale_100 * (0.96 / 0.75)
    image = centered_scaled_image(image, effective_scale)
    image = image.crop(
        (
            335 - horizontal_shift_100,
            vertical_shift_100,
            625 - horizontal_shift_100,
            640 + vertical_shift_100,
        )
    )
    image = image.resize((290, 640), Image.Resampling.LANCZOS)
    image = image.crop((0, 275, 290, 565))
    image.thumbnail(SMALL_OUTPUT_SIZE, Image.Resampling.LANCZOS)

    if playmark_data is not None:
        playmark = open_rgba(playmark_data, SMALL_OUTPUT_SIZE)
        image = Image.alpha_composite(image.convert("RGBA"), playmark)
    return image_to_png_bytes(image)


@st.cache_data(show_spinner=False)
def prepare_large_base(front_data, center_data, back_data, mask_data):
    image = png_bytes_to_image(
        build_composite(front_data, center_data, back_data, mask_data)
    )
    width, height = image.size
    if width < height:
        if width > 640:
            new_width = 448
            new_height = max(1, int(height * 448 / width))
        else:
            new_width = max(1, int(width * 640 / height))
            new_height = 640
    else:
        if height > 640:
            new_width = max(1, int(width * 448 / height))
            new_height = 448
        else:
            new_width = 640
            new_height = max(1, int(height * 640 / width))
    image = image.resize((new_width, new_height))
    return image_to_png_bytes(image)


def scaled_content_bounds(content_bounds, scale, image_width, image_height):
    left, upper, right, lower = content_bounds
    paste_x = 320 - round(image_width * scale / 2)
    paste_y = 640 - round(image_height * scale)
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
    alpha_mask = image.getchannel("A").point(
        lambda alpha: 255 if alpha > 1 else 0
    )
    content_bounds = alpha_mask.getbbox()
    if content_bounds is None:
        return 1.0, 0, 0

    for scale in INITIAL_LARGE_SCALES:
        bounds = scaled_content_bounds(
            content_bounds,
            scale,
            image.width,
            image.height,
        )
        if bounds_fit_canvas(bounds):
            return scale, 0, 0

    scale = INITIAL_LARGE_SCALES[-1]
    bounds = scaled_content_bounds(
        content_bounds,
        scale,
        image.width,
        image.height,
    )
    shift_x = required_axis_shift(bounds[0], bounds[2], LARGE_OUTPUT_SIZE[0])
    shift_y = required_axis_shift(bounds[1], bounds[3], LARGE_OUTPUT_SIZE[1])
    if bounds_fit_canvas(bounds, shift_x, shift_y):
        return scale, shift_x, shift_y

    for scale in ADDITIONAL_LARGE_SCALES:
        bounds = scaled_content_bounds(
            content_bounds,
            scale,
            image.width,
            image.height,
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
    front_data,
    center_data,
    back_data,
    mask_data,
    scale_640,
    horizontal_shift_640,
    vertical_shift_640,
):
    base_image_bytes = prepare_large_base(
        front_data,
        center_data,
        back_data,
        mask_data,
    )
    image = png_bytes_to_image(base_image_bytes)
    default_scale, default_shift_x, default_shift_y = (
        calculate_default_large_transform(base_image_bytes)
    )
    effective_scale = default_scale * scale_640
    new_width = max(1, round(image.width * effective_scale))
    new_height = max(1, round(image.height * effective_scale))
    image = image.resize((new_width, new_height))

    paste_x = (
        320
        - round(image.width / 2)
        + default_shift_x
        + horizontal_shift_640
    )
    paste_y = (
        640
        - image.height
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
def original_layer_png(file_data, mask_data=None):
    if mask_data is not None:
        return masked_center_png(file_data, mask_data)
    return image_to_png_bytes(open_rgba(file_data, SOURCE_SIZE))


@st.cache_data(show_spinner=False)
def load_preview_asset(relative_path):
    with Image.open(relative_path) as image:
        return image_to_png_bytes(image.convert("RGBA"))


@st.cache_data(show_spinner=False)
def make_preview_png(image_bytes, preview_size):
    image = png_bytes_to_image(image_bytes)
    if image.size != preview_size:
        image = image.resize(preview_size)
    draw = ImageDraw.Draw(image)
    draw.rectangle(
        (0, 0, image.width - 1, image.height - 1),
        outline="red",
        width=1,
    )
    draw.line(
        (image.width // 2, 0, image.width // 2, image.height - 1),
        fill="red",
        width=1,
    )
    draw.line(
        (0, image.height // 2, image.width - 1, image.height // 2),
        fill="red",
        width=1,
    )
    return image_to_png_bytes(image)


@st.cache_data(show_spinner=False)
def make_small_preview_png(image_bytes, frame_bytes):
    image = png_bytes_to_image(image_bytes)
    frame = png_bytes_to_image(frame_bytes)
    image.paste(frame, (0, 0), frame)
    draw = ImageDraw.Draw(image)
    draw.line((50, 0, 50, 100), fill="red", width=1)
    draw.line((0, 50, 100, 50), fill="red", width=1)
    return image_to_png_bytes(ImageOps.expand(image, border=1, fill="red"))


@st.cache_data(show_spinner=False)
def make_large_preview_png(image_bytes, background_bytes):
    image = png_bytes_to_image(image_bytes).resize((200, 200))
    background = png_bytes_to_image(background_bytes)
    preview = Image.new("RGBA", background.size, (0, 0, 0, 0))
    preview.paste(background, (0, 0))
    paste_x = preview.width // 2 - image.width // 2
    paste_y = preview.height // 2 - image.height // 2
    preview.paste(image, (paste_x, paste_y), image)
    draw = ImageDraw.Draw(preview)
    draw.line(
        (0, preview.height - 8, preview.width, preview.height - 8),
        fill="red",
        width=1,
    )
    draw.line(
        (preview.width // 2, 0, preview.width // 2, preview.height),
        fill="red",
        width=1,
    )
    return image_to_png_bytes(ImageOps.expand(preview, border=1, fill="red"))


def output_name(front_data, center_data, back_data):
    if front_data is not None:
        return front_data[0]
    if center_data is not None:
        return center_data[0]
    return back_data[0]


def pad_items(front_files, center_files, back_files):
    item_count = max(len(front_files), len(center_files), len(back_files))
    padded_front = list(front_files) + [None] * (item_count - len(front_files))
    padded_center = list(center_files) + [None] * (item_count - len(center_files))
    padded_back = list(back_files) + [None] * (item_count - len(back_files))
    return tuple(zip(padded_front, padded_center, padded_back))


def item_token(index, item):
    digest = hashlib.sha1(str(index).encode("utf-8"))
    for file_data in item:
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
    items,
    mask_data,
    playmark_data,
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
        front_data, center_data, back_data = items[index]
        file_name = output_name(front_data, center_data, back_data)
        image_100 = generate_small_png(
            front_data,
            center_data,
            back_data,
            mask_data,
            playmark_data,
            scale_100,
            horizontal_shift_100,
            vertical_shift_100,
        )
        image_640 = generate_large_png(
            front_data,
            center_data,
            back_data,
            mask_data,
            scale_640,
            horizontal_shift_640,
            vertical_shift_640,
        )
        outputs[f"100x100/{file_name}"] = image_100
        outputs[f"50x50/{file_name}"] = resize_png(image_100, (50, 50))
        outputs[f"640x640/{file_name}"] = image_640
        outputs[f"320x320/{file_name}"] = resize_png(image_640, (320, 320))

        if front_data is not None:
            outputs[f"960x640/{front_data[0]}"] = original_layer_png(
                front_data
            )
        if center_data is not None:
            outputs[f"960x640/{center_data[0]}"] = original_layer_png(
                center_data,
                mask_data,
            )
        if (
            back_data is not None
            and back_data[0] not in EXCLUDED_BACK_NAMES
        ):
            outputs[f"960x640/{back_data[0]}"] = original_layer_png(back_data)

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
def render_adjustment_and_export(items, mask_data, playmark_data):
    st.divider()

    vertical_shift_100 = st.slider(
        "100×100：下移動 ⇔ 上移動",
        min_value=-150,
        max_value=150,
        value=0,
        step=1,
        key="mm_body_vertical_shift_100",
    )
    horizontal_shift_100 = st.slider(
        "100×100：左移動 ⇔ 右移動",
        min_value=-150,
        max_value=150,
        value=0,
        step=1,
        key="mm_body_horizontal_shift_100",
    )
    scale_100 = st.slider(
        "100×100：縮小 ⇔ 拡大（デフォルトは0.75）",
        min_value=0.5,
        max_value=1.5,
        value=0.75,
        step=0.01,
        key="mm_body_scale_100",
    )

    try:
        small_frame = load_preview_asset("./data/100_flame.png")
    except FileNotFoundError:
        small_frame = None
        st.warning("./data/100_flame.pngが見つからないため、枠のみで表示します。")

    item_keys = []
    columns_100 = st.columns(4)
    for index, item in enumerate(items):
        front_data, center_data, back_data = item
        file_name = output_name(front_data, center_data, back_data)
        token = item_token(index, item)
        key_100 = f"mm_body_select_100_{token}"
        key_640 = f"mm_body_select_640_{token}"
        canonical_key = f"mm_body_selected_{token}"
        item_keys.append((key_100, key_640, canonical_key))

        selected = bool(st.session_state.get(canonical_key, False))
        st.session_state.setdefault(key_100, selected)
        st.session_state.setdefault(key_640, selected)

        image_100 = generate_small_png(
            front_data,
            center_data,
            back_data,
            mask_data,
            playmark_data,
            scale_100,
            horizontal_shift_100,
            vertical_shift_100,
        )
        if small_frame is not None:
            preview_png = make_small_preview_png(image_100, small_frame)
        else:
            preview_png = make_preview_png(image_100, SMALL_OUTPUT_SIZE)

        column = columns_100[index % 4]
        render_preview_filename(column, file_name)
        column.image(preview_png, width=102)
        column.checkbox(
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
        key="mm_body_vertical_shift_640",
    )
    horizontal_shift_640 = st.slider(
        "640×640：左移動 ⇔ 右移動",
        min_value=-150,
        max_value=150,
        value=0,
        step=1,
        key="mm_body_horizontal_shift_640",
    )
    scale_640 = st.slider(
        "640×640：縮小 ⇔ 拡大（デフォルトは1.0）",
        min_value=0.5,
        max_value=1.5,
        value=1.0,
        step=0.01,
        key="mm_body_scale_640",
    )

    try:
        large_background = load_preview_asset("./data/mm_640_back.png")
    except FileNotFoundError:
        large_background = None
        st.warning("./data/mm_640_back.pngが見つからないため、背景なしで表示します。")

    columns_640 = st.columns(4)
    for index, item in enumerate(items):
        front_data, center_data, back_data = item
        file_name = output_name(front_data, center_data, back_data)
        key_100, key_640, canonical_key = item_keys[index]
        image_640 = generate_large_png(
            front_data,
            center_data,
            back_data,
            mask_data,
            scale_640,
            horizontal_shift_640,
            vertical_shift_640,
        )
        if large_background is not None:
            preview_png = make_large_preview_png(
                image_640,
                large_background,
            )
        else:
            preview_png = make_preview_png(image_640, (200, 200))

        column = columns_640[index % 4]
        render_preview_filename(column, file_name)
        column.image(preview_png, width=202)
        column.checkbox(
            f"{file_name}を選択",
            key=key_640,
            label_visibility="collapsed",
            on_change=sync_selection_checkbox,
            args=(key_640, key_100, canonical_key),
        )

    selected_indices = tuple(
        index
        for index, (_, _, canonical_key) in enumerate(item_keys)
        if st.session_state.get(canonical_key, False)
    )
    current_config = (
        tuple(
            tuple(data_digest(file_data) for file_data in item)
            for item in items
        ),
        data_digest(mask_data),
        data_digest(playmark_data),
        vertical_shift_100,
        horizontal_shift_100,
        scale_100,
        vertical_shift_640,
        horizontal_shift_640,
        scale_640,
        selected_indices,
    )
    stored_download = st.session_state.get("mm_body_generated_zip")
    if stored_download and stored_download["config"] != current_config:
        del st.session_state["mm_body_generated_zip"]

    st.divider()
    export_all_column, export_selected_column = st.columns(2)
    with export_all_column:
        if st.button(
            "一括書き出し",
            key="mm_body_export_all",
            use_container_width=True,
        ):
            with st.spinner("ZIPを生成中です..."):
                zip_bytes = build_zip(
                    items,
                    mask_data,
                    playmark_data,
                    scale_100,
                    horizontal_shift_100,
                    vertical_shift_100,
                    scale_640,
                    horizontal_shift_640,
                    vertical_shift_640,
                    tuple(range(len(items))),
                )
            st.session_state["mm_body_generated_zip"] = {
                "config": current_config,
                "name": "mm_body1.zip",
                "bytes": zip_bytes,
                "key": "mm_body_download_all",
            }
        st.write("全てのファイルを書き出します。")

    with export_selected_column:
        if st.button(
            "個別書き出し",
            key="mm_body_export_selected",
            use_container_width=True,
        ):
            if not selected_indices:
                st.warning("書き出すファイルを1件以上選択してください。")
            else:
                with st.spinner("ZIPを生成中です..."):
                    zip_bytes = build_zip(
                        items,
                        mask_data,
                        playmark_data,
                        scale_100,
                        horizontal_shift_100,
                        vertical_shift_100,
                        scale_640,
                        horizontal_shift_640,
                        vertical_shift_640,
                        selected_indices,
                    )
                st.session_state["mm_body_generated_zip"] = {
                    "config": current_config,
                    "name": "mm_body2.zip",
                    "bytes": zip_bytes,
                    "key": "mm_body_download_selected",
                }
        st.write("チェックを入れたファイルを書き出します。")

    stored_download = st.session_state.get("mm_body_generated_zip")
    if stored_download:
        st.success("書き出しが完了しました。")
        show_download(
            stored_download["name"],
            stored_download["bytes"],
            stored_download.get("key", "mm_body_download"),
        )


def main():
    st.set_page_config(page_title="mm体書き出し")
    st.title("mm見た目体書き出し")
    st.markdown(
        "**通常素体のポーズはこちらのアプリでは書き出しできません。"
        "default bodyを使ってください。**"
    )
    st.markdown(
        '<span style="color:red;">※未圧縮データを使ってください</span>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<span style="color:red;">※mm体は独自影を設定したときのみ'
        "影付きで書き出してください</span>",
        unsafe_allow_html=True,
    )

    front_column, center_column, back_column = st.columns(3)
    with front_column:
        front_uploads = st.file_uploader(
            "**体_前ファイル**",
            type="png",
            accept_multiple_files=True,
            key="export_files_front",
        )
    with center_column:
        center_uploads = st.file_uploader(
            "**体_中ファイル**",
            type="png",
            accept_multiple_files=True,
            key="export_files_center",
        )
    with back_column:
        back_uploads = st.file_uploader(
            "**体_後ろファイル**",
            type="png",
            accept_multiple_files=True,
            key="export_files_back",
        )

    mask_column, playmark_column = st.columns(2)
    with mask_column:
        st.markdown(
            "**オマケ：顔輪郭マスク用<br>（なくても書き出しできます）**"
            "<p style='font-size:80%;'>「体_中」を首まで描いたときに"
            "「mask_face_silhouette.png」をアップロードして使用してください。"
            "<br>顔の輪郭部分を消すことができます。<br></p>",
            unsafe_allow_html=True,
        )
        mask_uploads = st.file_uploader(
            "顔輪郭マスクを選択",
            type="png",
            accept_multiple_files=True,
            key="mask_file",
            label_visibility="collapsed",
        )

    with playmark_column:
        st.markdown(
            "**再生マーク**<p style='font-size:80%;'>"
            "モーションアバター書き出しの際は、"
            "「100x100_playmark.png」をアップロードしてください。<br>"
            "50/100に再生マークを重ねます。</p>",
            unsafe_allow_html=True,
        )
        playmark_uploads = st.file_uploader(
            "再生マークを選択",
            type="png",
            accept_multiple_files=True,
            key="playmark_file",
            label_visibility="collapsed",
        )

    front_uploads = sorted(front_uploads or [], key=lambda file: file.name)
    center_uploads = sorted(center_uploads or [], key=lambda file: file.name)
    back_uploads = sorted(back_uploads or [], key=lambda file: file.name)
    mask_uploads = sorted(mask_uploads or [], key=lambda file: file.name)
    playmark_uploads = sorted(
        playmark_uploads or [],
        key=lambda file: file.name,
    )

    if not front_uploads and not center_uploads and not back_uploads:
        return
    if len(mask_uploads) > 1:
        st.info("顔輪郭マスクはファイル名順の先頭1件を使用します。")
    if len(playmark_uploads) > 1:
        st.info("再生マークはファイル名順の先頭1件を使用します。")

    front_data = tuple(uploaded_file_to_data(file) for file in front_uploads)
    center_data = tuple(uploaded_file_to_data(file) for file in center_uploads)
    back_data = tuple(uploaded_file_to_data(file) for file in back_uploads)
    mask_data = (
        uploaded_file_to_data(mask_uploads[0])
        if mask_uploads
        else None
    )
    playmark_data = (
        uploaded_file_to_data(playmark_uploads[0])
        if playmark_uploads
        else None
    )
    items = pad_items(front_data, center_data, back_data)
    render_adjustment_and_export(items, mask_data, playmark_data)


if __name__ == "__main__":
    main()
