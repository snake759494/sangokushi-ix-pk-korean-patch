# -*- coding: utf-8 -*-
"""능력 그래프 그림(G_SYSTEM.S9 0x102000, 8비트 256폭)의 統率/武力/政治/知力 글자를 한국어로 바꾼다.

같은 그림을 게임이 두 팔레트로 그린다: 색 팔레트(무장 선택 후, 글자가 노랑/빨강/파랑/초록)와
회색 팔레트(선택 전). 팔레트는 에뮬레이터 VRAM 에서 떠 둔 work/gfx/radar_cluts.npz.
방법: 옛 글자(색 글자 + 검은 테두리)를 지우고(주변 배경으로 채움) 서울한강체 EB 로 새 글자를 그린 뒤,
      색·회색 두 팔레트 모두에서 목표 색에 가장 가까운 팔레트 번호를 고른다.

python gfx_radar.py   -> work/patched/G_SYSTEM.S9, work/gfx/preview/radar.png
"""
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.normpath(os.path.join(HERE, ".."))
ROOT = os.path.dirname(WORK)
FONT = os.path.join(ROOT, "SeoulHangangEB.ttf")
SRC = os.path.join(WORK, "san9pk", "G_SYSTEM.S9")
DST = os.path.join(WORK, "patched", "G_SYSTEM.S9")
PREVIEW = os.path.join(WORK, "gfx", "preview", "radar.png")
BASE, STRIDE, W, H = 0x102000, 256, 200, 104
SS = 8

# 이름: (한국어, 글자 상자(x0,y0,x1,y1), 색 판별)
LABELS = [
    ("統率", "통솔", (104, 2, 154, 28), "yellow"),
    ("武力", "무력", (72, 42, 114, 68), "red"),
    ("政治", "정치", (158, 42, 200, 68), "blue"),
    ("知力", "지력", (114, 78, 156, 100), "green"),
]


def hue_mask(rgb, kind):
    r, g, b = [rgb[..., k].astype(int) for k in range(3)]
    if kind == "yellow":
        return (r > 70) & (g > 70) & (r - b > 45)
    if kind == "red":
        return (r > 70) & (r - g > 35) & (r - b > 35)
    if kind == "blue":
        return (b > 70) & (b - r > 35)
    return (g > 60) & (g - r > 25) & (g - b > 20)


