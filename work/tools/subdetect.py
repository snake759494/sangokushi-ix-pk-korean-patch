# -*- coding: utf-8 -*-
"""동영상 속 일본어 자막(흰 글자 + 검은 테두리) 구간 자동 검출.

python subdetect.py [--skip] [영상이름...]   (없으면 자막 있는 34편 전부, --skip = 결과 있는 것 건너뜀)

결과: work/movie/subs/<이름>.json
  {"frames": N, "cards": [{"id", "start", "end", "key", "bbox":[x0,y0,x1,y1], "alpha":{프레임: 0~1}}]}
      start/end = 자막이 조금이라도 보이는 첫/마지막 프레임, alpha = 그 사이 프레임별 불투명도
  work/movie/subs/crops/<이름>_<id>.png  = 대표 프레임 자막 부분(받아쓰기용)

방법
  1. 프레임마다 글자 획 마스크: 밝고(>170) 가늘고(톱햇>50) 무채색이며 가까이에 어두운 테두리
  2. 아직 안 쓴 프레임 중 글자 픽셀이 가장 많고 ±6프레임 안정된 것을 기준 글자 R 로 잡고,
     R 의 픽셀이 절반 이상 보이는 앞뒤 연속 구간 = 한 장의 자막 (배경이 바뀌어도 같은 글자면 한 장)
  3. 불투명도 = (글자 픽셀 밝기 - 둘레 픽셀 밝기) / 기준 프레임 값. 이웃 자막 글자와 겹치는 픽셀은 뺌
"""
import io
import json
import os
import sys

import av
import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pss  # noqa: E402

WORK = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ORIG = os.path.join(WORK, "movie", "orig")
OUT = os.path.join(WORK, "movie", "subs")
Y0, Y1, X0, X1 = 296, 440, 16, 624      # 자막 띠 (일본어 자막 줄: y 328~347, 354~373, 380~399)
TEXT_BOTTOM = 406                       # 일본어 자막 글자는 이 줄 위에만 있다


def movie_list():
    names = ["MOVIESOP/SOP_H%02d" % i for i in range(10)] + ["MOVIESOP/SOP_V%02d" % i for i in range(10)]
    names += ["MOVIE/EVENT%02d" % i for i in range(14)]
    return names


