# -*- coding: utf-8 -*-
"""패치된 실행파일의 데이터 영역에 남은 일본어 문자열(NUL 로 끝나는 SJIS 문자열)을 찾는다.

한글 슬롯(889F~94FC)은 한글이므로 제외하고, 가나·그 밖의 한자가 든 문자열만 보여 준다.
python scan_elf_left.py [시작 끝]   (기본 0x300000 ~ 파일 끝)
"""
import os
import re
import sys

from units import WORK

JP = re.compile(r"[ぁ-ゖァ-ヺ一-鿿]")


def is_hangul_slot(code):
    return 0x889F <= code <= 0x94FC


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    elf = open(os.path.join(WORK, "patched", "SLPM_656.73"), "rb").read()
    lo = int(sys.argv[1], 0) if len(sys.argv) > 2 else 0x300000
    hi = int(sys.argv[2], 0) if len(sys.argv) > 2 else len(elf)
    out = []
    i = lo
    while i < hi:
        if elf[i] == 0:
            i += 1
            continue
        j = elf.find(b"\0", i)
        raw = elf[i:j]
        # 문자열로 해석
        s, k, ok, jp = [], 0, True, False
        while k < len(raw):
            b = raw[k]
            if (0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC) and k + 1 < len(raw):
                code = (b << 8) | raw[k + 1]
                if is_hangul_slot(code):
                    s.append("가")
                else:
                    try:
                        ch = raw[k:k + 2].decode("cp932")
                    except UnicodeDecodeError:
                        ok = False
                        break
                    s.append(ch)
                    if JP.search(ch):
                        jp = True
                k += 2
            elif 0x20 <= b < 0x7F or b in (0x0A,):
                s.append(chr(b))
                k += 1
            else:
                ok = False
                break
        text = "".join(s)
        if ok and jp and len(raw) >= 2 and not (len(text) <= 3 and re.search(r"[\x20-\x7e]", text)):
            out.append((i, text))
        i = j + 1
    print("일본어가 남은 문자열 %d개" % len(out))
    for off, t in out:
        print("  0x%06X %s" % (off, t[:60]))


if __name__ == "__main__":
    main()
