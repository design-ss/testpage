import streamlit as st
import numpy as np
from scipy import ndimage
import zipfile
import io
from PIL import Image, ImageOps
import time


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

st.set_page_config(page_title='mmペット書き出し')

st.title('mmペット書き出し')

#ファイル選択
export_files = st.file_uploader("ファイルを選択", accept_multiple_files=True)

st.markdown('<br>''<br>', unsafe_allow_html=True)
st.markdown('---')


# パターン1説明
st.write('パターン1：見た目の中心を取って配置します。')

# パターン1
if st.button('パターン1：ペット一括書き出し'):
    with st.spinner("画像生成中です..."):
        binary_dict.clear() # 初期化

        for export_file in export_files:
            ####################################

            #　50 × 50、100×100　のリサイズ

            ####################################
            image = Image.open(export_file)

            # 不要な透明部分削除
            image = image.crop(image.getbbox())

            # メモ（のちほど）
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

            image_np = np.array(resized_image)
            # st.image(image, caption = "croped_image") ###test
            # st.image(resized_image, caption = "resized_image") ###test
            # st.write(f"image_np.shape: {image_np.shape}") # image_np の形(dimention)確認用 ###test
            # alpha = image_np[:, :, 3] # 圧縮 png は ndim(dimention)が２になるためエラーになる
            alpha = np.array(resized_image.convert('L')) # 2 dimention の grayscale イメージ化して取る。変数名は alpha のままだけで、値は alpha ではなく、grayscale の 2次元 numpy array
            cy, cx = ndimage.center_of_mass(alpha)

            # 中心座標
            center_x = int(cx)
            center_y = int(cy)

            bottom_coord = center_y + 50

            # 画像の不透明部分の最下部
            image_y = np.max(np.nonzero(alpha)[0])

            width, height = image.size
            if not (width < height and width > 100 and height / width > 1.7) and not (height < width and height > 100 and width / height > 1.7):
                # （center_y - 50）-　image_yの値により移動
                if bottom_coord - image_y > 6:
                    center_y -= (bottom_coord - image_y) - 6
                elif bottom_coord - image_y < 6:
                    center_y += 6 - (bottom_coord - image_y)

            # 0.8縮小
            resized_image = resized_image.resize((int(resized_image.width * 0.8), int(resized_image.height * 0.8)))
            center_x = int(center_x * 0.8)
            center_y = int(center_y * 0.8)

            # 100×100
            b_image = resized_image.crop((center_x - 50, center_y - 50, center_x + 50, center_y + 50))

            # 100 × 100保存
            # b_image.save(os.path.join(OUTPUT_PATH,'b.png'))
            binary_dict["/100x100/" + export_file.name] = b_image


            # 50 × 50保存
            b_image = b_image.resize((50, 50))
            # b_image.save(os.path.join(OUTPUT_PATH,'a.png'))
            binary_dict["/50x50/" + export_file.name] = b_image

            ####################################

            #　640 × 640、320 ×　320　のリサイズ

            ####################################

            # 画像を読み込む
            image = Image.open(export_file)

            # 960×640
            image = image.resize((960, 640))
            # image.save(os.path.join(OUTPUT_PATH,'e.png'))
            binary_dict["/960x640/" + export_file.name] = image


            # 不要な透明部分削除
            image = image.crop(image.getbbox())

            image_np = np.array(image)
            # alpha = image_np[:, :, 3] # 圧縮 png は ndim(dimention)が２になるためエラーになる
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

            # 640×640
            left = center_x - 640 // 2
            top = center_y - 640 // 2
            right = left + 640
            bottom = top + 640
            d_image = image.crop((left, top, right, bottom))

            # 320×320
            c_image = d_image.resize((320, 320))

            binary_dict["/320x320/" + export_file.name] = c_image
            binary_dict["/640x640/" + export_file.name] = d_image
        time.sleep(3)
    st.markdown(f'<span style="color:red">書き出しが完了しました。下のボタンでダウンロードできます。</span>', unsafe_allow_html=True)
    show_zip_download("output1.zip", binary_dict)


    
st.markdown('<br>', unsafe_allow_html=True)
st.markdown('---')

from PIL import ImageDraw

# パターン3の説明文
st.write('パターン3：1枚ずつ調整できます。スライダーを動かすとプレビューが出ます。')

