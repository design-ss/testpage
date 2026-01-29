import streamlit as st
from PIL import Image, ImageOps, ImageFilter
import io
import zipfile

# --- 高速化ポイント1: キャッシュを使用して再計算を防ぐ ---
@st.cache_data(show_spinner="画像を処理中...")
def process_image_fast(image_bytes, border_size, border_color='red'):
    # bytesから画像を開く
    image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    
    if border_size == 0:
        return image

    # --- 高速化ポイント2: ループを回さずフィルタでフチを作る ---
    # アルファチャンネル（透明度）だけを取り出す
    alpha = image.split()[3]
    
    # MaxFilterでアルファ値を膨張させる（これがフチになる）
    # size=3で1px、5で2px... のように広がります
    edge_alpha = alpha.filter(ImageFilter.MaxFilter(border_size * 2 + 1))
    
    # フチの色で塗りつぶした画像を作成
    border_img = Image.new("RGBA", image.size, border_color)
    
    # 膨張させたアルファをマスクとして、元の画像の上にフチを合成
    # 元の画像の上にフチを敷く（またはその逆）
    result = Image.composite(border_img, Image.new("RGBA", image.size, (0,0,0,0)), edge_alpha)
    result.alpha_composite(image)
    
    return result

def show_zip_download(file_name, target_dict):
    with io.BytesIO() as buffer:
        with zipfile.ZipFile(buffer, "w") as zip:
            for key, image in target_dict.items():
                img_buffer = io.BytesIO()
                image.save(img_buffer, "PNG")
                zip.writestr(key, img_buffer.getvalue())
        buffer.seek(0)
        st.download_button(label=file_name + "をダウンロード", data=buffer, file_name=file_name, mime='application/zip')

# --- UI設定 ---
st.set_page_config(page_title='消し残しチェック (高速版)')
st.title('消し残しチェック 🚀')
st.write('ピクセルループを廃止し、高速な画像フィルタでゴミを可視化します。')

check_files = st.file_uploader("チェックしたいファイルを選択", type='png', accept_multiple_files=True)

st.markdown('---')
border_width = st.slider('フチの太さ', min_value=0, max_value=10, value=3)

if check_files:
    selected_files = []
    # 画像を並べるカラム設定
    cols = st.columns(2)
    
    for idx, uploaded_file in enumerate(check_files):
        # bytesとして読み込んでキャッシュ効率を上げる
        file_bytes = uploaded_file.getvalue()
        
        # 処理実行
        processed_img = process_image_fast(file_bytes, border_width)
        
        col = cols[idx % 2]
        with col:
            st.image(processed_img, use_container_width=True)
            file_display_name = (uploaded_file.name[:10] + '...') if len(uploaded_file.name) > 10 else uploaded_file.name
            if st.checkbox(f"選択: {file_display_name}", key=f"sel_{uploaded_file.name}"):
                selected_files.append((uploaded_file.name, processed_img))

    if selected_files:
        st.markdown('---')
        if st.button('選択されたファイルをダウンロード'):
            binary_dict = {f"{name.rsplit('.', 1)[0]}_消し残し.png": img for name, img in selected_files}
            show_zip_download("消し残し_checked.zip", binary_dict)
