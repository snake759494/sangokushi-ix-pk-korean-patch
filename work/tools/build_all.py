# -*- coding: utf-8 -*-
"""단위 번역을 적용해 work/patched/ 에 M_MSG.S9, M_RTDN.S9, SLPM_656.73 을 만든다.

입력 (work/trans/ko/)
  units_central.tsv   고유명사·라벨·읽기 (make_central.py 가 생성)
  units_old.tsv       초반 테스트 번역 (convert_old.py 가 생성)
  units/*.tsv         번역 작업 결과 (나중 파일이 앞 파일을 덮어쓴다; 파일 이름 순)
  우선순위: central < old < units/*.tsv
  ELF: glossary.tsv(ELF/ALL) + *.txt 의 [E ..] 항목(build_text 형식) + elf/*.tsv (오프셋<TAB>번역)

검증 오류가 하나라도 있으면 파일을 쓰지 않는다 (--force 로 오류 단위만 빼고 빌드).
사용법: python build_all.py [--force] [--pad-msg 0x크기]
"""
import glob
import os
import re
import struct
import sys
from collections import Counter, defaultdict

import build_text as bt
from msg_dump import read_entries
from s9text import decode, load_hangul
from units import SRC, WORK, apply_entry, entry_units, classify_final
from validate import KO_DIR, check_chars, check_unit, load_tsv

OUT_DIR = os.path.join(WORK, "patched")
REPORT = os.path.join(WORK, "trans", "build_report.txt")

MSG_TABLE_INDEX, RTDN_TABLE_INDEX = 8, 9
MSG_SIZE_SITES = [(0x1535CC, 0x1535E8), (0x21104C, 0x211054), (0x20FDD4, 0x20FDE0)]
RTDN_SIZE_SITES = [(0x153604, 0x153618), (0x211048, 0x211050), (0x20FDD0, 0x20FDDC)]
ORIG_ALLOC = {"M": 0xD6800, "R": 0x14000}
FREE_START, FREE_END = 1121523, 1125000
DATA_START = 0x300000


def v2o(v):
    return v - 0x100000 + 0x80


def load_all_units():
    units = {}
    for src in "MR":
        ents = read_entries(open(SRC[src], "rb").read())
        for idx, (_, raw) in enumerate(ents):
            _, us = entry_units(src, idx, raw)
            for u in us:
                classify_final(u)
                units[u.uid] = u
    return units


def load_translations():
    tr, where = {}, {}
    files = [os.path.join(KO_DIR, "units_central.tsv"), os.path.join(KO_DIR, "units_old.tsv")]
    files += sorted(glob.glob(os.path.join(KO_DIR, "units", "*.tsv")))
    for path in files:
        if not os.path.exists(path):
            continue
        old = os.path.basename(path) == "units_old.tsv"
        for uid, ko, w in load_tsv(path):
            if old and ko == "{ESC:k}" and uid in tr:
                continue           # 테스트 때 비워 둔 읽기는 중앙 번역을 쓴다
            tr[uid] = ko
            where[uid] = w
    return tr, where


def pack(raws):
    n = len(raws)
    head = struct.pack("<H", n)
    offs, pos = [], 2 + 4 * n
    for r in raws:
        offs.append(pos)
        pos += len(r)
    return head + struct.pack("<%dI" % n, *offs) + b"".join(raws)


def build_file(src, tr, units, hangul, errors_ok):
    ents = read_entries(open(SRC[src], "rb").read())
    ko_rev = {int.from_bytes(v, "big"): k for k, v in hangul.items()}
    by_entry = defaultdict(dict)
    for uid, ko in tr.items():
        u = units.get(uid)
        if u is not None and u.src == src:
            by_entry[u.entry][uid] = ko
    raws = []
    for idx, (_, raw) in enumerate(ents):
        t = by_entry.get(idx)
        if not t:
            raws.append(raw)
            continue
        new = apply_entry(src, idx, raw, t, hangul)
        # 왕복 확인: 번역 뒤 항목의 구조 토큰은 원문과 같아야 한다
        a = [x for x in entry_units(src, idx, raw)[0] if x[0] not in ("txt", "var", "col", "esc")]
        from s9lex import lex
        b = [x for x in lex(new) if x[0] not in ("txt", "var", "col", "esc")]
        if a != b:
            raise SystemExit("%s#%d 스크립트 구조가 바뀜 (번역문에 제어 바이트?)" % (src, idx))
        raws.append(new)
    return pack(raws)


