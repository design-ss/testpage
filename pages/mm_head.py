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

st.set_page_config(page_title='mm頭・髪書き出し')

st.title('mm頭・髪書き出し')

col1, col2  = st.columns(2)

# 前ファイル指定
with col1:
    export_files_front = st.file_uploader("頭_前ファイルを選択", type='png', accept_multiple_files=True, key="export_files_front")

# 後ろファイル指定
with col2:
    export_files_back = st.file_uploader("頭_後ろファイルを選択", type='png', accept_multiple_files=True, key="export_files_back")

# 頭素体読み込み　変数変更めんどくさいので中のまま！！！！！！！！
export_files_center = st.file_uploader("「mm_頭素体.png」を選択", type='png', accept_multiple_files=True, key="export_files_center")
# ファイルが選択されていない場合はメッセージを表示する
if not export_files_center:
    st.write('<span style="color:red;">未選択です。「mm_頭素体.png」をアップロードしてください。</span>', unsafe_allow_html=True)

# ファイル名を昇順に並び替える　ローカルでは選択順にアップされるが、クラウド上ではなぜかバラバラになるので制御するために昇順に
export_files_front = sorted(export_files_front, key=lambda x: x.name)
export_files_center = sorted(export_files_center, key=lambda x: x.name)
export_files_back = sorted(export_files_back, key=lambda x: x.name)

st.write('**再生マーク**<p style="font-size: 80%;">'
         'モーションアバター書き出しの際は、再生マークをアップロードしてください。<br>'
        '現在は50/100に再生マークを載せるだけの機能になっています。'
        '</p>', 
        unsafe_allow_html=True)

# 100×100再生マーク
playmark_files = st.file_uploader("選択", type='png', accept_multiple_files=True, key="playmark_file")

    
st.markdown('---')
st.write('**320/640調整用** 50/100で調整が必要な場合はpsdでの書き出しで対応してください。', unsafe_allow_html=True)
# パラメータ調整スライダー 
vertical_shift = st.slider('下移動⇔上移動', min_value=-320, max_value=320, value=0)
horizontal_shift = st.slider('左移動⇔右移動', min_value=-320, max_value=320, value=0)
scale_640 = st.slider('縮小⇔拡大　デフォルトは1.0', min_value=0.5, max_value=1.5, value=1.0)


