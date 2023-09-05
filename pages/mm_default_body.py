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

st.set_page_config(page_title='mm素体ポーズ体書き出し')

st.title('mm素体ポーズ書き出し')

st.write('**見た目体はこちらのアプリでは書き出しできません。mm bodyを使ってください。** ', unsafe_allow_html=True)


col1, col2 = st.columns(2)

# 男体ファイル指定
with col1:
    default_pose_male = st.file_uploader("**男体ファイル指定**", type='png', accept_multiple_files=True, key="default_pose_male")

# 女体ファイル指定
with col2:
    default_pose_female = st.file_uploader("**女体ファイル指定**", type='png', accept_multiple_files=True, key="default_pose_female ")

    
# ファイル名を昇順に並び替える　ローカルでは選択順にアップされるが、クラウド上ではなぜかバラバラになるので制御するために昇順に
default_pose_male = sorted(default_pose_male, key=lambda x: x.name)
default_pose_female  = sorted(default_pose_female , key=lambda x: x.name)

col4 , col5 = st.columns(2)

with col4:
    st.write('**素体ファイル<br>** <p style="font-size: 80%;">「素体_男.png」「素体_女.png」から名前を変更しないでください。<br></p>', unsafe_allow_html=True)
    # 素体
    default_bodys = st.file_uploader("選択", type='png', accept_multiple_files=True, key="default_body")
    default_body_dict = {default_body.name: default_body for default_body in default_bodys}
    
with col5:
    st.write('**再生マーク**<p style="font-size: 80%;">モーションアバター書き出しの際は、再生マークをアップロードしてください。</p>', unsafe_allow_html=True)
    # 100×100再生マーク
    playmark_files = st.file_uploader("選択", type='png', accept_multiple_files=True, key="playmark_file")

    
st.markdown('---')
st.write('**50/100調整用** ', unsafe_allow_html=True)
# パラメータ調整スライダー 
vertical_shift = st.slider('下移動⇔上移動', min_value=-100, max_value=100, value=0)
horizontal_shift = st.slider('左移動⇔右移動', min_value=-100, max_value=100, value=0)
scale_100 = st.slider('縮小⇔拡大 デフォルトは0.96', min_value=0.5, max_value=1.5, value=0.96)


# 一括書き出しと個別書き出し
export_button1, export_selected_button1 = st.columns(2)

