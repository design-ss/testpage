import streamlit as st
import numpy as np
from scipy import ndimage
import zipfile
import io
from PIL import Image, ImageOps, ImageDraw
import time
import base64
import cv2

binary_dict = dict()

def show_zip_download(file_name, target_dict):
    # st.write(target_dict)
    with io.BytesIO() as buffer:
        with zipfile.ZipFile(buffer, "w") as zip:
            for key in target_dict.keys():
                image = target_dict[key]
                img_buffer = io.BytesIO()
                image.save(img_buffer, "PNG")
                zip.writestr(key, img_buffer.getvalue())
        buffer.seek(0)
        st.download_button(label=file_name + "をダウンロード", data=buffer, file_name=file_name, mime='application/zip')


def getPreviewImage(image, border_size = 1, border_color='red'):
    if image.mode == "P": # 圧縮されたイメージ
        converted_img = image.convert("RGBA")
        img_with_border = ImageOps.expand(converted_img, border = border_size, fill=border_color)
        return img_with_border
    
    img_with_border = ImageOps.expand(image, border = border_size, fill=border_color)
    return img_with_border


st.set_page_config(page_title='mm書き出し後チェック')

st.title('mm書き出し後チェック')

st.write('**mm100×100と640×640の位置を確認できます。** </p>', unsafe_allow_html=True)

# 100ファイル指定
files_100 = st.file_uploader("チェックしたい100×100ファイルを選択", type='png', accept_multiple_files=True, key="files_100")

# 640ファイル指定
files_640 = st.file_uploader("チェックしたい640×640ファイルを選択", type='png', accept_multiple_files=True, key="files_640")

# 100プレビュー処理
with st.spinner("画像生成中です..."):
    binary_dict.clear() # 初期化
    cols = st.columns(4)
    i = 0
    # 前面（top）と背面（bottom）の画像を一緒に処理する
    for file_100 in files_100:
        ####################################

        #　100画像処理

        ####################################
        # サンプルフレームを読み込む
        flame_image = Image.open("./data/100_flame.png")
        file_100 = Image.open(file_100).convert("RGBA")
        
        # b_imageとサンプルフレームを統合する
        file_100.paste(flame_image, (0, 0), flame_image)

        # 中心線を描画する
        draw = ImageDraw.Draw(file_100)
        draw.line((50, 0, 50, 100), fill="red", width=1)
        draw.line((0, 50, 100, 50), fill="red", width=1)

        # プレビュー画像を表示する
        preview_image = getPreviewImage(file_100)
        cols[i % 4].image(preview_image, use_column_width=False)

        # # チェックボックス
        # if cols[i % 4].checkbox("選択", key=f"select_{file_name}"):
        #     selected_files.append((file_front, file_center, file_back))
        i += 1


# 640プレビュー処理
with st.spinner("画像生成中です..."):
    binary_dict.clear() # 初期化
    cols = st.columns(3)
    i = 0

    # 前面（top）と背面（bottom）の画像を一緒に処理する
    for file_640 in files_640:
        ####################################

        #　640画像処理

        ####################################
        
        # 背景を読み込む
        back_image = Image.open("./data/mm_640_back.png")

        # 200×200
        file_640= Image.open(file_640).convert("RGBA")
        file_640 = file_640.resize((200, 200))

        # files_640と背景を統合する
        final_image = Image.new("RGBA", back_image.size)
        final_image.paste(back_image, (0, 0))
        final_image.paste(file_640, (final_image.width//2 - file_640.width//2, final_image.height//2 - file_640.height//2), file_640)

        # 中心線を描画する
        up = 8
        draw = ImageDraw.Draw(final_image)
        draw.line((0, final_image.height- up, final_image.width, final_image.height- up), fill="red", width=1)
        draw.line((final_image.width//2, 0, final_image.width//2, final_image.height), fill="red", width=1)

        # プレビュー画像を表示する
        preview_image = getPreviewImage(final_image)
        cols[i % 3].image(preview_image, use_column_width=False)

        # # チェックボックス
        # if cols[i % 3].checkbox("選択", key=f"select_{file_640.filename}"):
            # selected_files.append(file_640.filename)
        i += 1
