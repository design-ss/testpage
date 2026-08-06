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
#　100 × 100、50 ×　50　のリサイズ関数
def generate_small_images(file_front, file_back, file_center, attribution_file,scale_100, horizontal_shift_100, vertical_shift_100): 
   # 画像を読み込む
    if file_front:
        image_front = Image.open(file_front).convert("RGBA")
    else:
        image_front = Image.new("RGBA", (960, 640), (0, 0, 0, 0))

    if file_back:
        image_back = Image.open(file_back).convert("RGBA")
    else:
        image_back = Image.new("RGBA", (960, 640), (0, 0, 0, 0))
    
    # 顔素体　リスト0を指定しないとループで同じ画像使えない
    try:
        image_center = Image.open(file_center[0]).convert("RGBA")
    except IndexError:
        st.error('mc_w_head.pngファイルをアップしてください。')

    attribution = Image.open(attribution_file)

    # サイズに統一する
    image_front = image_front.resize((960, 640))
    image_center = image_center.resize((960, 640))
    image_back = image_back.resize((960, 640))

    # 統合
    combined_center_back = Image.alpha_composite(image_back.convert("RGBA"), image_center.convert("RGBA"))
    resized_image = Image.alpha_composite(combined_center_back, image_front.convert("RGBA"))

   # 中心座標（縮小率を考慮）
    center_x = int(490 * scale_100)
    center_y = int(120 * scale_100)

    # スケール変更
    resized_image = resized_image.resize((int(resized_image.width * scale_100), int(resized_image.height * scale_100)))
 

    # 100×100
    b_image= resized_image.crop((center_x - 50 - horizontal_shift_100, center_y - 50 - vertical_shift_100, center_x + 50 - horizontal_shift_100, center_y + 50 - vertical_shift_100))


    # 統合する
    b_image = Image.alpha_composite(b_image, attribution)

    # ファイル名を設定する
    if file_front:
        file_name = file_front.name
    elif file_center:
        file_name = file_center.name
    elif file_back:
        file_name = file_back.name

    return b_image, file_name


def generate_large_images(file_front, file_back, file_center, scale_640, horizontal_shift_640 , vertical_shift_640):
    # 画像を読み込む
    if file_front:
        image_front = Image.open(file_front).convert("RGBA")
    else:
        image_front = Image.new("RGBA", (960, 640), (0, 0, 0, 0))

    if file_back:
        image_back = Image.open(file_back).convert("RGBA")
    else:
        image_back = Image.new("RGBA", (960, 640), (0, 0, 0, 0))
    
    # 顔素体　リスト0を指定しないとループで同じ画像使えない
    try:
        image_center = Image.open(file_center[0]).convert("RGBA")
    except IndexError:
        st.error('mc_w_head.pngファイルをアップしてください。')
                
        
    # 1920×1280サイズに統一する
    image_front = image_front.resize((1920, 1280))
    image_back = image_back.resize((1920, 1280))
    
    # 統合する
    image = Image.alpha_composite(image_back.convert("RGBA"), image_center.convert("RGBA"))
    image = Image.alpha_composite(image.convert("RGBA"), image_front.convert("RGBA"))
    
    # 画像のサイズを変更
    image = image.resize((int(1920 * scale_640), int(1280 * scale_640)))
    new_image = Image.new('RGBA', (2000, 1920))

    # new_imageとimageの中心位置を取得、そしてシフト量を適用
    center_new_image = (990 - horizontal_shift_640 , 530 + vertical_shift_640 )
    center_image = (int(990 * scale_640), int(260 * scale_640))

    # 画像を新しい位置に貼り付けるためのシフト量を計算
    shift_x = center_new_image[0] - center_image[0]
    shift_y = center_new_image[1] - center_image[1]

    # 画像を新しい位置に貼り付け
    new_image.paste(image, (shift_x, shift_y))

    # 中心から640x640のサイズでトリミング + シフト量を考慮
    left = center_new_image[0] - 320 - horizontal_shift_640   # 640の半分
    upper = center_new_image[1] - 320 + vertical_shift_640 
    right = center_new_image[0] + 320 - horizontal_shift_640 
    lower = center_new_image[1] + 320 + vertical_shift_640 

    image = new_image.crop((int(left), int(upper), int(right), int(lower)))

    d_image = image
    # # 画像のフェザリングを適用
    # image_array = np.array(image)
    # feathered_array = apply_feathering(image_array)
    # d_image = Image.fromarray(feathered_array, 'RGBA')

    # ファイル名を設定する
    if file_front:
        file_name = file_front.name
    elif file_center:
        file_name = file_center.name
    elif file_back:
        file_name = file_back.name

    return d_image, file_name

