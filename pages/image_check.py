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
    with io.BytesIO() as buffer:
        with zipfile.ZipFile(buffer, "w") as zip:
            for key in target_dict.keys():
                image = target_dict[key]
                img_buffer = io.BytesIO()
                image.save(img_buffer, "PNG")
                zip.writestr(key, img_buffer.getvalue())
        buffer.seek(0)
        st.download_button(label=file_name + "をダウンロード", data=buffer, file_name=file_name, mime='application/zip')

def getPreviewImage(image, border_size=1, border_color='red'):
    if image.mode == "P":
        converted_img = image.convert("RGBA")
        img_with_border = ImageOps.expand(converted_img, border=border_size, fill=border_color)
        return img_with_border
    
    img_with_border = ImageOps.expand(image, border=border_size, fill=border_color)
    return img_with_border

st.set_page_config(page_title='mm書き出し後チェック')
st.title('書き出し後チェック')
st.write('**100×100と640×640の位置、960のフレームの位置を確認できます。** </p>', unsafe_allow_html=True)

files_100 = st.file_uploader("チェックしたい100×100ファイルを選択", type='png', accept_multiple_files=True, key="files_100")
files_640 = st.file_uploader("チェックしたい640×640ファイルを選択", type='png', accept_multiple_files=True, key="files_640")
files_960 = st.file_uploader("チェックしたい960×640ファイルを選択", type='png', accept_multiple_files=True, key="files_960")

with st.spinner("画像生成中です..."):
    binary_dict.clear()
    cols = st.columns(4)
    i = 0
    for file_100 in files_100:
        flame_image = Image.open("./data/100_flame.png")
        file_100 = Image.open(file_100).convert("RGBA")
        file_100.paste(flame_image, (0, 0), flame_image)
        draw = ImageDraw.Draw(file_100)
        draw.line((50, 0, 50, 100), fill="red", width=1)
        draw.line((0, 50, 100, 50), fill="red", width=1)
        preview_image = getPreviewImage(file_100)
        cols[i % 4].image(preview_image, use_container_width=True)
        i += 1

with st.spinner("画像生成中です..."):
    binary_dict.clear()
    cols = st.columns(3)
    i = 0
    for file_640 in files_640:
        back_image = Image.open("./data/mm_640_back.png")
        file_640 = Image.open(file_640).convert("RGBA")
        file_640 = file_640.resize((200, 200))
        final_image = Image.new("RGBA", back_image.size)
        final_image.paste(back_image, (0, 0))
        final_image.paste(file_640, (final_image.width//2 - file_640.width//2, final_image.height//2 - file_640.height//2), file_640)
        up = 8
        draw = ImageDraw.Draw(final_image)
        draw.line((0, final_image.height - up, final_image.width, final_image.height - up), fill="red", width=1)
        draw.line((final_image.width//2, 0, final_image.width//2, final_image.height), fill="red", width=1)
        preview_image = getPreviewImage(final_image)
        cols[i % 3].image(preview_image, use_container_width=True)
        i += 1

with st.spinner("画像生成中です..."):
    binary_dict.clear()
    cols = st.columns(2)
    i = 0
    for file_960 in files_960:
        flame_image = Image.open("./data/960_flame.png")
        flame_image = flame_image.resize((288, 192))
        file_960 = Image.open(file_960).convert("RGBA")
        file_960 = file_960.resize((288, 192))
        file_960.paste(flame_image, (0, 0), flame_image)
        preview_image = getPreviewImage(file_960)
        cols[i % 2].image(preview_image, use_container_width=True)
        i += 1
