"""Read a Boggle grid from a photo (no external OCR engine needed).

Pipeline
  1. find the dark tray, straighten it (perspective warp)
  2. locate the 16 cube faces (bright "holes" inside the dark tray)
  3. for each cube, isolate the black glyph; a thin detached bar is the
     underline printed under M, W and Z - it also tells us how the cube is
     turned (the bar sits below the letter when the letter is upright)
  4. compare the glyph with font templates in all 4 rotations and keep the
     best match, plus runner-up candidates so the user can correct mistakes
"""
from functools import lru_cache
from pathlib import Path
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from skimage.morphology import skeletonize

FONT_DIR = Path(__file__).with_name("fonts")
FONT_FILES = ["LiberationSans-Bold.ttf", "DejaVuSans-Bold.ttf", "Poppins-Bold.ttf"]
LABELS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + ["QU"]
UNDERLINED = ["M", "W", "Z"]
CANVAS = 64
STROKE_VARIANTS = (-5, 0, 6, 12)   # px at 160 px font size
CHAMFER_WEIGHT = 0.075
WARP = 960


# --------------------------------------------------------------------------
# templates
# --------------------------------------------------------------------------
def _prepare(binary: np.ndarray):
    """binary: 2-D array, glyph pixels > 0.
    Returns dict(vec, ar, skel, dt) or None.
      vec  - blurred, zero-mean, unit-norm image (for correlation)
      ar   - width / height of the glyph
      skel - (n, 2) skeleton points, dt - distance-to-skeleton map (chamfer)"""
    ys, xs = np.nonzero(binary)
    if len(xs) == 0:
        return None
    crop = binary[ys.min():ys.max() + 1, xs.min():xs.max() + 1].astype(np.float32)
    h, w = crop.shape
    scale = (CANVAS - 8) / max(h, w)
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
    crop = cv2.resize(crop, (nw, nh), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((CANVAS, CANVAS), np.float32)
    y0, x0 = (CANVAS - nh) // 2, (CANVAS - nw) // 2
    canvas[y0:y0 + nh, x0:x0 + nw] = crop
    skel = skeletonize(canvas > 0.5)
    sk = np.argwhere(skel)
    if len(sk) == 0:
        sk = np.argwhere(canvas > 0.5)
    inv = np.full((CANVAS, CANVAS), 255, np.uint8)
    inv[sk[:, 0], sk[:, 1]] = 0
    dt = cv2.distanceTransform(inv, cv2.DIST_L2, 3)
    blurred = cv2.GaussianBlur(canvas, (3, 3), 0)
    v = blurred - blurred.mean()
    n = np.linalg.norm(v)
    return dict(vec=v / n if n else v, ar=w / h, skel=sk, dt=dt)


@lru_cache(maxsize=1)
def _templates():
    """label -> list of prepared templates (one per bundled font / stroke weight)."""
    out = {lab: [] for lab in LABELS}
    for fname in FONT_FILES:
        path = FONT_DIR / fname
        if not path.exists():
            continue
        font = ImageFont.truetype(str(path), 160)
        for lab in LABELS:
            text = "Qu" if lab == "QU" else lab
            img = Image.new("L", (500, 300), 0)
            ImageDraw.Draw(img).text((20, 20), text, fill=255, font=font)
            base = (np.array(img) > 128).astype(np.uint8)
            for grow in STROKE_VARIANTS:          # thinner / bolder versions
                if grow == 0:
                    shaped = base
                else:
                    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * abs(grow) + 1,) * 2)
                    shaped = cv2.dilate(base, k) if grow > 0 else cv2.erode(base, k)
                p = _prepare(shaped)
                if p is not None:
                    out[lab].append(p)
    return out


def _score(glyph_bin: np.ndarray, allowed):
    """Best (score, rotation k) for every allowed label.
    score = correlation - aspect-ratio penalty - skeleton (chamfer) distance."""
    temps = _templates()
    res = {}
    for k in range(4):
        g = _prepare(np.rot90(glyph_bin, k))
        if g is None:
            continue
        for lab in allowed:
            for t in temps[lab]:
                chamfer = 0.5 * (t["dt"][g["skel"][:, 0], g["skel"][:, 1]].mean()
                                 + g["dt"][t["skel"][:, 0], t["skel"][:, 1]].mean())
                s = (float((g["vec"] * t["vec"]).sum())
                     - 0.35 * abs(math.log(g["ar"] / t["ar"]))
                     - CHAMFER_WEIGHT * chamfer)
                if lab not in res or s > res[lab][0]:
                    res[lab] = (s, k)
    return res


