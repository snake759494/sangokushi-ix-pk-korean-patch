# -*- coding: utf-8 -*-
"""SLPM_656.73 의 '진짜' 텍스트 문자열 목록을 만든다 (번역 대상 추출용).

조건: 데이터 영역(0x300000~), 4바이트 정렬 시작, 앞 바이트 NUL, NUL 종료,
      모든 문자가 유효한 SJIS 텍스트(전각/반각가나/ASCII 인쇄문자/\\n/ESC), 가나·한자 1자 이상.
출력: work/trans/elf_text.tsv   오프셋<TAB>슬롯바이트<TAB>문자열(\\n 은 ⏎, ESC 는 {ESC})
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ELF = os.path.join(HERE, "..", "iso", "SLPM_656.73")
OUT = os.path.join(HERE, "..", "trans", "elf_text.tsv")
DATA_START, DATA_END = 0x300000, 0x393D80


def valid_text(raw):
    i, n = 0, len(raw)
    jp = 0
    while i < n:
        b = raw[i]
        if 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC:
            if i + 1 >= n:
                return 0
            pair = raw[i:i + 2]
            try:
                ch = pair.decode("cp932")
            except UnicodeDecodeError:
                return 0
            if len(ch) != 1 or 0xE000 <= ord(ch) <= 0xF8FF:
                return 0
            if re.match(r"[ぁ-ヿ一-鿿々]", ch):
                jp += 1
            i += 2
        elif 0xA1 <= b <= 0xDF:
            jp += 1
            i += 1
        elif 0x20 <= b <= 0x7E or b in (0x0A, 0x1B):
            i += 1
        else:
            return 0
    return jp


def scan(d):
    out = []
    o = DATA_START
    while o < DATA_END:
        if d[o] != 0 and o % 4 == 0 and d[o - 1] == 0:
            e = d.index(b"\0", o)
            raw = d[o:e]
            if e - o <= 400:
                jp = valid_text(raw)
                if jp >= 1:
                    z = e
                    while z < len(d) and d[z] == 0:
                        z += 1
                    out.append((o, z - o, raw))
                    o = e
                    continue
            o = e if e > o else o + 1
        else:
            o += 1
    return out


def main():
    d = open(ELF, "rb").read()
    rows = scan(d)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        for o, slot, raw in rows:
            s = raw.decode("cp932").replace("\n", "⏎").replace("\x1b", "{ESC}")
            f.write("0x%06X\t%d\t%s\n" % (o, slot, s))
    print(len(rows), "strings ->", OUT)


if __name__ == "__main__":
    main()
