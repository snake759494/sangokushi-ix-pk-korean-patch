# -*- coding: utf-8 -*-
"""번역 파일을 적용해 work/patched/M_MSG.S9 와 work/patched/SLPM_656.73 을 만든다.

입력 (work/trans/ko/)
  glossary.tsv   용어집. JP<TAB>KO<TAB>범위(ELF|MSG|ALL)[<TAB>비고]
                 ELF 문자열 / M_MSG 항목 중 원문과 '완전히 같은' 것을 모두 바꾼다.
  *.txt          항목별 번역 (형식은 아래)

항목별 번역 형식
  [M 번호 종류]        M_MSG 항목.  종류: bar|desc|help|dlg|title|label|name (생략 = label)
  [E 0x오프셋 종류]    실행파일 문자열 (오프셋 = ELF 파일 오프셋)
  JP 원문조각          ⏎ = 줄바꿈. ESC(가나모드) 태그는 쓰지 않는다.
  KO 번역조각          한 항목에 JP/KO 쌍을 여러 개 둘 수 있다 (같은 조각은 항목 안에서 모두 교체)
  KO! 번역조각         제어태그({V:}/{C:}/{U:}) 구성이 원문과 달라도 허용
  ⎵                    공백 (줄 끝 공백을 명시할 때)
  # 주석

검증 (위반 시 빌드 중단)
  - 한글은 KS X 1001 2350자만, 가나 금지, 한글 슬롯(889F~94FC)의 한자 금지
  - 줄 폭(반각=1, 전각·한글=2, {V:}변수=8) <= 종류별 한계, 줄 수 <= 원문 (dlg 는 같아야 함)
  - ELF: 바이트 길이 <= 원문 슬롯(8바이트 정렬 패딩 포함)
"""
import os
import re
import struct
import sys

from msg_dump import read_entries
from s9text import TAG, decode, encode, load_hangul

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.normpath(os.path.join(HERE, ".."))
TRANS = os.path.join(WORK, "trans", "ko")
SRC_MSG = os.path.join(WORK, "san9pk", "M_MSG.S9")
SRC_ELF = os.path.join(WORK, "iso", "SLPM_656.73")
OUT_DIR = os.path.join(WORK, "patched")
HANGUL_TBL = os.path.join(WORK, "font_ko", "hangul.tbl")

# 화면 종류별 한 줄 최대 폭(반각 단위)과 최대 줄 수 (None = 원문 기준)
# desc/help 는 원문처럼 줄 끝 문장부호 하나만 한계를 넘어 걸칠 수 있다 (HANG_KINDS)
LIMITS = {
    "bar":   (52, 1),     # 화면 하단 도움말 줄
    "desc":  (30, 13),    # 시나리오 개요 (15자 + 끝 문장부호, 13줄)
    "help":  (32, 13),    # 도움말·용어사전 본문 (16자 + 끝 문장부호, 13줄)
    "dlg":   (28, None),  # 대사창 (14자, 3줄마다 페이지)
    "title": (None, 1),   # 목록 항목: 원문 폭 이하
    "stitle": (26, 1),    # 시나리오 제목: 시나리오 목록 칸(연도 뒤 13자) 이하
    "label": (None, None),
    "name":  (None, 1),
    "box":   (None, None),
}
VAR_WIDTH = 8
HANG_KINDS = ("desc", "help")
HANG_CHARS = ".,!?」』)"

# 용어집(완전일치)을 적용하지 않는 M_MSG 구간: 고유명사 블록은 항목별로만 번역한다
#   지명(주·지역) / 도시 / 아이템 / 인명(성·이름·자·읽기) + 일반무장 / 관직 / 국호
PROTECTED = [(136, 565), (723, 822), (1398, 1749), (1811, 5150), (5355, 5508), (5606, 5645)]


def protected(i):
    return any(a <= i <= b for a, b in PROTECTED)

# ELF: M_MSG 재배치 관련
ELF_TABLE = 0x32D130
MSG_TABLE_INDEX = 8
MSG_SIZE_SITES = [(0x1535CC, 0x1535E8), (0x21104C, 0x211054), (0x20FDD4, 0x20FDE0)]   # (lui, ori) 가상주소
ORIG_MSG_ALLOC = 0xD6800
NEW_MSG_LBA = 1121523      # SAN9PK.BIN 끝 바로 뒤의 빈 영역 (1121523~1124999 = 3477섹터)
FREE_END_LBA = 1125000


