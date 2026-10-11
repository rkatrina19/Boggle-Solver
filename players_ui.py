"""Multiplayer tab: 2-4 players enter their words, the app checks them and crosses off shared words.

Rendered from app.py inside the "Play with friends" tab.
"""
import io
import re

import pandas as pd
import streamlit as st

import boggle_core as core

STATUS_COLORS = {
    "Counts": "rgba(46,160,67,.22)",
    "Crossed off (shared)": "rgba(255,193,7,.28)",
}
INVALID_COLOR = "rgba(220,53,69,.18)"
MEDALS = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}


def _style(df: pd.DataFrame):
    return df.style.apply(
        lambda row: [f"background-color: {STATUS_COLORS.get(row['status'], INVALID_COLOR)}"] * len(row), axis=1)


def _excel(sheets: dict) -> bytes:
    out = io.BytesIO()
    used = set()
    with pd.ExcelWriter(out, engine="openpyxl") as xw:
        for name, frame in sheets.items():
            clean = re.sub(r"[\[\]\*\?/\\:]", "", name)[:31] or "Sheet"
            base, k = clean, 2
            while clean in used:                         # sheet names must be unique
                clean = f"{base[:28]}_{k}"
                k += 1
            used.add(clean)
            frame.to_excel(xw, sheet_name=clean, index=False)
    return out.getvalue()


def _collect_players(count: int):
    """Draw one input column per player; return {name: [entries]} plus any problems found."""
    cols = st.columns(count, gap="medium")
    players, problems, seen = {}, [], set()
    for i, col in enumerate(cols):
        with col:
            st.markdown(f"**Player {i + 1}**")
            name = st.text_input("Name", value=f"Player {i + 1}", key=f"pname-{i}", label_visibility="collapsed",
                                 placeholder=f"Player {i + 1}").strip() or f"Player {i + 1}"
            typed = st.text_area("Words", key=f"pwords-{i}", height=200, label_visibility="collapsed",
                                 placeholder="Type or paste words,\none per line or separated by commas")
            file = st.file_uploader("or upload a list", type=["txt", "csv", "xlsx"], key=f"pfile-{i}",
                                    help=".txt, .csv or .xlsx; words are added to anything typed above.")
        entries = []
        if typed.strip():
            entries += core.parse_wordlist_entries("typed.txt", typed.encode("utf-8"))
        if file is not None:
            try:
                entries += core.parse_wordlist_entries(file.name, file.getvalue())
            except Exception as exc:
                problems.append(f"{name}: couldn't read {file.name} ({exc}).")
        if name in seen:                                 # keep names unique
            k = 2
            while f"{name} ({k})" in seen:
                k += 1
            name = f"{name} ({k})"
        seen.add(name)
        players[name] = entries
    return players, problems


def _leaderboard(board: pd.DataFrame):
    top = int(board.Score.max())
    winners = board[board.Score == top].Player.tolist()
    if top == 0:
        st.info("Nobody scored this round.")
    elif len(winners) == 1:
        st.success(f"**{winners[0]}** wins this round with **{top}** points.")
    else:
        st.success(f"Tie between **{' and '.join(winners)}** at **{top}** points.")
    shown = board.copy()
    shown["Rank"] = shown.Rank.map(lambda r: MEDALS.get(r, str(r)))
    st.dataframe(shown, hide_index=True, width="stretch")


