# Boggle Photo Solver

Upload a photo of a Boggle board (classic 4x4 or Big Boggle 5x5) → the app reads the 16 cubes (even when letters are
sideways or upside down), lets you fix any misread letter, then finds every word and
scores it with the official Boggle points.

## Open it any time

**Option 1: permanent link (recommended).** Host it free on Streamlit Community Cloud so it
has a fixed web address that works from any device, with nothing running on your computer:

1. Go to https://share.streamlit.io and sign in with GitHub.
2. Click **Create app**, then **Deploy a public app from GitHub**.
3. Repository: `rkatrina19/Boggle-Solver` · Branch: `main` · Main file path: `app.py`.
4. Choose a custom subdomain (for example `boggle-solver`) and click **Deploy**.

Your app will live at `https://<your-subdomain>.streamlit.app`. Bookmark it. Apps that go
unused for a while are put to sleep; open the link and press "Yes, get this app back up!".
Every push to `main` updates the live app automatically.

**Option 2: one-click on your computer.** Download or clone this repo, then double-click
`run_boggle.command` (Mac; if blocked, right-click > Open) or `run_boggle.bat` (Windows).
It installs the packages on first run and opens the app in your browser. The link
(`http://localhost:8501`) only works while that window stays open.

**Option 3: terminal.**

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

No separate OCR program is needed. Python 3.10+.

Command-line version (no browser):

```bash
python solve_photo.py sample_photo.png
python solve_photo.py my_board.jpg --csv words.csv --debug-image what_it_saw.png
python solve_photo.py big_board.jpg --size 5 --min-len 4   # Big Boggle 5x5
python solve_photo.py --grid "GAUT PRMR DOLA ESIC"      # skip the photo, type the letters (Q = Qu)
```

## Board size
Choose **4 x 4 (Boggle)** or **5 x 5 (Big Boggle)** in the sidebar before uploading. The
minimum word length defaults to 3 for 4x4 and 4 for 5x5 (Big Boggle is usually played with
4+ letters); you can change it. From the command line use `--size 5 --min-len 4`.

## Your own word list
In the sidebar, **Use my own word list** accepts `.txt`, `.csv` or `.xlsx`:
- Put the words in any column, on any sheet; several words in one cell (separated by spaces,
  commas or semicolons) also work.
- A first row labelled `word`, `words`, `term`, `list` and similar is skipped as a header.
- Only purely alphabetic entries are used; numbers and punctuation are ignored. Keep the file
  to words only, since any other text in it would be read as words too.
- After uploading, choose what the list is:
  - **The words I found (score them)** – your game score. Each word is checked against the
    board and the dictionary. You get your total points, how many words counted, the share of
    the possible score, and a status for every word: *Counts*, *Not on the board*,
    *Not a dictionary word*, *Too short* or *Duplicate*. A "Words you missed" list shows
    what you could still have found, and everything can be downloaded as Excel or CSV.
  - **A dictionary to search with** – finds every board word that appears in your list.
- In a real game, words another player also found are crossed off for everyone, so subtract
  those from your score.

## Just me or multiplayer
Step 1 asks how you are playing: **Just me** (a Boggle checker: find every word, or score your own
list) or **Multiplayer** (2 to 4 players check each other's words). The rest of the page shows
only the tools for that choice.

## Checking words with Merriam-Webster
The built-in list is ENABLE, not Merriam-Webster. Merriam-Webster's dictionary is proprietary and
there is no downloadable word list (the official Scrabble list built on it, NWL2023, is licensed
by NASPA). What the app *can* do is look words up in Merriam-Webster's current Collegiate
Dictionary through their free API:

1. Get a free key at https://dictionaryapi.com (choose the *Collegiate Dictionary* reference).
2. In the sidebar, set **Check words against** to **Merriam-Webster (live)** and paste your key.
   To avoid pasting it each time, save it as `MW_API_KEY`: in Streamlit Cloud under
   *App settings > Secrets* (`MW_API_KEY = "your-key"`), or locally in `.streamlit/secrets.toml`
   (this file is git-ignored) or as an environment variable.

How it is used: a word counts if it is a regular (main-section) entry or one of its listed forms
(plurals, verb forms, variants). Names, abbreviations, prefixes/suffixes and idioms do not count.
Results are cached while the app runs. **Score my words** and **Multiplayer** look up the words
that were actually written down. **Find all words** checks the built-in list's candidates (about
200 lookups for a typical 4x4 board). "Possible", "missed" and "nobody found" lists always come from
the built-in list. If a word can't be checked (bad key, no connection, daily limit), the built-in
list is used for it and the app says so.

