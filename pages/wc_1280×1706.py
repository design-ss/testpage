from PIL import Image, ImageOps
import os
import streamlit as st
import zipfile
import io
import time

# 1. ページ設定
st.set_page_config(page_title='1280×1706加工処理')

# 2. Streamlit上でのみ画像に枠線をつけるCSS（保存用画像には影響しません）
st.markdown(
    """
    <style>
    [data-testid="stImage"] img {
        border: 2px solid #d3d3d3;
        box-shadow: 2px 2px 8px rgba(0,0,0,0.1);
    }
    </style>
    """,
    unsafe_allow_html=True
)

# 3. ZIPダウンロード用関数
def show_zip_download(zip_name, target_dict):
    """
    target_dict: {ファイル名: PIL画像オブジェクト}
    """
    with io.BytesIO() as buffer:
        with zipfile.ZipFile(buffer, "w") as zip_file:
            for file_name, image in target_dict.items():
                img_buffer = io.BytesIO()
                image.save(img_buffer, "PNG")
                zip_file.writestr(file_name, img_buffer.getvalue())
        buffer.seek(0)
        st.download_button(
            label=f"🎁 {zip_name} をダウンロード",
            data=buffer,
            file_name=zip_name,
            mime='application/zip'
        )

# 4. 画像処理用補助関数
def crop_except_bottom(image):
    bbox = image.getbbox()
    if bbox:
        left, top, right, _ = bbox
        bottom = image.height
        return image.crop((left, top, right, bottom))
    return image

def process_image(image, process_type=None):
    final_image = None
    
    # ステップ 1: 透明部分をトリミング
    if process_type == 7:  # 大神用
        temp_img = crop_except_bottom(image)
    else:
        bbox = image.getbbox()
        temp_img = image.crop(bbox) if bbox else image

    width, height = temp_img.size
    
    # 自動判別ロジック
    if process_type is None:
        if width >= 2600: process_type = 1
        elif width <= 2600 and 3500 <= height <= 3700: process_type = 2
        elif width <= 2600 and height >= 3750: process_type = 3
        elif width <= 2600 and height <= 2544: process_type = 4
        else: process_type = 5

    # 各処理の実装 (1280x1706)
    if process_type == 1:
        scale_factor = 1280 / width
        new_height = int(height * scale_factor)
        resized_image = temp_img.resize((1280, new_height), Image.LANCZOS)
        final_image = Image.new("RGBA", (1280, 1706), (255, 255, 255, 0))
        final_image.paste(resized_image, (0, 1706 - resized_image.height))

    elif process_type in [2, 4, 5, 6, 7]:
        # 各タイプごとのベース高さ設定
        base_h = {2:3750, 4:3000, 5:3500, 6:3200, 7:3200}.get(process_type, 3500)
        
        new_image = Image.new("RGBA", (width, base_h), (255, 255, 255, 0))
        new_image.paste(temp_img, (0, base_h - height))
        
        scale_factor = 1706 / new_image.height
        new_width = int(new_image.width * scale_factor)
        resized_image = new_image.resize((new_width, 1706), Image.LANCZOS)
        
        final_image = Image.new("RGBA", (1280, 1706), (255, 255, 255, 0))
        final_image.paste(resized_image, ((1280 - resized_image.width) // 2, 0))

    elif process_type == 3:
        scale_factor = 1706 / height
        new_width = int(width * scale_factor)
        resized_image = temp_img.resize((new_width, 1706), Image.LANCZOS)
        final_image = Image.new("RGBA", (1280, 1706), (255, 255, 255, 0))
        final_image.paste(resized_image, ((1280 - resized_image.width) // 2, 0))

    return final_image, width, height

# 5. メインUI
st.title('1280×1706加工処理')
uploaded_files = st.file_uploader("PNGファイルを選択", type='png', accept_multiple_files=True)

st.markdown('---')

# ボタン配置
col1, col2 = st.columns(2)
with col1:
    save_all = st.button("全ファイルを自動判別で処理・ZIP準備")
    process_1 = st.button("処理 1: 横幅2600以上")
    process_2 = st.button("処理 2: 3500-3700")
    process_3 = st.button("処理 3: 3750以上")
with col2:
    process_other = st.button("通常処理 (処理5)")
    process_4 = st.button("処理 4: 2544以下")
    process_5 = st.button("処理 5: 物足りない時用")
    process_6 = st.button("処理 6: 大神用")

# 6. 処理実行ロジック
if uploaded_files:
    # どの処理を行うか決定
    selected_type = None
    if process_1: selected_type = 1
    elif process_2: selected_type = 2
    elif process_3: selected_type = 3
    elif process_4: selected_type = 4
    elif process_other: selected_type = 5
    elif process_5: selected_type = 6
    elif process_6: selected_type = 7
    # save_all の時は None のまま（自動判別）

    if any([save_all, process_1, process_2, process_3, process_4, process_other, process_5, process_6]):
        results_dict = {}
        with st.spinner("処理中..."):
            for uploaded_file in uploaded_files:
                img = Image.open(uploaded_file).convert("RGBA")
                processed_img, orig_w, orig_h = process_image(img, selected_type)
                
                if processed_img:
                    results_dict[uploaded_file.name] = processed_img
                    # プレビュー表示
                    st.image(processed_img, caption=f"【{uploaded_file.name}】 元サイズ: {orig_w}x{orig_h}")
        
        if results_dict:
            st.success(f"{len(results_dict)} 件の処理が完了しました！")
            show_zip_download("processed_images_1280x1706.zip", results_dict)