# 실행파일 문자열 중 같은 목록에 더 긴 항목이 있어 칸 폭이 확인된 곳 (오프셋 -> 최대 폭)
ELF_WIDTH_OVERRIDE = {
    0x3538D0: 4,    # 良 (건강: 良/軽傷/重傷) -> 양호
    0x354B98: 4,    # 顔 (등록무장 메뉴: 名前/顔/生年/内面) -> 얼굴
    0x355798: 4,    # 親 (목록 머리글·정렬 항목: 捕虜武将 등과 함께) -> 부모
    0x356E28: 4,    # 親 (관계 편집: 親/相性/君主) -> 부모
    0x355758: 4,    # ﾙﾋﾞ (이름 입력 칸 머리: 姓/名/字/ﾙﾋﾞ) -> 읽기
}


class BuildError(Exception):
    pass


# ------------------------------------------------------------------ 폭 계산
def line_width(s):
    w = 0
    pos = 0
    for m in list(TAG.finditer(s)) + [None]:
        seg = s[pos:m.start()] if m else s[pos:]
        for ch in seg:
            w += 1 if (ord(ch) < 0x80 or 0xFF61 <= ord(ch) <= 0xFF9F) else 2
        if m is None:
            break
        name = m.group(1)
        if name in ("S", "U", "X"):
            w += 2
        elif name == "V":
            w += VAR_WIDTH
        elif name == "A":
            w += 1
        pos = m.end()
    return w


def body_width(line, hang):
    """줄 폭. hang=True 면 줄 끝 문장부호 하나는 폭에서 뺀다 (원문의 걸침 규칙)."""
    if hang and line and line[-1] in HANG_CHARS:
        return line_width(line[:-1])
    return line_width(line)


def plain(t):
    return re.sub(r"\{ESC:[HK]\}", "", t)


# ------------------------------------------------------------------ 파일 읽기
def read_glossary():
    items = []
    path = os.path.join(TRANS, "glossary.tsv")
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            cols = line.split("\t")
            if len(cols) < 3:
                raise BuildError("glossary.tsv:%d 열 부족" % n)
            items.append((cols[0], cols[1], cols[2].upper(), "glossary.tsv:%d" % n))
    return items


