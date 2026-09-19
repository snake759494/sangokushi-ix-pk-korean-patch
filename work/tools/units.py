# -*- coding: utf-8 -*-
"""번역 단위(unit) 추출·분류·적용.

단위 = 한 항목 안에서 스크립트 코드 사이에 있는 '일본어가 들어 있는 텍스트 덩어리'.
       (텍스트·변수·색·가나모드 토큰의 연속. 대사 변형 하나, 라벨 하나, 도움말 한 쪽 등)
단위 ID = M<항목번호 5자리>.<항목 안 일본어 단위 순번>  (M_RTDN 은 R<3자리>.<순번>)

분류(kind)와 제한
  name   고유명사 블록 (중앙 용어집으로 번역, 폭 = 원문)
  ruby   이름 읽기 ({ESC:k}...)  -> 번역된 이름의 한글 읽기로 자동 생성
  label  UI 라벨                    폭 = 원문 폭
  bar    화면 하단 한 줄 도움말       폭 52, 1줄
  msg    그 밖의 한 줄 문장            폭 = 원문+6 (최대 52), 1줄
  dlg    대사·이벤트·여러 줄 메시지     폭 = max(28, 원문 최대), 줄 수 = 원문과 같게
  help   도움말·용어사전 본문          폭 34 + 줄끝 문장부호, 13줄 이하
  desc   시나리오·챌린지 개요          폭 30 + 줄끝 문장부호, 원문 줄 수 이하(최대 13)
  bio    무장 열전 (M_RTDN)           폭 36, 4줄 이하
"""
import os
import re

from msg_dump import read_entries
from s9lex import lex
from s9text import TAG, decode, encode

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.normpath(os.path.join(HERE, ".."))
SRC = {"M": os.path.join(WORK, "san9pk", "M_MSG.S9"), "R": os.path.join(WORK, "san9pk", "M_RTDN.S9")}

JP_RE = re.compile(r"[ぁ-ヿ一-鿿々〆]")
# 게임 전용 외자(F040~F0AB)와 IBM 확장 한자({S:FAxx}/{S:FBxx})도 일본어 글자로 본다 (F0B0 이후는 버튼 아이콘)
KANJI_TAG_RE = re.compile(r"\{U:F0[4-9A][0-9A-F]\}|\{S:F[AB][0-9A-F]{2}\}")


def has_jp(plain):
    return bool(JP_RE.search(TAG.sub("", plain).replace("・", "")) or KANJI_TAG_RE.search(plain))
VAR_WIDTH = 8
HANG_CHARS = ".,!?」』)"

# ---------------------------------------------------------------- 구간 표 (M_MSG 항목 번호, 양끝 포함)
NAME_RANGES = [
    (136, 565),      # 주·지역·거점 + 읽기
    (723, 822),      # 도시 + 읽기
    (1398, 1749),    # 아이템 + 읽기
    (1785, 1800),    # 관작 + 읽기
    (1811, 5150),    # 무장 (성·이름·자·읽기) + 일반 무장
    (5355, 5508),    # 관직 + 읽기
    (5606, 5645),    # 국호 + 읽기
    (14544, 15701),  # 병사 발탁·육성용 성·이름 후보 + 읽기
]
LABEL_RANGES = [(566, 722), (823, 1397), (1750, 1810), (5151, 5354), (5509, 5605), (5646, 6030), (8410, 8427)]
BAR_RANGES = [(6490, 6760), (9150, 9898), (11330, 11430), (15702, 15713)]
HELP_RANGES = [(9899, 10775), (11176, 11329)]     # 10776~10808 은 이벤트·연표 메시지
DESC_RANGES = [(0, 135)]
EVENT_RANGES = [(8588, 8783), (8900, 9149), (10776, 11175), (11430, 12870), (12871, 14543), (15714, 16011)]
DLG_RANGES = [(6031, 6489), (6761, 8409), (8428, 8587)]     # 명령·전투·시스템 대사 (대사창)
TUTOR_MSG_RANGES = [(11176, 11187), (11255, 11300)]          # 튜토리얼 안내 메시지


def in_ranges(i, ranges):
    return any(a <= i <= b for a, b in ranges)


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
    if hang and line and line[-1] in HANG_CHARS:
        return line_width(line[:-1])
    return line_width(line)


def strip_esc(t):
    return re.sub(r"\{ESC:[HKk]\}", "", t)


