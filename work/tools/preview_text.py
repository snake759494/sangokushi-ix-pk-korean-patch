# -*- coding: utf-8 -*-
"""패치된 F_FONT.S9 로 M_MSG 항목을 게임과 같은 간격(전각 22px, 반각 11px)으로 그려 본다.

사용법: python preview_text.py 출력.png 번호[:상자폭전각수] ...
대사 분기 스크립트가 있는 항목은 첫 변형만 그린다. 색 태그는 색으로 표시, {V:}는 [이름] 자리표시.
"""
import os
import re
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw

from msg_dump import read_entries
from s9text import TAG, decode, load_hangul

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, "..", "patched", "F_FONT.S9")
MSG = os.path.join(HERE, "..", "patched", "M_MSG.S9")
TBL = os.path.join(HERE, "..", "font_ko", "hangul.tbl")
COLORS = {"9b": (120, 170, 255), "10b": (255, 110, 110), "16b": (110, 230, 230), "25b": (130, 170, 255),
          "32b": (235, 235, 235), "0b": (235, 235, 235), "2b": (255, 200, 90)}


class Font:
    def __init__(self):
        d = open(FONT, "rb").read()
        n = struct.unpack_from("<I", d, 0)[0]
        codes = struct.unpack_from("<%dH" % n, d, 4)
        self.idx = {c: i for i, c in enumerate(codes)}
        self.d = d

    def _px(self, off, w, h):
        b = np.frombuffer(self.d[off:off + w * h // 2], dtype=np.uint8)
        p = np.empty(w * h, np.uint8)
        p[0::2] = b & 15
        p[1::2] = b >> 4
        return p.reshape(h, w)

    def full(self, code):
        i = self.idx.get(code)
        return None if i is None else self._px(0xAD60 + i * 288, 24, 24)

    def half(self, b):
        return self._px(0x1D60 + b * 144, 12, 24)


def render_entry(font, text, ko_bytes, box_chars):
    lines = text.split("\n")
    W = 16 + box_chars * 22
    H = 16 + max(1, len(lines)) * 26
    img = np.zeros((H, W, 3), np.float32)
    img[:] = (40, 44, 60)
    color = COLORS["32b"]
    y = 8
    for line in lines:
        x = 8
        pos = 0
        for m in list(TAG.finditer(line)) + [None]:
            seg = line[pos:m.start()] if m else line[pos:]
            for ch in seg:
                if ch in ko_bytes:
                    g = font.full(int.from_bytes(ko_bytes[ch], "big")); adv = 22
                elif ord(ch) < 0x80:
                    g = font.half(ord(ch)); adv = 11
                else:
                    try:
                        c = int.from_bytes(ch.encode("cp932"), "big")
                    except UnicodeEncodeError:
                        c = 0x8148
                    g = font.full(c); adv = 22
                if g is not None:
                    h, w = g.shape
                    a = (g.astype(np.float32) / 15.0)[:, :, None]
                    x2 = min(W, x + w)
                    region = img[y:y + h, x:x2]
                    region[:] = region * (1 - a[:, :x2 - x]) + np.array(color) * a[:, :x2 - x]
                x += adv
            if m is None:
                break
            if m.group(1) == "C":
                color = COLORS.get(m.group(2), (255, 255, 255))
            elif m.group(1) == "V":
                x += 8 * 11
            elif m.group(1) == "U":
                g = font.full(int(m.group(2), 16))
                if g is not None:
                    a = (g.astype(np.float32) / 15.0)[:, :, None]
                    img[y:y + 24, x:x + 24] = img[y:y + 24, x:x + 24] * (1 - a) + np.array((255, 180, 180)) * a
                x += 22
            pos = m.end()
        y += 26
    # 상자 오른쪽 경계선
    img[:, 8 + box_chars * 22: 9 + box_chars * 22] = (255, 80, 80)
    return Image.fromarray(img.clip(0, 255).astype(np.uint8))


def first_variant(t):
    t = re.sub(r"\{ESC:[HKk]\}", "", t)
    if "{05}{05}{B:" in t or t.startswith("{05}"):
        m = re.search(r"=\d+([^{]+(?:\{(?:V|C|U):[^}]*\}[^{]*)*)\{05\}", t)
        if m:
            return m.group(1)
    return t.split("{05}")[0]


def main():
    out = sys.argv[1]
    hangul = load_hangul(TBL)
    rev = {int.from_bytes(v, "big"): k for k, v in hangul.items()}
    ents = read_entries(open(MSG, "rb").read())
    font = Font()
    ims = []
    for spec in sys.argv[2:]:
        n, _, box = spec.partition(":")
        t = first_variant(decode(ents[int(n)][1], rev))
        ims.append(render_entry(font, t, hangul, int(box or 17)))
    W = max(i.size[0] for i in ims)
    H = sum(i.size[1] + 6 for i in ims)
    sheet = Image.new("RGB", (W, H), (0, 0, 0))
    y = 0
    for im in ims:
        sheet.paste(im, (0, y))
        y += im.size[1] + 6
    sheet.save(out)
    print(out, sheet.size)


if __name__ == "__main__":
    main()
