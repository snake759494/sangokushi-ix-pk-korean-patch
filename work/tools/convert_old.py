# -*- coding: utf-8 -*-
"""초반 테스트 번역(조각 방식, build_text.py 결과)을 단위 번역으로 옮긴다.

python convert_old.py 옛_M_MSG.S9
  -> work/trans/ko/units_old.tsv   (단위ID<TAB>번역)
     일본어가 남은(일부만 번역된) 단위는 units_old_partial.tsv 에 참고용으로 따로 적는다.
"""
import os
import re
import sys

from msg_dump import read_entries
from s9lex import lex
from s9text import decode, load_hangul
from units import SRC, WORK, entry_units, has_jp

TEXTISH = ("txt", "var", "col", "esc")


def runs(toks):
    """(앞선 구조 토큰 수, 토큰 시작, 끝) 목록과 구조 토큰 목록."""
    out, struct_toks = [], []
    i, n = 0, len(toks)
    while i < n:
        if toks[i][0] in TEXTISH:
            j = i
            while j < n and toks[j][0] in TEXTISH:
                j += 1
            out.append((len(struct_toks), i, j))
            i = j
        else:
            struct_toks.append(toks[i][1])
            i += 1
    return out, struct_toks


def main():
    old_path = sys.argv[1]
    hangul = load_hangul(os.path.join(WORK, "font_ko", "hangul.tbl"))
    ko_rev = {int.from_bytes(v, "big"): k for k, v in hangul.items()}
    orig = read_entries(open(SRC["M"], "rb").read())
    new = read_entries(open(old_path, "rb").read())
    assert len(orig) == len(new)
    done, partial, bad = {}, {}, []
    for idx, ((_, a), (_, b)) in enumerate(zip(orig, new)):
        if a == b:
            continue
        ta, us = entry_units("M", idx, a)
        tb = lex(b)
        ra, sa = runs(ta)
        rb, sb = runs(tb)
        if sa != sb:
            bad.append(idx)
            continue
        by_key = {k: (lo, hi) for k, lo, hi in rb}
        key_of = {lo: k for k, lo, hi in ra}
        for u in us:
            k = key_of[u.tok_lo]
            if k not in by_key:
                ko = ""
            else:
                lo, hi = by_key[k]
                raw = b"".join(t[1] for t in tb[lo:hi])
                ko = decode(raw, ko_rev, mode=u.mode_in)
            ko = re.sub(r"\{ESC:[HK]\}", "", ko)
            if ko == u.jp:
                continue
            if has_jp(ko):
                partial[u.uid] = ko
            else:
                done[u.uid] = ko
    out = os.path.join(WORK, "trans", "ko", "units_old.tsv")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        for uid in sorted(done):
            f.write("%s\t%s\n" % (uid, done[uid].replace("\n", "⏎")))
    with open(os.path.join(WORK, "trans", "ko", "units_old_partial.tsv"), "w", encoding="utf-8", newline="\n") as f:
        for uid in sorted(partial):
            f.write("%s\t%s\n" % (uid, partial[uid].replace("\n", "⏎")))
    print("옮긴 단위 %d개, 일부만 번역 %d개, 구조 불일치 항목 %d개 %s" % (len(done), len(partial), len(bad), bad[:20]))


if __name__ == "__main__":
    main()