def frames_yuv(path):
    """-> (Y 띠, U 띠, V 띠) int16, 색차는 2배로 늘림"""
    v, _, _ = pss.demux(path)
    c = av.open(io.BytesIO(v), format="mpegvideo")
    H, W = 448, 640
    for fr in c.decode(video=0):
        f = fr.to_ndarray(format="yuv420p")
        y = f[Y0:Y1, X0:X1]
        u = f[H:H + H // 4].reshape(H // 2, W // 2)[Y0 // 2:Y1 // 2, X0 // 2:X1 // 2]
        v2 = f[H + H // 4:].reshape(H // 2, W // 2)[Y0 // 2:Y1 // 2, X0 // 2:X1 // 2]
        yield y.copy(), u.repeat(2, 0).repeat(2, 1), v2.repeat(2, 0).repeat(2, 1)
    c.close()


def text_mask(y, u, v):
    """흰 글자 획: 밝고, 가늘고(톱햇), 무채색이고, 가까이에 어두운 테두리가 있는 픽셀. 글자 줄 영역만."""
    y = y.astype(np.int16)
    th = y - ndimage.grey_opening(y, size=(7, 7))
    chroma = np.maximum(np.abs(u.astype(np.int16) - 128), np.abs(v.astype(np.int16) - 128))
    m = (y > 170) & (th > 50) & (chroma < 14) & (ndimage.minimum_filter(y, size=5) < 110)
    m[TEXT_BOTTOM - Y0:] = False
    return m


def detect(name):
    path = os.path.join(ORIG, name + ".PSS")
    ys = []
    packed = []
    for y, u, v in frames_yuv(path):
        ys.append(y)
        packed.append(np.packbits(text_mask(y, u, v)))
    n = len(ys)
    shape = ys[0].shape

    def M(t):
        return np.unpackbits(packed[t])[:shape[0] * shape[1]].reshape(shape).astype(bool)

    score = np.array([int(np.unpackbits(m).sum()) for m in packed])
    assigned = np.zeros(n, bool)
    raw = []
    while True:
        # 아직 안 쓴 프레임 중 글자가 가장 많고 안정된 것
        cand = [t for t in range(6, n - 6) if not assigned[t] and score[t] > 250]
        if not cand:
            break
        best = None
        for t in sorted(cand, key=lambda t: -score[t])[:40]:
            S = M(t) & M(t - 6) & M(t + 6)
            if best is None or S.sum() > best[1].sum():
                best = (t, S)
        tk, S = best
        lab, nl = ndimage.label(ndimage.binary_dilation(S, iterations=3))
        sizes = ndimage.sum(S, lab, range(1, nl + 1))
        R = np.isin(lab, [i + 1 for i, sz in enumerate(sizes) if sz >= 12]) & S
        if R.sum() < 250:
            assigned[tk] = True
            continue
        rs = R.sum()

        def presence(t):
            return (R & ndimage.binary_dilation(M(t), iterations=1)).sum() / rs

        lo = tk
        while lo > 0 and presence(lo - 1) >= 0.5:
            lo -= 1
        hi = tk
        while hi < n - 1 and presence(hi + 1) >= 0.5:
            hi += 1
        assigned[lo:hi + 1] = True
        if hi - lo < 20:
            continue
        raw.append({"s": lo, "e": hi, "key": tk, "keep": R})
    cards = sorted(raw, key=lambda c: c["s"])
    # 같은 글자가 두 장으로 잡힌 것 합치기 (구간이 겹치거나 붙어 있고, 서로의 글자가 상대 프레임에 보임)

    def seen(a, b):
        return (a["keep"] & ndimage.binary_dilation(M(b["key"]), iterations=1)).sum() / a["keep"].sum()

    merged = []
    for c in cards:
        if merged:
            p = merged[-1]
            if c["s"] <= p["e"] + 3 and max(seen(p, c), seen(c, p)) >= 0.5:
                p["e"] = max(p["e"], c["e"])
                if c["keep"].sum() > p["keep"].sum():
                    p["keep"], p["key"] = c["keep"], c["key"]
                continue
        merged.append(c)
    cards = merged
    # 불투명도
    out = []
    for k, c in enumerate(cards):
        keep = c["keep"]
        others = np.zeros_like(keep)
        for j in (k - 1, k + 1):
            if 0 <= j < len(cards):
                others |= ndimage.binary_dilation(cards[j]["keep"], iterations=2)
        excl = keep & ~others
        if excl.sum() < 0.3 * keep.sum():
            excl = keep
        ring = ndimage.binary_dilation(keep, iterations=2) & ~keep & ~others
        if ring.sum() < 50:
            ring = ndimage.binary_dilation(keep, iterations=2) & ~keep

        def contrast(t):
            b = ys[t].astype(np.float32)
            return float(b[excl].mean() - b[ring].mean())

        cmax = contrast(c["key"])
        s, e = c["s"], c["e"]
        lo_lim = cards[k - 1]["s"] if k > 0 else 0
        hi_lim = cards[k + 1]["e"] if k + 1 < len(cards) else n - 1
        lo = s
        while lo > lo_lim and contrast(lo - 1) / cmax > 0.04 and s - lo < 45:
            lo -= 1
        hi = e
        while hi < hi_lim and contrast(hi + 1) / cmax > 0.04 and hi - e < 45:
            hi += 1
        alpha = {}
        for t in range(lo, hi + 1):
            alpha[t] = round(min(1.0, max(0.0, contrast(t) / cmax)), 3)
        full = [t for t in range(lo, hi + 1) if alpha[t] >= 0.93]
        if full:
            for t in range(full[0], full[-1] + 1):
                alpha[t] = 1.0
        rows = np.where(keep.any(1))[0]
        cols = np.where(keep.any(0))[0]
        bbox = [int(cols.min() + X0), int(rows.min() + Y0), int(cols.max() + X0), int(rows.max() + Y0)]
        out.append({"id": k, "start": lo, "end": hi, "key": c["key"], "bbox": bbox,
                    "alpha": {str(t): alpha[t] for t in range(lo, hi + 1)}})
        crop = ys[c["key"]][max(0, bbox[1] - Y0 - 6):bbox[3] - Y0 + 7, :]
        os.makedirs(os.path.join(OUT, "crops"), exist_ok=True)
        Image.fromarray(crop.astype(np.uint8)).save(os.path.join(OUT, "crops", "%s_%02d.png" % (os.path.basename(name), k)))
    res = {"name": name, "frames": n, "cards": out}
    with open(os.path.join(OUT, os.path.basename(name) + ".json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False)
    return name, n, [(c["start"], c["end"], c["bbox"]) for c in out]


def main():
    args = [x for x in sys.argv[1:] if x != "--skip"]
    names = args or movie_list()
    names = [x if "/" in x else ("MOVIESOP/" + x if x.startswith("SOP") else "MOVIE/" + x) for x in names]
    if "--skip" in sys.argv:
        done = {f[:-5] for f in os.listdir(OUT) if f.endswith(".json")}
        names = [x for x in names if os.path.basename(x) not in done]
    for name in names:
        name, n, cards = detect(name)
        print(name, n, "frames", len(cards), "cards")
        for s, e, bb in cards:
            print("   %6.2f-%6.2f  %s" % (s / 30, e / 30, bb))
        sys.stdout.flush()


if __name__ == "__main__":
    main()
