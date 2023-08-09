import streamlit as st
import numpy as np
from scipy import ndimage
import zipfile
import io
from PIL import Image, ImageOps, ImageDraw
import time
import base64

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

st.set_page_config(page_title='mmフレーム書き出し')

st.title('mmフレーム書き出し')

st.write('複数のファイルを同時に書き出しする時は、選択順に気を付けてください。\n\n（例）\n\n【アイコン1、アイコン2、アイコン3】と選んだときは\n\n【ギルド1、ギルド2、ギルド3】と対応するフレームを同じ順で選択してください。')


# アイコンフレームファイル指定
export_files_iconframe = st.file_uploader("アイコンフレームファイルを選択", type='png', accept_multiple_files=True, key="export_files_iconframe")

# ギルドフレームファイル指定
export_files_guildframe = st.file_uploader("ギルドフレームファイルを選択", type='png', accept_multiple_files=True, key="export_files_guildframe")

# 一括書き出しと個別書き出し
export_button1, export_selected_button1 = st.columns(2)

# 一括書き出し
with export_button1:
    if st.button('一括書き出し'):
        with st.spinner("画像生成中です..."):
            binary_dict.clear() # 初期化
            
            for ICON in export_files_iconframe:
                ####################################

                #　50 × 50、100 × 100、200 × 200のリサイズ

                ####################################
                # 画像ファイルを開く
                image = Image.open(ICON)

                # 50、100、200にリサイズして保存
                resized_50 = image.resize((50, 50))
                resized_100 = image.resize((100, 100))
                resized_200 = image.resize((200, 200))
                
                # 50 × 50保存
                binary_dict["/frame/icon_frame/50x50/" + ICON.name] = resized_50

                # 100 × 100保存
                binary_dict["/frame/icon_frame/100x100/" + ICON.name] = resized_100

                # 200 × 200保存
                binary_dict["/frame/icon_frame/200x200/" + ICON.name] = resized_200


                ####################################

                #　640 × 640、320 ×　320　のリサイズ

                ####################################

                # 300 × 300 にリサイズしておく
                image = image.resize((300, 300))

                # 透明画像を作っておく
                blank_image = Image.new('RGBA', (640, 640), (0, 0, 0, 0))

                # 元の画像を貼り付け
                left = (blank_image.width - image.width) // 2
                top = int((blank_image.height - image.height) * 0.8)
                blank_image.paste(image, (left, top))
                resized_640 = blank_image
              
                # 320リサイズ
                resized_320 = blank_image.resize((320, 320))

                # 統合した画像の保存
                binary_dict["/frame/icon_frame/320x320/" + ICON.name] = resized_320
                binary_dict["/frame/icon_frame/640x640/" + ICON.name] = resized_640
                
            # ギルドフレーム処理　ループ一応残しておく
            for ICON, GUILD in zip(export_files_iconframe, export_files_guildframe):
                ####################################

                #　50 × 50、100 × 100、224 × 552のリサイズ

                ####################################

                # 画像ファイルを開く
                icon_image = Image.open(ICON)
                guild_image = Image.open(GUILD)

                # アイコンフレームを50、100にリサイズして保存
                resized_50 = icon_image.resize((50, 50))
                binary_dict["/frame/guild_frame/50x50/" + GUILD.name] = resized_50
                resized_100 = icon_image.resize((100, 100))
                binary_dict["/frame/guild_frame/100x100/" + GUILD.name] = resized_100

                # ギルドフレームを保存
                resized_224 = guild_image.resize((224, 552))
                binary_dict["/frame/guild_frame/224x552/" + GUILD.name] = resized_224
                    
            time.sleep(3)
        st.markdown(f'<span style="color:red">書き出しが完了しました。ダウンロードボタンが表示されるまでお待ちください。</span>', unsafe_allow_html=True)
        show_zip_download("mm_frame.zip", binary_dict)
st.markdown('---')


