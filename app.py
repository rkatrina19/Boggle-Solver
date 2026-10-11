"""Boggle photo solver  -  run with:  streamlit run app.py"""
import io
import os

import cv2
import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image, ImageOps

import boggle_core as core
import boggle_vision as vision
import players_ui

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
    n = len(grid)
    return pd.DataFrame(grid, columns=[str(i + 1) for i in range(n)],
                        index=[f"row {i + 1}" for i in range(n)])


ACCENT = "#d9480f"

st.markdown(f"""
<style>
.hero {{ text-align:center; padding: 0.5rem 0 0.25rem; }}
.hero h1 {{ font-size: 2.6rem; font-weight: 800; letter-spacing: -0.02em; margin: 0; }}
.hero p {{ opacity: .7; margin: .35rem 0 0; font-size: 1.05rem; }}
.pick-title {{ text-align:center; font-size: .8rem; font-weight: 700; letter-spacing: .14em;
              text-transform: uppercase; opacity: .6; margin: 1.6rem 0 .9rem; }}
.card {{ border: 2px solid rgba(128,128,128,.28); border-radius: 18px; padding: 1.1rem 1rem .9rem;
        text-align:center; transition: all .15s ease; background: rgba(128,128,128,.06); }}
.card.on {{ border-color: {ACCENT}; background: {ACCENT}14; box-shadow: 0 6px 22px {ACCENT}33; }}
.mini {{ display:grid; gap:4px; width:116px; margin: 0 auto .75rem; }}
.mini i {{ aspect-ratio:1; border-radius:5px; background: rgba(128,128,128,.38); display:block; }}
.card.on .mini i {{ background: {ACCENT}; }}
.card .name {{ font-size: 1.25rem; font-weight: 800; }}
.card .sub {{ font-size: .88rem; opacity: .65; margin-bottom: .2rem; }}
.icon-wrap {{ height:116px; display:flex; align-items:center; justify-content:center; margin-bottom:.75rem; }}
.dots {{ display:grid; gap:9px; }}
.dots i {{ border-radius:50%; background: rgba(128,128,128,.38); display:block; aspect-ratio:1; }}
.card.on .dots i {{ background: {ACCENT}; }}
div[class*="st-key-card-"] {{ position: relative; padding-bottom: 1rem; }}   /* markdown trims 1rem; keep the overlay covering the whole card */
div[class*="st-key-card-"] div[data-testid="stElementContainer"]:has(button),
div[class*="st-key-card-"] div[data-testid="stElementContainer"]:has(button) > div,
div[class*="st-key-card-"] button {{
    position: absolute !important; inset: 0 !important; width: 100% !important; height: 100% !important;
    min-width: 0 !important; margin: 0 !important; padding: 0 !important; }}
div[class*="st-key-card-"] div[data-testid="stElementContainer"]:has(button) {{ z-index: 3; }}
div[class*="st-key-card-"] button {{ opacity: 0; cursor: pointer; }}
div[class*="st-key-card-"]:hover .card {{ border-color: {ACCENT}; transform: translateY(-2px);
    box-shadow: 0 8px 24px {ACCENT}26; }}
div[class*="st-key-card-"]:has(button:focus-visible) .card {{ outline: 3px solid {ACCENT}; outline-offset: 2px; }}
.rule {{ height:1px; background: rgba(128,128,128,.22); margin: 1.4rem 0 .6rem; }}
</style>
<div class="hero">
  <h1>Boggle Photo Solver</h1>
  <p>Snap or upload a photo of your board. We read the letters and find every word.</p>
</div>
<div class="pick-title">Step 1 &middot; How are you playing?</div>
""", unsafe_allow_html=True)

st.session_state.setdefault("board_n", 4)
st.session_state.setdefault("game_mode", "solo")


def pick_mode(m):
    st.session_state.game_mode = m


