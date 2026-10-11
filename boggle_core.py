"""Boggle solving + scoring (pandas).

Rules (from the official instructions):
  * words of 3+ letters, formed from cubes that touch horizontally, vertically
    or diagonally, no cube used twice in one word
  * the Qu cube counts as two letters
  * scoring: 3-4 letters = 1, 5 = 2, 6 = 3, 7 = 5, 8+ = 11
"""
import datetime
import io
import json
import re
import urllib.parse
import urllib.request
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


def score_players(grid, players: dict, dictionary, min_len=3):
    """Boggle scoring for 2+ players.

    players: {name: [words...]}. Every word is first checked like score_words (long
    enough, on the board, in the dictionary, not repeated in the player's own list).
    Then, as in the real game, any valid word that appears on more than one player's
    list is crossed off for everybody and scores nothing.

    Returns (tables, leaderboard, shared):
      tables      {name: DataFrame(word, letters, status, points, shared with, path)}
      leaderboard DataFrame(Rank, Player, Score, Words counted, Crossed off (shared), Not counted)
      shared      DataFrame(word, letters, players, points lost each)
    """
    tables = {name: score_words(grid, entries, dictionary, min_len) for name, entries in players.items()}
    holders = {}
    for name, t in tables.items():
        for w in t.loc[t.status == "Counts", "word"]:
            holders.setdefault(w, []).append(name)
    shared_words = {w: names for w, names in holders.items() if len(names) > 1}

    for name, t in tables.items():
        t["shared with"] = ""
        hit = (t.status == "Counts") & t.word.isin(shared_words)
        t.loc[hit, "shared with"] = t.loc[hit, "word"].map(
            lambda w: ", ".join(p for p in shared_words[w] if p != name))
        t["points lost"] = 0
        t.loc[hit, "points lost"] = t.loc[hit, "points"]
        t.loc[hit, "status"] = "Crossed off (shared)"
        t.loc[hit, "points"] = 0
        tables[name] = t[["word", "letters", "status", "points", "shared with", "path (row,col)"]]

    board = pd.DataFrame([{
        "Player": name,
        "Score": int(t.points.sum()),
        "Words counted": int((t.status == "Counts").sum()),
        "Crossed off (shared)": int((t.status == "Crossed off (shared)").sum()),
        "Not counted": int((~t.status.isin(["Counts", "Crossed off (shared)"])).sum()),
    } for name, t in tables.items()])
    board = board.sort_values("Score", ascending=False, kind="stable").reset_index(drop=True)
    board.insert(0, "Rank", board.Score.rank(method="min", ascending=False).astype(int))

    shared = pd.DataFrame(
        [{"word": w, "letters": len(w), "players": ", ".join(n), "points lost each": points(len(w))}
         for w, n in sorted(shared_words.items(), key=lambda kv: (-len(kv[0]), kv[0]))],
        columns=["word", "letters", "players", "points lost each"])
    return tables, board, shared


# ---------------------------------------------------------------------------
# Optional live check against Merriam-Webster's Collegiate Dictionary API
# (free, non-commercial use, needs your own key from https://dictionaryapi.com)
# ---------------------------------------------------------------------------
MW_URL = "https://www.dictionaryapi.com/api/v3/references/collegiate/json/{word}?key={key}"
# entries that are not ordinary playable words
MW_EXCLUDED_FL = {"abbreviation", "prefix", "suffix", "combining form", "symbol", "biographical name",
                  "geographical name", "trademark"}
_MW_CACHE = {}                    # word -> bool; lives as long as the server process
_MW_USAGE = {"day": None, "count": 0}


class MWError(Exception):
    """The Merriam-Webster service could not answer (bad key, network, quota)."""


def mw_entries_valid(word: str, payload) -> bool:
    """Is `word` a playable word according to a Collegiate API response?

    Found words come back as a list of entry objects; unknown words come back as an empty
    list or a list of suggestion strings. A word is valid when it is one of an ordinary
    (main-section) entry's `stems`, which covers plurals, verb forms and variants. Names,
    abbreviations, prefixes/suffixes and idioms are rejected, as in Boggle and Scrabble.
    Proper nouns are rejected because their stems keep the capital letter.
    """
    if not isinstance(payload, list):
        return False
    word = word.lower()
    for entry in payload:
        if not isinstance(entry, dict):
            continue                                     # a suggestion string
        meta = entry.get("meta") or {}
        if meta.get("section", "alpha") != "alpha":
            continue
        if str(entry.get("fl", "")).lower() in MW_EXCLUDED_FL:
            continue
        if word in (meta.get("stems") or []):            # exact, case-sensitive match
            return True
    return False


def _mw_fetch(word: str, key: str, timeout: float = 8.0):
    """One HTTP call to the Collegiate API; returns the decoded JSON."""
    url = MW_URL.format(word=urllib.parse.quote(word), key=urllib.parse.quote(key))
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        raise MWError(f"network error ({exc})") from exc
    try:
        return json.loads(raw)
    except ValueError as exc:                            # e.g. "Invalid API key. Not subscribed ..."
        raise MWError(raw.strip()[:120] or "unreadable reply") from exc


class MerriamWebsterChecker:
    """Set-like object: `word in checker` asks Merriam-Webster (cached; falls back to the
    built-in list when the service can't answer or the daily quota is nearly used up)."""

    def __init__(self, api_key, fallback, daily_limit=1000, reserve=50):
        self.key, self.fallback = api_key, fallback
        self.limit, self.reserve = daily_limit, reserve
        self.api_calls = self.cache_hits = 0
        self.fallback_words, self.last_error = [], ""

    # -- quota -------------------------------------------------------------
    @staticmethod
    def _today():
        return datetime.datetime.now(datetime.timezone.utc).date().isoformat()

    def used_today(self):
        return _MW_USAGE["count"] if _MW_USAGE["day"] == self._today() else 0

    def remaining(self):
        return max(0, self.limit - self.reserve - self.used_today())

    def pending(self, words):
        """How many of `words` still need an API call."""
        return len({w.lower() for w in words if w.lower() not in _MW_CACHE})

    # -- lookups -----------------------------------------------------------
    def __contains__(self, word):
        word = str(word).lower()
        if word in _MW_CACHE:
            self.cache_hits += 1
            return _MW_CACHE[word]
        if not self.remaining():
            self.last_error = "daily limit reached"
            self.fallback_words.append(word)
            return word in self.fallback
        try:
            payload = _mw_fetch(word, self.key)
        except MWError as exc:
            self.last_error = str(exc)
            self.fallback_words.append(word)
            return word in self.fallback
        if _MW_USAGE["day"] != self._today():
            _MW_USAGE.update(day=self._today(), count=0)
        _MW_USAGE["count"] += 1
        self.api_calls += 1
        _MW_CACHE[word] = valid = mw_entries_valid(word, payload)
        return valid

    def filter(self, df):
        """Keep only the rows of a word table (column 'word') that Merriam-Webster accepts."""
        return df[[w in self for w in df["word"]]].reset_index(drop=True)
