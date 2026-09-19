# -*- coding: utf-8 -*-
"""F_FONT.S9 의 한자 슬롯(亜, 인덱스 330부터)에 KS X 1001 완성형 한글 2350자를 입힌다.

입력  work/san9pk/F_FONT.S9 (원본), SeoulHangangB.ttf
출력  work/patched/F_FONT.S9      ISO 빌드용 수정 폰트
      work/font_ko/hangul.tbl     SJIS 코드=한글 (텍스트 삽입용 테이블)
      work/font_ko/font_full_24x24.png, hangul_sheet.png, preview.png

렌더링: 22px(em), 베이스라인 y=19, 글자별 가로 중앙(x=10.5) 정렬.
원본 한자 영역(가로 0~21, 세로 1~21)과 크기를 맞춘 값이다.
"""
import os
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from font_export import FULL_H, FULL_W, SHEET_COLS, decode_4bpp, pack_sheet, preview_sheet, to_gray

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
SRC = os.path.join(ROOT, "work", "san9pk", "F_FONT.S9")
TTF = os.path.join(ROOT, "SeoulHangangB.ttf")
OUT_FONT = os.path.join(ROOT, "work", "patched", "F_FONT.S9")
OUT_DIR = os.path.join(ROOT, "work", "font_ko")

FULL_OFS = 0xAD60
GLYPH_BYTES = FULL_W * FULL_H // 2
START_INDEX = 330            # 亜 (SJIS 889F)
START_CODE = 0x889F
FONT_SIZE = 22
BASELINE = 19
CENTER_X = 10.5
PAD = 16                     # 잘림 검사용 여백


def ksx1001_hangul():
    return [bytes([hi, lo]).decode("euc-kr") for hi in range(0xB0, 0xC9) for lo in range(0xA1, 0xFF)]


def render(font, ch):
    """24x24, 0~15 값의 글리프와 셀 밖으로 잘린 잉크 여부를 돌려준다."""
    size = FULL_W + PAD * 2
    im = Image.new("L", (size, size), 0)
    ImageDraw.Draw(im).text((PAD, PAD + BASELINE), ch, font=font, fill=255, anchor="ls")
    a = np.asarray(im)
    cols = np.nonzero(a.max(axis=0))[0]
    x0, x1 = int(cols[0]), int(cols[-1])
    left = int(round(CENTER_X - (x1 - x0) / 2.0))
    out = np.zeros((FULL_H, FULL_W), dtype=np.uint8)
    w = x1 - x0 + 1
    src = a[PAD:PAD + FULL_H, x0:x1 + 1]
    lo, hi = max(0, -left), min(w, FULL_W - left)
    out[:, left + lo:left + hi] = src[:, lo:hi]
    clipped = int(a.sum()) != int(out.astype(np.int64).sum())
    return ((out.astype(np.int32) * 15 + 127) // 255).astype(np.uint8), clipped


def encode_4bpp(g):
    p = g.reshape(-1)
    return ((p[0::2] & 0x0F) | (p[1::2] << 4)).astype(np.uint8).tobytes()


def main():
    data = bytearray(open(SRC, "rb").read())
    n = struct.unpack_from("<I", data, 0)[0]
    codes = struct.unpack_from("<%dH" % n, data, 4)
    hangul = ksx1001_hangul()
    assert len(hangul) == 2350
    assert codes[START_INDEX] == START_CODE, "시작 슬롯이 亜(889F)가 아님"
    assert START_INDEX + len(hangul) <= n

    font = ImageFont.truetype(TTF, FONT_SIZE)
    clipped = []
    for k, ch in enumerate(hangul):
        g, clip = render(font, ch)
        if clip:
            clipped.append(ch)
        o = FULL_OFS + (START_INDEX + k) * GLYPH_BYTES
        data[o:o + GLYPH_BYTES] = encode_4bpp(g)

    os.makedirs(os.path.dirname(OUT_FONT), exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)
    open(OUT_FONT, "wb").write(data)

    with open(os.path.join(OUT_DIR, "hangul.tbl"), "w", encoding="utf-8", newline="\n") as f:
        for k, ch in enumerate(hangul):
            f.write("%04X=%s\n" % (codes[START_INDEX + k], ch))

    # 미리보기
    full = [decode_4bpp(bytes(data[FULL_OFS + i * GLYPH_BYTES:FULL_OFS + (i + 1) * GLYPH_BYTES]), FULL_W, FULL_H)
            for i in range(n)]
    Image.fromarray(pack_sheet(full, FULL_W, FULL_H, SHEET_COLS)).save(os.path.join(OUT_DIR, "font_full_24x24.png"))
    idx = list(range(START_INDEX, START_INDEX + len(hangul)))
    preview_sheet([full[i] for i in idx], idx, FULL_W, FULL_H, 50).save(os.path.join(OUT_DIR, "hangul_sheet.png"))

    slot = {ch: START_INDEX + k for k, ch in enumerate(hangul)}
    lines = ["유비는 관우, 장비와 도원에서 의형제를 맺었다.",
             "조조가 대군을 이끌고 적벽으로 향했습니다!",
             "뷁쀍똠방각하 햏했쌌 — 가나다라마바사아자차카타파하"]
    canvas = np.full((len(lines) * FULL_H, 30 * FULL_W), 255, dtype=np.uint8)
    for r, line in enumerate(lines):
        for c, ch in enumerate(line[:30]):
            if ch in slot:
                canvas[r * FULL_H:(r + 1) * FULL_H, c * FULL_W:(c + 1) * FULL_W] = to_gray(full[slot[ch]])
    im = Image.fromarray(canvas)
    im.resize((im.size[0] * 2, im.size[1] * 2), Image.NEAREST).save(os.path.join(OUT_DIR, "preview.png"))

    last = START_INDEX + len(hangul) - 1
    last_ch = struct.pack(">H", codes[last]).decode("cp932")
    print("한글 %d자 입힘: 인덱스 %d~%d, SJIS %04X(亜)~%04X(%s)" % (
        len(hangul), START_INDEX, last, codes[START_INDEX], codes[last], last_ch))
    print("셀 밖으로 잘린 글자: %d %s" % (len(clipped), "".join(clipped[:50])))
    print("출력:", OUT_FONT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