MODES = {
    "solo": ("Just me", "Boggle Checker", "Find every word or score your list", 1, "46px"),
    "multi": ("Multiplayer", "2 to 4 players", "Check each other's words, shared ones are crossed off", 4, "84px"),
}
_, mid0, _ = st.columns([1, 3, 1])
for col, (m, (name, sub, blurb, dots, width)) in zip(mid0.columns(2, gap="large"), MODES.items()):
    on = st.session_state.game_mode == m
    cols_css = "1fr 1fr" if dots == 4 else "1fr"
    with col, st.container(key=f"card-mode-{m}"):         # the whole card is the button
        st.markdown(
            f'<div class="card{" on" if on else ""}">'
            f'<div class="icon-wrap"><div class="dots" style="grid-template-columns:{cols_css};width:{width}">'
            f'{"<i></i>" * dots}</div></div>'
            f'<div class="name">{name}</div><div class="sub">{sub}</div>'
            f'<div class="sub" style="font-size:.78rem">{blurb}</div></div>',
            unsafe_allow_html=True)
        st.button(f"{name} {sub}", key=f"mode-{m}", on_click=pick_mode, args=(m,))
mode = st.session_state.game_mode

st.markdown('<div class="pick-title">Step 2 &middot; Choose your board size</div>', unsafe_allow_html=True)


def pick(n):
    st.session_state.board_n = n


BOARDS = {4: ("4x4", "Classic Boggle", "16 cubes"), 5: ("5x5", "Big Boggle", "25 cubes")}
_, mid, _ = st.columns([1, 3, 1])
card_cols = mid.columns(2, gap="large")
for col, (n, (name, sub, cubes)) in zip(card_cols, BOARDS.items()):
    on = st.session_state.board_n == n
    with col, st.container(key=f"card-board-{n}"):        # the whole card is the button
        st.markdown(
            f'<div class="card{" on" if on else ""}">'
            f'<div class="mini" style="grid-template-columns:repeat({n},1fr)">{"<i></i>" * (n * n)}</div>'
            f'<div class="name">{name}</div><div class="sub">{sub} &middot; {cubes}</div></div>',
            unsafe_allow_html=True)
        st.button(f"{name} {sub}", key=f"pick-{n}", on_click=pick, args=(n,))
N = st.session_state.board_n