def read_items():
    items = []
    for fn in sorted(os.listdir(TRANS)):
        if not fn.endswith(".txt"):
            continue
        cur = None
        with open(os.path.join(TRANS, fn), encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                line = line.rstrip("\n")
                where = "%s:%d" % (fn, n)
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                m = re.match(r"^\[(M|E)\s+(\S+)(?:\s+(\w+))?\]$", line.strip())
                if m:
                    kind = m.group(3) or "label"
                    if kind not in LIMITS:
                        raise BuildError("%s 알 수 없는 종류 %s" % (where, kind))
                    key = int(m.group(2), 0)
                    cur = {"src": m.group(1), "key": key, "kind": kind, "pairs": [], "where": where}
                    items.append(cur)
                    continue
                m = re.match(r"^(JP|KO!|KO) ?(.*)$", line)
                if not m or cur is None:
                    raise BuildError("%s 형식 오류: %r" % (where, line))
                tag, text = m.group(1), m.group(2).replace("⏎", "\n").replace("⎵", " ")
                if tag == "JP":
                    cur["pairs"].append([text, None, False, where])
                else:
                    if not cur["pairs"] or cur["pairs"][-1][1] is not None:
                        raise BuildError("%s KO 앞에 JP 가 없음" % where)
                    cur["pairs"][-1][1] = text
                    cur["pairs"][-1][2] = tag == "KO!"
        for it in items:
            for p in it["pairs"]:
                if p[1] is None:
                    raise BuildError("%s KO 누락" % p[3])
    return items


# ------------------------------------------------------------------ 검증
def check_ko_text(ko, hangul, where):
    body = TAG.sub("", ko)
    for ch in body:
        o = ord(ch)
        if 0xAC00 <= o <= 0xD7A3 and ch not in hangul:
            raise BuildError("%s KS X 1001 에 없는 한글 '%s': %r" % (where, ch, ko))
        if 0x3040 <= o <= 0x30FF and ch != "・":
            raise BuildError("%s 가나 사용: %r" % (where, ko))
        if 0x4E00 <= o <= 0x9FFF:
            raise BuildError("%s 한자 사용 금지: '%s' in %r" % (where, ch, ko))
        if ch in "、。":
            raise BuildError("%s 일본식 구두점 사용: %r" % (where, ko))
        if ch == "\t":
            raise BuildError("%s 탭 문자" % where)


def tags_of(s):
    return sorted(m.group(0) for m in TAG.finditer(s) if m.group(1) in ("V", "C", "U"))


def check_pair(jp, ko, kind, loose, where, orig_max_w, orig_lines):
    if not loose and tags_of(jp) != tags_of(ko):
        raise BuildError("%s 제어태그 불일치 JP%s KO%s" % (where, tags_of(jp), tags_of(ko)))
    lim_w, lim_lines = LIMITS[kind]
    maxw = lim_w if lim_w is not None else orig_max_w
    for ln in ko.split("\n"):
        w = body_width(ln, kind in HANG_KINDS)
        if w > maxw:
            raise BuildError("%s 폭 초과 %d > %d: %r" % (where, w, maxw, ln))
    jl, kl = jp.count("\n") + 1, ko.count("\n") + 1
    if kind == "dlg" and jl != kl:
        raise BuildError("%s 대사 줄 수 다름 JP %d / KO %d" % (where, jl, kl))
    if kl > jl and (lim_lines is None or kl > lim_lines):
        raise BuildError("%s 줄 수 초과 JP %d / KO %d" % (where, jl, kl))
    if lim_lines is not None and kl > lim_lines:
        raise BuildError("%s 최대 줄 수 %d 초과: %d" % (where, lim_lines, kl))


# ------------------------------------------------------------------ M_MSG 교체
def jp_regex(jp):
    """plain JP 조각 -> 태그 문자열에서 찾는 정규식 (사이사이 ESC H/K 허용)."""
    esc = r"(?:\{ESC:[HK]\})*"
    parts = []
    pos = 0
    for m in list(TAG.finditer(jp)) + [None]:
        seg = jp[pos:m.start()] if m else jp[pos:]
        for ch in seg:
            parts.append(re.escape(ch))
        if m is None:
            break
        parts.append(re.escape(m.group(0)))
        pos = m.end()
    # 끝 경계: 조각 뒤에는 태그·줄바꿈·끝만 올 수 있다 (「ある」가 「あります」 앞부분에 걸리지 않게)
    return re.compile(esc + esc.join(parts) + r"(?=\{|\n|$)")


def mode_before(text, idx):
    mode = "H"
    for m in re.finditer(r"\{ESC:([HKk])\}", text[:idx]):
        mode = m.group(1)
    return mode


def replace_in_entry(tagged, jp, ko):
    rx = jp_regex(jp)
    out = []
    pos = 0
    count = 0
    for m in rx.finditer(tagged):
        before = mode_before(tagged, m.start())
        end_mode = before
        for t in re.finditer(r"\{ESC:([HKk])\}", m.group(0)):
            end_mode = t.group(1)
        out.append(tagged[pos:m.start()])
        out.append(ko)
        ko_end = before
        for t in re.finditer(r"\{ESC:([HKk])\}", ko):
            ko_end = t.group(1)
        if end_mode != ko_end:
            out.append("{ESC:%s}" % end_mode)
        pos = m.end()
        count += 1
    out.append(tagged[pos:])
    return "".join(out), count


def build_msg(glossary, items, hangul, report):
    data = open(SRC_MSG, "rb").read()
    ents = read_entries(data)
    texts = [decode(raw) for _, raw in ents]
    orig = list(texts)
    changed = set()

    # 1) 항목별
    for it in items:
        if it["src"] != "M":
            continue
        i = it["key"]
        t = texts[i]
        o_lines = plain(orig[i]).replace("{05}", "\n").split("\n")
        o_max = max(line_width(x) for x in o_lines)
        for jp, ko, loose, where in it["pairs"]:
            check_ko_text(ko, hangul, where)
            seg_max = max(line_width(x) for x in jp.split("\n"))
            check_pair(jp, ko, it["kind"], loose, where, max(seg_max, 0) if it["kind"] in ("label", "title", "name", "box") else o_max, jp.count("\n") + 1)
            t, n = replace_in_entry(t, jp, ko)
            if n == 0:
                raise BuildError("%s 원문 조각을 #%d 에서 찾지 못함: %r\n  현재: %r" % (where, i, jp, plain(t)[:200]))
        texts[i] = t
        changed.add(i)

    # 2) 용어집: 항목 전체가 용어와 같은 경우
    for jp, ko, scope, where in glossary:
        if scope not in ("MSG", "ALL"):
            continue
        check_ko_text(ko, hangul, where)
        target = jp + "{05}{05}{05}"
        hits = [i for i, t in enumerate(texts) if plain(t) == target and i not in changed and not protected(i)]
        for i in hits:
            check_pair(jp, ko, "label", False, where, line_width(jp), 1)
            texts[i] = ko + "{05}{05}{05}"
            changed.add(i)
        report.append("MSG 용어 %-12s -> %-12s %d곳" % (jp, ko, len(hits)))

    # 3) 남은 가나 검사 (번역한 항목에 일본어가 남았는지)
    leftover = []
    for i in sorted(changed):
        body = TAG.sub("", texts[i])
        if re.search(r"[ぁ-ヶ]", body):
            leftover.append(i)
    if leftover:
        report.append("주의: 번역 항목에 가나 잔존 %s" % leftover[:30])

    # 4) 재조립
    ko_rev = {int.from_bytes(v, "big"): k for k, v in hangul.items()}
    raws = []
    for i, (o, raw) in enumerate(ents):
        if i in changed:
            b = encode(texts[i], hangul)
            if decode(b, ko_rev) != texts[i]:
                raise BuildError("#%d 인코딩 왕복 불일치" % i)
            raws.append(b)
        else:
            raws.append(raw)
    n = len(raws)
    head = struct.pack("<H", n)
    offs = []
    pos = 2 + 4 * n
    for r in raws:
        offs.append(pos)
        pos += len(r)
    body = head + struct.pack("<%dI" % n, *offs) + b"".join(raws)
    alloc = (len(body) + 0x7FF) // 0x800 * 0x800
    body += b"\0" * (alloc - len(body))
    report.append("M_MSG: 항목 %d개 변경, 크기 0x%X -> 0x%X (할당 0x%X)" % (len(changed), len(data), len(body), alloc))
    return body, changed


# ------------------------------------------------------------------ ELF 교체
def v2o(v):
    return v - 0x100000 + 0x80


def elf_slot(elf, off):
    """원문 문자열 길이와 사용 가능한 최대 바이트(NUL 포함)."""
    end = elf.index(b"\0", off)
    n = end - off
    avail = ((n + 1) + 7) // 8 * 8          # 8바이트 정렬 패딩까지
    z = end
    while z < len(elf) and elf[z] == 0 and z - off < avail:
        z += 1
    avail = min(avail, z - off)
    return n, avail


def elf_strings_equal(elf, jp_bytes):
    """jp 와 완전히 같은 NUL 종료 문자열의 오프셋 목록 (앞 바이트가 NUL 인 것만)."""
    res = []
    pat = jp_bytes + b"\0"
    i = elf.find(pat)
    while i >= 0:
        if i > 0 and elf[i - 1] == 0 and i % 4 == 0:
            res.append(i)
        i = elf.find(pat, i + 1)
    return res


def ko_elf_bytes(ko, hangul):
    out = bytearray()
    ko = ko.replace("{ESC}", "\x1b")        # 실행파일 문자열의 색·반전 제어 코드 (ESC[25b 등)
    for ch in ko:
        if ch in hangul:
            out += hangul[ch]
        elif ord(ch) < 0x80:
            out += ch.encode("ascii")
        else:
            b = ch.encode("cp932")
            out += b
    return bytes(out)


def build_elf(glossary, items, hangul, msg_size, report):
    elf = bytearray(open(SRC_ELF, "rb").read())
    done = {}
    DATA_START = 0x300000     # 문자열 데이터 영역 (코드는 ~0x2F0000 까지)

    def put(off, jp, ko, where, kind="label"):
        n, avail = elf_slot(elf, off)
        if elf[off:off + n] != jp.encode("cp932"):
            raise BuildError("%s ELF 0x%X 원문 불일치: %r" % (where, off, bytes(elf[off:off + n]).decode("cp932", "replace")))
        b = ko_elf_bytes(ko, hangul)
        if len(b) + 1 > avail:
            raise BuildError("%s ELF 0x%X 슬롯 초과 %d > %d: %r" % (where, off, len(b) + 1, avail, ko))
        jw = line_width(jp.replace("\x1b", ""))
        lim = LIMITS[kind][0] if LIMITS[kind][0] is not None else jw
        if line_width(ko) > lim:
            raise BuildError("%s ELF 0x%X 폭 초과 %d > %d: %r" % (where, off, line_width(ko), lim, ko))
        elf[off:off + avail] = b + b"\0" * (avail - len(b))
        done[off] = ko

    for it in items:
        if it["src"] != "E":
            continue
        for jp, ko, loose, where in it["pairs"]:
            check_ko_text(ko, hangul, where)
            put(it["key"], jp, ko, where, it["kind"])

    for jp, ko, scope, where in glossary:
        if scope not in ("ELF", "ALL"):
            continue
        check_ko_text(ko, hangul, where)
        offs = [o for o in elf_strings_equal(bytes(elf), jp.encode("cp932")) if o >= DATA_START and o not in done]
        for o in offs:
            put(o, jp, ko, where)
        report.append("ELF 용어 %-12s -> %-12s %d곳" % (jp, ko, len(offs)))

    # M_MSG 재배치: 파일 테이블 + 읽기 크기 상수
    alloc = msg_size
    secs = alloc // 0x800
    if NEW_MSG_LBA + secs > FREE_END_LBA:
        raise BuildError("M_MSG 가 빈 영역을 넘음 (%d 섹터)" % secs)
    e = ELF_TABLE + MSG_TABLE_INDEX * 32
    namep, _, s, _, en, _, cnt, _ = struct.unpack_from("<8I", elf, e)
    name = bytes(elf[v2o(namep):elf.index(b"\0", v2o(namep))])
    if name != b"\\M_MSG.S9;1" or cnt != ORIG_MSG_ALLOC // 0x800:
        raise BuildError("파일 테이블 항목 확인 실패: %r %d" % (name, cnt))
    struct.pack_into("<8I", elf, e, namep, 0, NEW_MSG_LBA, 0, NEW_MSG_LBA + secs - 1, 0, secs, 0)
    for lui_v, ori_v in MSG_SIZE_SITES:
        lo, oo = v2o(lui_v), v2o(ori_v)
        lui = struct.unpack_from("<I", elf, lo)[0]
        ori = struct.unpack_from("<I", elf, oo)[0]
        if (lui >> 26) != 0x0F or (lui & 0xFFFF) != (ORIG_MSG_ALLOC >> 16) or (ori >> 26) != 0x0D or (ori & 0xFFFF) != (ORIG_MSG_ALLOC & 0xFFFF):
            raise BuildError("크기 상수 위치 확인 실패 0x%X" % lui_v)
        struct.pack_into("<I", elf, lo, (lui & 0xFFFF0000) | (alloc >> 16))
        struct.pack_into("<I", elf, oo, (ori & 0xFFFF0000) | (alloc & 0xFFFF))
    report.append("ELF: 문자열 %d곳 교체, M_MSG -> LBA %d (%d섹터, 0x%X)" % (len(done), NEW_MSG_LBA, secs, alloc))
    return bytes(elf)


def main():
    hangul = load_hangul(HANGUL_TBL)
    report = []
    try:
        glossary = read_glossary()
        items = read_items()
        msg, changed = build_msg(glossary, items, hangul, report)
        elf = build_elf(glossary, items, hangul, len(msg), report)
    except BuildError as e:
        print("오류:", e)
        return 1
    os.makedirs(OUT_DIR, exist_ok=True)
    open(os.path.join(OUT_DIR, "M_MSG.S9"), "wb").write(msg)
    open(os.path.join(OUT_DIR, "SLPM_656.73"), "wb").write(elf)
    for r in report:
        print(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