Limits from Merriam-Webster's terms: free for **non-commercial** use only, 1,000 lookups per key per
day (shared by everyone using your hosted app), and apps must display the Merriam-Webster logo, so add
it from your developer account if you publish the app. This feature needs internet access and has been
tested here with simulated responses; try it once with your own key.

## Play with friends (2 to 4 players)
Choose **Multiplayer** in Step 1, then in Step 5:
1. Pick 2, 3 or 4 players and type each name.
2. Each player types or pastes the words they found (one per line or separated by commas),
   or uploads a `.txt`, `.csv` or `.xlsx` list. Both can be combined.
3. Click **Compare lists and score**. The app checks every word against the board and the
   dictionary, then applies the real Boggle rule: any word that appears on more than one
   player's list is crossed off for everyone and scores nothing.

You get a ranked leaderboard (ties share a rank), a table per player with the status of every
word (*Counts*, *Crossed off (shared)*, *Not on the board*, *Not a dictionary word*,
*Too short*, *Duplicate*), the list of shared words, the board words nobody found, and an
Excel download. **Match** keeps a running total over several rounds with an optional target
score (the instructions suggest 50 or 100) and announces who reaches it first.

## Tips for a good photo
- Shoot from straight above with the whole dark tray in the frame.
- Avoid glare and shadows across the cubes; a plain background helps.
- The photo can be tilted or rotated, and cubes can be turned any way.
- Always glance at the "Check the letters" table before solving. Low-confidence
  cubes are flagged with their runner-up guesses.

## Rules built in
- Words of 3+ letters, formed from touching cubes (horizontal, vertical, diagonal),
  no cube used twice in one word.
- Qu is one cube but counts as two letters.
- Points: 3–4 letters = 1, 5 = 2, 6 = 3, 7 = 5, 8+ = 11.
- Dictionary: the built-in ENABLE Scrabble list (plurals and verb forms, no proper nouns), or, optionally,
  a live check against Merriam-Webster (see below).
  It is generous, so a few obscure words are accepted. You can upload your own word list in
  the sidebar (see below). In a real game, words that other players also find are crossed off for
  everyone, so your actual score will be lower than the total shown.

## How the photo reading works (`boggle_vision.py`)
1. Find the dark tray and straighten it (perspective warp).
2. Locate the 16 cube faces; missing ones (e.g. merged by glare) are filled in from the
   spacing of the others.
3. In each cube, isolate the black glyph. A thin detached bar is the **underline** printed
   under M, W and Z; where it sits (below / left / above / right) also tells how the cube
   is turned, which removes the M/W and N/Z confusion.
4. Compare the glyph with templates of A–Z and Qu (three bold sans fonts, several stroke
   weights) in all four 90° rotations, using shape correlation plus a skeleton-distance
   check (this separates look-alikes such as R and P).

Tested on randomly generated, tilted/perspective photos (25 boards each, all letters
including Qu, M, W, Z): 100% of cubes read correctly for both 4x4 (400 cubes) and 5x5
(625 cubes). Real photos vary, so the correction table is there for the occasional miss.

## Files
- `app.py` – Streamlit app
- `solve_photo.py` – command-line version
- `boggle_core.py` – solver and scoring, solo and multiplayer (pandas)
- `players_ui.py` – the multiplayer tab
- `boggle_vision.py` – photo → grid
- `enable1.txt` – word list · `fonts/` – fonts used to build letter templates
- `sample_photo.png`, `sample_synthetic.png`, `sample_5x5.png` – photos to try (4x4, 4x4, 5x5)
- `tests/` – generates fake board photos and measures reading accuracy (`python tests/eval_reader.py 5 25`)
