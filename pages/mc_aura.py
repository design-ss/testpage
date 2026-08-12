import html

import streamlit as st
import zipfile
import io
from PIL import Image, ImageOps, ImageDraw


def render_preview_filename(container, file_name):
    escaped_name = html.escape(str(file_name), quote=True)
    container.markdown(
        f'<div title="{escaped_name}" style="height:1.25rem; line-height:1.25rem; '
        'overflow:hidden; text-overflow:ellipsis; white-space:nowrap; '
        'font-size:0.875rem; opacity:0.6;">'
        f'{escaped_name}</div>',
        unsafe_allow_html=True,
    )


LARGE_CANVAS_SIZE = (640, 640)
LARGE_BASE_BOTTOM = 544
INITIAL_SHRINK_SCALES = (1.0, 0.95, 0.90, 0.85, 0.80)
AUTO_POSITION_LIMIT = 64
FURTHER_SHRINK_SCALES = tuple(
    percent / 100 for percent in range(75, 19, -5)
)


def getPreviewImage(image, preview_size=None, border_size=1, border_color="red"):
    preview = image.convert("RGBA")
    if preview_size is not None:
        preview = preview.resize(preview_size, Image.Resampling.LANCZOS)

    draw = ImageDraw.Draw(preview)
    center_x = preview.width // 2
    center_y = preview.height // 2
    draw.line((center_x, 0, center_x, preview.height), fill="red", width=1)
    draw.line((0, center_y, preview.width, center_y), fill="red", width=1)
    return ImageOps.expand(preview, border=border_size, fill=border_color)


def open_upload_image(uploaded_file):
    if uploaded_file is None:
        return Image.new("RGBA", (960, 640), (0, 0, 0, 0))

    return uploaded_file_to_image(uploaded_file)


def uploaded_file_to_image(uploaded_file):
    image_bytes = uploaded_file.getvalue()
    with Image.open(io.BytesIO(image_bytes)) as image:
        return image.convert("RGBA").resize(
            (960, 640), Image.Resampling.LANCZOS
        )


def composite_aura(export_file_front, export_file_back):
    image_front = open_upload_image(export_file_front)
    image_back = open_upload_image(export_file_back)
    return Image.alpha_composite(image_back, image_front)


def fit_visible_image(image, max_size):
    bbox = image.getbbox()
    if bbox is None:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))

    visible = image.crop(bbox)
    width, height = visible.size
    scale = max_size / max(width, height)
    new_width = max(1, round(width * scale))
    new_height = max(1, round(height * scale))
    return visible.resize(
        (new_width, new_height), Image.Resampling.LANCZOS
    )


def scaled_image_bounds(image, scale, center_x, center_y):
    width = max(1, round(image.width * scale))
    height = max(1, round(image.height * scale))
    left = round(center_x - width / 2)
    top = round(center_y - height / 2)
    return left, top, left + width, top + height


def bounds_fit_canvas(bounds, canvas_size):
    left, top, right, bottom = bounds
    canvas_width, canvas_height = canvas_size
    return (
        left >= 0
        and top >= 0
        and right <= canvas_width
        and bottom <= canvas_height
    )


def limited_position_adjustment(bounds, canvas_size, limit):
    left, top, right, bottom = bounds
    canvas_width, canvas_height = canvas_size

    horizontal = 0
    if left < 0:
        horizontal = -left
    elif right > canvas_width:
        horizontal = canvas_width - right

    vertical = 0
    if top < 0:
        vertical = -top
    elif bottom > canvas_height:
        vertical = canvas_height - bottom

    horizontal = max(-limit, min(limit, horizontal))
    vertical = max(-limit, min(limit, vertical))
    return horizontal, vertical


