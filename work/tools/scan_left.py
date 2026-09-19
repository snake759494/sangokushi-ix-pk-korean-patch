# -*- coding: utf-8 -*-
"""빌드 결과(work/patched/*.S9)에 일본어가 남았는지 검사한다.

한글 슬롯은 한글로 읽고, 남은 가나·한자·한자 글리프 태그·2바이트 가나 태그를 찾는다.
스크립트 명령 안의 바이트(01 J xx yy 등)는 제외하려고 s9lex 의 txt 토큰만 본다.
python scan_left.py [--all]
"""
import os
import re
import sys

from msg_dump import read_entries
from s9lex import lex
from s9text import decode, load_hangul
from units import WORK

JP = re.compile(r"[ぁ-ゖァ-ヺー一-鿿々〆]")
GLYPH = re.compile(r"\{U:F0[4-9A][0-9A-F]\}|\{S:[0-9A-F]{4}\}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    hangul = load_hangul(os.path.join(WORK, "font_ko", "hangul.tbl"))
    ko_rev = {int.from_bytes(v, "big"): k for k, v in hangul.items()}
    show_all = "--all" in sys.argv
    for name in ("M_MSG.S9", "M_RTDN.S9"):
        path = os.path.join(WORK, "patched", name)
        if not os.path.exists(path):
            path = os.path.join(WORK, "san9pk", name)
        ents = read_entries(open(path, "rb").read())
        hits = []
        for idx, (_, raw) in enumerate(ents):
            mode = "H"
            for kind, b in lex(raw):
                if kind == "esc" and len(b) == 2:
                    mode = chr(b[1]) if chr(b[1]) in "HKk" else mode
                if kind != "txt":
                    continue
                t = decode(b, ko_rev, mode=mode)
                if JP.search(t) or GLYPH.search(t):
                    hits.append((idx, t))
        print("%s: 일본어가 남은 텍스트 조각 %d개" % (name, len(hits)))
        for idx, t in hits[: (len(hits) if show_all else 40)]:
            print("   #%05d %r" % (idx, t[:60]))


if __name__ == "__main__":
    main()
