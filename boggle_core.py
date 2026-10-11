"""Boggle solving + scoring (pandas).

Rules (from the official instructions):
  * words of 3+ letters, formed from cubes that touch horizontally, vertically
    or diagonally, no cube used twice in one word
  * the Qu cube counts as two letters
  * scoring: 3-4 letters = 1, 5 = 2, 6 = 3, 7 = 5, 8+ = 11
"""
import io
import re
from pathlib import Path
import pandas as pd

DEFAULT_WORDLIST = Path(__file__).with_name("enable1.txt")


def points(n_letters: int) -> int:
    if n_letters <= 4:
        return 1
    return {5: 2, 6: 3, 7: 5}.get(n_letters, 11)


def load_words(path=DEFAULT_WORDLIST) -> set:
    with open(path, encoding="utf-8") as f:
        return {w.strip().lower() for w in f if w.strip().isalpha()}


HEADER_LABELS = {"word", "words", "wordlist", "term", "terms", "entry", "entries",
                 "vocabulary", "vocab", "list", "dictionary"}


def _tokens(cell):
    for tok in re.split(r"[\s,;|]+", str(cell).strip().strip("\"'")):
        tok = tok.strip("\"'").lower()
        if tok.isalpha():
            yield tok


def parse_wordlist(filename: str, data: bytes) -> set:
    """Words from an uploaded list: .txt (one per line), .csv or .xlsx (every cell of
    every column / sheet; a cell may hold several words separated by spaces, commas or
    semicolons). A first row containing a header label such as 'word' is skipped.
    Entries that are not purely alphabetic are ignored."""
    ext = Path(filename).suffix.lower()
    rows = []                                           # list of lists of cell strings
    if ext == ".xlsx":
        frames = pd.read_excel(io.BytesIO(data), sheet_name=None, header=None, dtype=str)
        for df in frames.values():
            rows_df = df.fillna("").to_numpy().tolist()
            if rows_df and any(str(c).strip().lower() in HEADER_LABELS for c in rows_df[0]):
                rows_df = rows_df[1:]
            rows += rows_df
    else:                                               # .csv and .txt: read as plain text
        text = None
        for enc in ("utf-8-sig", "utf-16", "latin-1"):
            try:
                text = data.decode(enc)
                break
            except UnicodeError:
                continue
        lines = text.splitlines()
        if ext == ".csv" and lines and any(t in HEADER_LABELS for t in _tokens(lines[0])):
            lines = lines[1:]
        rows = [[ln] for ln in lines]
    return {tok for row in rows for cell in row for tok in _tokens(cell)}


def build_prefixes(words) -> set:
    return {w[:i] for w in words for i in range(1, len(w) + 1)}


def solve(grid, words, prefixes=None, min_len=3) -> pd.DataFrame:
    """grid: list of rows, each a list of cube strings ('A', 'QU', ...).

    Returns a DataFrame: word, letters, points, path.
    """
    if prefixes is None:
        prefixes = build_prefixes(words)
    cubes = [[str(c).strip().lower() for c in row] for row in grid]
    rows, cols = len(cubes), len(cubes[0])
    found = {}

    def dfs(r, c, path, word):
        word += cubes[r][c]
        if word not in prefixes:
            return
        path = path + [(r, c)]
        if len(word) >= min_len and word in words and word not in found:
            found[word] = path
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                nr, nc = r + dr, c + dc
                if (dr or dc) and 0 <= nr < rows and 0 <= nc < cols and (nr, nc) not in path:
                    dfs(nr, nc, path, word)

    for r in range(rows):
        for c in range(cols):
            if cubes[r][c]:
                dfs(r, c, [], "")

    df = pd.DataFrame(
        [{"word": w, "letters": len(w), "points": points(len(w)),
          "path (row,col)": " -> ".join(f"({r+1},{c+1})" for r, c in p)}
         for w, p in found.items()],
        columns=["word", "letters", "points", "path (row,col)"])
    return (df.sort_values(["letters", "word"], ascending=[False, True])
              .reset_index(drop=True))


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["letters", "words", "points_each", "total_points"])
    s = (df.groupby("letters")
           .agg(words=("word", "count"), points_each=("points", "first"),
                total_points=("points", "sum"))
           .reset_index().sort_values("letters", ascending=False))
    return s.reset_index(drop=True)