class Unit:
    __slots__ = ("uid", "src", "entry", "k", "tok_lo", "tok_hi", "raw", "jp", "mode_in", "mode_out",
                 "in_s", "is_ruby", "kind", "width", "width_plain", "lines_rule", "lines", "hang", "ctx")

    def __repr__(self):
        return "<Unit %s %s %r>" % (self.uid, self.kind, self.jp[:20])


def entry_units(src, idx, raw):
    toks = lex(raw)
    units = []
    mode = "H"
    in_s = False
    k = 0
    i = 0
    n = len(toks)
    while i < n:
        kind, b = toks[i]
        if kind in ("txt", "var", "col", "esc"):
            j = i
            while j < n and toks[j][0] in ("txt", "var", "col", "esc"):
                j += 1
            rb = b"".join(t[1] for t in toks[i:j])
            text, mode_out = decode(rb, mode=mode, want_mode=True)
            plain = strip_esc(text)
            if has_jp(plain):
                u = Unit()
                u.src, u.entry, u.k = src, idx, k
                u.uid = "%s%05d.%d" % (src, idx, k) if src == "M" else "%s%03d.%d" % (src, idx, k)
                u.tok_lo, u.tok_hi = i, j
                u.raw = rb
                u.jp = plain
                u.mode_in, u.mode_out = mode, mode_out
                u.in_s = in_s
                u.is_ruby = text.startswith("{ESC:k}") or text.startswith("色付き{ESC:k}")
                units.append(u)
                k += 1
            mode = mode_out
            i = j
            continue
        if kind == "cmd":
            if b[:2] == b"\x01S":
                in_s = True
            else:
                in_s = False
        elif kind == "cond":
            in_s = False
        i += 1
    return toks, units


def classify(u):
    lines = u.jp.split("\n")
    n = len(lines)
    ow = max(line_width(l) for l in lines)
    i = u.entry
    u.lines = n
    u.hang = False
    if u.src == "R":
        u.kind, u.width, u.lines_rule = "bio", max(36, ow), ("<=", 4)
        return u
    if u.is_ruby:
        u.kind, u.width, u.lines_rule = "ruby", None, ("==", 1)
        return u
    if in_ranges(i, NAME_RANGES):
        w = ow
        if 1398 <= i <= 1749:
            w = max(ow, 12)          # 아이템 이름 칸 (원문 최장 6자)
        elif 1811 <= i <= 5150:
            w = max(ow, 4)           # 성·이름 칸 (복성 2자)
        u.kind, u.width, u.lines_rule = "name", w, ("==", n)
        return u
    if in_ranges(i, TUTOR_MSG_RANGES):
        # 튜토리얼 진행 안내창 (최대 20자, 줄 수 유지)
        u.kind, u.width, u.lines_rule = "dlg", max(28, ow), ("==", n)
        return u
    if in_ranges(i, HELP_RANGES) and n >= 2:
        u.kind, u.width, u.lines_rule, u.hang = "help", max(34, ow if ow <= 36 else 34), ("<=", max(13, n)), True
        return u
    if in_ranges(i, DESC_RANGES) and n >= 2:
        u.kind, u.width, u.lines_rule, u.hang = "desc", 30, ("<=", 13), True     # 개요 상자 13줄 (에뮬레이터 확인)
        return u
    if n >= 2 or u.in_s:
        # 긴 서술형(15~16자 줄, 8줄 이상, 변수 없음)은 개요 상자로 본다
        if n >= 8 and ow <= 32 and "{V:" not in u.jp and not u.in_s:
            u.kind, u.width, u.lines_rule, u.hang = "desc", 30, ("<=", n), True
            return u
        u.kind, u.width, u.lines_rule = "dlg", max(28, ow), ("==", n)
        return u
    # 한 줄
    txt = TAG.sub("", u.jp)
    if in_ranges(i, BAR_RANGES):
        u.kind, u.width, u.lines_rule = "bar", 52, ("==", 1)
    elif in_ranges(i, DESC_RANGES):
        # 시나리오·튜토리얼 제목 (목록 칸 13자) / 챌린지·트라이얼 제목 (10자)
        u.kind, u.width, u.lines_rule = "label", max(26 if i <= 48 else 20, ow), ("==", 1)
    elif in_ranges(i, LABEL_RANGES) or in_ranges(i, DESC_RANGES):
        u.kind, u.width, u.lines_rule = "label", ow, ("==", 1)
    elif re.fullmatch(r"\d+年\d+月～\d+年\d+月", txt):
        u.kind, u.width, u.lines_rule = "label", ow, ("==", 1)       # 기간 표시 (자동 번역)
    elif in_ranges(i, EVENT_RANGES) or in_ranges(i, DLG_RANGES):
        u.kind, u.width, u.lines_rule = "dlg", max(28, ow), ("==", 1)
    elif len(txt) <= 8 and not re.search(r"[ぁ-ん]", txt):
        u.kind, u.width, u.lines_rule = "label", ow, ("==", 1)
    else:
        u.kind, u.width, u.lines_rule = "msg", (ow if ow >= 28 else min(28, ow + 6)), ("==", 1)
    return u


