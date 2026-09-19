# -*- coding: utf-8 -*-
"""문구를 ELF 문자열 목록과 M_MSG 항목에서 동시에 찾는다 (완전일치 우선 표시).

사용법: python find_all.py 문구 [문구 ...]
"""
import os
import re
import sys

from msg_dump import read_entries
from s9text import decode

HERE = os.path.dirname(os.path.abspath(__file__))


def load():
    elf = []
    with open(os.path.join(HERE, "..", "trans", "ELF_strings.txt"), encoding="utf-8") as f:
        for line in f:
            off, va, slot, s = line.rstrip("\n").split("\t", 3)
            elf.append((off, int(slot), s))
    ents = read_entries(open(os.path.join(HERE, "..", "san9pk", "M_MSG.S9"), "rb").read())
    msgs = [re.sub(r"\{ESC:[HK]\}", "", decode(raw)) for _, raw in ents]
    return elf, msgs


def main():
    elf, msgs = load()
    for q in sys.argv[1:]:
        e_exact = [(o, sl) for o, sl, s in elf if s == q]
        e_part = [(o, sl, s) for o, sl, s in elf if q in s and s != q]
        m_exact = [i for i, t in enumerate(msgs) if t.split("{05}")[0] == q]
        m_part = [i for i, t in enumerate(msgs) if q in t and i not in m_exact]
        print("== %s" % q)
        if e_exact:
            print("   ELF= " + " ".join("%s(%d)" % x for x in e_exact[:8]))
        if m_exact:
            print("   MSG= " + " ".join("#%d" % i for i in m_exact[:12]))
        if e_part:
            print("   ELF~ " + " | ".join("%s(%d):%s" % x for x in e_part[:5]))
        if m_part:
            print("   MSG~ " + " | ".join("#%d:%s" % (i, msgs[i][:50].replace("\n", "⏎")) for i in m_part[:4]))


if __name__ == "__main__":
    main()
