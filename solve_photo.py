"""Command-line version:  python solve_photo.py board.jpg [--min-len 3] [--csv out.csv]

Reads the board from the photo, prints the grid it saw, then every word with points.
If a letter is wrong, override the grid:  --grid "GAUT PRMR DOLA ESIC"  (use Q for the Qu cube)
"""
import argparse

import cv2
import pandas as pd
from PIL import Image, ImageOps
import numpy as np

import boggle_core as core
import boggle_vision as vision


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("photo", nargs="?", help="photo of the board")
    ap.add_argument("--grid", help='skip the photo: 4 rows of 4 letters, e.g. "GAUT PRMR DOLA ESIC"')
    ap.add_argument("--min-len", type=int, default=3)
    ap.add_argument("--csv", help="save the word list to this CSV file")
    ap.add_argument("--debug-image", help="save the annotated board to this file")
    a = ap.parse_args()

    if a.grid:
        rows = a.grid.upper().split()
        grid = [["QU" if ch == "Q" else ch for ch in row] for row in rows]
    elif a.photo:
        img = ImageOps.exif_transpose(Image.open(a.photo)).convert("RGB")
        res = vision.read_grid(cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR))
        grid = res["grid"]
        if a.debug_image:
            cv2.imwrite(a.debug_image, vision.annotate(res))
        shaky = [d for d in res["detail"] if not d["letter"] or d["score"] < 0.60]
        for d in shaky:
            print(f"! check row {d['row']}, col {d['col']}: read '{d['letter'] or '?'}', "
                  f"candidates {[x for x, _ in d['alts']]}")
    else:
        ap.error("give a photo or --grid")

    print("\nGrid read:")
    for row in grid:
        print("  " + " ".join(f"{c:>2}" for c in row))

    words = core.load_words()
    df = core.solve(grid, words, min_len=a.min_len)
    print(f"\n{len(df)} words, {int(df.points.sum())} points\n")
    print(core.summarize(df).to_string(index=False))
    print()
    for n, grp in df.groupby("letters", sort=False):
        print(f"{n}-letter ({grp.points.iloc[0]} pt each): " + ", ".join(grp.word))
    if a.csv:
        df.to_csv(a.csv, index=False)
        print(f"\nSaved {a.csv}")


if __name__ == "__main__":
    main()
