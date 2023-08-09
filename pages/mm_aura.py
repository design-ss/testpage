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

st.set_page_config(page_title='mmオーラ書き出し')

st.title('mmオーラ書き出し')

st.write('<br>**ID付与前に「前後オーラ」を「複数枚同時に」書き出す場合はお気をつけください。** <br>ファイルは選択順に関係なく「昇順」でアップされます。<br>そのため、前後オーラを書き出すときはファイル名の先頭に3桁の数字を付けるなどで順番を制御してください。', unsafe_allow_html=True)

st.write('例<br>前オーラ：「001.前_目玉A」「002.前_目玉B」「003.前_目玉C」<br>後ろオーラ：「004.後ろ_目玉A」「005.後ろ_目玉B」「006.後ろ_目玉C」<br> ', unsafe_allow_html=True)


col1, col2 = st.columns(2)

col1, _, col2 = st.columns([1, 0.1, 1])  # '_'は空のカラム

# 男オーラ前ファイル指定
with col1:
    export_files_top_male = st.file_uploader("男性用オーラ前ファイルを選択", type='png', accept_multiple_files=True, key="export_files_top_male")

# 女オーラ前ファイル指定
with col2:
    export_files_top_female = st.file_uploader("女性用オーラ前ファイルを選択", type='png', accept_multiple_files=True, key="export_files_top_female")


col3, _, col4 = st.columns([1, 0.1, 1])  # '_'は空のカラム

# 男オーラ後ろファイル指定
with col3:
    export_files_bottom_male = st.file_uploader("男性用オーラ後ろファイルを選択", type='png', accept_multiple_files=True, key="export_files_bottom_male")


# 女オーラ後ろファイル指定
with col4:
    export_files_bottom_female = st.file_uploader("女性用オーラ後ろファイルを選択", type='png', accept_multiple_files=True, key="export_files_bottom_female")
    
# ファイル名を昇順に並び替える
export_files_top_male = sorted(export_files_top_male, key=lambda x: x.name)
export_files_top_female = sorted(export_files_top_female, key=lambda x: x.name)
export_files_bottom_male = sorted(export_files_bottom_male, key=lambda x: x.name)
export_files_bottom_female = sorted(export_files_bottom_female, key=lambda x: x.name)


st.markdown('---')
st.write('**男女シルエットを選択** <br>100×100男女シルエット画像をアップロードしてください。<br>「シルエット_男性.png」「シルエット_女性.png」から名前を変更しないでください。', unsafe_allow_html=True)
# 100×100男女シルエット
silhouette_files = st.file_uploader("選択", type='png', accept_multiple_files=True, key="silhouette_file")
silhouette_dict = {silhouette_file.name: silhouette_file for silhouette_file in silhouette_files}

# ファイルが選択されていない場合はメッセージを表示する
if not silhouette_files:
    st.write('<span style="color:red;">未選択です。シルエットをアップロードしてください。</span>', unsafe_allow_html=True)


st.markdown('---')
st.write('**320/640調整用** ', unsafe_allow_html=True)
# パラメータ調整スライダー 
vertical_shift = st.slider('下移動⇔上移動', min_value=-320, max_value=320, value=0)
horizontal_shift = st.slider('左移動⇔右移動', min_value=-320, max_value=320, value=0)
scale_640 = st.slider('縮小⇔拡大　デフォルトは0.67', min_value=0.5, max_value=0.84, value=0.67)


# 一括書き出しと個別書き出し
export_button1, export_selected_button1 = st.columns(2)

