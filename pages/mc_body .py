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


CANVAS_SIZE = (960, 640)
LARGE_SIZE = (640, 640)
SMALL_SIZE = (100, 100)


def safe_name(name):
    """ZIP内にディレクトリを作らない安全なファイル名にする。"""
    normalized = (name or "image.png").replace("\\", "/")
    return normalized.rsplit("/", 1)[-1] or "image.png"


def uploaded_file_to_data(uploaded_file):
    """UploadedFileをキャッシュ可能な(name, bytes)へ変換する。"""
    if uploaded_file is None:
        return None
    return safe_name(uploaded_file.name), uploaded_file.getvalue()


def uploaded_files_to_data(uploaded_files):
    return tuple(uploaded_file_to_data(file) for file in uploaded_files)


def open_rgba(file_data):
    if file_data is None:
        return Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))

    _, image_bytes = file_data
    with Image.open(io.BytesIO(image_bytes)) as image:
        return image.convert("RGBA").resize(CANVAS_SIZE, Image.Resampling.LANCZOS)


def image_to_png_bytes(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def png_bytes_to_image(image_bytes):
    with Image.open(io.BytesIO(image_bytes)) as image:
        return image.convert("RGBA")


def select_output_name(front, center, back):
    for file_data in (front, center, back):
        if file_data is not None:
            return file_data[0]
    return "image.png"


def make_large_image(composite):
    """合成済み960x640画像から640x640画像を作る。"""
    bbox = composite.getbbox()
    if bbox is None:
        return Image.new("RGBA", LARGE_SIZE, (0, 0, 0, 0))

    alpha = composite.getchannel("A")
    alpha_bbox = alpha.getbbox()
    left = alpha_bbox[0]
    right = alpha_bbox[2] - 1

    if left < 180 or right > 820:
        crop_image = composite.crop(bbox)
        width, height = crop_image.size
        scale = 640 / max(width, height)
        new_width = min(640, max(1, round(width * scale)))
        new_height = min(640, max(1, round(height * scale)))
        resized = crop_image.resize(
            (new_width, new_height), Image.Resampling.LANCZOS
        )

        output = Image.new("RGBA", LARGE_SIZE, (0, 0, 0, 0))
        paste_x = (640 - new_width) // 2
        paste_y = (640 - new_height) // 2
        output.alpha_composite(resized, (paste_x, paste_y))
        return output

    return composite.crop((180, 0, 820, 640))


@st.cache_data(show_spinner=False)
def prepare_items(front_files, center_files, back_files, head_file):
    """
    スライダーに依存しない処理を一度だけ実行する。

    戻り値はpickle可能なbytes中心の構造にして、Streamlitのキャッシュへ安全に
    保存できるようにする。
    """
    max_length = max(len(front_files), len(center_files), len(back_files))
    fronts = list(front_files) + [None] * (max_length - len(front_files))
    centers = list(center_files) + [None] * (max_length - len(center_files))
    backs = list(back_files) + [None] * (max_length - len(back_files))

    head_image = open_rgba(head_file) if head_file is not None else None
    prepared = []

    for front, center, back in zip(fronts, centers, backs):
        front_image = open_rgba(front)
        center_image = open_rgba(center)
        back_image = open_rgba(back)

        if head_image is not None:
            center_image = Image.alpha_composite(center_image, head_image)

        composite = Image.alpha_composite(back_image, center_image)
        composite = Image.alpha_composite(composite, front_image)
        output_name = select_output_name(front, center, back)
        large_image = make_large_image(composite)

        layer_outputs = []
        if front is not None:
            layer_outputs.append((front[0], image_to_png_bytes(front_image)))
        if center is not None:
            layer_outputs.append((center[0], image_to_png_bytes(center_image)))
        if back is not None and back[0] not in ("素体_男.png", "素体_女.png"):
            layer_outputs.append((back[0], image_to_png_bytes(back_image)))

        prepared.append(
            {
                "name": output_name,
                "composite_png": image_to_png_bytes(composite),
                "large_png": image_to_png_bytes(large_image),
                "layer_outputs": tuple(layer_outputs),
            }
        )

    return tuple(prepared)


def scale_about_center(image, scale):
    """元コードと同じく、960x640の中心を基準に拡大・縮小する。"""
    width, height = image.size
    new_width = max(1, round(width * scale))
    new_height = max(1, round(height * scale))
    resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    if new_width <= width and new_height <= height:
        output = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        output.alpha_composite(
            resized,
            ((width - new_width) // 2, (height - new_height) // 2),
        )
        return output

    left = (new_width - width) // 2
    top = (new_height - height) // 2
    return resized.crop((left, top, left + width, top + height))


@st.cache_data(show_spinner=False)
def make_small_image(
    composite_png,
    attribution_bytes,
    horizontal_shift,
    vertical_shift,
    scale,
):
    """スライダー値に応じた100x100画像を生成し、結果をキャッシュする。"""
    composite = png_bytes_to_image(composite_png)
    scaled = scale_about_center(composite, scale)

    # 元コードの2段階cropと同じ範囲を直接切り抜く。
    left = 350 - horizontal_shift
    top = 100 + vertical_shift
    cropped = scaled.crop((left, top, left + 290, top + 290))
    small = cropped.resize(SMALL_SIZE, Image.Resampling.LANCZOS)

    with Image.open(io.BytesIO(attribution_bytes)) as attribution:
        attribution_rgba = attribution.convert("RGBA")
    small.paste(attribution_rgba, (0, 0), attribution_rgba)
    return image_to_png_bytes(small)


def make_preview_image(small_png):
    preview = png_bytes_to_image(small_png)
    draw = ImageDraw.Draw(preview)
    draw.line((50, 0, 50, 100), fill="red", width=1)
    draw.line((0, 50, 100, 50), fill="red", width=1)
    return ImageOps.expand(preview, border=1, fill="red")


@st.cache_data(show_spinner=False)
def adjust_large_image(
    large_png,
    horizontal_shift,
    vertical_shift,
    scale,
):
    """スライダー値に応じて640x640画像を拡大・縮小・移動する。"""
    large = png_bytes_to_image(large_png)
    width, height = large.size
    new_width = max(1, round(width * scale))
    new_height = max(1, round(height * scale))
    scaled = large.resize(
        (new_width, new_height), Image.Resampling.LANCZOS
    )

    # 拡大後の画像を先に640x640へcropすると、画面外の情報が失われて
    # 移動時に戻せない。全体を保持したまま配置し、最後に出力枠で切り取る。
    paste_x = (LARGE_SIZE[0] - new_width) // 2 + horizontal_shift
    paste_y = (LARGE_SIZE[1] - new_height) // 2 - vertical_shift

    output = Image.new("RGBA", LARGE_SIZE, (0, 0, 0, 0))
    output.alpha_composite(
        scaled,
        (paste_x, paste_y),
    )
    return image_to_png_bytes(output)


def make_large_preview_image(large_png):
    preview = png_bytes_to_image(large_png).resize(
        (200, 200), Image.Resampling.LANCZOS
    )
    draw = ImageDraw.Draw(preview)
    draw.line((100, 0, 100, 200), fill="red", width=1)
    draw.line((0, 100, 200, 100), fill="red", width=1)
    return ImageOps.expand(preview, border=1, fill="red")


def resize_png(image_bytes, size):
    image = png_bytes_to_image(image_bytes)
    resized = image.resize(size, Image.Resampling.LANCZOS)
    return image_to_png_bytes(resized)


@st.cache_data(show_spinner=False)
def build_zip(
    prepared_items,
    attribution_bytes,
    horizontal_shift,
    vertical_shift,
    scale,
    large_horizontal_shift,
    large_vertical_shift,
    large_scale,
    selected_indices,
):
    """指定された画像を各サイズへ書き出し、ZIPのbytesを返す。"""
    outputs = {}

    for index in selected_indices:
        item = prepared_items[index]
        name = item["name"]
        small_png = make_small_image(
            item["composite_png"],
            attribution_bytes,
            horizontal_shift,
            vertical_shift,
            scale,
        )
        large_png = adjust_large_image(
            item["large_png"],
            large_horizontal_shift,
            large_vertical_shift,
            large_scale,
        )

        outputs[f"100x100/{name}"] = small_png
        outputs[f"50x50/{name}"] = resize_png(small_png, (50, 50))
        outputs[f"640x640/{name}"] = large_png
        outputs[f"320x320/{name}"] = resize_png(large_png, (320, 320))

        for layer_name, layer_png in item["layer_outputs"]:
            # 同名レイヤーがある場合は、元コードと同様に後の画像を採用する。
            outputs[f"960x640/{layer_name}"] = layer_png

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, image_bytes in outputs.items():
            archive.writestr(path, image_bytes)
    return buffer.getvalue()


def show_download(zip_name, zip_bytes, key):
    st.download_button(
        label=f"{zip_name}をダウンロード",
        data=zip_bytes,
        file_name=zip_name,
        mime="application/zip",
        key=key,
        on_click="ignore",
    )


def selection_checkbox_keys(index, name):
    suffix = f"{index}_{name}"
    return f"select_100_{suffix}", f"select_640_{suffix}"


def sync_selection_checkbox(source_key, target_key):
    """100と640の同一画像の選択状態を同期する。"""
    st.session_state[target_key] = st.session_state[source_key]


@st.fragment
def render_adjustment_and_export(prepared_items, attribution_bytes):
    """
    スライダー・プレビュー・書き出しだけを部分再実行する。

    スライダー操作ではmain()全体やアップロード画像の基本合成を再実行しない。
    """
    st.markdown("---")

    vertical_shift = st.slider(
        "100×100：下移動 ⇔ 上移動",
        min_value=-150,
        max_value=150,
        value=0,
        key="vertical_shift",
    )
    horizontal_shift = st.slider(
        "100×100：左移動 ⇔ 右移動",
        min_value=-150,
        max_value=150,
        value=0,
        key="horizontal_shift",
    )
    scale = st.slider(
        "100×100：縮小 ⇔ 拡大（デフォルトは0.75）",
        min_value=0.5,
        max_value=1.5,
        value=0.75,
        step=0.01,
        key="scale_100",
    )

    st.caption(
        "スライダー操作時は、この調整・プレビュー部分だけを再実行します。"
    )

    st.write("**100×100プレビュー**")
    preview_columns = st.columns(4)

    with st.spinner("100×100プレビュー画像を生成中です..."):
        for index, item in enumerate(prepared_items):
            small_png = make_small_image(
                item["composite_png"],
                attribution_bytes,
                horizontal_shift,
                vertical_shift,
                scale,
            )
            column = preview_columns[index % 4]
            render_preview_filename(column, item["name"])
            column.image(make_preview_image(small_png), width="content")
            small_key, large_key = selection_checkbox_keys(
                index, item["name"]
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
        key="large_vertical_shift",
    )
    large_horizontal_shift = st.slider(
        "640×640：左移動 ⇔ 右移動",
        min_value=-150,
        max_value=150,
        value=0,
        key="large_horizontal_shift",
    )
    large_scale = st.slider(
        "640×640：縮小 ⇔ 拡大（デフォルトは1.0）",
        min_value=0.5,
        max_value=1.5,
        value=1.0,
        step=0.01,
        key="large_scale",
    )

    st.write("**640×640プレビュー**")
    large_preview_columns = st.columns(4)
    with st.spinner("640×640プレビュー画像を生成中です..."):
        for index, item in enumerate(prepared_items):
            large_png = adjust_large_image(
                item["large_png"],
                large_horizontal_shift,
                large_vertical_shift,
                large_scale,
            )
            column = large_preview_columns[index % 4]
            render_preview_filename(column, item["name"])
            column.image(
                make_large_preview_image(large_png),
                width="content",
            )
            small_key, large_key = selection_checkbox_keys(
                index, item["name"]
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
        for index, item in enumerate(prepared_items)
        if st.session_state.get(
            selection_checkbox_keys(index, item["name"])[0], False
        )
    ]

    current_config = (
        horizontal_shift,
        vertical_shift,
        scale,
        large_horizontal_shift,
        large_vertical_shift,
        large_scale,
        tuple(selected_indices),
    )
    saved_result = st.session_state.get("generated_zip")
    if saved_result and saved_result["config"] != current_config:
        del st.session_state["generated_zip"]

    st.markdown("---")
    all_column, selected_column = st.columns(2)

    with all_column:
        if st.button("一括書き出し", key="export_all", width="stretch"):
            with st.spinner("ZIPを生成中です..."):
                zip_bytes = build_zip(
                    prepared_items,
                    attribution_bytes,
                    horizontal_shift,
                    vertical_shift,
                    scale,
                    large_horizontal_shift,
                    large_vertical_shift,
                    large_scale,
                    tuple(range(len(prepared_items))),
                )
            st.session_state["generated_zip"] = {
                "config": current_config,
                "name": "mc_body1.zip",
                "bytes": zip_bytes,
                "key": "download_all",
            }
        st.write("全てのファイルを書き出します。")

    with selected_column:
        if st.button("個別書き出し", key="export_selected", width="stretch"):
            if not selected_indices:
                st.warning("書き出すファイルを1件以上選択してください。")
            else:
                with st.spinner("ZIPを生成中です..."):
                    zip_bytes = build_zip(
                        prepared_items,
                        attribution_bytes,
                        horizontal_shift,
                        vertical_shift,
                        scale,
                        large_horizontal_shift,
                        large_vertical_shift,
                        large_scale,
                        tuple(selected_indices),
                    )
                st.session_state["generated_zip"] = {
                    "config": current_config,
                    "name": "mc_body2.zip",
                    "bytes": zip_bytes,
                    "key": "download_selected",
                }
        st.write("チェックを入れたファイルを書き出します。")

    generated_zip = st.session_state.get("generated_zip")
    if generated_zip:
        st.success("書き出しが完了しました。")
        show_download(
            generated_zip["name"],
            generated_zip["bytes"],
            generated_zip["key"],
        )


def main():
    st.set_page_config(page_title="mc体書き出し")
    st.title("mc見た目体書き出し")

    st.write(
        "**「前後ありオーラ」「前のみ」「後ろのみ」の3種類を一気に処理は"
        "できません。** <p style=\"font-size: 80%;\">アプリをリロードして"
        "それぞれ書き出してください。<br><br><br></p>",
        unsafe_allow_html=True,
    )
    st.write(
        '<span style="color:red;">※未圧縮データを使ってください</span>',
        unsafe_allow_html=True,
    )
    st.write(
        '<span style="color:red;">※mcの体は独自ポーズの場合は影付きで'
        "書き出してください</span>",
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

    front_uploads = sorted(front_uploads, key=lambda file: file.name)
    center_uploads = sorted(center_uploads, key=lambda file: file.name)
    back_uploads = sorted(back_uploads, key=lambda file: file.name)

    attribution_column, head_column = st.columns(2)
    with attribution_column:
        st.write(
            '**属性**<span style="color:red; font-size: 80%;">　※必須</span>',
            unsafe_allow_html=True,
        )
        attribution_upload = st.file_uploader(
            "選択",
            type="png",
            accept_multiple_files=False,
            key="attribution_file",
        )
        if attribution_upload is None:
            st.write(
                '<span style="color:red;">未選択です。属性画像をアップロード'
                "してください。</span>",
                unsafe_allow_html=True,
            )

    with head_column:
        st.write(
            "**オマケ：頭（なくても書き出しできます）**"
            '<p style="font-size: 80%;">頭素体を付け忘れた時に追加できます。'
            "「mc_head.png」をアップロードしてください。<br></p>",
            unsafe_allow_html=True,
        )
        head_uploads = st.file_uploader(
            "選択",
            type="png",
            accept_multiple_files=True,
            key="head_file",
        )

    has_body_files = bool(front_uploads or center_uploads or back_uploads)
    if not has_body_files:
        return
    if attribution_upload is None:
        st.info("属性画像をアップロードすると、調整プレビューを表示します。")
        return

    if len(head_uploads) > 1:
        st.warning("頭ファイルは先頭の1件だけを使用します。")

    front_files = uploaded_files_to_data(front_uploads)
    center_files = uploaded_files_to_data(center_uploads)
    back_files = uploaded_files_to_data(back_uploads)
    head_file = uploaded_file_to_data(head_uploads[0]) if head_uploads else None
    attribution_bytes = attribution_upload.getvalue()

    # アップローダー変更による全体再実行時は、古いZIPを破棄する。
    st.session_state.pop("generated_zip", None)

    with st.spinner("アップロード画像を準備中です..."):
        prepared = prepare_items(
            front_files,
            center_files,
            back_files,
            head_file,
        )

    render_adjustment_and_export(prepared, attribution_bytes)


if __name__ == "__main__":
    main()