# --------------------------------------------------------------------------
# step 1-2: tray and cube detection
# --------------------------------------------------------------------------
def _order(pts):
    pts = np.array(pts, np.float32)
    s, d = pts.sum(1), np.diff(pts, axis=1).ravel()
    return np.array([pts[s.argmin()], pts[d.argmin()], pts[s.argmax()], pts[d.argmax()]], np.float32)


def _dark_mask(gray):
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, dark = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return dark


def straighten(img_bgr):
    """Return the tray warped to a square (or the whole image if not found)."""
    h, w = img_bgr.shape[:2]
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    dark = _dark_mask(gray)
    dark = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    cnts, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = [c for c in cnts if cv2.contourArea(c) < 0.97 * h * w]
    if not cnts:
        return cv2.resize(img_bgr, (WARP, WARP)), False
    c = max(cnts, key=cv2.contourArea)
    if cv2.contourArea(c) < 0.08 * h * w:
        return cv2.resize(img_bgr, (WARP, WARP)), False
    hull = cv2.convexHull(c)
    approx = cv2.approxPolyDP(hull, 0.03 * cv2.arcLength(hull, True), True)
    quad = approx.reshape(-1, 2) if len(approx) == 4 else cv2.boxPoints(cv2.minAreaRect(c))
    src = _order(quad)
    dst = np.array([[0, 0], [WARP, 0], [WARP, WARP], [0, WARP]], np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(img_bgr, M, (WARP, WARP)), True


def _cluster_1d(values, tol):
    values = sorted(values)
    groups = [[values[0]]]
    for v in values[1:]:
        if v - groups[-1][-1] <= tol:
            groups[-1].append(v)
        else:
            groups.append([v])
    return [float(np.mean(g)) for g in groups]


def _fit_lattice(boxes):
    """Place detected cube boxes on a 4x4 lattice; missing cubes (e.g. two cubes
    merged by glare) are filled in from the spacing of the others."""
    cx = [(b[0] + b[2]) / 2 for b in boxes]
    cy = [(b[1] + b[3]) / 2 for b in boxes]
    size = float(np.median([b[2] - b[0] for b in boxes])), float(np.median([b[3] - b[1] for b in boxes]))
    xs, ys = _cluster_1d(cx, 0.4 * size[0]), _cluster_1d(cy, 0.4 * size[1])
    if len(xs) < 2 or len(ys) < 2 or len(xs) > 4 or len(ys) > 4:
        return None
    px = float(np.median(np.diff(xs))) if len(xs) > 1 else None
    py = float(np.median(np.diff(ys))) if len(ys) > 1 else None
    # the tray was warped to a square, so the lattice is centred on the image
    ix = lambda v: int(np.clip(round((v - WARP / 2) / px + 1.5), 0, 3))
    iy = lambda v: int(np.clip(round((v - WARP / 2) / py + 1.5), 0, 3))
    cells = {}
    for b, x, y in zip(boxes, cx, cy):
        cells[(iy(y), ix(x))] = b
    out = []
    for r in range(4):
        row = []
        for c in range(4):
            if (r, c) in cells:
                row.append(cells[(r, c)])
            else:
                x = WARP / 2 + (c - 1.5) * px
                y = WARP / 2 + (r - 1.5) * py
                row.append((int(x - size[0] / 2), int(y - size[1] / 2),
                            int(x + size[0] / 2), int(y + size[1] / 2)))
        out.append(row)
    return out


def find_cubes(warped_bgr):
    """Return 4x4 list of (x0, y0, x1, y1) boxes, and whether they were detected
    (False -> evenly divided fallback)."""
    gray = cv2.cvtColor(warped_bgr, cv2.COLOR_BGR2GRAY)
    dark = _dark_mask(gray)
    cnts, hier = cv2.findContours(dark, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    area_all = WARP * WARP
    holes = {}
    if hier is not None:
        for i, c in enumerate(cnts):
            parent = hier[0][i][3]
            if parent == -1:
                continue
            a = cv2.contourArea(c)
            x, y, w, h = cv2.boundingRect(c)
            if 0.02 * area_all < a < 0.085 * area_all and 0.6 < w / h < 1.6 and a > 0.55 * w * h:
                holes.setdefault(parent, []).append((x, y, x + w, y + h))
    if holes:
        best = max(holes.values(), key=len)
        areas = [(b[2] - b[0]) * (b[3] - b[1]) for b in best]
        med = np.median(areas)
        best = [b for b, a in zip(best, areas) if 0.6 * med < a < 1.5 * med]
        if len(best) >= 9:                      # enough cubes to infer the lattice
            rows = _fit_lattice(best)
            if rows is not None:
                return rows, True
    step = WARP / 4
    rows = [[(int(c * step), int(r * step), int((c + 1) * step), int((r + 1) * step))
             for c in range(4)] for r in range(4)]
    return rows, False


# --------------------------------------------------------------------------
# step 3-4: reading one cube
# --------------------------------------------------------------------------
def _glyph_parts(cell_gray):
    """Return (letter_mask, bar_direction) for one cube crop.
    bar_direction: None or one of 'below','left','above','right' (as seen in the photo)."""
    h, w = cell_gray.shape
    blur = cv2.GaussianBlur(cell_gray, (3, 3), 0)
    _, dark = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    n, lab, stats, cent = cv2.connectedComponentsWithStats(dark, connectivity=8)
    comps = []
    for i in range(1, n):
        x, y, cw, ch, a = stats[i]
        touches = x <= 0 or y <= 0 or x + cw >= w or y + ch >= h
        if touches or a < 0.004 * h * w or a > 0.6 * h * w:
            continue
        comps.append(dict(i=i, x=x, y=y, w=cw, h=ch, a=a, c=cent[i]))
    if not comps:
        return None, None
    bar, direction = None, None
    if len(comps) >= 2:
        main = max(comps, key=lambda c: c["a"])
        for c in comps:
            if c is main:
                continue
            long_, short_ = max(c["w"], c["h"]), min(c["w"], c["h"])
            if long_ / max(short_, 1) >= 3.0 and long_ >= 0.5 * max(main["w"], main["h"]):
                horizontal = c["w"] >= c["h"]
                # a horizontal bar must sit above/below the letter, a vertical bar left/right
                dx, dy = c["c"][0] - main["c"][0], c["c"][1] - main["c"][1]
                if horizontal and abs(dy) > 0.3 * main["h"]:
                    bar, direction = c, "below" if dy > 0 else "above"
                elif not horizontal and abs(dx) > 0.3 * main["w"]:
                    bar, direction = c, "right" if dx > 0 else "left"
    keep = [c["i"] for c in comps if c is not bar]
    mask = np.isin(lab, keep).astype(np.uint8) * 255
    return mask, direction


# bar position in the photo -> number of 90-degree counter-clockwise turns
# (np.rot90 k) that bring the cube upright (bar below the letter)
_BAR_TO_K = {"below": 0, "left": 1, "above": 2, "right": 3}


def read_cube(cell_bgr):
    gray = cv2.cvtColor(cell_bgr, cv2.COLOR_BGR2GRAY)
    mask, direction = _glyph_parts(gray)
    if mask is None:
        return dict(letter="", score=0.0, alts=[], underline=False, turns=0)
    if direction:
        k_up = _BAR_TO_K[direction]
        scores = _score(np.rot90(mask, k_up) > 0, UNDERLINED)
        turns = k_up
    else:
        scores = _score(mask > 0, [l for l in LABELS])
        turns = None
    ranked = sorted(((s, lab, k) for lab, (s, k) in scores.items()), reverse=True)
    best = ranked[0]
    return dict(letter=best[1], score=round(float(best[0]), 3),
                alts=[(lab, round(float(s), 3)) for s, lab, _ in ranked[:4]],
                underline=bool(direction),
                turns=turns if turns is not None else best[2])


def read_grid(image):
    """image: numpy BGR array. Returns dict(grid, detail, warped, cubes_found)."""
    h, w = image.shape[:2]
    if max(h, w) > 1400:
        s = 1400 / max(h, w)
        image = cv2.resize(image, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    warped, tray_found = straighten(image)
    boxes, cubes_found = find_cubes(warped)
    grid, detail = [], []
    for r in range(4):
        row = []
        for c in range(4):
            x0, y0, x1, y1 = boxes[r][c]
            pad = int(0.06 * (x1 - x0))
            crop = warped[max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad]
            res = read_cube(crop)
            res.update(row=r + 1, col=c + 1)
            detail.append(res)
            row.append(res["letter"])
        grid.append(row)
    return dict(grid=grid, detail=detail, warped=warped, boxes=boxes,
                tray_found=tray_found, cubes_found=cubes_found)


def annotate(result):
    """Warped board with the detected letters drawn on it."""
    img = result["warped"].copy()
    for r in range(4):
        for c in range(4):
            x0, y0, x1, y1 = result["boxes"][r][c]
            cv2.rectangle(img, (x0, y0), (x1, y1), (0, 140, 255), 3)
            d = result["detail"][r * 4 + c]
            cv2.putText(img, d["letter"] or "?", (x0 + 8, y0 + 44),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 4)
    return img