st.markdown('<div class="rule"></div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("Settings")
    min_len = st.slider("Minimum word length", 3, 5, 3 if N == 4 else 4, key=f"minlen-{N}",
                        help="Classic Boggle accepts 3+ letters; Big Boggle is usually played with 4+.")
    st.markdown("**Check words against**")
    word_source = st.radio("Dictionary", ["Built-in word list", "Merriam-Webster (live)"],
                           label_visibility="collapsed",
                           help="Built-in: the ENABLE Scrabble word list, works offline. Merriam-Webster: each word is "
                                "looked up in Merriam-Webster's current Collegiate Dictionary through their free API "
                                "(you need your own key).")
    mw_key = ""
    if word_source.startswith("Merriam"):
        try:
            saved = st.secrets.get("MW_API_KEY", "")
        except Exception:                                    # no secrets file
            saved = ""
        mw_key = st.text_input("Merriam-Webster API key", value=saved or os.environ.get("MW_API_KEY", ""),
                               type="password", help="Free for non-commercial use at dictionaryapi.com "
                               "(Collegiate Dictionary, up to 1,000 lookups a day).").strip()
        st.caption("Word checks powered by [Merriam-Webster's Collegiate Dictionary API](https://dictionaryapi.com). "
                   "Words that can't be checked fall back to the built-in list.")
    custom, list_mode = None, "dict"
    if mode == "solo":
        custom = st.file_uploader("Use my own word list", type=["txt", "csv", "xlsx"],
                                  help="Upload .txt, .csv or .xlsx. Words can be in any column or sheet, one or several per cell.")
        if custom is not None:
            list_mode = "score" if st.radio(
                "What is this list?",
                ["The words I found (score them)", "A dictionary to search with"],
                help="Score: checks each of your words against the board and the dictionary and "
                     "totals your points. Dictionary: finds every board word that appears in your list."
            ).startswith("The words") else "dict"
    st.markdown(
        "**Scoring**  \n3–4 letters = 1 pt · 5 = 2 · 6 = 3 · 7 = 5 · 8+ = 11  \n"
        "Qu counts as two letters.")

def get_validator():
    """The word checker to use for validity: Merriam-Webster (live) if chosen and a key is set, else the built-in set."""
    base, _ = get_dictionary()
    if word_source.startswith("Merriam"):
        if mw_key:
            return core.MerriamWebsterChecker(mw_key, fallback=base)
        st.sidebar.warning("Enter your Merriam-Webster API key to use it. Using the built-in list for now.")
    return base


def mw_note(checker):
    """One-line summary of what a Merriam-Webster check did (None for the built-in list)."""
    if not isinstance(checker, core.MerriamWebsterChecker):
        return None
    note = (f"Checked with Merriam-Webster: {checker.api_calls} new lookups, {checker.cache_hits} reused from earlier "
            f"checks, about {checker.remaining()} lookups left today.")
    if checker.fallback_words:
        shown = ", ".join(sorted(set(checker.fallback_words))[:8])
        note += (f" {len(set(checker.fallback_words))} word(s) could not be checked ({checker.last_error}) and used the "
                 f"built-in list instead: {shown}.")
    return note


st.markdown('<div class="pick-title" style="margin-top:.4rem">Step 3 &middot; Add your photo</div>',
            unsafe_allow_html=True)
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

key = f"{getattr(photo, 'name', 'camera')}-{photo.size}-{N}"
if st.session_state.get("photo_key") != key:           # new photo -> read it
    st.session_state.photo_key = key
    with st.spinner("Reading the board..."):
        st.session_state.result = vision.read_grid(decode(photo), N)
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

st.subheader("Step 4 · Check the letters")
st.caption("Edit any cell that is wrong (type **Qu** for the Qu cube). Row 1 is the top of the photo.")
edited = st.data_editor(to_df_grid(res["grid"]), width="stretch", key=f"grid-{key}",
                        column_config={str(i + 1): st.column_config.TextColumn(str(i + 1), max_chars=2)
                                       for i in range(N)})

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
bad = [(r + 1, c + 1) for r in range(N) for c in range(N)
       if not (len(grid[r][c]) == 1 and grid[r][c].isalpha()) and grid[r][c] != "QU"]

st.subheader("Step 5 · Solve and score" if mode == "solo" else "Step 5 · Play with friends")
if bad:
    st.error(f"Each cell needs one letter (or Qu). Fix: {bad}")
    st.stop()

if mode == "solo":
    score_mode = custom is not None and list_mode == "score"
    if st.button("Score my words" if score_mode else "Find all words", type="primary"):
        entries = None
        if custom is not None:
            try:
                entries = core.parse_wordlist_entries(custom.name, custom.getvalue())
            except Exception as exc:
                st.error(f"Couldn't read that word list ({exc}). Try .txt, .csv or .xlsx with one word per cell.")
                st.stop()
            if not entries:
                st.error("No words found in that file. Put one word per cell (or per line).")
                st.stop()
        dictionary, dict_prefixes = get_dictionary()
        validator = get_validator()
        st.session_state.mine = None
        st.session_state.mw_note = None
        if score_mode:                                   # score the player's words, keep the full list for comparison
            st.session_state.solved = core.solve(grid, dictionary, dict_prefixes, min_len)
            st.session_state.mine = core.score_words(grid, entries, validator, min_len)
            st.session_state.mw_note = mw_note(validator)
        elif entries is not None:                        # custom dictionary (Merriam-Webster setting not used)
            words = set(entries)
            st.toast(f"Using your word list: {len(words):,} words")
            st.session_state.solved = core.solve(grid, words, core.build_prefixes(words), min_len)
        else:
            found = core.solve(grid, dictionary, dict_prefixes, min_len)
            if isinstance(validator, core.MerriamWebsterChecker):
                need = validator.pending(found.word)
                if need <= validator.remaining():
                    with st.spinner(f"Checking {len(found)} words with Merriam-Webster..."):
                        kept = validator.filter(found)
                    st.session_state.mw_note = mw_note(validator) + f" {len(found) - len(kept)} candidate words were not accepted."
                    found = kept
                else:
                    st.session_state.mw_note = (f"Not enough Merriam-Webster lookups left today ({validator.remaining()}) "
                                                f"to check {need} words, so the built-in list is shown unchecked.")
            st.session_state.solved = found

    df = st.session_state.get("solved")
    mine = st.session_state.get("mine")


    def excel_bytes(sheets: dict) -> bytes:
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as xw:
            for name, frame in sheets.items():
                frame.to_excel(xw, sheet_name=name, index=False)
        return out.getvalue()


    XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    if mine is not None and df is not None:
        counted = mine[mine.status == "Counts"]
        possible = int(df.points.sum())
        my_score = int(counted.points.sum())
        st.markdown("### My score")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("My score", my_score)
        m2.metric("Words counted", f"{len(counted)} of {len(mine)}")
        m3.metric("Possible on this board", possible)
        m4.metric("Share of possible", f"{my_score / possible:.0%}" if possible else "-")
        st.caption("Words that another player also found are crossed off for everyone in a real game, "
                   "so subtract those from your score. 'Possible' and 'missed' words come from the built-in list.")
        if st.session_state.get("mw_note"):
            st.caption(st.session_state.mw_note)

        palette = {"Counts": "rgba(46,160,67,.22)"}
        styled = mine.style.apply(
            lambda row: [f"background-color: {palette.get(row['status'], 'rgba(220,53,69,.18)')}"] * len(row), axis=1)
        st.dataframe(styled, hide_index=True, width="stretch", height=min(420, 38 + 35 * len(mine)))

        reasons = mine[mine.status != "Counts"].status.value_counts()
        if len(reasons):
            st.caption("Not counted: " + " · ".join(f"{n} {k.lower()}" for k, n in reasons.items()))

        missed = df[~df.word.isin(counted.word)].sort_values(["points", "letters", "word"], ascending=[False, False, True])
        with st.expander(f"Words you missed ({len(missed)}, worth {int(missed.points.sum())} more points)"):
            st.dataframe(missed, hide_index=True, width="stretch", height=360)
        with st.expander("All possible words on this board"):
            st.dataframe(df, hide_index=True, width="stretch", height=360)

        d1, d2 = st.columns(2)
        d1.download_button("Download my score (Excel)", excel_bytes({"My score": mine, "Missed": missed, "All words": df}),
                           "boggle_my_score.xlsx", XLSX)
        d2.download_button("Download my score (CSV)", mine.to_csv(index=False), "boggle_my_score.csv", "text/csv")
    elif df is not None:
        summary = core.summarize(df)
        m1, m2, m3 = st.columns(3)
        m1.metric("Words found", len(df))
        m2.metric("Total points", int(df.points.sum()))
        m3.metric("Longest word", df.word.iloc[0] if len(df) else "-")
        st.caption("Remember: any word another player also finds is crossed off for everyone.")
        if st.session_state.get("mw_note"):
            st.caption(st.session_state.mw_note)

        left, right = st.columns([1, 2])
        with left:
            st.dataframe(summary, hide_index=True, width="stretch")
        with right:
            st.dataframe(df, hide_index=True, width="stretch", height=420)

        d1, d2 = st.columns(2)
        d1.download_button("Download Excel", excel_bytes({"All words": df, "Summary": summary}),
                           "boggle_words.xlsx", XLSX)
        d2.download_button("Download CSV", df.to_csv(index=False), "boggle_words.csv", "text/csv")

else:
    players_ui.render(grid, min_len, get_dictionary, get_validator, mw_note)
