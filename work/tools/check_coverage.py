# -*- coding: utf-8 -*-
"""스크린샷 원문 기록(trans/screens_*.txt)의 일본어 문구가 모두 번역되었는지 점검한다.

각 문구를 원본 M_MSG 항목·ELF 문자열에서 찾고, 그 항목이 패치 결과에서 바뀌었는지 확인한다.
사용법: python check_coverage.py
"""
import glob
import os
import re
import struct

from msg_dump import read_entries
from s9text import decode

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "..")

JP = re.compile(r"[ぁ-ヿ一-鿿々〆ー・「」『』（）【】？！、。～＜＞：；０-９Ａ-Ｚａ-ｚ]+")


def plain(t):
    return re.sub(r"\{ESC:[HKk]\}", "", t)


def main():
    orig = read_entries(open(os.path.join(WORK, "san9pk", "M_MSG.S9"), "rb").read())
    new = read_entries(open(os.path.join(WORK, "patched", "M_MSG.S9"), "rb").read())
    otext = [plain(decode(r)) for _, r in orig]
    changed = {i for i, ((_, a), (_, b)) in enumerate(zip(orig, new)) if a != b}
    elf_o = open(os.path.join(WORK, "iso", "SLPM_656.73"), "rb").read()
    elf_n = open(os.path.join(WORK, "patched", "SLPM_656.73"), "rb").read()

    phrases = []
    for fn in sorted(glob.glob(os.path.join(WORK, "trans", "screens_*.txt"))):
        for line in open(fn, encoding="utf-8"):
            if line.startswith("#"):
                continue
            line = re.sub(r"^\[[^\]]*\]", "", line)
            for part in re.split(r"[ /|:]+", line):
                for m in JP.finditer(part):
                    s = m.group(0).strip("「」（）、。")
                    if len(s) >= 2 and re.search(r"[ぁ-ヿ一-鿿]", s):
                        phrases.append(s)
    seen = set()
    missing = []
    for p in phrases:
        if p in seen:
            continue
        seen.add(p)
        hits = [i for i, t in enumerate(otext) if p in t.replace("\n", "")]
        exact = [i for i in hits if otext[i].split("{05}")[0].replace("\n", "") == p]
        cand = exact or hits
        try:
            pb = p.encode("cp932") + b"\0"
        except UnicodeEncodeError:
            pb = None
        elf_hits = []
        if pb:
            i = elf_o.find(pb)
            while i >= 0:
                if i >= 0x300000 and elf_o[i - 1] == 0:
                    elf_hits.append(i)
                i = elf_o.find(pb, i + 1)
        msg_ok = any(i in changed for i in cand) if cand else None
        elf_ok = bool(elf_hits) and all(elf_n[o:o + len(pb)] != elf_o[o:o + len(pb)] for o in elf_hits)
        if cand or elf_hits:
            if not (msg_ok or elf_ok):
                missing.append((p, cand[:5], [hex(o) for o in elf_hits[:3]]))
    print("문구 %d개 점검" % len(seen))
    for p, c, e in missing:
        print("미번역: %-30s MSG%s ELF%s" % (p, c, e))
    print("미번역 %d개" % len(missing))


if __name__ == "__main__":
    main()