# 640長髪用処理　フェザリング
def apply_feathering(img_array):
    l_row, l_col, nb_channel = img_array.shape
    
    feathering_width = 80
    t = np.linspace(0, 1, feathering_width)
    fade = 255 * (1 - t**2)
    
    # 水平方向のフェザリング
    fade_horizontal = np.ones(l_col) * 255
    fade_horizontal[:feathering_width] = fade[::-1]
    fade_horizontal[-feathering_width:] = fade
    
    # 垂直方向のフェザリング
    fade_vertical = np.ones(l_row) * 255
    fade_vertical[:feathering_width] = fade[::-1]
    fade_vertical[-feathering_width:] = fade

    # fade_horizontal と fade_vertical を2Dに拡張
    fade_horizontal_matrix = np.tile(fade_horizontal, (l_row, 1))
    fade_vertical_matrix = np.tile(fade_vertical[:, np.newaxis], (1, l_col))
    combined_fade = np.minimum(fade_horizontal_matrix, fade_vertical_matrix)
    
    # アルファチャンネルを更新
    combined_alpha = np.minimum(combined_fade, img_array[..., 3])
    img_array[..., 3] = combined_alpha.astype(np.uint8)

    return img_array



st.set_page_config(page_title='mc頭・髪書き出し')

st.title('mc頭・髪書き出し')

col1, col2  = st.columns(2)

# 前ファイル指定
with col1:
    export_files_front = st.file_uploader("頭_前ファイルを選択", type='png', accept_multiple_files=True, key="export_files_front")

# 後ろファイル指定
with col2:
    export_files_back = st.file_uploader("頭_後ろファイルを選択", type='png', accept_multiple_files=True, key="export_files_back")

col3, col4  = st.columns(2)
with col3:
    # 白黒頭素体　
    st.write('**mc_白黒頭素体**<span style="color:red; font-size: 80%;">　※必須</span>', unsafe_allow_html=True)
    st.write('<span style="font-size: 80%;">「mc_w_head.png」をアップロードしてください。</span>', unsafe_allow_html=True)
    export_files_center = st.file_uploader("選択", type='png', accept_multiple_files=True, key="export_files_center")
    # ファイルが選択されていない場合はメッセージを表示する
    if not export_files_center:
        st.write('<span style="color:red;">未選択です。「mc_w_head.png」をアップロードしてください。</span>', unsafe_allow_html=True)

with col4:
    # 属性ファイル　
    st.write('**属性**<span style="color:red; font-size: 80%;">　※必須</span>', unsafe_allow_html=True)
    st.write('<span style="font-size: 80%;">属性画像をアップロードしてください。</span>', unsafe_allow_html=True)
    attribution_file = st.file_uploader("選択", type='png', accept_multiple_files=False, key="attribution_file")
     # ファイルが選択されていない場合はメッセージを表示する
    if not export_files_center:
        st.write('<span style="color:red;">未選択です。属性画像をアップロードしてください。</span>', unsafe_allow_html=True)

# ファイル名を昇順に並び替える　ローカルでは選択順にアップされるが、クラウド上ではなぜかバラバラになるので制御するために昇順に
export_files_front = sorted(export_files_front, key=lambda x: x.name)
export_files_center = sorted(export_files_center, key=lambda x: x.name)
export_files_back = sorted(export_files_back, key=lambda x: x.name)

# 一括書き出しと個別書き出し
export_button1, export_selected_button1 = st.columns(2)

st.markdown('---')
st.write('**50/100調整用** ', unsafe_allow_html=True)
# パラメータ調整スライダー 
vertical_shift_100  = st.slider('下移動⇔上移動', min_value=-100, max_value=100, value=0, key='vertical_shift_100')
horizontal_shift_100  = st.slider('左移動⇔右移動', min_value=-100, max_value=100, value=0, key='horizontal_shift_100')
scale_100 = st.slider('縮小⇔拡大　デフォルトは1.0', min_value=0.01, max_value=1.0, value=0.4, key='scale_100')



