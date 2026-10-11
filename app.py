"""Boggle photo solver  -  run with:  streamlit run app.py"""
import io

import cv2
import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image, ImageOps

import boggle_core as core
import boggle_vision as vision

st.set_page_config(page_title="Boggle Photo Solver", layout="wide")


@st.cache_resource(show_spinner="Loading dictionary...")
def get_dictionary():
    words = core.load_words()
    return words, core.build_prefixes(words)


def decode(file) -> np.ndarray:
    """Uploaded file -> BGR array, honouring the phone's EXIF rotation."""
    img = ImageOps.exif_transpose(Image.open(file)).convert("RGB")
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def to_df_grid(grid):
    return pd.DataFrame(grid, columns=["1", "2", "3", "4"], index=["row 1", "row 2", "row 3", "row 4"])


st.title("Boggle Photo Solver")
st.caption("Upload a photo of a Boggle board (tilted or rotated letters are fine). "
           "Check the grid it read, fix any mistakes, then solve.")

with st.sidebar:
    st.header("Settings")
    min_len = st.slider("Minimum word length", 3, 5, 3)
    custom = st.file_uploader("Use my own word list (.txt, one word per line)", type=["txt"])
    st.markdown(
        "**Scoring**  \n3–4 letters = 1 pt · 5 = 2 · 6 = 3 · 7 = 5 · 8+ = 11  \n"
        "Qu counts as two letters.")

tab_up, tab_cam = st.tabs(["Upload a photo", "Use the camera"])
with tab_up:
    up = st.file_uploader("Photo of the board", type=["png", "jpg", "jpeg", "webp", "bmp"])
with tab_cam:
    cam = st.camera_input("Take a picture of the board")
photo = up or cam

if photo is None:
    st.info("Waiting for a photo. Tips: shoot from straight above, keep the whole tray in view, "
            "and avoid glare on the cubes.")
    st.stop()

key = f"{getattr(photo, 'name', 'camera')}-{photo.size}"
if st.session_state.get("photo_key") != key:           # new photo -> read it
    st.session_state.photo_key = key
    with st.spinner("Reading the board..."):
        st.session_state.result = vision.read_grid(decode(photo))
    st.session_state.pop("solved", None)
res = st.session_state.result

c1, c2 = st.columns(2)
with c1:
    st.subheader("Your photo")
    st.image(photo, width="stretch")
with c2:
    st.subheader("What the app saw")
    st.image(cv2.cvtColor(vision.annotate(res), cv2.COLOR_BGR2RGB), width="stretch")
    if not res["tray_found"]:
        st.warning("Couldn't find the dark tray - the whole photo was used. Try a closer, straighter shot.")
    elif not res["cubes_found"]:
        st.warning("Couldn't locate each cube precisely - the board was split evenly instead.")

st.subheader("1 · Check the letters")
st.caption("Edit any cell that is wrong (type **Qu** for the Qu cube). Row 1 is the top of the photo.")
edited = st.data_editor(to_df_grid(res["grid"]), width="stretch", key=f"grid-{key}",
                        column_config={c: st.column_config.TextColumn(c, max_chars=2)
                                       for c in ["1", "2", "3", "4"]})

shaky = [d for d in res["detail"] if not d["letter"] or d["score"] < 0.60]
if shaky:
    st.warning("Please double-check: " + "; ".join(
        f"row {d['row']}, col {d['col']} (read '{d['letter'] or '?'}'"
        + (f", could also be {', '.join(a for a, _ in d['alts'][1:3])}" if d["alts"][1:] else "") + ")"
        for d in shaky))

def clean(v):
    v = (v or "").strip().upper()
    return "QU" if v == "Q" else v          # the Qu cube may be typed as Q


grid = [[clean(v) for v in row] for row in edited.values.tolist()]
bad = [(r + 1, c + 1) for r in range(4) for c in range(4)
       if not (len(grid[r][c]) == 1 and grid[r][c].isalpha()) and grid[r][c] != "QU"]

st.subheader("2 · Solve")
if bad:
    st.error(f"Each cell needs one letter (or Qu). Fix: {bad}")
    st.stop()

if st.button("Find all words", type="primary"):
    if custom is not None:
        words = {w.strip().lower() for w in io.TextIOWrapper(custom, encoding="utf-8") if w.strip().isalpha()}
        prefixes = core.build_prefixes(words)
    else:
        words, prefixes = get_dictionary()
    st.session_state.solved = core.solve(grid, words, prefixes, min_len)

df = st.session_state.get("solved")
if df is not None:
    summary = core.summarize(df)
    m1, m2, m3 = st.columns(3)
    m1.metric("Words found", len(df))
    m2.metric("Total points", int(df.points.sum()))
    m3.metric("Longest word", df.word.iloc[0] if len(df) else "-")
    st.caption("Remember: any word another player also finds is crossed off for everyone.")

    left, right = st.columns([1, 2])
    with left:
        st.dataframe(summary, hide_index=True, width="stretch")
    with right:
        st.dataframe(df, hide_index=True, width="stretch", height=420)

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        df.to_excel(xw, sheet_name="All words", index=False)
        summary.to_excel(xw, sheet_name="Summary", index=False)
    d1, d2 = st.columns(2)
    d1.download_button("Download Excel", buf.getvalue(), "boggle_words.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    d2.download_button("Download CSV", df.to_csv(index=False), "boggle_words.csv", "text/csv")
