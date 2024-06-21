import streamlit as st
import numpy as np
from scipy import ndimage
import zipfile
import io
from PIL import Image, ImageOps, ImageDraw
import time
import base64
import cv2
from scipy import ndimage


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


def generate_small_images(file_front, file_center, file_back, playmark_files, mask_file, scale_100, horizontal_shift, vertical_shift):
    # 画像を読み込む
    if file_front:
        image_front = Image.open(file_front).convert("RGBA")
    else:
        image_front = Image.new("RGBA", (960, 640), (0, 0, 0, 0))

    if file_center:
        image_center = Image.open(file_center).convert("RGBA")
    else:
        image_center = Image.new("RGBA", (960, 640), (0, 0, 0, 0))

    if file_back:
        image_back = Image.open(file_back).convert("RGBA")
    else:
        image_back = Image.new("RGBA", (960, 640), (0, 0, 0, 0))

    # 再生マークがあったら読み込む
    if playmark_files:
        playmark_image = Image.open(playmark_files[0]).convert("RGBA")

    # 顔輪郭マスクがあったら image_centerを書き換える
    if mask_file:
        mask_image = Image.open(mask_file[0]).convert('L')
        image = np.array(image_center)
        mask = np.array(mask_image)
        image[:, :, 3] = (1.0 - mask / 255.0) * image[:, :, 3]
        image_center = Image.fromarray(image)

    # 統合
    combined_center_back = Image.alpha_composite(image_back.convert("RGBA"), image_center.convert("RGBA"))
    final_image = Image.alpha_composite(combined_center_back, image_front.convert("RGBA"))

    # 縮小する
    scale = scale_100
    width, height = final_image.size
    new_width, new_height = int(width * scale), int(height * scale)
    x1, y1 = width // 2, height // 2
    x2, y2 = int(x1 * scale), int(y1 * scale)
    size_after = (int(width * scale), int(height * scale))
    image_np = np.array(final_image)
    resized_img = cv2.resize(image_np, dsize=size_after)
    deltax = (width / 2 - x1) - (resized_img.shape[1] / 2 - x2)
    deltay = (height / 2 - y1) - (resized_img.shape[0] / 2 - y2)
    framey = int(height * scale * 2)
    framex = int(width * scale * 2)
    finalimg_np = np.zeros((framey, framex, 4), np.uint8)
    finalimg_np[int(-deltay + framey / 2 - resized_img.shape[0] / 2):int(-deltay + framey / 2 + resized_img.shape[0] / 2),
                int(-deltax + framex / 2 - resized_img.shape[1] / 2):int(-deltax + framex / 2 + resized_img.shape[1] / 2)] = resized_img
    finalimg_np = finalimg_np[int(finalimg_np.shape[0] / 2 - height / 2):int(finalimg_np.shape[0] / 2 + height / 2),
                              int(finalimg_np.shape[1] / 2 - width / 2):int(finalimg_np.shape[1] / 2 + width / 2)]
    final_image = Image.fromarray(finalimg_np)

    # リサイズしてトリミング
    final_image = final_image.crop((335 - horizontal_shift, 0 + vertical_shift, 625 - horizontal_shift, 640 + vertical_shift))
    final_image = final_image.resize((290, 640), Image.LANCZOS)

    # 正方形にする
    start_y = 640 - 290 - 75
    end_y = start_y + 290
    b_image = final_image.crop((0, start_y, 290, end_y))

    # 縮小する
    b_image.thumbnail((100, 100), Image.LANCZOS)

    # 再生マークがあったら統合する
    if playmark_files:
        b_image = Image.alpha_composite(b_image.convert("RGBA"), playmark_image.convert("RGBA"))

    # ファイル名
    if file_front:
        file_name = file_front.name
    elif file_center:
        file_name = file_center.name
    elif file_back:
        file_name = file_back.name

    return b_image, file_name

