# -*- coding: utf-8 -*-
"""번역 작업 결과(work/trans/jobs/out/*.tsv)를 같은 원문 단위까지 펼쳐
work/trans/ko/units/job_<작업>.tsv 로 옮긴다. 검사에 걸린 줄은 옮기지 않고 알려 준다.
"""
import glob
import os
import sys

from build_all import load_all_units
from units import WORK
from check_job import out_files
from validate import check_unit, load_tsv

JOBS = os.path.join(WORK, "trans", "jobs")
DEST = os.path.join(WORK, "trans", "ko", "units")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    units = load_all_units()
    total, bad = 0, 0
    names = sorted({os.path.splitext(os.path.basename(p))[0].split("_")[0]
                    for p in glob.glob(os.path.join(JOBS, "out", "*.tsv"))})
    for name in names:
        mp = {}
        map_path = os.path.join(JOBS, name + ".map.tsv")
        if not os.path.exists(map_path):
            print("%s: map 없음, 건너뜀" % name)
            continue
        for line in open(map_path, encoding="utf-8"):
            rep, others = line.rstrip("\n").split("\t")
            mp[rep] = [x for x in others.split(",") if x]
        out = []
        rows = []
        for path in out_files(name):
            rows += load_tsv(path)
        for uid, ko, where in rows:
            if uid not in units or uid not in mp:
                print("  %s: 알 수 없는 단위 %s" % (where, uid))
                bad += 1
                continue
            e, _ = check_unit(units[uid], ko)
            if e:
                print("  %s %s: %s" % (where, uid, "; ".join(e)))
                bad += 1
                continue
            for x in [uid] + mp[uid]:
                out.append((x, ko))
        with open(os.path.join(DEST, "job_%s.tsv" % name), "w", encoding="utf-8", newline="\n") as f:
            for uid, ko in out:
                f.write("%s\t%s\n" % (uid, ko.replace("\n", "⏎")))
        total += len(out)
    print("합친 단위 %d개, 제외 %d줄" % (total, bad))


if __name__ == "__main__":
    main()