# 一括書き出しと個別書き出し
export_button1, export_selected_button1 = st.columns(2)

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
                    image_center = Image.open(export_files_center[0]).convert("RGBA")
                    
                    # 再生マークあったら開く
                    if playmark_files:  
                         playmark_image = Image.open(playmark_files[0]).convert("RGBA")  
                    
                    # 統合する
                    image = Image.alpha_composite(image_back.convert("RGBA"), image_center.convert("RGBA"))
                    image = Image.alpha_composite(image.convert("RGBA"), image_front.convert("RGBA"))

                    # ちょっと縮小する　AI生成 汚くなるけど楽に縮小できる
                    scale = 0.92 
                    width, height = image.size
                    new_width, new_height = int(width * scale), int(height * scale)
                    x1, y1 = width // 2, height // 2
                    x2, y2 = int(x1 * scale), int(y1 * scale)
                    size_after = (int(width * scale), int(height * scale))
                    image_np = np.array(image)
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
                    final_image = final_image.crop((360, 0, 600, 640))
                    final_image = final_image.resize((240, 640), Image.LANCZOS)

                    # 正方形にする
                    start_y = 100
                    end_y = start_y + 240
                    b_image = final_image.crop((0, start_y, 240, end_y))

                    # 縮小する
                    b_image.thumbnail((100,100), Image.LANCZOS)
                    
                    # 再生マークあったら統合する
                    if playmark_files:
                        b_image = Image.alpha_composite(b_image.convert("RGBA"), playmark_image.convert("RGBA"))   
                    
                    # ファイル名を設定する
                    if file_front:
                        file_name = file_front.name
                    elif file_center:
                        file_name = file_center.name
                    elif file_back:
                        file_name = file_back.name
                    
                    # 100 × 100保存
                    binary_dict["/100x100/" + file_name] = b_image

                    # 50 × 50保存
                    b_image = b_image.resize((50, 50))
                    binary_dict["/50x50/" + file_name] = b_image


                    ####################################

                    #　640 × 640、320 ×　320　のリサイズ

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
                    
                    # 顔素体　リスト0を指定しないとループで同じ画像使えない
                    image_center = Image.open(export_files_center[0]).convert("RGBA")
                    
                    # 統合
                    image= Image.alpha_composite(image_back.convert("RGBA"), image_center.convert("RGBA"))
                    image = Image.alpha_composite(image.convert("RGBA"), image_front.convert("RGBA"))
                        
                    # 960×640
                    if file_front:
                        image_front = image_front.resize((960, 640))
                        binary_dict["/960x640/" + file_front.name] = image_front

                    if file_back:
                        image_back = image_back.resize((960, 640))
                        binary_dict["/960x640/" + file_back.name] = image_back
                    
                    # 統合する
                    image = Image.alpha_composite(image_back.convert("RGBA"), image_center.convert("RGBA"))
                    image = Image.alpha_composite(image.convert("RGBA"), image_front.convert("RGBA"))
                    
                     # 縮小して元サイズに貼り付けてる
                    width, height = image.size
                    image = image.resize((int(960 * scale_640), int(640 * scale_640)))
                    new_image = Image.new('RGBA', (960, 640))
                    new_image.paste(image, ((960 - image.width) // 2, (640 - image.height) // 2))

                    # 幅
                    image = new_image.crop((160 - horizontal_shift, 0, width + 160 - horizontal_shift, height))

                    # 上下だけ消す
                    bbox = image.getbbox()
                    image = image.crop((0, bbox[1], 640, bbox[3]))
                    width, height = image.size # サイズを再取得

                    # 高さ
                    new_image = Image.new('RGBA', (width, 640), (0, 0, 0, 0))
                    pad_height = 640 - height - 15 - vertical_shift
                    new_image.paste(image, (0, pad_height))
                    d_image = new_image
                                
                    # 320×320を生成
                    c_image = d_image.resize((320, 320))
                    
                    # ファイル名を設定する
                    if file_front:
                        file_name = file_front.name
                    elif file_center:
                        file_name = file_center.name
                    elif file_back:
                        file_name = file_back.name

                    # 統合した画像の保存（
                    binary_dict["/640x640/" + file_name] = d_image
                    binary_dict["/320x320/" + file_name] = c_image
            time.sleep(3)
        st.markdown(f'<span style="color:red">書き出しが完了しました。ダウンロードボタンが表示されるまでお待ちください。</span>', unsafe_allow_html=True)
        show_zip_download("mm_head.zip", binary_dict)
    st.write('全てのファイルを書き出します。')
st.markdown('---')



# 100プレビュー処理
# if vertical_shift or horizontal_shift or scale  or preview_button1:
with st.spinner("画像生成中です..."):
    binary_dict.clear() # 初期化
    # 個別書き出し用空のファイルリスト
    selected_files = []
    cols = st.columns(3)
    i = 0
    # リスト数調整
    max_length = max(len(export_files_front), len(export_files_back))
    export_files_front += [None] * (max_length - len(export_files_front))
    # export_files_center += [None] * (max_length - len(export_files_center))
    export_files_back += [None] * (max_length - len(export_files_back))

    for file_front, file_back in zip(export_files_front,export_files_back):
        ####################################

        #　640 × 640、320 ×　320　のリサイズ

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
        
        # 顔素体　リスト0を指定しないとループで同じ画像使えない
        try:
            image_center = Image.open(export_files_center[0]).convert("RGBA")
        except IndexError:
            st.error('mm_頭素体.pngファイルをアップしてください。')
                    
        # 960×640
        if file_front:
            image_front = image_front.resize((960, 640))
            binary_dict["/960x640/" + file_front.name] = image_front

        if file_back:
            image_back = image_back.resize((960, 640))
            binary_dict["/960x640/" + file_back.name] = image_back
        
        # 統合する
        image = Image.alpha_composite(image_back.convert("RGBA"), image_center.convert("RGBA"))
        image = Image.alpha_composite(image.convert("RGBA"), image_front.convert("RGBA"))
        
        
        # 縮小して元サイズに貼り付けてる
        width, height = image.size
        image = image.resize((int(960 * scale_640), int(640 * scale_640)))
        new_image = Image.new('RGBA', (960, 640))
        new_image.paste(image, ((960 - image.width) // 2, (640 - image.height) // 2))

        # 幅
        image = new_image.crop((160 - horizontal_shift, 0, width + 160 - horizontal_shift, height))

        # 上下だけ消す
        bbox = image.getbbox()
        image = image.crop((0, bbox[1], 640, bbox[3]))
        width, height = image.size # サイズを再取得

        # 高さ
        new_image = Image.new('RGBA', (width, 640), (0, 0, 0, 0))
        pad_height = 640 - height - 15 - vertical_shift
        new_image.paste(image, (0, pad_height))
        d_image = new_image

        # ファイル名を設定する
        if file_front:
            file_name = file_front.name
        elif file_center:
            file_name = file_center.name
        elif file_back:
            file_name = file_back.name
            
         # 背景を読み込む
        back_image = Image.open("./data/mm_640_back.png")

        # 200×200
        c_image = d_image.resize((200, 200))

        # c_imageと背景を統合する
        final_image = Image.new("RGBA", back_image.size)
        final_image.paste(back_image, (0, 0))
        final_image.paste(c_image, (final_image.width//2 - c_image.width//2, final_image.height//2 - c_image.height//2), c_image)

        # 中心線を描画する
        up = 8
        draw = ImageDraw.Draw(final_image)
        draw.line((0, final_image.height- up, final_image.width, final_image.height- up), fill="red", width=1)
        draw.line((final_image.width//2, 0, final_image.width//2, final_image.height), fill="red", width=1)

        # プレビュー画像を表示する
        preview_image = getPreviewImage(final_image)
        cols[i % 3].image(preview_image, use_column_width=False)

        # チェックボックス
        if cols[i % 3].checkbox("選択", key=f"select_{file_name}"):
            selected_files.append((file_front, file_back))
        
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

            for file_front, file_back in selected_files:
                     ####################################

                    #　50 × 50、100 × 100　のリサイズ

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
                    
                    # 顔素体　リスト0を指定しないとループで同じ画像使えない
                    image_center = Image.open(export_files_center[0]).convert("RGBA")
                    
                    # 再生マークあったら開く
                    if playmark_files:  
                         playmark_image = Image.open(playmark_files[0]).convert("RGBA")  
                    
                    # 統合する
                    image = Image.alpha_composite(image_back.convert("RGBA"), image_center.convert("RGBA"))
                    image = Image.alpha_composite(image.convert("RGBA"), image_front.convert("RGBA"))

                    # ちょっと縮小する　AI生成 汚くなるけど楽に縮小できる
                    scale = 0.92 
                    width, height = image.size
                    new_width, new_height = int(width * scale), int(height * scale)
                    x1, y1 = width // 2, height // 2
                    x2, y2 = int(x1 * scale), int(y1 * scale)
                    size_after = (int(width * scale), int(height * scale))
                    image_np = np.array(image)
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
                    final_image = final_image.crop((360, 0, 600, 640))
                    final_image = final_image.resize((240, 640), Image.LANCZOS)

                    # 正方形にする
                    start_y = 100
                    end_y = start_y + 240
                    b_image = final_image.crop((0, start_y, 240, end_y))

                    # 縮小する
                    b_image.thumbnail((100,100), Image.LANCZOS)
                    
                    # 再生マークあったら統合する
                    if playmark_files:
                        b_image = Image.alpha_composite(b_image.convert("RGBA"), playmark_image.convert("RGBA"))   
                    
                    # ファイル名を設定する
                    if file_front:
                        file_name = file_front.name
                    elif file_center:
                        file_name = file_center.name
                    elif file_back:
                        file_name = file_back.name
                    
                    # 100 × 100保存
                    binary_dict["/100x100/" + file_name] = b_image

                    # 50 × 50保存
                    b_image = b_image.resize((50, 50))
                    binary_dict["/50x50/" + file_name] = b_image


                    ####################################

                    #　640 × 640、320 ×　320　のリサイズ

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
                    
                    # 顔素体　リスト0を指定しないとループで同じ画像使えない
                    image_center = Image.open(export_files_center[0]).convert("RGBA")
                    
                    # 統合
                    image= Image.alpha_composite(image_back.convert("RGBA"), image_center.convert("RGBA"))
                    image = Image.alpha_composite(image.convert("RGBA"), image_front.convert("RGBA"))
                        
                    # 960×640
                    if file_front:
                        image_front = image_front.resize((960, 640))
                        binary_dict["/960x640/" + file_front.name] = image_front

                    if file_back:
                        image_back = image_back.resize((960, 640))
                        binary_dict["/960x640/" + file_back.name] = image_back
                    
                    # 統合する
                    image = Image.alpha_composite(image_back.convert("RGBA"), image_center.convert("RGBA"))
                    image = Image.alpha_composite(image.convert("RGBA"), image_front.convert("RGBA"))
                    
                    # 縮小して元サイズに貼り付けてる
                    width, height = image.size
                    image = image.resize((int(960 * scale_640), int(640 * scale_640)))
                    new_image = Image.new('RGBA', (960, 640))
                    new_image.paste(image, ((960 - image.width) // 2, (640 - image.height) // 2))

                    # 幅
                    image = new_image.crop((160 - horizontal_shift, 0, width + 160 - horizontal_shift, height))

                    # 上下だけ消す
                    bbox = image.getbbox()
                    image = image.crop((0, bbox[1], 640, bbox[3]))
                    width, height = image.size # サイズを再取得

                    # 高さ
                    new_image = Image.new('RGBA', (width, 640), (0, 0, 0, 0))
                    pad_height = 640 - height - 15 - vertical_shift
                    new_image.paste(image, (0, pad_height))
                    d_image = new_image
                                
                    # 320×320を生成
                    c_image = d_image.resize((320, 320))
                    
                    # ファイル名を設定する
                    if file_front:
                        file_name = file_front.name
                    elif file_center:
                        file_name = file_center.name
                    elif file_back:
                        file_name = file_back.name

                    # 統合した画像の保存（
                    binary_dict["/640x640/" + file_name] = d_image
                    binary_dict["/320x320/" + file_name] = c_image
            time.sleep(3)
        st.markdown(f'<span style="color:red">書き出しが完了しました。ダウンロードボタンが表示されるまでお待ちください。</span>', unsafe_allow_html=True)
        show_zip_download("mm_head2.zip", binary_dict)
    st.write('チェックを入れたファイルを書き出します。')