# 一括書き出し
with export_button1:
    if st.button('一括書き出し'):
        with st.spinner("画像生成中です..."):
            binary_dict.clear() # 初期化
            
            # # リスト数調整
            # max_length = max(len(export_files_front), len(default_body_male ), len(export_files_back))
            # export_files_front += [None] * (max_length - len(export_files_front))
            # default_body_male  += [None] * (max_length - len(default_body_male ))
            # export_files_back += [None] * (max_length - len(export_files_back))

            for default_pose_list in (default_pose_male, default_pose_female):
                for default_pose_file in default_pose_list: 
                    # ####################################
                    
                    #　50 × 50、100 × 100　のリサイズ
                    
                    # ####################################

                    # 画像を読み込む
                    default_pose_image = Image.open(default_pose_file).convert("RGBA") 

                    # 再生マークあったら開く
                    if playmark_files:
                        playmark_image = Image.open(playmark_files[0]).convert("RGBA")

                    # 男女画像 
                    if default_pose_file in default_pose_male:
                        default_body_image = Image.open(default_body_dict["素体_男.png"])
                    else:
                        default_body_image = Image.open(default_body_dict["素体_女.png"])

                    # 統合
                    final_image = Image.alpha_composite(default_body_image.convert("RGBA"), default_pose_image.convert("RGBA"))

                    # ちょっと縮小する　AI生成
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

                    # リサイズする 非対称
                    final_image = final_image.crop((315 - horizontal_shift, 0 + vertical_shift, 605 - horizontal_shift, 640+ vertical_shift))
                    final_image = final_image.resize((290, 640), Image.LANCZOS)

                    # 正方形にする　
                    start_y = 640 - 290 - 65 
                    end_y = start_y + 290
                    b_image = final_image.crop((0, start_y, 290, end_y))

                    # 縮小する
                    b_image.thumbnail((100,100), Image.LANCZOS)
                    
                    # 再生マークあったら統合する
                    if playmark_files:
                        b_image = Image.alpha_composite(b_image.convert("RGBA"), playmark_image.convert("RGBA"))   
                    
                    # ファイル名を設定する
                    file_name = default_pose_file.name
                    
                    # 100 × 100保存
                    binary_dict["/100x100/" + file_name] = b_image

                    # 50 × 50保存
                    b_image = b_image.resize((50, 50))
                    binary_dict["/50x50/" + file_name] = b_image


                    ####################################

                    #　640 × 640、320 ×　320　のリサイズ

                    ####################################
                    # 画像を読み込む
                    default_pose_image = Image.open(default_pose_file).convert("RGBA") 
                        
                    # 960×640        
                    default_pose_image = default_pose_image.resize((960, 640))
                    binary_dict["/960x640/" + default_pose_file.name] = default_pose_image
                    
                    # 統合する
                    image = Image.alpha_composite(default_body_image.convert("RGBA"), default_pose_image.convert("RGBA"))

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

                    # スケール変更 のこしとく
                    scale = 1
                    image = image.resize((int(image.width * scale), int(image.height * scale)))

                    # 画像のサイズを取得
                    width, height = image.size

                    # 高さが足りない場合、足りない分を上に足す
                    if height < 640:
                        new_image = Image.new('RGBA', (width, 640), (0, 0, 0, 0))
                        new_image.paste(image, (0, 640 - height))
                        d_image = new_image

                    # 幅が足りない場合、足りない分を両方に足す
                    if width < 640:
                        new_image = Image.new('RGBA', (640, 640), (0, 0, 0, 0))
                        new_image.paste(image, ((640 - width) // 2, 0))
                        d_image = new_image
                                
                    # 320×320を生成
                    c_image = d_image.resize((320, 320))
                    
                    # ファイル名を設定する
                    file_name = default_pose_file.name

                    # 統合した画像の保存（
                    binary_dict["/640x640/" + file_name] = d_image
                    binary_dict["/320x320/" + file_name] = c_image
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
    # # リスト数調整
    # max_length = max(len(export_files_front), len(default_body_male ), len(export_files_back))
    # export_files_front += [None] * (max_length - len(export_files_front))
    # default_body_male  += [None] * (max_length - len(default_body_male ))
    # export_files_back += [None] * (max_length - len(export_files_back))

    for default_pose_list in (default_pose_male, default_pose_female):
                for default_pose_file in default_pose_list: 
                ####################################

                #　50 × 50、100 × 100　のリサイズ

                ####################################
                     # 画像を読み込む
                    default_pose_image = Image.open(default_pose_file).convert("RGBA") 

                    # 再生マークあったら開く
                    if playmark_files:
                        playmark_image = Image.open(playmark_files[0]).convert("RGBA")

                    # 男女画像 
                    if default_pose_file in default_pose_male:
                        default_body_image = Image.open(default_body_dict["素体_男.png"])
                    else:
                        default_body_image = Image.open(default_body_dict["素体_女.png"])

                    # 統合
                    final_image = Image.alpha_composite(default_body_image.convert("RGBA"), default_pose_image.convert("RGBA"))

                    # ちょっと縮小する　AI生成
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

                    # リサイズする 両端切る
                    final_image = final_image.crop((315 - horizontal_shift, 0 + vertical_shift, 605 - horizontal_shift, 640+ vertical_shift))
                    final_image = final_image.resize((290, 640), Image.LANCZOS)

                    # 正方形にする　350px分消し去りたい　
                    start_y = 640 - 290 - 65 
                    end_y = start_y + 290
                    b_image = final_image.crop((0, start_y, 290, end_y))

                    # 縮小する
                    b_image.thumbnail((100,100), Image.LANCZOS)
        
                    # ファイル名を設定する
                    file_name = default_pose_file.name
                        
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
                        selected_files.append((default_pose_file))
                    
                    i += 1

# 個別書き出し 空のファイルリストはプレビューの中に
with export_selected_button1:
    if st.button('個別書き出し'):
        with st.spinner("画像生成中です..."):
            binary_dict.clear() # 初期化
            #  # リスト数調整
            # max_length = max(len(export_files_front), len(default_body_male ), len(export_files_back))
            # export_files_front += [None] * (max_length - len(export_files_front))
            # default_body_male  += [None] * (max_length - len(default_body_male ))
            # export_files_back += [None] * (max_length - len(export_files_back))

            for default_pose_file in selected_files:
                    # ####################################
                    
                    #　50 × 50、100 × 100　のリサイズ
                    
                    # ####################################

                    # 画像を読み込む
                    default_pose_image = Image.open(default_pose_file).convert("RGBA") 

                    # 再生マークあったら開く
                    if playmark_files:
                        playmark_image = Image.open(playmark_files[0]).convert("RGBA")

                    # 男女画像 
                    if default_pose_file in default_pose_male:
                        default_body_image = Image.open(default_body_dict["素体_男.png"])
                    else:
                        default_body_image = Image.open(default_body_dict["素体_女.png"])

                    # 統合
                    final_image = Image.alpha_composite(default_body_image.convert("RGBA"), default_pose_image.convert("RGBA"))

                    # ちょっと縮小する　AI生成
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

                    # リサイズする 両端切る
                    final_image = final_image.crop((315 - horizontal_shift, 0 + vertical_shift, 605 - horizontal_shift, 640+ vertical_shift))
                    final_image = final_image.resize((290, 640), Image.LANCZOS)

                    # 正方形にする　350px分消し去りたい　
                    start_y = 640 - 290 - 65 
                    end_y = start_y + 290
                    b_image = final_image.crop((0, start_y, 290, end_y))

                    # 縮小する
                    b_image.thumbnail((100,100), Image.LANCZOS)
                    
                    # 再生マークあったら統合する
                    if playmark_files:
                        b_image = Image.alpha_composite(b_image.convert("RGBA"), playmark_image.convert("RGBA"))   
                    
                    # ファイル名を設定する
                    file_name = default_pose_file.name
                    
                    # 100 × 100保存
                    binary_dict["/100x100/" + file_name] = b_image

                    # 50 × 50保存
                    b_image = b_image.resize((50, 50))
                    binary_dict["/50x50/" + file_name] = b_image


                    ####################################

                    #　640 × 640、320 ×　320　のリサイズ

                    ####################################
                    # 画像を読み込む
                    default_pose_image = Image.open(default_pose_file).convert("RGBA") 
                        
                    # 960×640        
                    default_pose_image = default_pose_image.resize((960, 640))
                    binary_dict["/960x640/" + default_pose_file.name] = default_pose_image
                    
                    # 統合する
                    image = Image.alpha_composite(default_body_image.convert("RGBA"), default_pose_image.convert("RGBA"))

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

                    # スケール変更 のこしとく
                    scale = 1
                    image = image.resize((int(image.width * scale), int(image.height * scale)))

                    # 画像のサイズを取得
                    width, height = image.size

                    # 高さが足りない場合、足りない分を上に足す
                    if height < 640:
                        new_image = Image.new('RGBA', (width, 640), (0, 0, 0, 0))
                        new_image.paste(image, (0, 640 - height))
                        d_image = new_image

                    # 幅が足りない場合、足りない分を両方に足す
                    if width < 640:
                        new_image = Image.new('RGBA', (640, 640), (0, 0, 0, 0))
                        new_image.paste(image, ((640 - width) // 2, 0))
                        d_image = new_image
                                
                    # 320×320を生成
                    c_image = d_image.resize((320, 320))
                    
                    # ファイル名を設定する
                    file_name = default_pose_file.name

                    # 統合した画像の保存（
                    binary_dict["/640x640/" + file_name] = d_image
                    binary_dict["/320x320/" + file_name] = c_image
            time.sleep(3)
        st.markdown(f'<span style="color:red">書き出しが完了しました。ダウンロードボタンが表示されるまでお待ちください。</span>', unsafe_allow_html=True)
        show_zip_download("mm_body2.zip", binary_dict)
    st.write('チェックを入れたファイルを書き出します。')