# 一括書き出し
with export_button1:
    if st.button('一括書き出し'):
        with st.spinner("画像生成中です..."):
            binary_dict.clear() # 初期化
            
            for gender_files_top, gender_files_bottom in [(export_files_top_male, export_files_bottom_male), (export_files_top_female, export_files_bottom_female)]:
                # 前ファイルと後ろファイル足りない部分調整
                if not gender_files_top:
                    gender_files_top = [None] * len(gender_files_bottom)
                if not gender_files_bottom:
                    gender_files_bottom = [None] * len(gender_files_top)
                gender_files = list(zip(gender_files_top, gender_files_bottom))

                # 前面（top）と背面（bottom）の画像を一緒に処理する
                for export_file_top, export_file_bottom in gender_files:
                    # ####################################

                    #　50 × 50、100 × 100　のリサイズ

                    # ####################################
                    # 画像を読み込む
                    if export_file_top:
                        image_top = Image.open(export_file_top).convert("RGBA")
                    else:
                        image_top = Image.new("RGBA", (960, 640), (0, 0, 0, 0))

                    if export_file_bottom:
                        image_bottom = Image.open(export_file_bottom).convert("RGBA")
                    else:
                        image_bottom = Image.new("RGBA", (960, 640), (0, 0, 0, 0))

                                        
                    # 男女画像 
                    if export_file_top in export_files_top_male or export_file_bottom in export_files_bottom_male:
                        silhouette_image = Image.open(silhouette_dict["シルエット_男性.png"])
                    else:
                        silhouette_image = Image.open(silhouette_dict["シルエット_女性.png"])

                    
                    # ちょっと縮小する　AI生成
                    scale = 0.93
                    for image in [image_top, image_bottom]:
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
                        finalimg = np.zeros((framey, framex, 4), np.uint8)
                        finalimg[int(-deltay + framey / 2 - resized_img.shape[0] / 2):int(-deltay + framey / 2 + resized_img.shape[0] / 2),
                                int(-deltax + framex / 2 - resized_img.shape[1] / 2):int(-deltax + framex / 2 + resized_img.shape[1] / 2)] = resized_img
                        finalimg = finalimg[int(finalimg.shape[0] / 2 - height / 2):int(finalimg.shape[0] / 2 + height / 2),
                                            int(finalimg.shape[1] / 2 - width / 2):int(finalimg.shape[1] / 2 + width / 2)]
                        image.paste(Image.fromarray(finalimg), (0,0))
                        

                    # リサイズする 両端切る
                    image_top = image_top.crop((132, 0, 828, 640))
                    image_bottom = image_bottom.crop((132, 0, 828, 640))
                    image_top = image_top.resize((696, 640), Image.LANCZOS)
                    image_bottom = image_bottom.resize((696, 640), Image.LANCZOS)


                    # 正方形にする　上下整える
                    image_top = image_top.crop((28, 0, 668, 640)) # (696-640)/2 = 28
                    image_bottom = image_bottom.crop((28, 0, 668, 640))
                    image_top = image_top.resize((640, 640), Image.LANCZOS)
                    image_bottom = image_bottom.resize((640, 640), Image.LANCZOS)
                    
                    # 縮小する
                    image_top.thumbnail((100,100), Image.LANCZOS)
                    image_bottom.thumbnail((100,100), Image.LANCZOS)
                    silhouette_image.thumbnail((100,100), Image.LANCZOS)

                    # 統合する
                    final_image = Image.alpha_composite(image_bottom.convert("RGBA"), silhouette_image.convert("RGBA"))
                    b_image = Image.alpha_composite(final_image.convert("RGBA"), image_top.convert("RGBA"))
                    
                    # ファイル名を設定する
                    if export_file_top:
                        file_name = export_file_top.name
                    else:
                        file_name = export_file_bottom.name
                    
                    # 100 × 100保存
                    binary_dict["/100x100/" + file_name] = b_image

                    # 50 × 50保存
                    b_image = b_image.resize((50, 50))
                    binary_dict["/50x50/" + file_name] = b_image


                    ####################################

                    #　640 × 640、320 ×　320　のリサイズ

                    ####################################
                   # 画像を読み込む
                    if export_file_top:
                        image_top = Image.open(export_file_top).convert("RGBA")
                    else:
                        image_top = Image.new("RGBA", (960, 640), (0, 0, 0, 0))

                    if export_file_bottom:
                        image_bottom = Image.open(export_file_bottom).convert("RGBA")
                    else:
                        image_bottom = Image.new("RGBA", (960, 640), (0, 0, 0, 0))
                    
                    # 960×640
                    if export_file_top:
                        image_top = image_top.resize((960, 640))
                        binary_dict["/960x640/" + export_file_top.name] = image_top
                    if export_file_bottom:
                        image_bottom = image_bottom.resize((960, 640))
                        binary_dict["/960x640/" + export_file_bottom.name] = image_bottom


                    # 統合する
                    image = Image.alpha_composite(image_bottom.convert("RGBA"), image_top.convert("RGBA"))

                    # ちょっと縮小する　AI生成
                    scale = scale_640
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
                    finalimg = np.zeros((framey, framex, 4), np.uint8)
                    finalimg[int(-deltay + framey / 2 - resized_img.shape[0] / 2):int(-deltay + framey / 2 + resized_img.shape[0] / 2),
                            int(-deltax + framex / 2 - resized_img.shape[1] / 2):int(-deltax + framex / 2 + resized_img.shape[1] / 2)] = resized_img
                    finalimg = finalimg[int(finalimg.shape[0] / 2 - height / 2):int(finalimg.shape[0] / 2 + height / 2),
                                        int(finalimg.shape[1] / 2 - width / 2):int(finalimg.shape[1] / 2 + width / 2)]
                    image.paste(Image.fromarray(finalimg), (0,0))
                        
                    # 不要な透明画素を除去
                    image = image.crop(image.getbbox())

                    # 画像の幅と高さを取得
                    width, height = image.size

                    # 幅で足りない分は左右に足す
                    pad_width_left = (640 - width) // 2 + horizontal_shift
                    pad_width_right = (640 - width) // 2 - horizontal_shift
                    
                    # 高さで足りない分は足す 下部微調整
                    up = vertical_shift + 15
                    pad_height = 640 - height - up
                    padding = (pad_width_left, pad_height, pad_width_right, up)
                    d_image = ImageOps.expand(image, padding)
                    
                    # 320×320を生成
                    c_image = d_image.resize((320, 320))
                    
                    # ファイル名を設定する
                    if export_file_top:
                        file_name = export_file_top.name
                    else:
                        file_name = export_file_bottom.name

                    # 統合した画像の保存（
                    binary_dict["/640x640/" + file_name] = d_image
                    binary_dict["/320x320/" + file_name] = c_image
            time.sleep(3)
        st.markdown(f'<span style="color:red">書き出しが完了しました。ダウンロードボタンが表示されるまでお待ちください。</span>', unsafe_allow_html=True)
        show_zip_download("mm_aura.zip", binary_dict)
    st.write('全てのファイルを書き出します。')
