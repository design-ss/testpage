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

#　100 × 100、50 ×　50　のリサイズ関数
def generate_small_images(export_file_front, export_file_back, attribution_file):
    
    # 画像を読み込む
    if export_file_front:
        image_front = Image.open(export_file_front)
        image_front = image_front.resize((960, 640))
    else:
        image_front = Image.new("RGBA", (960, 640), (0, 0, 0, 0))

    if export_file_back:
        image_back = Image.open(export_file_back)
        image_back = image_back.resize((960, 640))
    else:
        image_back = Image.new("RGBA", (960, 640), (0, 0, 0, 0))

    attribution = Image.open(attribution_file)

    # 統合する
    image = Image.alpha_composite(image_back, image_front)

    # 不要な透明画素を除去
    image = image.crop(image.getbbox())

    # 画像の幅と高さを取得
    width, height = image.size

    # 短い辺を100に合わせるようにリサイズ
    if width < height:
        resized_image = image.resize((int(width * 100 / height), 100))
    else:
        resized_image = image.resize((100, int(height * 100 / width)))

    # 画像をちょっと縮小
    resized_image = resized_image.resize((int(resized_image.width * 1), int(resized_image.height * 1)))

    # 画像を中央に合わせて切り抜く
    left = (resized_image.width - 100) // 2
    front = (resized_image.height - 100) // 2
    right = left + 100
    back = front + 100
    b_image = resized_image.crop((left, front, right, back))

    # 統合する
    b_image = Image.alpha_composite(b_image, attribution)

    # ファイル名を設定する
    if export_file_front:
        file_name = export_file_front.name
    else:
        file_name = export_file_back.name

    return b_image, file_name

#　640 × 640、320 ×　320　のリサイズ関数
def generate_large_images(export_file_front, export_file_back):
    # 画像を読み込む
    if export_file_front:
        image_front = Image.open(export_file_front)
        image_front = image_front.resize((960, 640))
    else:
        image_front = Image.new("RGBA", (960, 640), (0, 0, 0, 0))

    if export_file_back:
        image_back = Image.open(export_file_back)
        image_back = image_back.resize((960, 640))
    else:
        image_back = Image.new("RGBA", (960, 640), (0, 0, 0, 0))

    # 統合する
    image = Image.alpha_composite(image_back, image_front)

    # 不要な透明画素を除去
    image = image.crop(image.getbbox())

    # 画像の幅と高さを取得
    width, height = image.size

    # 短い辺を640に合わせるようにリサイズ
    if width < height:
        resized_image = image.resize((int(width * 640 / height), 640))
    else:
        resized_image = image.resize((640, int(height * 640 / width)))

    # 画像をちょっと縮小
    resized_image = resized_image.resize((int(resized_image.width * 1), int(resized_image.height * 1)))

    # 画像を下に移動
    left = (resized_image.width - 640) / 2
    front = resized_image.height - 640 * 0.85
    right = left + 640
    back = front + 640
    d_image = resized_image.crop((left, front, right, back))

    # ファイル名を設定する
    if export_file_front:
        file_name = export_file_front.name
    else:
        file_name = export_file_back.name

    return d_image, file_name

st.set_page_config(page_title='mcオーラ書き出し')
st.title('mcオーラ書き出し')
st.write('<span style="color:red;">※未圧縮データを使ってください！</span>', unsafe_allow_html=True)
# オーラ前ファイル指定
export_files_front = st.file_uploader("**オーラ前**", type='png', accept_multiple_files=True, key="export_files_front")

# オーラ後ろファイル指定
export_files_back = st.file_uploader("**オーラ後ろ**", type='png', accept_multiple_files=True, key="export_files_back")

# 属性ファイル　
st.write('**属性**<span style="color:red; font-size: 80%;">　※必須</span>', unsafe_allow_html=True)
st.write('<span style="font-size: 80%;">属性画像はローカルからアップロードお願いします。トレロに全属性画像のフォルダを記載してます。</span>', unsafe_allow_html=True)

attribution_file = st.file_uploader("選択", type='png', accept_multiple_files=False, key="attribution_file")
# ファイルが選択されていない場合はメッセージを表示する
if not attribution_file:
    st.write('<span style="color:red;">未選択です。属性画像をアップロードしてください。</span>', unsafe_allow_html=True)


# ファイル名を昇順に並び替える　ローカルでは選択順にアップされるが、クラウド上ではなぜかバラバラになるので制御するために昇順に
export_files_front = sorted(export_files_front, key=lambda x: x.name)
export_files_back = sorted(export_files_back, key=lambda x: x.name)

# パターン1説明
st.write('100/50の見た目の中心を取って配置します。')


# # パラメータ調整スライダー オーラ調整しなくてもいけそうなので不要？
# vertical_shift = st.slider('下移動⇔上移動', min_value=-30, max_value=30, value=0)
# horizontal_shift = st.slider('左移動⇔右移動', min_value=-30, max_value=30, value=0)
# scale = st.slider('縮小⇔拡大', min_value=0.0, max_value=2.0, value=0.7)