def main():
    data = bytearray(open(SRC, "rb").read())
    pal = np.load(os.path.join(WORK, "gfx", "radar_cluts.npz"))
    Cc = pal["color"][:, :3].astype(float)
    Cg = pal["gray"][:, :3].astype(float)
    T = np.frombuffer(bytes(data), np.uint8)[BASE:BASE + H * STRIDE].reshape(H, STRIDE)[:, :W].copy()
    col = Cc[T]
    gry = Cg[T]
    out = T.copy()
    lum = gry.mean(-1)
    font_cache = {}
    for jp, ko, (x0, y0, x1, y1), kind in LABELS:
        box = np.zeros((H, W), bool)
        box[y0:y1, x0:x1] = True
        fill = hue_mask(col, kind) & box
        fill = ndimage.binary_opening(fill, iterations=0) if False else fill
        ys, xs = np.where(fill)
        fy0, fy1, fx0, fx1 = ys.min(), ys.max(), xs.min(), xs.max()
        near = ndimage.binary_dilation(fill, iterations=2) & box
        outline = near & ~fill & (lum < lum[fill].mean() * 0.7)
        foot = ndimage.binary_dilation(fill | outline, iterations=1) & box
        # 1) 배경 복원: 색·회색 영상을 각각 채운 뒤 주변 배경 번호 중 가장 가까운 것
        ring = ndimage.binary_dilation(foot, iterations=4) & ~foot
        bg_idx = np.unique(T[ring])
        m8 = foot.astype(np.uint8) * 255
        col_in = cv2.inpaint(np.clip(col, 0, 255).astype(np.uint8), m8, 3, cv2.INPAINT_TELEA).astype(float)
        gry_in = cv2.inpaint(np.clip(gry, 0, 255).astype(np.uint8), m8, 3, cv2.INPAINT_TELEA).astype(float)
        # 2) 새 글자 (8배로 그려 줄임)
        glyph_h = fy1 - fy0 + 1
        if ko not in font_cache:
            size = 10
            while True:
                f = ImageFont.truetype(FONT, size * SS)
                hb = f.getbbox("한")
                if (hb[3] - hb[1]) / SS >= glyph_h * 0.97 or size > 40:
                    break
                size += 1
            font_cache[ko] = (f, size)
        f, size = font_cache[ko]
        bb = f.getbbox(ko)
        hb = f.getbbox("한")
        cx = (fx0 + fx1 + 1) / 2 * SS
        cy = (fy0 + fy1 + 1) / 2 * SS
        img = Image.new("L", (W * SS, H * SS), 0)
        ImageDraw.Draw(img).text((cx - (bb[0] + bb[2]) / 2, cy - (hb[1] + hb[3]) / 2), ko, font=f, fill=255)
        gm = np.asarray(img) >= 128
        a_f = gm.reshape(H, SS, W, SS).mean((1, 3))
        om = ndimage.binary_dilation(gm, iterations=int(1.9 * SS))
        a_o = om.reshape(H, SS, W, SS).mean((1, 3))
        # 원본 글자색: 행 위치(0~1)별 평균 (밝은 채움 픽셀만)
        bright = fill & (lum >= np.percentile(lum[fill], 55))
        rel = (np.arange(H) - fy0) / max(1, fy1 - fy0)
        prof_c = np.zeros((H, 3))
        prof_g = np.zeros((H, 3))
        brows = np.where(bright.any(1))[0]
        for y in range(H):
            ry = np.clip(rel[y], 0, 1)
            yy = int(round(fy0 + ry * (fy1 - fy0)))
            yy = brows[np.argmin(np.abs(brows - yy))]
            m = bright[yy]
            prof_c[y] = col[yy][m].mean(0)
            prof_g[y] = gry[yy][m].mean(0)
        dark = outline & (lum <= np.percentile(lum[outline], 35)) if outline.any() else outline
        oc = col[dark].mean(0) if dark.any() else np.zeros(3)
        og = gry[dark].mean(0) if dark.any() else np.zeros(3)
        region = ndimage.binary_dilation((a_o > 0.02) | foot, iterations=1) & box
        cand = np.unique(np.concatenate([T[fill | outline], bg_idx]))
        for y, x in zip(*np.where(region)):
            af, ao = a_f[y, x], a_o[y, x]
            bc = col_in[y, x] if foot[y, x] else col[y, x]
            bgv = gry_in[y, x] if foot[y, x] else gry[y, x]
            under_c = ao * oc + (1 - ao) * bc
            under_g = ao * og + (1 - ao) * bgv
            tc = af * prof_c[y] + (1 - af) * under_c
            tg = af * prof_g[y] + (1 - af) * under_g
            pool = cand if (af > 0.02 or ao > 0.02) else bg_idx
            err = ((Cc[pool] - tc) ** 2).sum(1) + ((Cg[pool] - tg) ** 2).sum(1)
            out[y, x] = pool[int(np.argmin(err))]
        print("  %s -> %s  옛 글자 %d~%d x %d~%d, 글꼴 %dpx, 후보 팔레트 %d" % (jp, ko, fx0, fx1, fy0, fy1, size, len(cand)))
    buf = np.frombuffer(bytes(data), np.uint8)[BASE:BASE + H * STRIDE].reshape(H, STRIDE).copy()
    buf[:, :W] = out
    data[BASE:BASE + H * STRIDE] = buf.tobytes()
    os.makedirs(os.path.dirname(DST), exist_ok=True)
    open(DST, "wb").write(data)
    # 미리보기: 원본/새것 x 색/회색, 4배
    rows = []
    for t in (T, out):
        rows.append(np.concatenate([Cc[t], Cg[t]], 1))
    pv = np.concatenate(rows, 0).clip(0, 255).astype(np.uint8)
    os.makedirs(os.path.dirname(PREVIEW), exist_ok=True)
    Image.fromarray(pv).resize((pv.shape[1] * 3, pv.shape[0] * 3), Image.NEAREST).save(PREVIEW)
    print("완료:", DST)


if __name__ == "__main__":
    main()