def find_large_default_placement(image):
    canvas_size = LARGE_CANVAS_SIZE
    base_center_x = canvas_size[0] / 2
    base_center_y = LARGE_BASE_BOTTOM - image.height / 2

    # まず従来の固定位置を保ったまま、5%刻みで最大20%縮小する。
    for scale in INITIAL_SHRINK_SCALES:
        bounds = scaled_image_bounds(
            image, scale, base_center_x, base_center_y
        )
        if bounds_fit_canvas(bounds, canvas_size):
            return scale, base_center_x, base_center_y

    # 20%縮小で収まらなければ、固定位置から最大64pxだけ最小限移動する。
    scale = INITIAL_SHRINK_SCALES[-1]
    bounds = scaled_image_bounds(
        image, scale, base_center_x, base_center_y
    )
    horizontal, vertical = limited_position_adjustment(
        bounds, canvas_size, AUTO_POSITION_LIMIT
    )
    adjusted_center_x = base_center_x + horizontal
    adjusted_center_y = base_center_y + vertical
    adjusted_bounds = scaled_image_bounds(
        image, scale, adjusted_center_x, adjusted_center_y
    )
    if bounds_fit_canvas(adjusted_bounds, canvas_size):
        return scale, adjusted_center_x, adjusted_center_y

    # 位置調整後も収まらない場合は、5%刻みでさらに縮小する。
    for scale in FURTHER_SHRINK_SCALES:
        bounds = scaled_image_bounds(
            image, scale, base_center_x, base_center_y
        )
        horizontal, vertical = limited_position_adjustment(
            bounds, canvas_size, AUTO_POSITION_LIMIT
        )
        adjusted_center_x = base_center_x + horizontal
        adjusted_center_y = base_center_y + vertical
        adjusted_bounds = scaled_image_bounds(
            image, scale, adjusted_center_x, adjusted_center_y
        )
        if bounds_fit_canvas(adjusted_bounds, canvas_size):
            return scale, adjusted_center_x, adjusted_center_y

    # 念のための最終処理。中央配置で必ずキャンバス内に収める。
    contain_scale = min(
        canvas_size[0] / image.width,
        canvas_size[1] / image.height,
        FURTHER_SHRINK_SCALES[-1],
    )
    return contain_scale, canvas_size[0] / 2, canvas_size[1] / 2


def place_scaled_image(
    image,
    canvas_size,
    scale,
    center_x,
    center_y,
    horizontal_shift,
    vertical_shift,
):
    new_width = max(1, round(image.width * scale))
    new_height = max(1, round(image.height * scale))
    resized = image.resize(
        (new_width, new_height), Image.Resampling.LANCZOS
    )

    paste_x = round(center_x - new_width / 2 + horizontal_shift)
    paste_y = round(center_y - new_height / 2 - vertical_shift)
    output = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    output.alpha_composite(resized, (paste_x, paste_y))
    return output


# 100 × 100、50 × 50の基準画像を作る。
def generate_small_images(
    export_file_front,
    export_file_back,
    attribution_file,
    horizontal_shift,
    vertical_shift,
    scale,
):
    composite = composite_aura(export_file_front, export_file_back)
    fitted = fit_visible_image(composite, 100)

    # 標準の初期値0.75で従来と同じ大きさになるよう正規化する。
    adjusted = place_scaled_image(
        fitted,
        (100, 100),
        scale / 0.75,
        50,
        50,
        horizontal_shift,
        vertical_shift,
    )

    attribution_bytes = attribution_file.getvalue()
    with Image.open(io.BytesIO(attribution_bytes)) as attribution:
        attribution_rgba = attribution.convert("RGBA").resize(
            (100, 100), Image.Resampling.LANCZOS
        )
    adjusted = Image.alpha_composite(adjusted, attribution_rgba)

    file_name = (
        export_file_front.name
        if export_file_front is not None
        else export_file_back.name
    )
    return adjusted, file_name


# 640 × 640、320 × 320の基準画像を作る。
def generate_large_images(
    export_file_front,
    export_file_back,
    horizontal_shift,
    vertical_shift,
    scale,
):
    composite = composite_aura(export_file_front, export_file_back)
    fitted = fit_visible_image(composite, 640)

    # 自動調整した初期配置を基準に、スライダーの倍率・移動量を適用する。
    auto_scale, auto_center_x, auto_center_y = find_large_default_placement(
        fitted
    )
    adjusted = place_scaled_image(
        fitted,
        LARGE_CANVAS_SIZE,
        auto_scale * scale,
        auto_center_x,
        auto_center_y,
        horizontal_shift,
        vertical_shift,
    )

    file_name = (
        export_file_front.name
        if export_file_front is not None
        else export_file_back.name
    )
    return adjusted, file_name


def prepare_file_pairs(front_files, back_files):
    max_length = max(len(front_files), len(back_files))
    fronts = list(front_files) + [None] * (max_length - len(front_files))
    backs = list(back_files) + [None] * (max_length - len(back_files))
    return tuple(zip(fronts, backs))


