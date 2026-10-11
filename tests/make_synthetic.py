"""Generate fake Boggle photos (random letters, cube rotations, perspective, noise)
so the photo reader can be tested without a real board."""
import random, sys
import cv2, numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/truetype/crosextra/Carlito-Bold.ttf"   # NOT one of the template fonts
DICE = ["AAEEGN","ELRTTY","AOOTTW","ABBJOO","EHRTVW","CIMOTU","DISTTY","EIOSST",
        "DELRVY","ACHOPS","HIMNQU","EEINSU","EEGHNW","AFFKPS","HLNNRZ","DEILRX"]

def cube(letter, k, jitter, size=200, bg_gray=175):
    img = Image.new("L", (size, size), bg_gray)
    d = ImageDraw.Draw(img)
    text = "Qu" if letter == "QU" else letter
    f = ImageFont.truetype(FONT, 120)
    bb = d.textbbox((0, 0), text, font=f)
    w, h = bb[2]-bb[0], bb[3]-bb[1]
    x, y = (size-w)//2 - bb[0], (size-h)//2 - bb[1] - (8 if letter in "MWZ" else 0)
    d.text((x, y), text, fill=15, font=f)
    if letter in "MWZ":                      # underline below the (upright) letter
        d.rectangle([x+bb[0], y+bb[3]+10, x+bb[2], y+bb[3]+18], fill=15)
    a = np.array(img)
    a = np.rot90(a, k).copy()
    M = cv2.getRotationMatrix2D((size/2, size/2), jitter, 1)
    return cv2.warpAffine(a, M, (size, size), borderValue=bg_gray)

POOL = "EEEEEEEEEEEEAAAAAAAAAIIIIIIIIOOOOOOOONNNNNNRRRRRRTTTTTTLLLLSSSSUUUUDDDDGGGBBCCMMPPFFHHVVWWYYKJXQZ"


def make(seed, out, n=4):
    rng = random.Random(seed)
    if n == 4:
        letters = [rng.choice(die) for die in DICE]
        rng.shuffle(letters)
    else:
        letters = [rng.choice(POOL) for _ in range(n * n)]
    letters = ["QU" if l == "Q" else l for l in letters]
    cs, gap, pad = 200, 28, 50
    W = pad*2 + n*cs + (n-1)*gap
    board = np.full((W, W), 28, np.uint8)
    for i, l in enumerate(letters):
        r, c = divmod(i, n)
        face = cube(l, rng.randrange(4), rng.uniform(-6, 6), cs)
        mask = np.zeros((cs, cs), np.uint8)
        cv2.rectangle(mask, (0, 0), (cs-1, cs-1), 255, -1)
        x0, y0 = pad + c*(cs+gap), pad + r*(cs+gap)
        board[y0:y0+cs, x0:x0+cs] = face
    board = cv2.cvtColor(board, cv2.COLOR_GRAY2BGR)
    # place on a table with perspective + rotation
    H = 1000
    table = np.full((H, H, 3), (60, 110, 160), np.uint8)       # brown-ish (BGR)
    table = cv2.add(table, rng.randrange(0, 40))
    jitter = lambda: rng.uniform(-60, 60)
    src = np.float32([[0,0],[W,0],[W,W],[0,W]])
    ang = rng.uniform(-25, 25)
    dst = np.float32([[150+jitter(), 150+jitter()],[850+jitter(), 140+jitter()],
                      [860+jitter(), 860+jitter()],[140+jitter(), 850+jitter()]])
    Mrot = cv2.getRotationMatrix2D((H/2, H/2), ang, 1)
    dst = cv2.transform(dst.reshape(-1,1,2), Mrot).reshape(-1,2).astype(np.float32)
    P = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(board, P, (H, H), borderValue=(0,0,0))
    m = cv2.warpPerspective(np.full((W, W), 255, np.uint8), P, (H, H))
    photo = np.where(m[..., None] > 0, warped, table)
    # lighting gradient, blur, noise
    grad = np.linspace(0.75, 1.1, H, dtype=np.float32)[None, :, None]
    photo = np.clip(photo.astype(np.float32) * grad, 0, 255)
    photo = cv2.GaussianBlur(photo, (5, 5), 0)
    photo += np.random.RandomState(seed).normal(0, 4, photo.shape)
    cv2.imwrite(out, np.clip(photo, 0, 255).astype(np.uint8))
    return letters

if __name__ == "__main__":
    print(make(int(sys.argv[1]), sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 4))