horizontal_shift = st.slider('数字を増やすほど左に移動します。', min_value=-30, max_value=30, value=0)
vertical_shift = st.slider('数字を増やすほど上に移動します。', min_value=-30, max_value=30, value=0)
scale = st.slider('数字を増やすほど拡大されます。', min_value=0.0, max_value=2.0, value=0.7)

# ボタンを追加
preview_button = st.button('パターン3：プレビュー')

# スライダーの値が変更されたときだけ処理を実行する
if horizontal_shift or vertical_shift or scale != 0.7 or preview_button:
    if not export_files:
        st.error("エラー: export_filesが空です。")
    else:
        # パターン3の処理実行
        with st.spinner("画像生成中です..."):
            binary_dict.clear() # 初期化

            # 最初の1枚だけプレビューする
            export_file = export_files[0]

            ####################################

            #　50 × 50、100×100　のリサイズ

            ####################################
            image = Image.open(export_file)
            image = image.crop(image.getbbox())
            width, height = image.size

            # 短い辺を100に合わせるようにリサイズ
            if width < height:
                resized_image = image.resize((int(width * 100 / height), 100))
            else:
                resized_image = image.resize((100, int(height * 100 / width)))

            # 画像をちょっと縮小　ユーザーが弄れる
            resized_image = resized_image.resize((int(resized_image.width * scale), int(resized_image.height * scale)))


            # 画像を中央に合わせて切り抜く
            left = (resized_image.width - 100) // 2 + horizontal_shift
            top = (resized_image.height - 100) // 2 + vertical_shift
            right = left + 100
            bottom = top + 100
            b_image = resized_image.crop((left, top, right, bottom))

            # 中心線を描画する
            draw = ImageDraw.Draw(b_image)
            draw.line((50, 0, 50, 100), fill="red", width=1)
            draw.line((0, 50, 100, 50), fill="red", width=1)

            # プレビュー画像を表示する
            st.image(getPreviewImage(b_image), caption='100×100のプレビュー', use_column_width=False)

# パターン3のボタンクリックで処理実行
if st.button('パターン3：ペット一括書き出し'):
    with st.spinner("画像生成中です..."):
        binary_dict.clear() # 初期化

        for export_file in export_files:
            ####################################

            #　50 × 50、100×100　のリサイズ

            ####################################
            image = Image.open(export_file)
            image = image.crop(image.getbbox())
            width, height = image.size

            # 短い辺を100に合わせるようにリサイズ
            if width < height:
                resized_image = image.resize((int(width * 100 / height), 100))
            else:
                resized_image = image.resize((100, int(height * 100 / width)))

            # 画像をちょっと縮小　ユーザーが弄れる
            resized_image = resized_image.resize((int(resized_image.width * scale), int(resized_image.height * scale)))


            # 画像を中央に合わせて切り抜く
            left = (resized_image.width - 100) // 2 + horizontal_shift
            top = (resized_image.height - 100) // 2 + vertical_shift
            right = left + 100
            bottom = top + 100
            b_image = resized_image.crop((left, top, right, bottom))


            # 100×100保存
            # b_image.save(os.path.join(OUTPUT_PATH,'b.png'))
            binary_dict["/100x100/" + export_file.name] = b_image

            # 50×50保存
            b_image = b_image.resize((50, 50))
            # b_image.save(os.path.join(OUTPUT_PATH,'a.png'))
            binary_dict["/50x50/" + export_file.name] = b_image

                    
            ####################################

            #　640 × 640、320 ×　320　のリサイズ

            ####################################

            # 画像を読み込む
            image = Image.open(export_file)

            # 960×640保存
            image = image.resize((960, 640))
            # image.save(os.path.join(OUTPUT_PATH,'e.png'))
            binary_dict["/960x640/" + export_file.name] = image

            # 不要な透明部分削除
            image = image.crop(image.getbbox())

            image_np = np.array(image)
            # alpha = image_np[:, :, 3] # 圧縮 png は ndim(dimention)が２になるためエラーになる
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

            # 640×640
            left = center_x - 640 // 2
            top = center_y - 640 // 2
            right = left + 640
            bottom = top + 640
            d_image = image.crop((left, top, right, bottom))

            # 320×320
            c_image = d_image.resize((320, 320))

            binary_dict["/320x320/" + export_file.name] = c_image
            binary_dict["/640x640/" + export_file.name] = d_image

        time.sleep(3)
    st.markdown(f'<span style="color:red">書き出しが完了しました。下のボタンでダウンロードできます。</span>', unsafe_allow_html=True)
    show_zip_download("output3.zip", binary_dict)