def selection_checkbox_keys(index, file_name):
    suffix = f"{index}_{file_name}"
    return f"select_100_{suffix}", f"select_640_{suffix}"


def sync_selection_checkbox(source_key, target_key):
    st.session_state[target_key] = st.session_state[source_key]


def build_output_images(
    file_pairs,
    attribution_file,
    small_horizontal_shift,
    small_vertical_shift,
    small_scale,
    large_horizontal_shift,
    large_vertical_shift,
    large_scale,
    selected_indices,
):
    outputs = {}

    for index in selected_indices:
        export_file_front, export_file_back = file_pairs[index]
        small_image, file_name = generate_small_images(
            export_file_front,
            export_file_back,
            attribution_file,
            small_horizontal_shift,
            small_vertical_shift,
            small_scale,
        )
        large_image, _ = generate_large_images(
            export_file_front,
            export_file_back,
            large_horizontal_shift,
            large_vertical_shift,
            large_scale,
        )

        outputs[f"100x100/{file_name}"] = small_image
        outputs[f"50x50/{file_name}"] = small_image.resize(
            (50, 50), Image.Resampling.LANCZOS
        )
        outputs[f"640x640/{file_name}"] = large_image
        outputs[f"320x320/{file_name}"] = large_image.resize(
            (320, 320), Image.Resampling.LANCZOS
        )

        if export_file_front is not None:
            outputs[f"960x640/{export_file_front.name}"] = (
                uploaded_file_to_image(export_file_front)
            )
        if export_file_back is not None:
            outputs[f"960x640/{export_file_back.name}"] = (
                uploaded_file_to_image(export_file_back)
            )

    return outputs