def generate_large_images(file_front, file_center, file_back, mask_file, binary_dict):
    # 画像を読み込む
    if file_front:
        image_front = Image.open(file_front).convert("RGBA")
    else:
        image_front = Image.new("RGBA", (960, 640), (0, 0, 0, 0))

    if file_center:
        image_center = Image.open(file_center).convert("RGBA")
    else:
        image_center = Image.new("RGBA", (960, 640), (0, 0, 0, 0))

    if file_back:
        image_back = Image.open(file_back).convert("RGBA")
    else:
        image_back = Image.new("RGBA", (960, 640), (0, 0, 0, 0))

    # 顔輪郭マスクがあったら image_centerを書き換える
    if mask_file:
        mask_image = Image.open(mask_file[0]).convert('L')
        image = np.array(image_center)
        mask = np.array(mask_image)
        image[:, :, 3] = (1.0 - mask / 255.0) * image[:, :, 3]
        image_center = Image.fromarray(image)

    # 統合する
    image = Image.alpha_composite(image_back.convert("RGBA"), image_center.convert("RGBA"))
    image = Image.alpha_composite(image.convert("RGBA"), image_front.convert("RGBA"))

    # 画像サイズ調整
    width, height = image.size
    if width < height:
        if width > 640:
            image = image.resize((448, int(height * 448 / width)))
        else:
            image = image.resize((int(width * 640 / height), 640))
    else:
        if height > 640:
            image = image.resize((int(width * 448 / height), 448))
        else:
            image = image.resize((640, int(height * 640 / width)))

    # スケール変更 もしプレビュー増やせたらこれも使うので残しておく
    scale = 1
    image = image.resize((int(image.width * scale), int(image.height * scale)))

    # 高さが足りない場合、足りない分を上に足す
    width, height = image.size
    if height < 640:
        new_image = Image.new('RGBA', (width, 640), (0, 0, 0, 0))
        new_image.paste(image, (0, 640 - height))
        image = new_image

    # 幅が足りない場合、足りない分を両方に足す
    if width < 640:
        new_image = Image.new('RGBA', (640, 640), (0, 0, 0, 0))
        new_image.paste(image, ((640 - width) // 2, 0))
        image = new_image

    # 640×640の画像を生成
    d_image = image

    # ファイル名を設定する
    if file_front:
        file_name = file_front.name
    elif file_center:
        file_name = file_center.name
    elif file_back:
        file_name = file_back.name

    return d_image, file_name


st.set_page_config(page_title='mm体書き出し')

st.title('mm見た目体書き出し')

st.write('**通常素体のポーズはこちらのアプリでは書き出しできません。default bodyを使ってください。** ', unsafe_allow_html=True)

st.write('**ID付与前に複数構造のものを書き出す場合はお気をつけください。** <p style="font-size: 80%;">ファイルは選択順に関係なく「昇順」でアップされます。<br> そのため、適切に前後パーツを組み合わせるために、ファイル名の先頭に3桁の数字を付けるなどで順番を制御してください。<br>（例）<br>前体：「001.前_目玉A」「002.前_目玉B」「003.前_目玉C」<br>後ろ体：「004.後ろ_目玉A」「005.後ろ_目玉B」「006.後ろ_目玉C」<br> とABCそれぞれの順番が正しくなるように数字を付けてください。</p>', unsafe_allow_html=True)
st.write('<span style="color:red;">※未圧縮データを使ってください！</span>', unsafe_allow_html=True)
col1, col2 , col3 = st.columns(3)

# 前ファイル指定
with col1:
    export_files_front = st.file_uploader("**体_前ファイル**", type='png', accept_multiple_files=True, key="export_files_front")

# 中ファイル指定
with col2:
    export_files_center = st.file_uploader("**体_中ファイル**", type='png', accept_multiple_files=True, key="export_files_center")

# 後ろファイル指定
with col3:
    export_files_back = st.file_uploader("**体_後ろファイル**", type='png', accept_multiple_files=True, key="export_files_back")
    
# ファイル名を昇順に並び替える　ローカルでは選択順にアップされるが、クラウド上ではなぜかバラバラになるので制御するために昇順に
export_files_front = sorted(export_files_front, key=lambda x: x.name)
export_files_center = sorted(export_files_center, key=lambda x: x.name)
export_files_back = sorted(export_files_back, key=lambda x: x.name)

col4 , col5 = st.columns(2)

with col4:
    st.write('**オマケ：顔輪郭マスク用<br>（なくても書き出しできます）** <p style="font-size: 80%;">「体_中」を首まで描いたときに「マスク用_顔シルエット.png」をアップロードして使用してください。<br>顔の輪郭部分を消すことができます。<br></p>', unsafe_allow_html=True)
    # マスク用
    mask_file = st.file_uploader("選択", type='png', accept_multiple_files=True, key="mask_file")

with col5:
    st.write('**再生マーク**<p style="font-size: 80%;">'
         'モーションアバター書き出しの際は、再生マークをアップロードしてください。<br>'
        '50/100に再生マークを重ねます。'
        '</p>', 
        unsafe_allow_html=True)
    # 100×100再生マーク
    playmark_files = st.file_uploader("選択", type='png', accept_multiple_files=True, key="playmark_file")
    
    
st.markdown('---')
st.write('**50/100調整用** 　　320/640で調整が必要な場合はpsdでの書き出しで対応してください。', unsafe_allow_html=True)
# パラメータ調整スライダー 
vertical_shift = st.slider('下移動⇔上移動', min_value=-150, max_value=150,value=0)
horizontal_shift = st.slider('左移動⇔右移動', min_value=-150, max_value=150,value=0)
scale_100 = st.slider('縮小⇔拡大　デフォルトは0.96', min_value=0.5, max_value=1.5, value=0.96)


# 一括書き出しと個別書き出し
export_button1, export_selected_button1 = st.columns(2)

# 一括書き出し
with export_button1:
    if st.button('一括書き出し'):
        with st.spinner("画像生成中です..."):
            binary_dict.clear() # 初期化
            
            # リスト数調整
            max_length = max(len(export_files_front), len(export_files_center), len(export_files_back))
            export_files_front += [None] * (max_length - len(export_files_front))
            export_files_center += [None] * (max_length - len(export_files_center))
            export_files_back += [None] * (max_length - len(export_files_back))

            for file_front, file_center, file_back in zip(export_files_front, export_files_center, export_files_back):
                # ####################################

                #　50 × 50、100 × 100　のリサイズ

                # ####################################
                b_image, file_name = generate_small_images(file_front, file_center, file_back, playmark_files, mask_file, scale_100, horizontal_shift, vertical_shift)

                # 100 x 100
                binary_dict["/100x100/" + file_name] = b_image

                # 50 x 50
                b_image_50 = b_image.resize((50, 50))
                binary_dict["/50x50/" + file_name] = b_image_50

                ####################################

                #　640 × 640、320 ×　320　のリサイズ

                ####################################
                d_image, file_name = generate_large_images(file_front, file_center, file_back, mask_file, binary_dict)

                # 640 x 640 
                binary_dict["/640x640/" + file_name] = d_image

                # 320 x 320
                c_image = d_image.resize((320, 320))
                binary_dict["/320x320/" + file_name] = c_image
                
                ####################################
                
                #　960 × 640のリサイズ

                ###################################
                # 画像を読み込む
                if file_front:
                    image_front = Image.open(file_front).convert("RGBA")
                else:
                    image_front = Image.new("RGBA", (960, 640), (0, 0, 0, 0))

                if file_center:
                    image_center = Image.open(file_center).convert("RGBA")
                else:
                    image_center = Image.new("RGBA", (960, 640), (0, 0, 0, 0))

                if file_back:
                    image_back = Image.open(file_back).convert("RGBA")
                else:
                    image_back = Image.new("RGBA", (960, 640), (0, 0, 0, 0))

                # 顔輪郭マスクがあったら image_centerを書き換える
                if mask_file:
                    mask_image = Image.open(mask_file[0]).convert('L')
                    image = np.array(image_center)
                    mask = np.array(mask_image)
                    image[:, :, 3] = (1.0 - mask / 255.0) * image[:, :, 3]
                    image_center = Image.fromarray(image)

                if file_front:
                    image_front = image_front.resize((960, 640))
                    binary_dict["/960x640/" + file_front.name] = image_front
                if file_center:
                    image_center = image_center.resize((960, 640))
                    binary_dict["/960x640/" + file_center.name] = image_center
                if file_back and file_back.name not in ['素体_男.png', '素体_女.png']:
                    image_back = image_back.resize((960, 640))
                    binary_dict["/960x640/" + file_back.name] = image_back
                        
                
            time.sleep(3)
        st.markdown(f'<span style="color:red">書き出しが完了しました。ダウンロードボタンが表示されるまでお待ちください。</span>', unsafe_allow_html=True)
        show_zip_download("mm_body.zip", binary_dict)
    st.write('全てのファイルを書き出します。')
st.markdown('---')



# 100プレビュー処理
# if vertical_shift or horizontal_shift or scale  or preview_button1:
with st.spinner("画像生成中です..."):
    binary_dict.clear() # 初期化
    # 個別書き出し用空のファイルリスト
    selected_files = []
    cols = st.columns(4)
    i = 0
    # リスト数調整
    max_length = max(len(export_files_front), len(export_files_center), len(export_files_back))
    export_files_front += [None] * (max_length - len(export_files_front))
    export_files_center += [None] * (max_length - len(export_files_center))
    export_files_back += [None] * (max_length - len(export_files_back))

    for file_front, file_center, file_back in zip(export_files_front, export_files_center, export_files_back):
        ####################################

        #　50 × 50、100 × 100　のリサイズ

        ####################################
        b_image, file_name = generate_small_images(file_front, file_center, file_back, playmark_files, mask_file, scale_100, horizontal_shift, vertical_shift)
            
        # サンプルフレームを読み込む
        flame_image = Image.open("./data/100_flame.png")
        
        # b_imageとサンプルフレームを統合する
        b_image.paste(flame_image, (0, 0), flame_image)

        # 中心線を描画する
        draw = ImageDraw.Draw(b_image)
        draw.line((50, 0, 50, 100), fill="red", width=1)
        draw.line((0, 50, 100, 50), fill="red", width=1)

        # プレビュー画像を表示する
        preview_image = getPreviewImage(b_image)
        cols[i % 4].image(preview_image, use_column_width=False)

        # チェックボックス
        if cols[i % 4].checkbox("選択", key=f"select_{file_name}"):
            selected_files.append((file_front, file_center, file_back))
        
        i += 1

# 個別書き出し 空のファイルリストはプレビューの中に
with export_selected_button1:
    if st.button('個別書き出し'):
        with st.spinner("画像生成中です..."):
            binary_dict.clear() # 初期化
             # リスト数調整
            max_length = max(len(export_files_front), len(export_files_center), len(export_files_back))
            export_files_front += [None] * (max_length - len(export_files_front))
            export_files_center += [None] * (max_length - len(export_files_center))
            export_files_back += [None] * (max_length - len(export_files_back))

            for file_front, file_center, file_back in selected_files:
                # ####################################

                #　50 × 50、100 × 100　のリサイズ

                # ####################################
                # 画像を読み込む
                b_image, file_name = generate_small_images(file_front, file_center, file_back, playmark_files, mask_file, scale_100, horizontal_shift, vertical_shift)

                # 100 x 100
                binary_dict["/100x100/" + file_name] = b_image

                # 50 x 50
                b_image_50 = b_image.resize((50, 50))
                binary_dict["/50x50/" + file_name] = b_image_50


                ####################################

                #　640 × 640、320 ×　320　のリサイズ

                ####################################
                d_image, file_name = generate_large_images(file_front, file_center, file_back, mask_file,  binary_dict)

                # 640 x 640
                binary_dict["/640x640/" + file_name] = d_image

                # 320 x 320
                c_image = d_image.resize((320, 320))
                binary_dict["/320x320/" + file_name] = c_image
                
                ####################################
                
                #　960 × 640のリサイズ

                ###################################

                if file_front:
                    image_front = Image.open(file_front).convert("RGBA")
                else:
                    image_front = Image.new("RGBA", (960, 640), (0, 0, 0, 0))

                if file_center:
                    image_center = Image.open(file_center).convert("RGBA")
                else:
                    image_center = Image.new("RGBA", (960, 640), (0, 0, 0, 0))

                if file_back:
                    image_back = Image.open(file_back).convert("RGBA")
                else:
                    image_back = Image.new("RGBA", (960, 640), (0, 0, 0, 0))

                # 顔輪郭マスクがあったら image_centerを書き換える
                if mask_file:
                    mask_image = Image.open(mask_file[0]).convert('L')
                    image = np.array(image_center)
                    mask = np.array(mask_image)
                    image[:, :, 3] = (1.0 - mask / 255.0) * image[:, :, 3]
                    image_center = Image.fromarray(image)

                if file_front:
                    image_front = image_front.resize((960, 640))
                    binary_dict["/960x640/" + file_front.name] = image_front
                if file_center:
                    image_center = image_center.resize((960, 640))
                    binary_dict["/960x640/" + file_center.name] = image_center
                if file_back and file_back.name not in ['素体_男.png', '素体_女.png']:
                    image_back = image_back.resize((960, 640))
                    binary_dict["/960x640/" + file_back.name] = image_back
            time.sleep(3)
        st.markdown(f'<span style="color:red">書き出しが完了しました。ダウンロードボタンが表示されるまでお待ちください。</span>', unsafe_allow_html=True)
        show_zip_download("mm_body2.zip", binary_dict)
    st.write('チェックを入れたファイルを書き出します。')
