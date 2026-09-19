# -*- coding: utf-8 -*-
"""실행파일(SLPM_656.73) UI 문자열 번역 작업.

python elf_jobs.py make     -> trans/jobs/e01.txt (+ 사전에 있는 말은 trans/ko/elf/00_auto.tsv 로 자동 번역)
python elf_jobs.py check [파일...]   -> trans/ko/elf/*.tsv 검사 (슬롯 바이트·폭·서식 지정자·문자)

대상: 포인터로 참조되는 문자열(trans/elf_ref.tsv) 가운데 0x350000~0x370000 영역의 일본어 문자열.
      (용어집·[E ..] 항목으로 이미 바뀌는 곳은 뺀다)
"""
import glob
import os
import re
import sys

import build_text as bt
from make_central import load_label_tsv
from s9text import load_hangul
from units import WORK, line_width
from validate import check_chars, load_tsv

ZONE = (0x350000, 0x370000)
REF = os.path.join(WORK, "trans", "elf_ref.tsv")
ELF_DIR = os.path.join(WORK, "trans", "ko", "elf")
JOB = os.path.join(WORK, "trans", "jobs", "e01.txt")
JP_RE = re.compile(r"[ぁ-ヿ一-鿿]")


def elf_bytes():
    return open(bt.SRC_ELF, "rb").read()


def candidates(elf):
    out = []
    for line in open(REF, encoding="utf-8"):
        off, n, _ = line.rstrip("\n").split("\t", 2)
        off = int(off, 16)
        if not (ZONE[0] <= off < ZONE[1]):
            continue
        end = elf.index(b"\0", off)
        raw = elf[off:end]
        try:
            s = raw.decode("cp932")
        except UnicodeDecodeError:
            continue
        if not JP_RE.search(s):
            continue
        if any(0xFF61 <= ord(c) <= 0xFF9F or (ord(c) < 0x20) for c in s):
            continue
        if raw.find(b"\x1b") >= 0:
            continue
        # 데이터가 우연히 글자로 읽힌 것(疹E, `職, 犒␠ 등)
        if len(s) <= 3 and any(ord(c) < 0x80 for c in s) and "%" not in s:
            continue
        # 이름 입력용 가나 배열·가나 입력 모드 이름, 메모리카드 저장 파일 이름(PS2 본체 화면에 나옴)
        if "あいうえお" in s or "アイウエオ" in s or s in ("かな", "カナ") or "プレイデータ" in s:
            continue
        out.append((off, s))
    return out


def handled_offsets(elf):
    """용어집(ELF/ALL)과 [E ..] 항목이 바꾸는 오프셋."""
    done = set()
    for it in bt.read_items():
        if it["src"] == "E":
            done.add(it["key"])
    for jp, ko, scope, where in bt.read_glossary():
        if scope in ("ELF", "ALL"):
            for o in bt.elf_strings_equal(elf, jp.encode("cp932")):
                if o >= 0x300000:
                    done.add(o)
    return done


def slot(elf, off):
    return bt.elf_slot(elf, off)


def check_one(elf, hangul, off, ko):
    errs = []
    n, avail = slot(elf, off)
    orig = elf[off:off + n].decode("cp932")
    errs += check_chars(ko)
    try:
        b = bt.ko_elf_bytes(ko, hangul)
    except Exception as e:
        return ["인코딩 불가: %s" % e]
    if len(b) + 1 > avail:
        errs.append("바이트 초과 %d > %d" % (len(b), avail - 1))
    lim = max(line_width(orig), bt.ELF_WIDTH_OVERRIDE.get(off, 0))
    if line_width(ko) > lim:
        errs.append("폭 초과 %d > %d" % (line_width(ko), lim))
    fj = re.findall(r"%[-0-9.]*[a-zA-Z]", orig)
    fk = re.findall(r"%[-0-9.]*[a-zA-Z]", ko)
    if fj != fk:
        errs.append("서식 지정자 불일치 %s / %s" % (fj, fk))
    return errs


def make():
    elf = elf_bytes()
    hangul = load_hangul(bt.HANGUL_TBL)
    done = handled_offsets(elf)
    labels = load_label_tsv()
    cands = [(o, s) for o, s in candidates(elf) if o not in done]
    auto, todo = [], []
    for off, s in cands:
        ko = labels.get(s)
        if ko is not None and not check_one(elf, hangul, off, ko):
            auto.append((off, ko))
        else:
            todo.append((off, s))
    os.makedirs(ELF_DIR, exist_ok=True)
    with open(os.path.join(ELF_DIR, "00_auto.tsv"), "w", encoding="utf-8", newline="\n") as f:
        f.write("# 라벨 사전(labels_*.tsv)과 원문이 같은 실행파일 문자열 (elf_jobs.py make 가 생성)\n")
        for off, ko in auto:
            f.write("0x%06X\t%s\n" % (off, ko))
    lines = ["# 작업 e01 — 실행파일 속 메뉴·라벨 문자열",
             "# 먼저 work/trans/번역규칙.md 를 끝까지 읽고 그대로 따른다.",
             "# 결과 파일: work/trans/ko/elf/e01.tsv  (한 줄에 하나: 오프셋<TAB>번역)",
             "# 검사: python work/tools/elf_jobs.py check   (오류가 0이 될 때까지 고친다)",
             "# 머리의 [폭N 바이트M]: 화면 폭(한글 1자=2, 반각=1) N 이하, 인코딩 바이트(한글 1자=2, 반각=1) M 이하.",
             "# 주변 문자열(같은 메뉴·표)의 번역과 어울리게 옮긴다. 이미 번역된 이웃은 (참고) 로 보여 준다.",
             "# %d, %s 같은 서식 지정자는 그대로 두고 순서도 바꾸지 않는다.",
             ""]
    auto_map = dict(auto)
    all_sorted = sorted([(o, s, None) for o, s in todo] + [(o, s, auto_map[o]) for o, s in cands if o in auto_map])
    for off, s, ko in all_sorted:
        n, avail = slot(elf, off)
        if ko is not None:
            lines.append("(참고) 0x%06X %s = %s" % (off, s, ko))
            continue
        lines.append("@0x%06X [폭%d 바이트%d]" % (off, line_width(s), avail - 1))
        lines.append(s)
    with open(JOB, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print("후보 %d, 자동 %d, 작업 %d -> %s" % (len(cands), len(auto), len(todo), JOB))


def check(files):
    elf = elf_bytes()
    hangul = load_hangul(bt.HANGUL_TBL)
    files = files or sorted(glob.glob(os.path.join(ELF_DIR, "*.tsv")))
    job_offs = set()
    if os.path.exists(JOB):
        for line in open(JOB, encoding="utf-8"):
            m = re.match(r"@0x([0-9A-F]+) ", line)
            if m:
                job_offs.add(int(m.group(1), 16))
    got = set()
    nerr = 0
    for path in files:
        for key, ko, where in load_tsv(path):
            off = int(key, 16)
            got.add(off)
            e = check_one(elf, hangul, off, ko)
            for x in e:
                print("오류 %s %s: %s  (%r)" % (where, key, x, ko))
                nerr += 1
    missing = sorted(job_offs - got)
    if missing:
        print("빠진 문자열 %d개: %s" % (len(missing), " ".join("0x%06X" % o for o in missing[:30])))
    print("검사: 오류 %d, 빠짐 %d" % (nerr, len(missing)))
    return nerr


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    if sys.argv[1] == "make":
        make()
    elif sys.argv[1] == "check":
        return 1 if check(sys.argv[2:]) else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