def images_to_zip_bytes(images):
    buffer = io.BytesIO()
    with zipfile.ZipFile(
        buffer, "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        for path, image in images.items():
            image_buffer = io.BytesIO()
            image.save(image_buffer, format="PNG")
            archive.writestr(path, image_buffer.getvalue())
    return buffer.getvalue()


def uploaded_file_signature(uploaded_file):
    if uploaded_file is None:
        return None
    return uploaded_file.name, len(uploaded_file.getvalue())


@st.fragment
def render_adjustment_and_export(file_pairs, attribution_file):
    st.markdown("---")

    small_vertical_shift = st.slider(
        "100×100：下移動 ⇔ 上移動",
        min_value=-150,
        max_value=150,
        value=0,
        key="aura_small_vertical_shift",
    )
    small_horizontal_shift = st.slider(
        "100×100：左移動 ⇔ 右移動",
        min_value=-150,
        max_value=150,
        value=0,
        key="aura_small_horizontal_shift",
    )
    small_scale = st.slider(
        "100×100：縮小 ⇔ 拡大（デフォルトは0.75）",
        min_value=0.5,
        max_value=1.5,
        value=0.75,
        step=0.01,
        key="aura_small_scale",
    )

    st.write("**100×100プレビュー**")
    small_columns = st.columns(4)
    with st.spinner("100×100プレビュー画像を生成中です..."):
        for index, (export_file_front, export_file_back) in enumerate(
            file_pairs
        ):
            preview_image, file_name = generate_small_images(
                export_file_front,
                export_file_back,
                attribution_file,
                small_horizontal_shift,
                small_vertical_shift,
                small_scale,
            )
            column = small_columns[index % 4]
            render_preview_filename(column, file_name)
            column.image(getPreviewImage(preview_image), width="content")
            small_key, large_key = selection_checkbox_keys(index, file_name)
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
        key="aura_large_vertical_shift",
    )
    large_horizontal_shift = st.slider(
        "640×640：左移動 ⇔ 右移動",
        min_value=-150,
        max_value=150,
        value=0,
        key="aura_large_horizontal_shift",
    )
    large_scale = st.slider(
        "640×640：縮小 ⇔ 拡大（デフォルトは1.0）",
        min_value=0.5,
        max_value=1.5,
        value=1.0,
        step=0.01,
        key="aura_large_scale",
    )

    st.write("**640×640プレビュー**")
    large_columns = st.columns(4)
    with st.spinner("640×640プレビュー画像を生成中です..."):
        for index, (export_file_front, export_file_back) in enumerate(
            file_pairs
        ):
            preview_image, file_name = generate_large_images(
                export_file_front,
                export_file_back,
                large_horizontal_shift,
                large_vertical_shift,
                large_scale,
            )
            column = large_columns[index % 4]
            render_preview_filename(column, file_name)
            column.image(
                getPreviewImage(preview_image, (200, 200)),
                width="content",
            )
            small_key, large_key = selection_checkbox_keys(index, file_name)
            column.checkbox(
                "個別書き出し",
                key=large_key,
                label_visibility="collapsed",
                on_change=sync_selection_checkbox,
                args=(large_key, small_key),
            )

    selected_indices = [
        index
        for index, (export_file_front, export_file_back) in enumerate(
            file_pairs
        )
        if st.session_state.get(
            selection_checkbox_keys(
                index,
                (
                    export_file_front.name
                    if export_file_front is not None
                    else export_file_back.name
                ),
            )[0],
            False,
        )
    ]

    file_signature = tuple(
        (
            uploaded_file_signature(export_file_front),
            uploaded_file_signature(export_file_back),
        )
        for export_file_front, export_file_back in file_pairs
    )
    current_config = (
        file_signature,
        uploaded_file_signature(attribution_file),
        small_horizontal_shift,
        small_vertical_shift,
        small_scale,
        large_horizontal_shift,
        large_vertical_shift,
        large_scale,
        tuple(selected_indices),
    )
    saved_result = st.session_state.get("aura_generated_zip")
    if saved_result and saved_result["config"] != current_config:
        del st.session_state["aura_generated_zip"]

    st.markdown("---")
    all_column, selected_column = st.columns(2)

    with all_column:
        if st.button("一括書き出し", key="aura_export_all", width="stretch"):
            with st.spinner("ZIPを生成中です..."):
                images = build_output_images(
                    file_pairs,
                    attribution_file,
                    small_horizontal_shift,
                    small_vertical_shift,
                    small_scale,
                    large_horizontal_shift,
                    large_vertical_shift,
                    large_scale,
                    tuple(range(len(file_pairs))),
                )
                zip_bytes = images_to_zip_bytes(images)
            st.session_state["aura_generated_zip"] = {
                "config": current_config,
                "name": "mc_aura1.zip",
                "bytes": zip_bytes,
                "key": "aura_download_all",
            }
        st.write("全てのファイルを書き出します。")

    with selected_column:
        if st.button(
            "個別書き出し",
            key="aura_export_selected",
            width="stretch",
        ):
            if not selected_indices:
                st.warning("書き出すファイルを1件以上選択してください。")
            else:
                with st.spinner("ZIPを生成中です..."):
                    images = build_output_images(
                        file_pairs,
                        attribution_file,
                        small_horizontal_shift,
                        small_vertical_shift,
                        small_scale,
                        large_horizontal_shift,
                        large_vertical_shift,
                        large_scale,
                        tuple(selected_indices),
                    )
                    zip_bytes = images_to_zip_bytes(images)
                st.session_state["aura_generated_zip"] = {
                    "config": current_config,
                    "name": "mc_aura2.zip",
                    "bytes": zip_bytes,
                    "key": "aura_download_selected",
                }
        st.write("チェックを入れたファイルを書き出します。")

    generated_zip = st.session_state.get("aura_generated_zip")
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


st.set_page_config(page_title="mcオーラ書き出し")
st.title("mcオーラ書き出し")
st.write(
    '<span style="color:red;">※未圧縮データを使ってください！</span>',
    unsafe_allow_html=True,
)

front_column, back_column = st.columns(2)
with front_column:
    export_files_front = st.file_uploader(
        "**オーラ前**",
        type="png",
        accept_multiple_files=True,
        key="export_files_front",
    )
with back_column:
    export_files_back = st.file_uploader(
        "**オーラ後ろ**",
        type="png",
        accept_multiple_files=True,
        key="export_files_back",
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

export_files_front = sorted(
    export_files_front, key=lambda uploaded_file: uploaded_file.name
)
export_files_back = sorted(
    export_files_back, key=lambda uploaded_file: uploaded_file.name
)

has_aura_files = bool(export_files_front or export_files_back)
if has_aura_files and attribution_file is not None:
    file_pairs = prepare_file_pairs(
        export_files_front,
        export_files_back,
    )
    render_adjustment_and_export(file_pairs, attribution_file)
