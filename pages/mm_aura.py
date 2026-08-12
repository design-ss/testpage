import hashlib
import html
import io
import zipfile

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
MALE_SILHOUETTE_NAMES = ("シルエット_男性.png", "silhouette_male.png")
FEMALE_SILHOUETTE_NAMES = ("シルエット_女性.png", "silhouette_female.png")


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
    frame_width = max(width, int(width * scale * 2))
    frame_height = max(height, int(height * scale * 2))
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


def visible_crop(image):
    bounds = image.getbbox()
    if bounds is None:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    return image.crop(bounds)


@st.cache_data(show_spinner=False)
def build_small_base(top_data, bottom_data, silhouette_data):
    image_top = centered_scaled_image(
        open_rgba(top_data, SOURCE_SIZE),
        0.93,
    )
    image_bottom = centered_scaled_image(
        open_rgba(bottom_data, SOURCE_SIZE),
        0.93,
    )

    image_top = image_top.crop((132, 0, 828, 640))
    image_bottom = image_bottom.crop((132, 0, 828, 640))
    image_top = image_top.resize((696, 640), Image.Resampling.LANCZOS)
    image_bottom = image_bottom.resize((696, 640), Image.Resampling.LANCZOS)
    image_top = image_top.crop((28, 0, 668, 640))
    image_bottom = image_bottom.crop((28, 0, 668, 640))
    image_top = image_top.resize((640, 640), Image.Resampling.LANCZOS)
    image_bottom = image_bottom.resize((640, 640), Image.Resampling.LANCZOS)
    image_top.thumbnail(SMALL_OUTPUT_SIZE, Image.Resampling.LANCZOS)
    image_bottom.thumbnail(SMALL_OUTPUT_SIZE, Image.Resampling.LANCZOS)

    silhouette = open_rgba(silhouette_data, SMALL_OUTPUT_SIZE)
    combined = Image.alpha_composite(image_bottom, silhouette)
    combined = Image.alpha_composite(combined, image_top)
    return image_to_png_bytes(combined)


@st.cache_data(show_spinner=False)
def generate_small_png(
    top_data,
    bottom_data,
    silhouette_data,
    playmark_data,
    scale_100,
    horizontal_shift_100,
    vertical_shift_100,
):
    image = png_bytes_to_image(
        build_small_base(top_data, bottom_data, silhouette_data)
    )
    effective_scale = scale_100 / 0.75
    if (
        effective_scale != 1.0
        or horizontal_shift_100 != 0
        or vertical_shift_100 != 0
    ):
        new_width = max(1, round(image.width * effective_scale))
        new_height = max(1, round(image.height * effective_scale))
        image = image.resize((new_width, new_height))
        paste_x = (100 - new_width) // 2 + horizontal_shift_100
        paste_y = (100 - new_height) // 2 - vertical_shift_100
        canvas = Image.new("RGBA", SMALL_OUTPUT_SIZE, (0, 0, 0, 0))
        canvas.alpha_composite(image, dest=(paste_x, paste_y))
        image = canvas

    if playmark_data is not None:
        playmark = open_rgba(playmark_data, SMALL_OUTPUT_SIZE)
        image = Image.alpha_composite(image, playmark)
    return image_to_png_bytes(image)


@st.cache_data(show_spinner=False)
def build_large_base(top_data, bottom_data):
    image_top = open_rgba(top_data, SOURCE_SIZE)
    image_bottom = open_rgba(bottom_data, SOURCE_SIZE)
    combined = Image.alpha_composite(image_bottom, image_top)

    # 従来の640初期倍率0.67を基準画像へ反映する。
    combined = centered_scaled_image(combined, 0.67)
    combined = visible_crop(combined)
    return image_to_png_bytes(combined)


def scaled_content_bounds(content_bounds, scale, image_width, image_height):
    left, upper, right, lower = content_bounds
    paste_x = 320 - round(image_width * scale / 2)
    paste_y = 625 - round(image_height * scale)
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
    top_data,
    bottom_data,
    scale_640,
    horizontal_shift_640,
    vertical_shift_640,
):
    base_image_bytes = build_large_base(top_data, bottom_data)
    image = png_bytes_to_image(base_image_bytes)
    default_scale, default_shift_x, default_shift_y = (
        calculate_default_large_transform(base_image_bytes)
    )
    if (
        default_scale == 1.0
        and default_shift_x == 0
        and default_shift_y == 0
        and scale_640 == 1.0
        and horizontal_shift_640 == 0
        and vertical_shift_640 == 0
    ):
        # もともと収まる画像は、従来の余白計算と最終リサイズを維持する。
        pad_left = (640 - image.width) // 2
        pad_right = (640 - image.width) // 2
        pad_top = 640 - image.height - 15
        legacy_output = ImageOps.expand(
            image,
            (pad_left, pad_top, pad_right, 15),
        )
        legacy_output = legacy_output.resize(LARGE_OUTPUT_SIZE)
        return image_to_png_bytes(legacy_output)

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
        625
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
def original_960_png(file_data):
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


