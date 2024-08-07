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


def getPreviewImage(image, border_size = 1, border_color='red'):
    if image.mode == "P": # 圧縮されたイメージ
        converted_img = image.convert("RGBA")
        img_with_border = ImageOps.expand(converted_img, border = border_size, fill=border_color)
        return img_with_border
    
    img_with_border = ImageOps.expand(image, border = border_size, fill=border_color)
    return img_with_border

def generate_small_images(export_file, attribution_file, vertical_shift, horizontal_shift, scale):
    image = Image.open(export_file)
    attribution = Image.open(attribution_file)

    # 不要な透明部分削除
    image = image.crop(image.getbbox())

    width, height = image.size
    if width < height:
        if width > 100 and height / width > 1.7:
            resized_image = image.resize((70, int(height * 70 / width)))
        else:
            resized_image = image.resize((int(width * 100 / height), 100))
    else:
        if height > 100 and width / height > 1.7:
            resized_image = image.resize((int(width * 70 / height), 70))
        else:
            resized_image = image.resize((100, int(height * 100 / width)))

    # スケール変更
    resized_image = resized_image.resize((int(resized_image.width * scale), int(resized_image.height * scale)))

    image_np = np.array(resized_image)
    alpha = np.array(resized_image.convert('L'))
    cy, cx = ndimage.center_of_mass(alpha)

    # 中心座標
    center_x = int(cx)
    center_y = int(cy)

    # 画像の不透明部分の最下部
    image_y = np.max(np.nonzero(alpha)[0])
    image_x = np.max(np.nonzero(alpha)[0])

    width, height = image.size
    if not (width < height and width > 100 and height / width > 1.7) and not (height < width and height > 100 and width / height > 1.7):
        center_y += vertical_shift
        center_x += -horizontal_shift

    # 100×100
    b_image = resized_image.crop((center_x - 50, center_y - 50, center_x + 50, center_y + 50))

    # b_imageとサンプルフレームを統合する
    b_image.paste(attribution, (0, 0), attribution)

    file_name = export_file.name

    return b_image, file_name

def generate_large_images(export_file):
    image = Image.open(export_file)

    # 960×640
    image = image.resize((960, 640))

    # 不要な透明部分削除
    image = image.crop(image.getbbox())

    image_np = np.array(image)
    alpha = np.array(image.convert('L')) # 2 dimention の grayscale イメージ化して取る。変数名は alpha のままだけで、値は alpha ではなく、grayscale の 2次元 numpy array
    cy, cx = ndimage.center_of_mass(alpha)

    center_x = int(cx)
    center_y = int(cy)

    # 下の座標を取得
    bottom_coord = center_y + 320

    # 画像の不透明部分の最下部の座標を測定（変数image_yとする）
    image_y = np.max(np.nonzero(alpha)[0])

    width, height = image.size

    # （center_y - 50）-　image_yの値により移動
    if bottom_coord - image_y > 15:
        center_y -= (bottom_coord - image_y) - 15
    elif bottom_coord - image_y < 15:
        center_y += 15 - (bottom_coord - image_y)
        
    # 画像を上に移動する
    center_y += 30 # 移動量は適宜調整してください
    
    # 640×640
    left = center_x - 640 // 2
    top = center_y - 640 // 2
    right = left + 640
    bottom = top + 640
    d_image = image.crop((left, top, right, bottom))

    file_name = export_file.name

    return d_image, file_name


st.set_page_config(page_title='mcペット書き出し')

st.title('mcペット書き出し')

st.write('<span style="color:red;">※未圧縮データを使ってください！</span>', unsafe_allow_html=True)
# 書き出しファイル
export_files = st.file_uploader("**ペット**", type='png', accept_multiple_files=True, key="export_files")

# ファイル名を昇順に並び替える　ローカルでは選択順にアップされるが、クラウド上ではなぜかバラバラになるので制御するために昇順に
export_files = sorted(export_files, key=lambda x: x.name)

# 属性ファイル　
st.write('**属性**<span style="color:red; font-size: 80%;">　※必須</span>', unsafe_allow_html=True)
st.write('<span style="font-size: 80%;">属性画像はローカルからアップロードお願いします。トレロに全属性画像のフォルダを記載してます。</span>', unsafe_allow_html=True)
# 属性ファイル
attribution_file = st.file_uploader("選択", type='png', accept_multiple_files=False, key="attribution_file")
# ファイルが選択されていない場合はメッセージを表示する
if not attribution_file:
    st.write('<span style="color:red;">未選択です。属性画像をアップロードしてください。</span>', unsafe_allow_html=True)