st.markdown('---')



# 320 640プレビュー処理
# if vertical_shift or horizontal_shift or scale  or preview_button1:
with st.spinner("画像生成中です..."):
    binary_dict.clear() # 初期化
    # 個別書き出し用空のファイルリスト
    selected_files = []
    cols = st.columns(3)
    i = 0
    for gender_files_top, gender_files_bottom in [(export_files_top_male, export_files_bottom_male), (export_files_top_female, export_files_bottom_female)]:
        # 前ファイルと後ろファイル足りない部分調整
        if not gender_files_top:
            gender_files_top = [None] * len(gender_files_bottom)
        if not gender_files_bottom:
            gender_files_bottom = [None] * len(gender_files_top)
        gender_files = list(zip(gender_files_top, gender_files_bottom))

        # 前面（top）と背面（bottom）の画像を一緒に処理する
        for export_file_top, export_file_bottom in gender_files:
            ####################################

            #　640 × 640、320 ×　320　のリサイズ

            ####################################
            # 画像を読み込む
            if export_file_top:
                image_top = Image.open(export_file_top).convert("RGBA")
            else:
                image_top = Image.new("RGBA", (960, 640), (0, 0, 0, 0))

            if export_file_bottom:
                image_bottom = Image.open(export_file_bottom).convert("RGBA")
            else:
                image_bottom = Image.new("RGBA", (960, 640), (0, 0, 0, 0))

            # 統合する
            image = Image.alpha_composite(image_bottom.convert("RGBA"), image_top.convert("RGBA"))

            # ちょっと縮小する　AI生成
            scale = scale_640
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
            finalimg = np.zeros((framey, framex, 4), np.uint8)
            finalimg[int(-deltay + framey / 2 - resized_img.shape[0] / 2):int(-deltay + framey / 2 + resized_img.shape[0] / 2),
                    int(-deltax + framex / 2 - resized_img.shape[1] / 2):int(-deltax + framex / 2 + resized_img.shape[1] / 2)] = resized_img
            finalimg = finalimg[int(finalimg.shape[0] / 2 - height / 2):int(finalimg.shape[0] / 2 + height / 2),
                                int(finalimg.shape[1] / 2 - width / 2):int(finalimg.shape[1] / 2 + width / 2)]
            image.paste(Image.fromarray(finalimg), (0,0))
                
            # 不要な透明画素を除去
            image = image.crop(image.getbbox())

            # 画像の幅と高さを取得
            width, height = image.size

            # 幅で足りない分は左右に足す
            pad_width_left = (640 - width) // 2 + horizontal_shift
            pad_width_right = (640 - width) // 2 - horizontal_shift

            
            # 高さで足りない分は足す 下部微調整
            up = vertical_shift + 15
            pad_height = 640 - height - up
            padding = (pad_width_left, pad_height, pad_width_right, up)
            d_image = ImageOps.expand(image, padding)
            
            # ファイル名を設定する
            if export_file_top:
                file_name = export_file_top.name
            else:
                file_name = export_file_bottom.name
            
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
                selected_files.append((export_file_top, export_file_bottom))
            
            i += 1



