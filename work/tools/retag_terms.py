# -*- coding: utf-8 -*-
"""이미 병합된 번역(trans/ko/units*.tsv, units/*.tsv)의 용어 표기를 바꾼다.

fix_terms.py 는 병합 전 작업 결과(trans/jobs/out)를 손보는 도구이고, 이 도구는 배포 뒤 제보로
용어를 고칠 때 병합본을 직접 고친다. 원문에 해당 낱말이 있는 단위에서만 바꾸고, 바꾼 뒤 검사에
걸리면 건너뛴다.

python retag_terms.py [--dry]
"""
import glob
import os
import sys

from build_all import KO_DIR, load_all_units
from validate import check_unit

# (원문에 있어야 하는 말, 바꿀 표기, 바른 표기)  2026-09-20 카페 제보(안도리르) 반영: 정발판 표기에 맞춤
RULES = [
    ("心攻", "심공", "배반"),     # 적 병사를 꾀어 아군으로 돌리는 병법
    ("教唆", "선동", "교사"),
    ("罵声", "야유", "매도"),
    ("罠破", "간파", "파괴"),     # 看破(간파) 와 헷갈리던 병법 이름
    ("改修", "개수", "보수"),
    ("偽報", "위보", "허보"),
    ("呼寄", "호출", "소환"),
    ("呼び寄せ", "호출", "소환"),
]

# 낱말 하나로 쓰인 자리만 바꾼다 (성채·연노·책략 같은 말 속의 글자는 그대로 둔다)
WORD_RULES = [
    ("砦", "채", "요새"),
    ("櫓", "노", "망루"),
    ("柵", "책", "목책"),
]
JOSA = ("를|을|은|는|이|가|와|과|에|도|로|의|만|부터|까지|보다|처럼|나|랑|였")   # 조사 첫 글자로 판별


def word_sub(text, bad, good):
    import re
    pat = re.compile(r"(?<![가-힣])%s(?=(?:%s)|[^가-힣]|$)" % (bad, JOSA))
    return pat.sub(good, text)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    dry = "--dry" in sys.argv
    units = load_all_units()
    files = [os.path.join(KO_DIR, "units_central.tsv"), os.path.join(KO_DIR, "units_old.tsv")]
    files += sorted(glob.glob(os.path.join(KO_DIR, "units", "*.tsv")))
    changed = skipped = 0
    for path in files:
        if not os.path.exists(path):
            continue
        lines = open(path, encoding="utf-8").read().split("\n")
        out = []
        for line in lines:
            if "\t" in line and not line.startswith("#"):
                uid, ko = line.split("\t", 1)
                u = units.get(uid)
                if u is not None:
                    new = ko
                    for jp, bad, good in RULES:
                        if jp in u.jp and bad in new:
                            new = new.replace(bad, good)
                    for jp, bad, good in WORD_RULES:
                        if jp in u.jp and bad in new:
                            new = word_sub(new, bad, good)
                    if new != ko:
                        errs, _ = check_unit(u, new.replace("⏎", "\n").replace("⎵", " "))
                        if errs:
                            print("건너뜀 %s %s: %s" % (os.path.basename(path), uid, errs))
                            skipped += 1
                        else:
                            print("%-20s %s: %s -> %s" % (os.path.basename(path), uid, ko[:36], new[:36]))
                            line = uid + "\t" + new
                            changed += 1
            out.append(line)
        if not dry:
            open(path, "w", encoding="utf-8", newline="\n").write("\n".join(out))
    print("바꾼 단위 %d개, 건너뜀 %d개%s" % (changed, skipped, " (시험)" if dry else ""))


if __name__ == "__main__":
    main()
