# -*- coding: utf-8 -*-
"""번역 일관성 점검 (자동 번역이 아니라 '확인'용).

1) 고유명사: 원문에 나오는 인명·지명·아이템·관직이 번역문에 목록 표기대로 들어 있는지
2) 용어 흔들림: 같은 원문 용어가 여러 한국어로 옮겨진 경우 (지정한 용어만)
사용법: python qa_names.py [작업이름...]   (없으면 trans/ko/units/*.tsv 전체 + jobs/out)
결과: work/trans/qa_names.txt
"""
import glob
import os
import sys
from collections import defaultdict

from build_all import load_all_units, load_translations
from make_jobs import build_dict
from units import TAG, WORK
from validate import load_tsv

OUT = os.path.join(WORK, "trans", "qa_names.txt")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    units = load_all_units()
    tr, where = load_translations()
    # 작업 결과(아직 합치지 않은 것 포함)
    for path in sorted(glob.glob(os.path.join(WORK, "trans", "jobs", "out", "*.tsv"))):
        for uid, ko, w in load_tsv(path):
            tr[uid] = ko
            where[uid] = w
    names, _terms = build_dict(units, tr)
    keys = sorted(names, key=lambda s: -len(s))
    miss = defaultdict(list)
    for uid, ko in tr.items():
        u = units.get(uid)
        if u is None or u.kind in ("name", "ruby", "label"):
            continue
        jp = u.jp
        used = []
        for k in keys:
            if k in jp and not any(k in x for x in used):
                used.append(k)
                want = names[k]
                if want.replace(" ", "") not in TAG.sub("", ko).replace(" ", ""):
                    miss[k].append((uid, ko))
    lines = []
    total = 0
    for k in sorted(miss, key=lambda k: -len(miss[k])):
        lst = miss[k]
        total += len(lst)
        lines.append("## %s = %s  (%d곳)" % (k, names[k], len(lst)))
        for uid, ko in lst[:8]:
            lines.append("   %s  %s | %s" % (uid, units[uid].jp.replace("\n", "⏎")[:40], ko.replace("\n", "⏎")[:60]))
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print("고유명사 불일치 후보 %d곳 (%d종) -> %s" % (total, len(miss), OUT))


if __name__ == "__main__":
    main()