# 個別書き出し 空のファイルリストはプレビューの中に
with export_selected_button1:
    if st.button('個別書き出し'):
        with st.spinner("画像生成中です..."):
            binary_dict.clear() # 初期化
            #  # 前ファイルと後ろファイルを結合　一旦空白埋めてるのでＯＫ？
            # if not export_files_top:
            #     export_files_top = [None] * len(export_files_bottom)
            # if not export_files_bottom:
            #     export_files_bottom = [None] * len(export_files_top)
            # export_files = list(zip(export_files_top, export_files_bottom))

            for export_file_top, export_file_bottom in selected_files:
                # ####################################

                    #　50 × 50、100 × 100　のリサイズ

                    # ####################################
                    # 画像を読み込む
                    if export_file_top:
                        image_top = Image.open(export_file_top).convert("RGBA")
                    else:
                        image_top = Image.new("RGBA", (960, 640), (0, 0, 0, 0))

                    if export_file_bottom:
                        image_bottom = Image.open(export_file_bottom).convert("RGBA")
                    else:
                        image_bottom = Image.new("RGBA", (960, 640), (0, 0, 0, 0))

                                        
                    # 男女画像 
                    if export_file_top in export_files_top_male or export_file_bottom in export_files_bottom_male:
                        silhouette_image = Image.open(silhouette_dict["シルエット_男性.png"])
                    else:
                        silhouette_image = Image.open(silhouette_dict["シルエット_女性.png"])

                    
                    # ちょっと縮小する　AI生成
                    scale = 0.93
                    for image in [image_top, image_bottom]:
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
                        finalimg = np.zeros((framey, framex, 4), np.uint8)
                        finalimg[int(-deltay + framey / 2 - resized_img.shape[0] / 2):int(-deltay + framey / 2 + resized_img.shape[0] / 2),
                                int(-deltax + framex / 2 - resized_img.shape[1] / 2):int(-deltax + framex / 2 + resized_img.shape[1] / 2)] = resized_img
                        finalimg = finalimg[int(finalimg.shape[0] / 2 - height / 2):int(finalimg.shape[0] / 2 + height / 2),
                                            int(finalimg.shape[1] / 2 - width / 2):int(finalimg.shape[1] / 2 + width / 2)]
                        image.paste(Image.fromarray(finalimg), (0,0))
                        

                    # リサイズする 両端切る
                    image_top = image_top.crop((132, 0, 828, 640))
                    image_bottom = image_bottom.crop((132, 0, 828, 640))
                    image_top = image_top.resize((696, 640), Image.LANCZOS)
                    image_bottom = image_bottom.resize((696, 640), Image.LANCZOS)


                    # 正方形にする　上下整える
                    image_top = image_top.crop((28, 0, 668, 640)) # (696-640)/2 = 28
                    image_bottom = image_bottom.crop((28, 0, 668, 640))
                    image_top = image_top.resize((640, 640), Image.LANCZOS)
                    image_bottom = image_bottom.resize((640, 640), Image.LANCZOS)
                    
                    # 縮小する
                    image_top.thumbnail((100,100), Image.LANCZOS)
                    image_bottom.thumbnail((100,100), Image.LANCZOS)
                    silhouette_image.thumbnail((100,100), Image.LANCZOS)

                    # 統合する
                    final_image = Image.alpha_composite(image_bottom.convert("RGBA"), silhouette_image.convert("RGBA"))
                    b_image = Image.alpha_composite(final_image.convert("RGBA"), image_top.convert("RGBA"))
                    
                    # ファイル名を設定する
                    if export_file_top:
                        file_name = export_file_top.name
                    else:
                        file_name = export_file_bottom.name
                    
                    # 100 × 100保存
                    binary_dict["/100x100/" + file_name] = b_image

                    # 50 × 50保存
                    b_image = b_image.resize((50, 50))
                    binary_dict["/50x50/" + file_name] = b_image


                    ####################################

                    #　640 × 640、320 ×　320　のリサイズ

                    ####################################
                   # 画像を読み込む
                    if export_file_top:
                        image_top = Image.open(export_file_top).convert("RGBA")
                    else:
                        image_top = Image.new("RGBA", (960, 640), (0, 0, 0, 0))

                    if export_file_bottom:
                        image_bottom = Image.open(export_file_bottom).convert("RGBA")
                    else:
                        image_bottom = Image.new("RGBA", (960, 640), (0, 0, 0, 0))
                    
                    # 960×640
                    if export_file_top:
                        image_top = image_top.resize((960, 640))
                        binary_dict["/960x640/" + export_file_top.name] = image_top
                    if export_file_bottom:
                        image_bottom = image_bottom.resize((960, 640))
                        binary_dict["/960x640/" + export_file_bottom.name] = image_bottom


                    # 統合する
                    image = Image.alpha_composite(image_bottom.convert("RGBA"), image_top.convert("RGBA"))

                    # ちょっと縮小する　AI生成
                    scale = scale_640
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
                    finalimg = np.zeros((framey, framex, 4), np.uint8)
                    finalimg[int(-deltay + framey / 2 - resized_img.shape[0] / 2):int(-deltay + framey / 2 + resized_img.shape[0] / 2),
                            int(-deltax + framex / 2 - resized_img.shape[1] / 2):int(-deltax + framex / 2 + resized_img.shape[1] / 2)] = resized_img
                    finalimg = finalimg[int(finalimg.shape[0] / 2 - height / 2):int(finalimg.shape[0] / 2 + height / 2),
                                        int(finalimg.shape[1] / 2 - width / 2):int(finalimg.shape[1] / 2 + width / 2)]
                    image.paste(Image.fromarray(finalimg), (0,0))
                        
                    # 不要な透明画素を除去
                    image = image.crop(image.getbbox())

                    # 画像の幅と高さを取得
                    width, height = image.size

                    # 幅で足りない分は左右に足す
                    pad_width_left = (640 - width) // 2 + horizontal_shift
                    pad_width_right = (640 - width) // 2 - horizontal_shift
                    
                    # 高さで足りない分は足す 下部微調整
                    up = vertical_shift + 15
                    pad_height = 640 - height - up
                    padding = (pad_width_left, pad_height, pad_width_right, up)
                    d_image = ImageOps.expand(image, padding)
                    
                    # 320×320を生成
                    c_image = d_image.resize((320, 320))
                    
                    # ファイル名を設定する
                    if export_file_top:
                        file_name = export_file_top.name
                    else:
                        file_name = export_file_bottom.name

                    # 統合した画像の保存（
                    binary_dict["/640x640/" + file_name] = d_image
                    binary_dict["/320x320/" + file_name] = c_image
            time.sleep(3)
        st.markdown(f'<span style="color:red">書き出しが完了しました。ダウンロードボタンが表示されるまでお待ちください。</span>', unsafe_allow_html=True)
        show_zip_download("mm_aura2.zip", binary_dict)
    st.write('チェックを入れたファイルを書き出します。')