def output_name(top_data, bottom_data):
    if top_data is not None:
        return top_data[0]
    return bottom_data[0]


def pad_gender_items(gender, top_files, bottom_files):
    item_count = max(len(top_files), len(bottom_files))
    padded_top = list(top_files) + [None] * (item_count - len(top_files))
    padded_bottom = list(bottom_files) + [None] * (
        item_count - len(bottom_files)
    )
    return tuple(
        (gender, top_data, bottom_data)
        for top_data, bottom_data in zip(padded_top, padded_bottom)
    )


def item_token(index, item):
    gender, top_data, bottom_data = item
    digest = hashlib.sha1(f"{index}:{gender}".encode("utf-8"))
    for file_data in (top_data, bottom_data):
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
    male_silhouette,
    female_silhouette,
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
        gender, top_data, bottom_data = items[index]
        silhouette_data = (
            male_silhouette if gender == "male" else female_silhouette
        )
        file_name = output_name(top_data, bottom_data)
        image_100 = generate_small_png(
            top_data,
            bottom_data,
            silhouette_data,
            playmark_data,
            scale_100,
            horizontal_shift_100,
            vertical_shift_100,
        )
        image_640 = generate_large_png(
            top_data,
            bottom_data,
            scale_640,
            horizontal_shift_640,
            vertical_shift_640,
        )
        outputs[f"100x100/{file_name}"] = image_100
        outputs[f"50x50/{file_name}"] = resize_png(image_100, (50, 50))
        outputs[f"640x640/{file_name}"] = image_640
        outputs[f"320x320/{file_name}"] = resize_png(image_640, (320, 320))
        if top_data is not None:
            outputs[f"960x640/{top_data[0]}"] = original_960_png(top_data)
        if bottom_data is not None:
            outputs[f"960x640/{bottom_data[0]}"] = original_960_png(
                bottom_data
            )

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
def render_adjustment_and_export(
    items,
    male_silhouette,
    female_silhouette,
    playmark_data,
):
    st.divider()

    vertical_shift_100 = st.slider(
        "100×100：下移動 ⇔ 上移動",
        min_value=-150,
        max_value=150,
        value=0,
        step=1,
        key="mm_aura_vertical_shift_100",
    )
    horizontal_shift_100 = st.slider(
        "100×100：左移動 ⇔ 右移動",
        min_value=-150,
        max_value=150,
        value=0,
        step=1,
        key="mm_aura_horizontal_shift_100",
    )
    scale_100 = st.slider(
        "100×100：縮小 ⇔ 拡大（デフォルトは0.75）",
        min_value=0.5,
        max_value=1.5,
        value=0.75,
        step=0.01,
        key="mm_aura_scale_100",
    )

    try:
        small_frame = load_preview_asset("./data/100_flame.png")
    except FileNotFoundError:
        small_frame = None
        st.warning("./data/100_flame.pngが見つからないため、枠のみで表示します。")

    item_keys = []
    columns_100 = st.columns(4)
    for index, item in enumerate(items):
        gender, top_data, bottom_data = item
        silhouette_data = (
            male_silhouette if gender == "male" else female_silhouette
        )
        file_name = output_name(top_data, bottom_data)
        token = item_token(index, item)
        key_100 = f"mm_aura_select_100_{token}"
        key_640 = f"mm_aura_select_640_{token}"
        canonical_key = f"mm_aura_selected_{token}"
        item_keys.append((key_100, key_640, canonical_key))

        selected = bool(st.session_state.get(canonical_key, False))
        st.session_state.setdefault(key_100, selected)
        st.session_state.setdefault(key_640, selected)

        image_100 = generate_small_png(
            top_data,
            bottom_data,
            silhouette_data,
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
        key="mm_aura_vertical_shift_640",
    )
    horizontal_shift_640 = st.slider(
        "640×640：左移動 ⇔ 右移動",
        min_value=-150,
        max_value=150,
        value=0,
        step=1,
        key="mm_aura_horizontal_shift_640",
    )
    scale_640 = st.slider(
        "640×640：縮小 ⇔ 拡大（デフォルトは1.0）",
        min_value=0.5,
        max_value=1.5,
        value=1.0,
        step=0.01,
        key="mm_aura_scale_640",
    )

    try:
        large_background = load_preview_asset("./data/mm_640_back.png")
    except FileNotFoundError:
        large_background = None
        st.warning("./data/mm_640_back.pngが見つからないため、背景なしで表示します。")

    columns_640 = st.columns(4)
    for index, item in enumerate(items):
        _, top_data, bottom_data = item
        file_name = output_name(top_data, bottom_data)
        key_100, key_640, canonical_key = item_keys[index]
        image_640 = generate_large_png(
            top_data,
            bottom_data,
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
            (
                gender,
                data_digest(top_data),
                data_digest(bottom_data),
            )
            for gender, top_data, bottom_data in items
        ),
        data_digest(male_silhouette),
        data_digest(female_silhouette),
        data_digest(playmark_data),
        vertical_shift_100,
        horizontal_shift_100,
        scale_100,
        vertical_shift_640,
        horizontal_shift_640,
        scale_640,
        selected_indices,
    )
    stored_download = st.session_state.get("mm_aura_generated_zip")
    if stored_download and stored_download["config"] != current_config:
        del st.session_state["mm_aura_generated_zip"]

    st.divider()
    export_all_column, export_selected_column = st.columns(2)
    with export_all_column:
        if st.button(
            "一括書き出し",
            key="mm_aura_export_all",
            use_container_width=True,
        ):
            with st.spinner("ZIPを生成中です..."):
                zip_bytes = build_zip(
                    items,
                    male_silhouette,
                    female_silhouette,
                    playmark_data,
                    scale_100,
                    horizontal_shift_100,
                    vertical_shift_100,
                    scale_640,
                    horizontal_shift_640,
                    vertical_shift_640,
                    tuple(range(len(items))),
                )
            st.session_state["mm_aura_generated_zip"] = {
                "config": current_config,
                "name": "mm_aura1.zip",
                "bytes": zip_bytes,
                "key": "mm_aura_download_all",
            }
        st.write("全てのファイルを書き出します。")

    with export_selected_column:
        if st.button(
            "個別書き出し",
            key="mm_aura_export_selected",
            use_container_width=True,
        ):
            if not selected_indices:
                st.warning("書き出すファイルを1件以上選択してください。")
            else:
                with st.spinner("ZIPを生成中です..."):
                    zip_bytes = build_zip(
                        items,
                        male_silhouette,
                        female_silhouette,
                        playmark_data,
                        scale_100,
                        horizontal_shift_100,
                        vertical_shift_100,
                        scale_640,
                        horizontal_shift_640,
                        vertical_shift_640,
                        selected_indices,
                    )
                st.session_state["mm_aura_generated_zip"] = {
                    "config": current_config,
                    "name": "mm_aura2.zip",
                    "bytes": zip_bytes,
                    "key": "mm_aura_download_selected",
                }
        st.write("チェックを入れたファイルを書き出します。")

    stored_download = st.session_state.get("mm_aura_generated_zip")
    if stored_download:
        st.success("書き出しが完了しました。")
        show_download(
            stored_download["name"],
            stored_download["bytes"],
            stored_download.get("key", "mm_aura_download"),
        )