# 一括書き出しと個別書き出し
export_button1, export_selected_button1 = st.columns(2)

# 一括書き出し
with export_button1:
    if st.button('一括書き出し'):
        with st.spinner("画像生成中です..."):
            binary_dict.clear() # 初期化
             # 前ファイルと後ろファイル　
            if not export_files_front:
                export_files_front = [None] * len(export_files_back)
            if not export_files_back:
                export_files_back = [None] * len(export_files_front)
            export_files = list(zip(export_files_front, export_files_back))
            
            for export_file_front, export_file_back in export_files:
                ####################################
                #　100 × 100、50 ×　50　のリサイズ
                ####################################
                b_image, file_name = generate_small_images(export_file_front, export_file_back, attribution_file)

                # 100 × 100保存
                binary_dict["/100x100/" + file_name] = b_image

                # 50 × 50保存
                a_image = b_image.resize((50, 50))
                binary_dict["/50x50/" + file_name] = a_image


                ####################################
                #　640 × 640、320 ×　320　のリサイズ
                ####################################
                d_image, file_name = generate_large_images(export_file_front, export_file_back)

                # 640 × 640保存
                binary_dict["/640x640/" + file_name] = d_image

                # 320 × 320保存
                c_image = d_image.resize((320, 320))
                binary_dict["/320x320/" + file_name] = c_image

                ####################################
                #　960 × 640　の保存
                ####################################
                # 画像を読み込む
                if export_file_front:
                    image_front = Image.open(export_file_front)
                    image_front = image_front.resize((960, 640))
                    binary_dict["/960x640/" + export_file_front.name] = image_front
                if export_file_back:
                    image_back = Image.open(export_file_back)
                    image_back = image_back.resize((960, 640))
                    binary_dict["/960x640/" + export_file_back.name] = image_back

            time.sleep(3)
        st.markdown(f'<span style="color:red">書き出しが完了しました。ダウンロードボタンが表示されるまでお待ちください。</span>', unsafe_allow_html=True)
        show_zip_download("mc_aura.zip", binary_dict)
    st.write('全てのファイルを書き出します。')
st.markdown('---')


# パターン1のプレビュー処理
with st.spinner("プレビュー画像生成中です..."):
    binary_dict.clear()  # 初期化
    if not export_files_front:
        export_files_front = [None] * len(export_files_back)
    if not export_files_back:
        export_files_back = [None] * len(export_files_front)
    export_files = list(zip(export_files_front, export_files_back))

    # プレビュー画像にチェックボックスを付ける　個別書き出し用の空のリスト作る
    selected_files = []
    cols = st.columns(4)
    for i, (export_file_front, export_file_back) in enumerate(export_files):
        preview_image, file_name = generate_small_images(export_file_front, export_file_back, attribution_file)

        # プレビュー画像を表示する
        cols[i % 4].image(getPreviewImage(preview_image), use_column_width=False)
        
        if cols[i % 4].checkbox(file_name, key=f"select_{file_name}"):
            selected_files.append((export_file_front, export_file_back))

# 個別書き出し 空のファイルリストはプレビューの中に
with export_selected_button1:
    if st.button('個別書き出し'):
        with st.spinner("画像生成中です..."):
            binary_dict.clear() # 初期化
             # 前ファイルと後ろファイルを結合
            if not export_files_front:
                export_files_front = [None] * len(export_files_back)
            if not export_files_back:
                export_files_back = [None] * len(export_files_front)
            export_files = list(zip(export_files_front, export_files_back))

            for export_file_front, export_file_back in selected_files:
                
                ####################################
                #　100 × 100、50 ×　50　のリサイズ
                ####################################
                b_image, file_name = generate_small_images(export_file_front, export_file_back, attribution_file)
                # 100 × 100保存
                binary_dict["/100x100/" + file_name] = b_image

                # 50 × 50保存
                b_image = b_image.resize((50, 50))
                binary_dict["/50x50/" + file_name] = b_image

                ####################################
                #　640 × 640、320 ×　320　のリサイズ
                ####################################
                d_image, file_name = generate_large_images(export_file_front, export_file_back)

                # 統合した画像の保存（
                binary_dict["/640x640/" + file_name] = d_image
      
                c_image = d_image.resize((320, 320))
                binary_dict["/320x320/" + file_name] = c_image

                ####################################
                #　960 × 640　の保存
                ####################################
                # 画像を読み込む
                if export_file_front:
                    image_front = Image.open(export_file_front)
                    image_front = image_front.resize((960, 640))
                    binary_dict["/960x640/" + export_file_front.name] = image_front
                if export_file_back:
                    image_back = Image.open(export_file_back)
                    image_back = image_back.resize((960, 640))
                    binary_dict["/960x640/" + export_file_back.name] = image_back

            time.sleep(3)
        st.markdown(f'<span style="color:red">書き出しが完了しました。ダウンロードボタンが表示されるまでお待ちください。</span>', unsafe_allow_html=True)
        show_zip_download("mc_aura2.zip", binary_dict)
    st.write('チェックを入れたファイルを書き出します。')
