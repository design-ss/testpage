import streamlit as st
from PIL import Image, ImageOps
import io

st.set_page_config(page_title='装着チェック')

st.title('装着チェック')

st.markdown('### ファイルをアップロード')

# アップローダーを横に3つずつ並べる
columns = st.columns(3)
uploaded_files = []

for i in range(6):
    with columns[i % 3]:
        uploaded_file = st.file_uploader(f"装着ファイル{i+1}", type='png', key=f"check_file{i+1}")
        if uploaded_file:
            uploaded_files.append(uploaded_file)

st.markdown('---')

if uploaded_files:
    images = [Image.open(file).convert("RGBA") for file in uploaded_files]
    
    # 最大の画像のサイズを基にキャンバスのサイズを計算
    max_width = max(image.width for image in images)
    max_height = max(image.height for image in images)
    
    # 透明な背景を作成
    combined_image = Image.new("RGBA", (max_width, max_height), (255, 255, 255, 0))
    
    # 画像を順番に背景に貼り付ける（逆順にしてcheck_file1が一番上になるようにする）
    for image in reversed(images):
        combined_image.paste(image, (0, 0), image)
    
    # プレビュー表示
    st.image(combined_image, caption='結合画像のプレビュー')

    st.markdown('### 結果の画像')
    result_buffer = io.BytesIO()
    combined_image.save(result_buffer, format="PNG")
    result_buffer.seek(0)
    
    st.download_button(
        label="結合画像をダウンロード",
        data=result_buffer,
        file_name="combined_image.png",
        mime="image/png"
    )