# 100プレビュー処理
with st.spinner("画像生成中です..."):
    binary_dict.clear() # 初期化
    selected_files_100 = []
    cols = st.columns(4)
    i = 0
    max_length = max(len(export_files_front), len(export_files_back))
    export_files_front += [None] * (max_length - len(export_files_front))
    export_files_back += [None] * (max_length - len(export_files_back))

    for file_front, file_back in zip(export_files_front, export_files_back):
        
        ####################################

        # 100 × 100、50 ×　50　のリサイズ

        ####################################
        b_image, file_name = generate_small_images(file_front, file_back, export_files_center, attribution_file,scale_100, horizontal_shift_100, vertical_shift_100)
        
        # 背景を読み込む
        flame_image = Image.open("./data/100_flame.png")

        # b_imageとサンプルフレームを統合する
        b_image.paste(flame_image, (0, 0), flame_image)

        # 中心線を描画する
        draw = ImageDraw.Draw(b_image)
        draw.line((50, 0, 50, 100), fill="red", width=1)
        draw.line((0, 50, 100, 50), fill="red", width=1)

        # プレビュー画像を表示する
        cols[i % 4].image(getPreviewImage(b_image), use_column_width=False)
        
        # チェックボックス
        if cols[i % 4].checkbox("選択", key=f"select_100_{i}_{file_name}"):
            selected_files_100.append((file_front, file_back))

        i += 1


st.write('**320/640調整用** ', unsafe_allow_html=True)
# パラメータ調整スライダー 
vertical_shift_640  = st.slider('下移動⇔上移動', min_value=-320, max_value=320, value=0, key='vertical_shift_640')
horizontal_shift_640  = st.slider('左移動⇔右移動', min_value=-320, max_value=320, value=0, key='horizontal_shift_640')
scale_640 = st.slider('縮小⇔拡大　デフォルトは1.0', min_value=0.5, max_value=1.5, value=1.0, key='scale_640')

