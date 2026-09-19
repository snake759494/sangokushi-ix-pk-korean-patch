# -*- coding: utf-8 -*-
"""대사창 넘침 위험 찾기.

변수 {V:..} 를 8칸으로 세는 바람에 원문 폭(ow)이 부풀어 단위 허용 폭이 28 보다 커진 경우,
변수가 없는 번역 줄이 '변수 없는 원문 줄의 최대 폭'과 28 가운데 큰 값을 넘으면 넘침 위험으로 본다.
python scan_wide.py [--fix-list]   결과: work/trans/wide_lines.txt
"""
import os
import re
import sys

from build_all import load_all_units, load_translations
from units import WORK, line_width

OUT = os.path.join(WORK, "trans", "wide_lines.txt")


def plain_limit(u):
    lines = u.jp.split("\n")
    plain = [line_width(l) for l in lines if "{V:" not in l]
    return max([28] + plain)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    units = load_all_units()
    tr, where = load_translations()
    rows = []
    for uid, ko in tr.items():
        u = units.get(uid)
        if u is None or u.kind != "dlg" or u.width is None or u.width <= 28:
            continue
        lim = plain_limit(u)
        if lim >= u.width:
            continue
        for ln in ko.split("\n"):
            if "{V:" in ln:
                continue
            w = line_width(ln)
            if w > lim:
                rows.append((uid, where[uid], u.width, lim, w, ln))
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write("%s\t%s\t허용%d 실제한계%d 폭%d\t%s\n" % r)
    print("넘침 위험 줄 %d개 (단위 %d개) -> %s" % (len(rows), len({r[0] for r in rows}), OUT))
    for r in rows[:30]:
        print("  %s %s 허용%d 한계%d 폭%d %r" % r)


if __name__ == "__main__":
    main()