# 에뮬레이터 화면으로 확인한 개별 폭 (단위ID -> 최대 폭)
WIDTH_OVERRIDE = {
    "M08385.0": 36,      # 타이틀 화면 「버튼을 누르면 게임을 시작합니다」 (넓은 안내창)
    "M10944.0": 20,      # 튜토리얼 【クリア条件】【ポイント】 패널 (원문이 10자에서 낱말 중간도 끊음)
    "M11086.0": 20,
}


# 같은 목록 안에 더 긴 항목이 있어 칸 폭이 확인되는 라벨 블록 (항목 범위 -> 최소 폭)
LIST_BLOCKS = [
    ((964, 979), 4),       # 시설 종류 (港 関 陣 砦 櫓 城塞 柵 土砂 土塁 石兵)
    ((9899, 10775), 16),   # 도움말·용어사전 제목 (エキスパート設定 = 16)
    ((5241, 5242), 4),     # 무장 편집 親/子 (옆 칸 血縁番号 = 8)
    ((8410, 8427), 12),    # BGM 제목 (交戦・小勢力 = 12)
]


# 서술형처럼 보여 개요(desc)로 분류됐지만 실제로는 대사창에 나오는 이벤트 대사 (작업자 확인)
DLG_UIDS = {"M13042.0", "M13190.0"}


# 아이템 설명창: 한 줄 10자(폭 20)에서 자동 줄바꿈, 4줄 (실행파일 0x237DC4 창 228x96px, 0x241880 줄바꿈 폭 20)
ITEM_DESC = (8686, 8800)


def plain_width(u):
    """변수가 없는 원문 줄의 최대 폭 (변수를 8칸으로 세어 부풀려진 폭을 빼고 창 폭을 가늠)."""
    ws = [line_width(l) for l in u.jp.split("\n") if "{V:" not in l]
    return max(ws) if ws else 0


def classify_final(u):
    classify(u)
    u.width_plain = None
    if u.kind == "dlg" and u.width is not None:
        # 대사창은 한글 14자(28). 원문의 변수 없는 줄이 더 길면 그 폭까지. 변수가 든 줄은 기존 폭(변수 8칸 가정)
        u.width_plain = min(u.width, max(28, plain_width(u)))
    if ITEM_DESC[0] <= u.entry <= ITEM_DESC[1] and u.kind == "dlg":
        u.width, u.lines_rule, u.width_plain = 20, ("<=", 4), None
    if u.uid in DLG_UIDS:
        ow = max(line_width(l) for l in u.jp.split("\n"))
        u.kind, u.width, u.lines_rule, u.hang = "dlg", max(28, ow), ("==", u.lines), False
    if u.kind == "label":
        for (a, b), w in LIST_BLOCKS:
            if a <= u.entry <= b:
                u.width = max(u.width, w)
    if u.uid in WIDTH_OVERRIDE:
        u.width = WIDTH_OVERRIDE[u.uid]
        u.width_plain = None
    return u


def load_units(src="M"):
    ents = read_entries(open(SRC[src], "rb").read())
    out = []
    for idx, (_, raw) in enumerate(ents):
        _, us = entry_units(src, idx, raw)
        for u in us:
            classify_final(u)
            out.append(u)
    return ents, out


def apply_entry(src, idx, raw, tr, hangul):
    """tr: {uid: 한국어 태그문자열}. 번역된 단위를 바꿔 넣은 새 바이트열."""
    toks, us = entry_units(src, idx, raw)
    if not any(u.uid in tr for u in us):
        return raw
    out = bytearray()
    pos = 0
    for u in us:
        out += b"".join(t[1] for t in toks[pos:u.tok_lo])
        if u.uid in tr:
            ko = tr[u.uid]
            enc = encode(ko, hangul)
            out += enc
            ko_mode = u.mode_in
            for m in re.finditer(r"\{ESC:([HKk])\}", ko):
                ko_mode = m.group(1)
            if ko_mode != u.mode_out:
                out += b"\x1b" + u.mode_out.encode("ascii")
        else:
            out += u.raw
        pos = u.tok_hi
    out += b"".join(t[1] for t in toks[pos:])
    return bytes(out)