def _match(result_id: int, board: pd.DataFrame):
    """Running tournament: add rounds, track totals against a target score."""
    st.markdown("#### Match")
    st.caption("Play several rounds: add each round here, and the first to reach the target score wins "
               "(the instructions suggest 50 or 100).")
    st.session_state.setdefault("match_rounds", [])
    st.session_state.setdefault("match_added", set())
    target = int(st.number_input("Play to (points, 0 = no target)", min_value=0, step=10, value=0, key="match_target"))

    a, b, _ = st.columns([1.3, 1, 3])
    already = result_id in st.session_state.match_added
    if a.button("Add this round to the match", disabled=already, type="primary"):
        st.session_state.match_rounds.append(dict(zip(board.Player, board.Score)))
        st.session_state.match_added.add(result_id)
        st.rerun()
    if b.button("Reset match", disabled=not st.session_state.match_rounds):
        st.session_state.match_rounds = []
        st.session_state.match_added = set()
        st.rerun()
    if already:
        st.caption("This round is already in the match. Compare new lists to add another round.")

    rounds = st.session_state.match_rounds
    if not rounds:
        return
    table = pd.DataFrame(rounds).fillna(0).astype(int)
    table.index = [f"Round {i + 1}" for i in range(len(table))]
    totals = table.sum()
    table.loc["Total"] = totals
    st.dataframe(table, width="stretch")
    leader_score = int(totals.max())
    leaders = totals[totals == leader_score].index.tolist()
    if target and leader_score >= target:
        who = leaders[0] if len(leaders) == 1 else " and ".join(leaders)
        st.success(f"Match over: **{who}** reached {target}+ points ({leader_score}).")
    elif target:
        st.progress(min(leader_score / target, 1.0),
                    text=f"{' / '.join(leaders)} lead with {leader_score} of {target} points")


def render(grid, min_len, get_dictionary, get_validator=None, mw_note=None):
    st.caption("Each player writes down the words they found. The app checks every word against the board and "
               "the dictionary, then crosses off any word that appears on more than one list, as in the real game.")
    count = st.radio("Number of players", [2, 3, 4], horizontal=True, format_func=lambda n: f"{n} players",
                     key="player_count")
    players, problems = _collect_players(count)
    for p in problems:
        st.error(p)

    ready = [n for n, e in players.items() if e]
    if st.button("Compare lists and score", type="primary", key="compare"):
        if len(ready) < 2:
            st.error("Enter words for at least two players to compare.")
        else:
            dictionary, prefixes = get_dictionary()
            validator = get_validator() if get_validator else dictionary
            tables, board, shared = core.score_players(grid, {n: players[n] for n in ready}, validator, min_len)
            everything = {w for n in ready for w in players[n]}
            full = core.solve(grid, dictionary, prefixes, min_len)
            st.session_state.play = dict(
                id=st.session_state.get("play_id", 0) + 1, tables=tables, board=board, shared=shared,
                unfound=full[~full.word.isin(everything)].reset_index(drop=True), possible=int(full.points.sum()),
                note=mw_note(validator) if mw_note else None)
            st.session_state.play_id = st.session_state.play["id"]

    res = st.session_state.get("play")
    if not res:
        return
    st.markdown("### Results")
    _leaderboard(res["board"])
    st.caption(f"Possible on this board: {res['possible']} points (built-in list). Words crossed off lose their "
               "points for every player who listed them.")
    if res.get("note"):
        st.caption(res["note"])

    tabs = st.tabs(list(res["tables"]) + ["Shared words", "Nobody found"])
    for tab, (name, table) in zip(tabs, res["tables"].items()):
        with tab:
            row = res["board"][res["board"].Player == name].iloc[0]
            m1, m2, m3 = st.columns(3)
            m1.metric("Score", int(row.Score))
            m2.metric("Counted", int(row["Words counted"]))
            m3.metric("Crossed off", int(row["Crossed off (shared)"]))
            st.dataframe(_style(table), hide_index=True, width="stretch", height=min(420, 38 + 35 * len(table)))
    with tabs[-2]:
        if res["shared"].empty:
            st.write("No shared words this round.")
        else:
            st.dataframe(res["shared"], hide_index=True, width="stretch")
    with tabs[-1]:
        un = res["unfound"]
        st.write(f"{len(un)} words worth {int(un.points.sum())} points were on the board but on nobody's list.")
        st.dataframe(un.sort_values(["points", "letters", "word"], ascending=[False, False, True]),
                     hide_index=True, width="stretch", height=360)

    sheets = {"Leaderboard": res["board"], "Shared words": res["shared"], "Nobody found": res["unfound"]}
    sheets.update(res["tables"])
    st.download_button("Download results (Excel)", _excel(sheets), "boggle_players.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    _match(res["id"], res["board"])
