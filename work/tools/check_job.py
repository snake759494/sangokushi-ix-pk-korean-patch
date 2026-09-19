# -*- coding: utf-8 -*-
"""번역 작업 결과 검사.

python check_job.py d01          work/trans/jobs/out/d01.tsv 검사
python check_job.py d01 --all    오류가 없어도 경고까지 모두 보여 준다

검사 항목: 빠진 단위, 없는 단위ID, 폭, 줄 수, 제어 태그, 한글(KS X 1001), 가나·한자,
          {V:..} 변수 바로 뒤 조사(을/를/이/가/은/는/과/와/로/으로...)
"""
import os
import sys

from build_all import load_all_units
from units import WORK
from validate import check_unit, load_tsv

JOBS = os.path.join(WORK, "trans", "jobs")


def out_files(name):
    """결과 파일: out/<작업>.tsv 와 나눠 쓴 out/<작업>_1.tsv, out/<작업>_2.tsv ..."""
    import glob
    files = []
    main = os.path.join(JOBS, "out", name + ".tsv")
    if os.path.exists(main):
        files.append(main)
    files += sorted(glob.glob(os.path.join(JOBS, "out", name + "_*.tsv")))
    return files


def job_uids(name):
    reps = []
    for line in open(os.path.join(JOBS, name + ".map.tsv"), encoding="utf-8"):
        reps.append(line.split("\t")[0])
    return reps


def check(name, units=None, show_warn=False, quiet=False):
    units = units or load_all_units()
    reps = job_uids(name)
    outs = out_files(name)
    if not outs:
        print("%s: 결과 파일 없음 (%s)" % (name, os.path.join(JOBS, "out", name + ".tsv")))
        return None
    rows = []
    for out in outs:
        rows += load_tsv(out)
    got = {}
    errs, warns = [], []
    for uid, ko, where in rows:
        if uid not in units or uid not in reps:
            errs.append("%s %s: 이 작업에 없는 단위ID" % (where, uid))
            continue
        if uid in got:
            errs.append("%s %s: 같은 단위ID 가 두 번 나옴" % (where, uid))
        got[uid] = ko
        e, w = check_unit(units[uid], ko)
        u = units[uid]
        for x in e:
            errs.append("%s %s: %s" % (where, uid, x))
        for x in w:
            warns.append("%s %s: %s" % (where, uid, x))
    missing = [u for u in reps if u not in got]
    if not quiet:
        for x in errs:
            print("오류", x)
        if show_warn or not errs:
            for x in warns:
                print("경고", x)
        if missing:
            print("빠진 단위 %d개: %s%s" % (len(missing), " ".join(missing[:30]), " ..." if len(missing) > 30 else ""))
        print("%s: 단위 %d개 중 %d개 번역, 오류 %d, 경고 %d, 빠짐 %d" % (
            name, len(reps), len(got), len(errs), len(warns), len(missing)))
    return len(errs), len(missing), len(got), len(reps)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    r = check(sys.argv[1], show_warn="--all" in sys.argv)
    return 0 if r and r[0] == 0 and r[1] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
