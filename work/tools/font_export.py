# -*- coding: utf-8 -*-
"""F_FONT.S9 폰트를 PNG 로 추출한다.

F_FONT.S9 구조
  0x0000  u32   전각 글자 수 N (= 3758)
  0x0004  u16[N] 각 글리프의 Shift-JIS 코드 (리틀엔디언)
  0x1D60  반각 글리프 256개 : 12x24, 4bpp (144 바이트/자) - 1바이트 코드 0x00~0xFF 순서
  0xAD60  전각 글리프 N개   : 24x24, 4bpp (288 바이트/자) - 코드 테이블 순서
  4bpp 는 하위 니블이 왼쪽 픽셀, 값 0(투명)~15(가장 진함)

출력 (work/font_jp/)
  font_full_24x24.png   전각 전체 시트 (셀 간격 없음, 재삽입용 원본 배치)
  font_half_12x24.png   반각 256자 시트
  kanji_sheet.png       한자만 모은 확인용 시트 (격자 + 행 번호)
  kanji/*.png           한자 개별 PNG (인덱스_SJIS코드_글자.png)
  font_table.tsv        인덱스/SJIS/유니코드/분류/파일오프셋 목록
"""
import os
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "san9pk", "F_FONT.S9")
OUT = os.path.join(HERE, "..", "font_jp")

HALF_OFS, HALF_W, HALF_H, HALF_N = 0x1D60, 12, 24, 256
FULL_W, FULL_H = 24, 24
SHEET_COLS = 64


def classify(code):
    if code < 0x824F:
        return "symbol"
    if code < 0x829F:
        return "alnum"
    if code < 0x8340:
        return "hiragana"
    if code < 0x839F:
        return "katakana"
    if code < 0x8740:
        return "greek/cyrillic/box"
    if code < 0x889F:
        return "nec-special"
    if code < 0x9873:
        return "kanji-L1"
    if code < 0xEAA5:
        return "kanji-L2"
    if code < 0xF040:
        return "kanji-nec-ext"
    if code < 0xFA40:
        return "kanji-user"      # 코에이 외자 (사용자 정의 영역)
    return "kanji-ibm-ext"


def sjis_char(code):
    try:
        ch = struct.pack(">H", code).decode("cp932")
    except UnicodeDecodeError:
        return ""
    # F040~F9FC 는 cp932 에서 사용자 정의(PUA)로 디코딩됨 -> 실제 글자 미상
    return "" if 0xE000 <= ord(ch) <= 0xF8FF else ch


def decode_4bpp(buf, w, h):
    b = np.frombuffer(buf, dtype=np.uint8)
    px = np.empty(w * h, dtype=np.uint8)
    px[0::2] = b & 0x0F
    px[1::2] = b >> 4
    return px.reshape(h, w)


def to_gray(g):
    # 0(배경)=흰색, 15(획)=검정
    return (255 - g * 17).astype(np.uint8)


def pack_sheet(glyphs, w, h, cols):
    rows = (len(glyphs) + cols - 1) // cols
    sheet = np.full((rows * h, cols * w), 255, dtype=np.uint8)
    for i, g in enumerate(glyphs):
        r, c = divmod(i, cols)
        sheet[r * h:(r + 1) * h, c * w:(c + 1) * w] = to_gray(g)
    return sheet


def preview_sheet(glyphs, labels, w, h, cols, scale=2):
    """격자선과 행 시작 인덱스가 있는 확인용 시트."""
    cell_w, cell_h = w * scale + 2, h * scale + 2
    margin = 48
    rows = (len(glyphs) + cols - 1) // cols
    img = Image.new("L", (margin + cols * cell_w + 1, rows * cell_h + 1), 200)
    draw = ImageDraw.Draw(img)
    for i, g in enumerate(glyphs):
        r, c = divmod(i, cols)
        x, y = margin + c * cell_w + 1, r * cell_h + 1
        gi = Image.fromarray(to_gray(g)).resize((w * scale, h * scale), Image.NEAREST)
        img.paste(gi, (x, y))
        if c == 0:
            draw.text((2, y + cell_h // 2 - 6), str(labels[i]), fill=0)
    return img


def main():
    data = open(SRC, "rb").read()
    n = struct.unpack_from("<I", data, 0)[0]
    codes = struct.unpack_from("<%dH" % n, data, 4)
    full_ofs = HALF_OFS + HALF_N * HALF_W * HALF_H // 2
    full_size = FULL_W * FULL_H // 2
    assert full_ofs == 0xAD60 and full_ofs + n * full_size <= len(data)

    os.makedirs(os.path.join(OUT, "kanji"), exist_ok=True)

    half = [decode_4bpp(data[HALF_OFS + i * 144:HALF_OFS + (i + 1) * 144], HALF_W, HALF_H)
            for i in range(HALF_N)]
    full = [decode_4bpp(data[full_ofs + i * full_size:full_ofs + (i + 1) * full_size], FULL_W, FULL_H)
            for i in range(n)]

    # 1) 시트 (셀 간격 없음)
    Image.fromarray(pack_sheet(full, FULL_W, FULL_H, SHEET_COLS)).save(os.path.join(OUT, "font_full_24x24.png"))
    Image.fromarray(pack_sheet(half, HALF_W, HALF_H, 16)).save(os.path.join(OUT, "font_half_12x24.png"))

    # 2) 목록 + 한자 개별 PNG
    kanji_idx = []
    counts = {}
    with open(os.path.join(OUT, "font_table.tsv"), "w", encoding="utf-8-sig", newline="\n") as f:
        f.write("index\tsjis\tunicode\tchar\tcategory\tfile_offset\tsheet_x\tsheet_y\n")
        for i, code in enumerate(codes):
            cat = classify(code)
            counts[cat] = counts.get(cat, 0) + 1
            ch = sjis_char(code)
            uni = "U+%04X" % ord(ch) if ch else ""
            r, c = divmod(i, SHEET_COLS)
            f.write("%d\t%04X\t%s\t%s\t%s\t0x%X\t%d\t%d\n" % (
                i, code, uni, ch, cat, full_ofs + i * full_size, c * FULL_W, r * FULL_H))
            if cat.startswith("kanji"):
                kanji_idx.append(i)
                name = "%04d_%04X%s.png" % (i, code, "_" + ch if ch else "")
                Image.fromarray(to_gray(full[i])).save(os.path.join(OUT, "kanji", name))

    # 3) 한자 확인용 시트
    preview_sheet([full[i] for i in kanji_idx], kanji_idx, FULL_W, FULL_H, 50).save(
        os.path.join(OUT, "kanji_sheet.png"))

    print("전각 글리프 총 %d자 (24x24, 4bpp)" % n)
    for k in sorted(counts):
        print("  %-20s %5d" % (k, counts[k]))
    print("한자 합계 %d자" % len(kanji_idx))
    print("반각 글리프 %d칸 (12x24, 4bpp)" % HALF_N)
    return 0


if __name__ == "__main__":
    sys.exit(main())
