import streamlit as st
from PIL import Image, ImageDraw, ImageOps
import io
import zipfile

def getPreviewImage(image, border_size=1, border_color='red'):
    if image.mode == "P":
        converted_img = image.convert("RGBA")
        img_with_border = ImageOps.expand(converted_img, border=border_size, fill=border_color)
        return img_with_border
    
    img_with_border = ImageOps.expand(image, border=border_size, fill=border_color)
    return img_with_border

def add_border_around_opaque(image, border_size=1, border_color=(255, 0, 0, 255)):
    if image.mode != "RGBA":
        image = image.convert("RGBA")

    border_image = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(border_image)

    for x in range(image.width):
        for y in range(image.height):
            if image.getpixel((x, y))[3] > 0:
                draw.rectangle((x - border_size, y - border_size, x + border_size, y + border_size), outline=border_color)

    border_image.alpha_composite(image)
    return border_image

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



st.set_page_config(page_title='消し残しチェック')

st.title('消し残しチェック')

st.write('書き出しが上手くいかない時は小さいゴミが画面に散らばってるかもしれないので、これでチェックしてください。')

check_files = st.file_uploader("チェックしたいファイルを選択", type='png', accept_multiple_files=True, key="check_files")

st.markdown('---')

border_width = st.slider('フチの太さ', min_value=0, max_value=10, value=5)

selected_files = []

if check_files:
    num_files = len(check_files)
    for i in range(0, num_files, 2):
        col1, col2 = st.columns(2)
        with col1:
            if i < num_files:
                image1 = Image.open(check_files[i])
                bordered_image1 = add_border_around_opaque(getPreviewImage(image1), border_size=border_width)
                st.image(bordered_image1, use_column_width=True)
                file_name = check_files[i].name
                if len(file_name) > 6:
                    file_name = file_name[:6] + "..."
                if st.checkbox(file_name, key=f"select_{check_files[i].name}"):
                    selected_files.append((check_files[i], bordered_image1))
        with col2:
            if i + 1 < num_files:
                image2 = Image.open(check_files[i + 1])
                bordered_image2 = add_border_around_opaque(getPreviewImage(image2), border_size=border_width)
                st.image(bordered_image2, use_column_width=True)
                file_name = check_files[i + 1].name
                if len(file_name) > 6:
                    file_name = file_name[:6] + "..."
                if st.checkbox(file_name, key=f"select_{check_files[i + 1].name}"):
                    selected_files.append((check_files[i + 1], bordered_image2))

if selected_files:
    binary_dict = dict()
    for export_file, image in selected_files:
        new_name = export_file.name.rsplit('.', 1)
        new_name = new_name[0] + "_消し残し." + new_name[1]
        binary_dict[new_name] = image

    if st.button('選択されたファイルをダウンロード'):
        show_zip_download("消し残し.zip", binary_dict)
