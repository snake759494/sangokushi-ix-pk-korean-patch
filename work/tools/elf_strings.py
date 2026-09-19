# -*- coding: utf-8 -*-
"""SLPM_656.73 에서 Shift-JIS 문자열(전각 1자 이상 포함, NUL 종료)을 찾아 덤프한다.

출력: work/trans/ELF_strings.txt  (파일오프셋<TAB>가상주소<TAB>슬롯크기<TAB>문자열)
슬롯크기 = 다음 문자열 시작까지의 바이트 수 (제자리 교체 시 넘으면 안 되는 최대 길이 참고용)
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ELF = os.path.join(HERE, "..", "iso", "SLPM_656.73")
OUT = os.path.join(HERE, "..", "trans", "ELF_strings.txt")

LEAD = set(range(0x81, 0xA0)) | set(range(0xE0, 0xFD))


def scan(data):
    i, n = 0, len(data)
    while i < n:
        j = i
        wide = 0
        while j < n:
            b = data[j]
            if b in LEAD and j + 1 < n and 0x40 <= data[j + 1] <= 0xFC and data[j + 1] != 0x7F:
                j += 2
                wide += 1
            elif 0x20 <= b <= 0x7E or b in (0x0A, 0x1B) or 0xA1 <= b <= 0xDF:
                j += 1
            else:
                break
        if wide and j < n and data[j] == 0 and j > i:
            yield i, data[i:j]
            i = j + 1
        else:
            i = j + 1 if j == i else j


def main():
    data = open(ELF, "rb").read()
    found = list(scan(data))
    with open(OUT, "w", encoding="utf-8") as f:
        for k, (off, raw) in enumerate(found):
            nxt = found[k + 1][0] if k + 1 < len(found) else off + len(raw) + 1
            slot = nxt - off
            try:
                s = raw.decode("cp932")
            except UnicodeDecodeError:
                s = raw.decode("cp932", "replace")
            s = s.replace("\n", "\\n").replace("\x1b", "\\e")
            f.write("0x%06X\t0x%08X\t%d\t%s\n" % (off, off - 0x80 + 0x100000, slot, s))
    print(len(found), "strings ->", OUT)


if __name__ == "__main__":
    main()
