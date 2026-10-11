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


def parse_wordlist_entries(filename: str, data: bytes) -> list:
    """Words from an uploaded list, in file order (duplicates kept): .txt (one per line), .csv or .xlsx (every cell of
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
    return [tok for row in rows for cell in row for tok in _tokens(cell)]


def parse_wordlist(filename: str, data: bytes) -> set:
    """Same as parse_wordlist_entries but as a set of unique words."""
    return set(parse_wordlist_entries(filename, data))


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


def find_on_board(grid, word):
    """Return the list of (row, col) cubes spelling `word`, or None if it can't be formed."""
    cubes = [[str(c).strip().lower() for c in row] for row in grid]
    rows, cols = len(cubes), len(cubes[0])
    word = word.lower()

    def dfs(r, c, pos, path):
        cube = cubes[r][c]
        if not cube or not word.startswith(cube, pos):
            return None
        path = path + [(r, c)]
        pos += len(cube)
        if pos == len(word):
            return path
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                nr, nc = r + dr, c + dc
                if (dr or dc) and 0 <= nr < rows and 0 <= nc < cols and (nr, nc) not in path:
                    found = dfs(nr, nc, pos, path)
                    if found:
                        return found
        return None

    for r in range(rows):
        for c in range(cols):
            found = dfs(r, c, 0, [])
            if found:
                return found
    return None


def score_words(grid, entries, dictionary, min_len=3) -> pd.DataFrame:
    """Score a player's own list against the board.

    A word counts only if it is long enough, can be traced on the board, is a real
    dictionary word and was not already listed. Returns one row per entry:
    word, letters, status, points, path.
    """
    seen, rows = set(), []
    for w in entries:
        w = w.lower()
        path = find_on_board(grid, w)
        if w in seen:
            status = "Duplicate"
        elif len(w) < min_len:
            status = "Too short"
        elif path is None:
            status = "Not on the board"
        elif w not in dictionary:
            status = "Not a dictionary word"
        else:
            status = "Counts"
        seen.add(w)
        rows.append({"word": w, "letters": len(w), "status": status,
                     "points": points(len(w)) if status == "Counts" else 0,
                     "path (row,col)": " -> ".join(f"({r+1},{c+1})" for r, c in path) if path else ""})
    return pd.DataFrame(rows, columns=["word", "letters", "status", "points", "path (row,col)"])
