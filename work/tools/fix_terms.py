# -*- coding: utf-8 -*-
"""작업 결과(trans/jobs/out/*.tsv)의 용어 표기를 규칙서에 맞게 통일한다.

원문에 해당 용어가 있는 단위에서만, 정해 둔 한국어 표기를 바꾼다(번역문을 새로 만드는 것이 아니라
여러 작업자가 서로 다르게 적은 같은 용어를 하나로 맞추는 교정). 바꾼 뒤 검사에 걸리면 바꾸지 않는다.
python fix_terms.py [--dry]
"""
import glob
import os
import sys

from build_all import load_all_units
from units import WORK
from validate import check_unit

# (원문에 있어야 하는 말, 바꿀 표기, 바른 표기, 대사(dlg)에도 적용?)
# 自勢力/他勢力 의 UI 용어(자세력/타세력)는 화면 설명에만 맞춘다. 인물 대사는 「다른 세력」 등 자연스러운 말을 둔다.
RULES = [
    ("実行武将", "실행 무장", "실행무장", True),
    ("桃園", "도원의 맹세", "도원결의", True),
    ("自勢力", "자기 세력", "자세력", False),
    ("自勢力", "아군 세력", "자세력", False),
    ("他勢力", "다른 세력", "타세력", False),
    ("三國志Ⅷ読込", "삼국지Ⅷ 로드", "삼국지Ⅷ로드", True),
    ("攻略難度", "공략 난이도", "공략난도", True),
]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    dry = "--dry" in sys.argv
    units = load_all_units()
    changed = 0
    for path in sorted(glob.glob(os.path.join(WORK, "trans", "jobs", "out", "*.tsv"))):
        lines = open(path, encoding="utf-8").read().split("\n")
        out = []
        for line in lines:
            if "\t" in line and not line.startswith("#"):
                uid, ko = line.split("\t", 1)
                u = units.get(uid)
                if u is not None:
                    new = ko
                    for jp, bad, good, in_dlg in RULES:
                        if u.kind == "dlg" and not in_dlg:
                            continue
                        if jp in u.jp and bad in new:
                            new = new.replace(bad, good)
                    if new != ko:
                        errs, _ = check_unit(u, new.replace("⏎", "\n").replace("⎵", " "))
                        if errs:
                            print("건너뜀 %s %s: %s" % (os.path.basename(path), uid, errs))
                        else:
                            print("%s %s: %s -> %s" % (os.path.basename(path), uid, ko[:40], new[:40]))
                            line = uid + "\t" + new
                            changed += 1
            out.append(line)
        if not dry:
            open(path, "w", encoding="utf-8", newline="\n").write("\n".join(out))
    print("바꾼 단위 %d개%s" % (changed, " (시험)" if dry else ""))


if __name__ == "__main__":
    main()
