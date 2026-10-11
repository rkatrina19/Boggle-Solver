"""Accuracy check for the photo reader on generated boards:  python tests/eval_reader.py [n] [boards]"""
import sys, tempfile, os, collections
import cv2
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.dirname(__file__))
import make_synthetic as ms
import boggle_vision as bv

n = int(sys.argv[1]) if len(sys.argv) > 1 else 4
boards = int(sys.argv[2]) if len(sys.argv) > 2 else 20
path = os.path.join(tempfile.mkdtemp(), 'board.png')
tot = ok = perfect = fallback = 0
errs = collections.Counter()
for seed in range(1, boards + 1):
    truth = ms.make(seed, path, n)
    res = bv.read_grid(cv2.imread(path), n)
    fallback += not res['cubes_found']
    got = [d['letter'] for d in res['detail']]
    good = sum(g == t for g, t in zip(got, truth))
    ok += good; tot += n * n; perfect += good == n * n
    for g, t in zip(got, truth):
        if g != t:
            errs[(t, g)] += 1
print(f'{n}x{n}: cubes {ok}/{tot} = {ok/tot:.1%} | perfect boards {perfect}/{boards} | layout fallbacks {fallback}')
if errs:
    print('errors (truth -> read):', dict(errs))
