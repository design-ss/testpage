
import streamlit as st

st.title('書き出し用アプリ')
st.caption('書き出し用のアプリです。')

st.write('**使い方**')
st.markdown(
    '<p style="line-height: 1.5;">'
    '①ペイントソフトで各パーツをpngで保存<br>'
    '②左メニューから書き出したいパーツのアプリを選ぶ<br>'
    '③pngファイルをアップロード<br>'
    '④ボタンを押して書き出し<br>'
    '⑤zipをダウンロード<br>'
    '⑥zipを解凍※1<br>'
    '⑦Pngyuで圧縮する※2<br>'
    '</p>'
     '<p style="font-size: 80%; margin-top: -10px;">'
    '　　※1　Windowsでデフォルトの解凍を使うとエラーが出ます。7-Zipなどの解凍ソフトを使用してください。<br>'
    '　　　　 7-Zip https://7-zip.opensource.jp/<br>'
     '　　※2　Pngyu https://nukesaq88.github.io/Pngyu/ja.html<br>'
    '　　　　  Macで稀にPngyuが使えないことがあるようです。その場合はお知らせください。'
    '</p>',
    unsafe_allow_html=True
)

st.markdown('---')

st.write('**注意**')
st.markdown(
    '<p style="line-height: 1.5;">'
    '・今のところ圧縮機能はないので、Pngyuなどで別途圧縮が必要です。<br>'
    '・属性画像や、シルエット画像等は都度アップロードが必要です。Trelloにフォルダの場所を記載してますので自分のPCに保存のうえお使いください。<br>'
    '</p>',
    unsafe_allow_html=True
)

st.markdown('---')

st.markdown(
    '<p style="line-height: 1.5;">'
    '・Photoshopが動かない、大量に同じ種類のものを書き出す時などにお使いください。<br>'
     '・Pythonの知識がある方、ローカルで動かせる方はzipファイルを生成せずに、直接ローカルに書き出しできます。githubお渡しするので、書き出し先にローカルパスを指定し、必要モジュールインストールのうえ動かしてください。<br>'
    '</p>',
    unsafe_allow_html=True
)
st.write()