# パラメータ調整スライダー
st.write('**50/100調整用** 　　320/640で調整が必要な場合はpsdでの書き出しで対応してください。', unsafe_allow_html=True)
vertical_shift = st.slider('下移動⇔上移動', min_value=-30, max_value=30, value=0)
horizontal_shift = st.slider('左移動⇔右移動', min_value=-30, max_value=30, value=0)
scale = st.slider('縮小⇔拡大', min_value=0.0, max_value=2.0, value=0.7)

# 一括書き出しと個別書き出し
export_button1, export_selected_button1 = st.columns(2)

# 一括書き出し
with export_button1:
    if st.button('一括書き出し'):
        with st.spinner("画像生成中です..."):
            binary_dict.clear() # 初期化

            for export_file in export_files:
                ####################################
                #　50 × 50、100×100　のリサイズ
                ####################################
                b_image, file_name = generate_small_images(export_file, attribution_file, vertical_shift, horizontal_shift, scale)

                # 100 × 100保存
                binary_dict["/100x100/" + file_name] = b_image

                # 50 × 50保存
                b_image = b_image.resize((50, 50))
                binary_dict["/50x50/" + file_name] = b_image

                ####################################
                #　640 × 640、320 ×　320　のリサイズ
                ####################################
                d_image, file_name = generate_large_images(export_file)

                c_image = d_image.resize((320, 320))
                binary_dict["/320x320/" + export_file.name] = c_image
                binary_dict["/640x640/" + export_file.name] = d_image
                
                ####################################
                #　960 × 640　の保存
                ####################################
                # 960×640
                image = Image.open(export_file)
                image = image.resize((960, 640))
                binary_dict["/960x640/" + export_file.name] = image
            time.sleep(3)
        st.markdown(f'<span style="color:red">書き出しが完了しました。ダウンロードボタンが表示されるまでお待ちください。</span>', unsafe_allow_html=True)
        show_zip_download("mc_pet.zip", binary_dict)
    st.write('全てのファイルを書き出します。')
st.markdown('---')

# プレビュー処理
if vertical_shift or horizontal_shift or scale  or preview_button1:
    with st.spinner("プレビュー画像生成中です..."):
        binary_dict.clear() # 初期化
        # 全部プレビュー　enumerate関数リスト型変数から要素を一つずつ取り出し、要素の位置と要素をタプル型変数として返す
        # プレビュー画像にチェックボックスを付ける　個別書き出し用の空のリスト作る
        selected_files = []
        cols = st.columns(4)
        for i, export_file in enumerate(export_files):
            ####################################
            #　50 × 50、100×100　のリサイズ
            ####################################
            b_image, file_name = generate_small_images(export_file, attribution_file, vertical_shift, horizontal_shift, scale)

            # プレビュー画像を表示する
            cols[i % 4].image(getPreviewImage(b_image), use_column_width=False)
            # チェックボックス
            # 名前長いのは省略
            if len(file_name) > 6:
                file_name = file_name[:6] + "..."
            if cols[i % 4].checkbox(file_name, key=f"select_{export_file.name}"):
                selected_files.append(export_file)

# 個別書き出し 空のファイルリストはプレビューの中に
with export_selected_button1:
    if st.button('個別書き出し'):
        with st.spinner("画像生成中です..."):
            binary_dict.clear() # 初期化

            for export_file in selected_files:
                ####################################
                #　50 × 50、100×100　のリサイズ
                ####################################
                b_image, file_name = generate_small_images(export_file, attribution_file, vertical_shift, horizontal_shift, scale)

                # 100 × 100保存
                binary_dict["/100x100/" + file_name] = b_image

                # 50 × 50保存
                a_image = b_image.resize((50, 50))
                binary_dict["/50x50/" + file_name] = a_image


                ####################################
                #　640 × 640、320 ×　320　のリサイズ
                ####################################
                d_image, file_name = generate_large_images(export_file)

                c_image = d_image.resize((320, 320))
                binary_dict["/320x320/" + export_file.name] = c_image
                binary_dict["/640x640/" + export_file.name] = d_image
                
                ####################################
                #　960 × 640　の保存
                ####################################
                # 960×640
                image = Image.open(export_file)
                image = image.resize((960, 640))
                binary_dict["/960x640/" + export_file.name] = image
            time.sleep(3)
        st.markdown(f'<span style="color:red">書き出しが完了しました。ダウンロードボタンが表示されるまでお待ちください。</span>', unsafe_allow_html=True)
        show_zip_download("mc_pet2.zip", binary_dict)
    st.write('チェックを入れたファイルを書き出します。')