# 640プレビュー処理
with st.spinner("画像生成中です..."):
    binary_dict.clear() # 初期化
    selected_files_640 = []
    cols = st.columns(3)
    i = 0
    max_length = max(len(export_files_front), len(export_files_back))
    export_files_front += [None] * (max_length - len(export_files_front))
    export_files_back += [None] * (max_length - len(export_files_back))

    for file_front, file_back in zip(export_files_front, export_files_back):
        
        ####################################

        # 640 × 640、320 ×　320　のリサイズ

        ####################################
        d_image, file_name = generate_large_images(file_front, file_back, export_files_center, scale_640, horizontal_shift_640 , vertical_shift_640 )
        
        back_image = Image.open("./data/mm_640_back.png")
        c_image = d_image.resize((200, 200))
        final_image = Image.new("RGBA", back_image.size)
        final_image.paste(back_image, (0, 0))
        final_image.paste(c_image, (final_image.width//2 - c_image.width//2, final_image.height//2 - c_image.height//2), c_image)

        draw = ImageDraw.Draw(final_image)
        draw.line((0, final_image.height // 2, final_image.width, final_image.height // 2), fill="red", width=1)
        draw.line((final_image.width // 2, 0, final_image.width // 2, final_image.height), fill="red", width=1)

        preview_image = getPreviewImage(final_image)
        cols[i % 3].image(preview_image, use_column_width=False)

         # チェックボックス
        if cols[i % 3].checkbox("選択", key=f"select_640_{i}_{file_name}"):
            selected_files_640.append((file_front, file_back))

        i += 1

# 100プレビューと640プレビューの選択ファイルを統合してselected_filesに追加
selected_files = selected_files_100 + selected_files_640

# 一括書き出し
with export_button1:
    if st.button('一括書き出し'):
        with st.spinner("画像生成中です..."):
            binary_dict.clear() # 初期化
            
           # リスト数調整
            max_length = max(len(export_files_front), len(export_files_back))
            export_files_front += [None] * (max_length - len(export_files_front))
            # export_files_center += [None] * (max_length - len(export_files_center))
            export_files_back += [None] * (max_length - len(export_files_back))

            for file_front, file_back in zip(export_files_front,export_files_back):
                    ####################################

                    #　50 × 50、100 × 100　のリサイズ

                    ####################################
                    b_image, file_name = generate_small_images(file_front, file_back, export_files_center, attribution_file,scale_100, horizontal_shift_100, vertical_shift_100)
                    a_image = b_image.resize((50, 50))
                    
                    # 100 × 100保存
                    binary_dict["/100x100/" + file_name] = b_image
                    # 50 × 50保存
                    binary_dict["/50x50/" + file_name] = a_image


                    ####################################

                    #　640 × 640、320 ×　320　のリサイズ

                    ####################################
                    d_image, file_name = generate_large_images(file_front, file_back, export_files_center, scale_640, horizontal_shift_640 , vertical_shift_640 )
                    c_image = d_image.resize((320, 320))
                    # 統合した画像の保存（
                    binary_dict["/640x640/" + file_name] = d_image
                    binary_dict["/320x320/" + file_name] = c_image
                    
                    ####################################
                    
                    #　960 × 640　の保存
                    
                    ####################################
                     # 画像を読み込む
                    if file_front:
                        image_front = Image.open(file_front).convert("RGBA")
                    else:
                        image_front = Image.new("RGBA", (960, 640), (0, 0, 0, 0))

                    if file_back:
                        image_back = Image.open(file_back).convert("RGBA")
                    else:
                        image_back = Image.new("RGBA", (960, 640), (0, 0, 0, 0))
                    if file_front:
                        image_front = image_front.resize((960, 640))
                        binary_dict["/960x640/" + file_front.name] = image_front

                    if file_back:
                        image_back = image_back.resize((960, 640))
                        binary_dict["/960x640/" + file_back.name] = image_back
                                    
                    
            time.sleep(3)
        st.markdown(f'<span style="color:red">書き出しが完了しました。ダウンロードボタンが表示されるまでお待ちください。</span>', unsafe_allow_html=True)
        show_zip_download("mc_head.zip", binary_dict)
    st.write('全てのファイルを書き出します。')
st.markdown('---')


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

            for file_front, file_back in selected_files:
                      ####################################

                    #　50 × 50、100 × 100　のリサイズ

                    ####################################
                    b_image, file_name = generate_small_images(file_front, file_back, export_files_center, attribution_file,scale_100, horizontal_shift_100, vertical_shift_100)
                    a_image = b_image.resize((50, 50))
                    
                    # 100 × 100保存
                    binary_dict["/100x100/" + file_name] = b_image
                    # 50 × 50保存
                    binary_dict["/50x50/" + file_name] = a_image


                    ####################################

                    #　640 × 640、320 ×　320　のリサイズ

                    ####################################
                    d_image, file_name = generate_large_images(file_front, file_back, export_files_center, scale_640, horizontal_shift_640 , vertical_shift_640 )
                    c_image = d_image.resize((320, 320))
                    # 統合した画像の保存（
                    binary_dict["/640x640/" + file_name] = d_image
                    binary_dict["/320x320/" + file_name] = c_image
                    
                    ####################################
                    
                    #　960 × 640　の保存
                    
                    ####################################
                     # 画像を読み込む
                    if file_front:
                        image_front = Image.open(file_front).convert("RGBA")
                    else:
                        image_front = Image.new("RGBA", (960, 640), (0, 0, 0, 0))

                    if file_back:
                        image_back = Image.open(file_back).convert("RGBA")
                    else:
                        image_back = Image.new("RGBA", (960, 640), (0, 0, 0, 0))
                    if file_front:
                        image_front = image_front.resize((960, 640))
                        binary_dict["/960x640/" + file_front.name] = image_front

                    if file_back:
                        image_back = image_back.resize((960, 640))
                        binary_dict["/960x640/" + file_back.name] = image_back
            time.sleep(3)
        st.markdown(f'<span style="color:red">書き出しが完了しました。ダウンロードボタンが表示されるまでお待ちください。</span>', unsafe_allow_html=True)
        show_zip_download("mc_head2.zip", binary_dict)
    st.write('チェックを入れたファイルを書き出します。')