def find_silhouette(silhouette_by_name, candidates):
    for name in candidates:
        if name in silhouette_by_name:
            return silhouette_by_name[name]
    return None


def main():
    st.set_page_config(page_title="mmオーラ書き出し")
    st.title("mmオーラ書き出し")
    st.markdown(
        "**「前後ありオーラ」「前のみ」「後ろのみ」の3種類を一気に"
        "処理はできません。** <p style='font-size:80%;'>"
        "アプリをリロードしてそれぞれ書き出してください。</p>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "**ID付与前に「前後オーラ」を「複数枚同時に」書き出す場合は"
        "お気をつけください。** <p style='font-size:80%;'>"
        "ファイルは選択順に関係なく「昇順」でアップされます。<br>"
        "適切に前後パーツを組み合わせるために、ファイル名の先頭に"
        "3桁の数字を付けるなどで順番を制御してください。<br>（例）<br>"
        "前オーラ：「001.前_目玉A」「002.前_目玉B」「003.前_目玉C」<br>"
        "後ろオーラ：「004.後ろ_目玉A」「005.後ろ_目玉B」"
        "「006.後ろ_目玉C」<br>ABCそれぞれの順番が正しくなるように"
        "数字を付けてください。</p>",
        unsafe_allow_html=True,
    )

    male_top_column, _, female_top_column = st.columns([1, 0.1, 1])
    with male_top_column:
        male_top_uploads = st.file_uploader(
            "男性用オーラ前ファイルを選択",
            type="png",
            accept_multiple_files=True,
            key="export_files_top_male",
        )
    with female_top_column:
        female_top_uploads = st.file_uploader(
            "女性用オーラ前ファイルを選択",
            type="png",
            accept_multiple_files=True,
            key="export_files_top_female",
        )

    male_bottom_column, _, female_bottom_column = st.columns([1, 0.1, 1])
    with male_bottom_column:
        male_bottom_uploads = st.file_uploader(
            "男性用オーラ後ろファイルを選択",
            type="png",
            accept_multiple_files=True,
            key="export_files_bottom_male",
        )
    with female_bottom_column:
        female_bottom_uploads = st.file_uploader(
            "女性用オーラ後ろファイルを選択",
            type="png",
            accept_multiple_files=True,
            key="export_files_bottom_female",
        )

    st.divider()
    silhouette_column, _, playmark_column = st.columns([1, 0.1, 1])
    with silhouette_column:
        st.markdown(
            "**男女シルエット** <p style='font-size:80%;'>"
            "100×100男女シルエット画像をアップロードしてください。<br>"
            "「silhouette_male.png」「silhouette_female.png」から"
            "名前を変更しないでください。</p>",
            unsafe_allow_html=True,
        )
        silhouette_uploads = st.file_uploader(
            "男女シルエットを選択",
            type="png",
            accept_multiple_files=True,
            key="silhouette_file",
            label_visibility="collapsed",
        )
        if not silhouette_uploads:
            st.markdown(
                '<span style="color:red;">未選択です。シルエットを'
                "アップロードしてください。</span>",
                unsafe_allow_html=True,
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

    male_top_uploads = sorted(
        male_top_uploads or [],
        key=lambda file: file.name,
    )
    male_bottom_uploads = sorted(
        male_bottom_uploads or [],
        key=lambda file: file.name,
    )
    female_top_uploads = sorted(
        female_top_uploads or [],
        key=lambda file: file.name,
    )
    female_bottom_uploads = sorted(
        female_bottom_uploads or [],
        key=lambda file: file.name,
    )
    silhouette_uploads = sorted(
        silhouette_uploads or [],
        key=lambda file: file.name,
    )
    playmark_uploads = sorted(
        playmark_uploads or [],
        key=lambda file: file.name,
    )

    male_top = tuple(uploaded_file_to_data(file) for file in male_top_uploads)
    male_bottom = tuple(
        uploaded_file_to_data(file) for file in male_bottom_uploads
    )
    female_top = tuple(
        uploaded_file_to_data(file) for file in female_top_uploads
    )
    female_bottom = tuple(
        uploaded_file_to_data(file) for file in female_bottom_uploads
    )
    male_items = pad_gender_items("male", male_top, male_bottom)
    female_items = pad_gender_items("female", female_top, female_bottom)
    items = male_items + female_items
    if not items:
        return

    silhouette_by_name = {
        file.name: uploaded_file_to_data(file)
        for file in silhouette_uploads
    }
    male_silhouette = find_silhouette(
        silhouette_by_name,
        MALE_SILHOUETTE_NAMES,
    )
    female_silhouette = find_silhouette(
        silhouette_by_name,
        FEMALE_SILHOUETTE_NAMES,
    )
    missing_silhouette = False
    if male_items and male_silhouette is None:
        st.warning("男性用シルエット画像を選択してください。")
        missing_silhouette = True
    if female_items and female_silhouette is None:
        st.warning("女性用シルエット画像を選択してください。")
        missing_silhouette = True
    if missing_silhouette:
        return

    playmark_data = (
        uploaded_file_to_data(playmark_uploads[0])
        if playmark_uploads
        else None
    )
    if len(playmark_uploads) > 1:
        st.info("再生マークはファイル名順の先頭1件を使用します。")

    render_adjustment_and_export(
        items,
        male_silhouette,
        female_silhouette,
        playmark_data,
    )


if __name__ == "__main__":
    main()