def patch_size_sites(elf, sites, old, new):
    for lui_v, ori_v in sites:
        lo, oo = v2o(lui_v), v2o(ori_v)
        lui = struct.unpack_from("<I", elf, lo)[0]
        ori = struct.unpack_from("<I", elf, oo)[0]
        if (lui >> 26) != 0x0F or (lui & 0xFFFF) != (old >> 16) or (ori >> 26) != 0x0D or (ori & 0xFFFF) != (old & 0xFFFF):
            raise SystemExit("크기 상수 위치 확인 실패 0x%X" % lui_v)
        struct.pack_into("<I", elf, lo, (lui & 0xFFFF0000) | (new >> 16))
        struct.pack_into("<I", elf, oo, (ori & 0xFFFF0000) | (new & 0xFFFF))


def relocate(elf, index, name, lba, alloc, orig_alloc, sites):
    secs = alloc // 0x800
    e = bt.ELF_TABLE + index * 32
    namep, _, s, _, en, _, cnt, _ = struct.unpack_from("<8I", elf, e)
    nm = bytes(elf[v2o(namep):elf.index(b"\0", v2o(namep))])
    if nm != name or cnt != orig_alloc // 0x800:
        raise SystemExit("파일 테이블 항목 확인 실패: %r %d" % (nm, cnt))
    struct.pack_into("<8I", elf, e, namep, 0, lba, 0, lba + secs - 1, 0, secs, 0)
    patch_size_sites(elf, sites, orig_alloc, alloc)


def load_elf_tr():
    out = []
    for path in sorted(glob.glob(os.path.join(KO_DIR, "elf", "*.tsv"))):
        for key, ko, w in load_tsv(path):
            out.append((int(key, 16), ko, w))
    return out


