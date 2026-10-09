"""Boggle solver for the practice grid in the instructions, using pandas.

Grid (as printed in the instruction figures):
    G A U T
    P R M R
    D O L A
    E S I C

Rules applied: words of 3+ letters, built from adjacent cubes
(horizontal, vertical, diagonal), no cube reused within a word.
Scoring: 3-4 letters = 1, 5 = 2, 6 = 3, 7 = 5, 8+ = 11.
Dictionary: ENABLE (standard Scrabble word list: includes plurals and verb
forms, excludes proper nouns).
"""
import sys
import pandas as pd

GRID = ["GAUT",
        "PRMR",
        "DOLA",
        "ESIC"]
N = 4
WORDLIST, OUT_XLSX, OUT_CSV = sys.argv[1:4]


def points(n):
    if n <= 4:
        return 1
    return {5: 2, 6: 3, 7: 5}.get(n, 11)


with open(WORDLIST, encoding="utf-8") as f:
    words = {w.strip().lower() for w in f if w.strip().isalpha()}
prefixes = {w[:i] for w in words for i in range(1, len(w) + 1)}

found = {}  # word -> first path found


def dfs(r, c, path, word):
    word += GRID[r][c].lower()
    if word not in prefixes:
        return
    path = path + [(r, c)]
    if len(word) >= 3 and word in words and word not in found:
        found[word] = path
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            nr, nc = r + dr, c + dc
            if (dr or dc) and 0 <= nr < N and 0 <= nc < N and (nr, nc) not in path:
                dfs(nr, nc, path, word)


for r in range(N):
    for c in range(N):
        dfs(r, c, [], "")

df = pd.DataFrame(
    [{"word": w, "letters": len(w), "points": points(len(w)),
      "path (row,col)": " -> ".join(f"({r+1},{c+1})" for r, c in p)}
     for w, p in found.items()]
).sort_values(["letters", "word"], ascending=[False, True]).reset_index(drop=True)

summary = (df.groupby("letters")
           .agg(words=("word", "count"), points_each=("points", "first"),
                total_points=("points", "sum"))
           .reset_index())
total = pd.DataFrame([{"letters": "Total", "words": summary.words.sum(),
                       "points_each": "", "total_points": summary.total_points.sum()}])
summary = pd.concat([summary, total], ignore_index=True)

print(summary.to_string(index=False))
print()
for n, grp in df.groupby("letters", sort=False):
    print(f"{n}-letter ({grp.points.iloc[0]} pt each): " + ", ".join(grp.word))

with pd.ExcelWriter(OUT_XLSX) as xw:
    df.to_excel(xw, sheet_name="All words", index=False)
    summary.to_excel(xw, sheet_name="Summary", index=False)
df.to_csv(OUT_CSV, index=False)