def build_elf(hangul, msg_alloc, rtdn_alloc, report):
    elf = bytearray(open(bt.SRC_ELF, "rb").read())
    done = {}

    def put(off, ko, where, jp=None, kind="label"):
        n, avail = bt.elf_slot(elf, off)
        if jp is not None and elf[off:off + n] != jp.encode("cp932"):
            raise SystemExit("%s ELF 0x%X 원문 불일치" % (where, off))
        orig = bytes(elf[off:off + n])
        b = bt.ko_elf_bytes(ko, hangul)
        if len(b) + 1 > avail:
            raise SystemExit("%s ELF 0x%X 슬롯 초과 %d > %d: %r" % (where, off, len(b) + 1, avail, ko))
        jw = bt.line_width(orig.decode("cp932", "replace").replace("\x1b", ""))
        lim = bt.LIMITS[kind][0] if bt.LIMITS[kind][0] is not None else jw
        lim = max(lim, bt.ELF_WIDTH_OVERRIDE.get(off, 0))
        if bt.line_width(ko) > lim:
            raise SystemExit("%s ELF 0x%X 폭 초과 %d > %d: %r" % (where, off, bt.line_width(ko), lim, ko))
        # 서식 지정자(%d, %s ...)는 원문과 같아야 한다
        fj = re.findall(rb"%[-0-9.]*[a-zA-Z]", orig)
        fk = re.findall(rb"%[-0-9.]*[a-zA-Z]", b)
        if fj != fk:
            raise SystemExit("%s ELF 0x%X 서식 지정자 불일치 %r / %r" % (where, off, fj, fk))
        elf[off:off + avail] = b + b"\0" * (avail - len(b))
        done[off] = ko

    items = bt.read_items()
    glossary = bt.read_glossary()
    for off, ko, where in load_elf_tr():
        errs = check_chars(ko)
        if errs:
            raise SystemExit("%s %s" % (where, errs))
        put(off, ko, where)
    for it in items:
        if it["src"] != "E":
            continue
        for jp, ko, loose, where in it["pairs"]:
            if it["key"] in done:
                continue
            bt.check_ko_text(ko, hangul, where)
            put(it["key"], ko, where, jp, it["kind"])
    for jp, ko, scope, where in glossary:
        if scope not in ("ELF", "ALL"):
            continue
        offs = [o for o in bt.elf_strings_equal(bytes(elf), jp.encode("cp932")) if o >= DATA_START and o not in done]
        for o in offs:
            put(o, ko, where, jp)
    # 재배치
    msg_lba = FREE_START
    relocate(elf, MSG_TABLE_INDEX, b"\\M_MSG.S9;1", msg_lba, msg_alloc, ORIG_ALLOC["M"], MSG_SIZE_SITES)
    rtdn_lba = None
    if rtdn_alloc != ORIG_ALLOC["R"]:
        rtdn_lba = msg_lba + msg_alloc // 0x800
        relocate(elf, RTDN_TABLE_INDEX, b"\\M_RTDN.S9;1", rtdn_lba, rtdn_alloc, ORIG_ALLOC["R"], RTDN_SIZE_SITES)
    end = (rtdn_lba + rtdn_alloc // 0x800) if rtdn_lba else msg_lba + msg_alloc // 0x800
    if end > FREE_END:
        raise SystemExit("빈 영역 초과 (끝 LBA %d)" % end)
    report.append("ELF: 문자열 %d곳 교체 / M_MSG -> LBA %d (0x%X) / M_RTDN -> %s (0x%X)" % (
        len(done), msg_lba, msg_alloc, rtdn_lba if rtdn_lba else "원래 자리", rtdn_alloc))
    return bytes(elf)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    force = "--force" in sys.argv
    pad_msg = None
    if "--pad-msg" in sys.argv:
        pad_msg = int(sys.argv[sys.argv.index("--pad-msg") + 1], 0)
    hangul = load_hangul(bt.HANGUL_TBL)
    units = load_all_units()
    tr, where = load_translations()
    report = []
    errs_all, warns_all = [], []
    good = {}
    for uid, ko in tr.items():
        u = units.get(uid)
        if u is None:
            errs_all.append("%s %s 없는 단위ID" % (where[uid], uid))
            continue
        errs, warns = check_unit(u, ko)
        for e in errs:
            errs_all.append("%s %s [%s] %s" % (where[uid], uid, u.kind, e))
        for w in warns:
            warns_all.append("%s %s [%s] %s" % (where[uid], uid, u.kind, w))
        if not errs:
            good[uid] = ko
    # 남은 일본어 단위
    left = Counter()
    left_chars = Counter()
    for uid, u in units.items():
        if uid not in good:
            left[u.kind] += 1
            left_chars[u.kind] += len(u.jp)
    report.append("번역 단위 %d / 전체 %d  (오류 %d, 경고 %d)" % (len(good), len(units), len(errs_all), len(warns_all)))
    report.append("미번역: " + ", ".join("%s %d개(%d자)" % (k, left[k], left_chars[k]) for k in sorted(left)))
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(report) + "\n\n[오류]\n" + "\n".join(errs_all) + "\n\n[경고]\n" + "\n".join(warns_all) + "\n")
    for r in report:
        print(r)
    if errs_all:
        print("오류 %d건 (처음 30건):" % len(errs_all))
        for e in errs_all[:30]:
            print("  ", e)
        if not force:
            print("빌드 중단. 전체 목록:", REPORT)
            return 1
    msg = build_file("M", good, units, hangul, force)
    rtdn = build_file("R", good, units, hangul, force)
    msg_alloc = (len(msg) + 0x7FF) // 0x800 * 0x800
    if pad_msg:
        msg_alloc = max(msg_alloc, pad_msg)
    rtdn_alloc = max(ORIG_ALLOC["R"], (len(rtdn) + 0x7FF) // 0x800 * 0x800)
    elf = build_elf(hangul, msg_alloc, rtdn_alloc, report)
    os.makedirs(OUT_DIR, exist_ok=True)
    open(os.path.join(OUT_DIR, "M_MSG.S9"), "wb").write(msg + b"\0" * (msg_alloc - len(msg)))
    rtdn_path = os.path.join(OUT_DIR, "M_RTDN.S9")
    if rtdn != open(SRC["R"], "rb").read()[:len(rtdn)] or rtdn_alloc != ORIG_ALLOC["R"]:
        open(rtdn_path, "wb").write(rtdn + b"\0" * (rtdn_alloc - len(rtdn)))
    elif os.path.exists(rtdn_path):
        os.remove(rtdn_path)
    open(os.path.join(OUT_DIR, "SLPM_656.73"), "wb").write(elf)
    print(report[-1])
    print("M_MSG 0x%X 바이트 (할당 0x%X), M_RTDN 0x%X (할당 0x%X)" % (len(msg), msg_alloc, len(rtdn), rtdn_alloc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
