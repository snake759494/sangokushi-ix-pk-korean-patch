# -*- coding: utf-8 -*-
"""단위 번역 읽기·검증 (build_all.py 와 check_job.py 가 함께 쓴다).

번역 파일 형식 (TSV, UTF-8)
  단위ID<TAB>번역문        ⏎ = 줄바꿈, ⎵ = 공백(줄 끝 공백을 적을 때), # 로 시작하면 주석
"""
import os
import re
from collections import Counter

from s9text import TAG, load_hangul
from units import WORK, body_width, line_width

HANGUL_TBL = os.path.join(WORK, "font_ko", "hangul.tbl")
KO_DIR = os.path.join(WORK, "trans", "ko")

# {V:..} 바로 뒤에 붙으면 안 되는 조사 첫 글자 (받침 유무에 따라 모양이 바뀌는 것)
PARTICLE_AFTER_VAR = re.compile(r"\{V:[0-9A-F]+\}([을를이가은는과와로나야여라랑으였아란])")
COPULA_AFTER_VAR = re.compile(r"\{V:[0-9A-F]+\}(다(?![가-힣])|예요|예)")
ICON_RE = re.compile(r"\{U:F0[B-F][0-9A-F]\}")          # 버튼 아이콘 (유지)
GLYPH_RE = re.compile(r"\{U:F0[4-9A][0-9A-F]\}|\{S:[0-9A-F]{4}\}")   # 한자·가나 글리프 (번역문 금지)


def load_tsv(path):
    """-> [(uid, 번역, '파일:줄')]"""
    out = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.rstrip("\n").rstrip("\r")
            if not line.strip() or line.startswith("#"):
                continue
            if "\t" not in line:
                raise ValueError("%s:%d 탭 없음: %r" % (os.path.basename(path), n, line[:60]))
            uid, ko = line.split("\t", 1)
            ko = ko.replace("⏎", "\n").replace("⎵", " ")
            out.append((uid.strip(), ko, "%s:%d" % (os.path.basename(path), n)))
    return out


def tag_counter(s, names):
    c = Counter()
    for m in TAG.finditer(s):
        if m.group(1) in names:
            if m.group(1) == "U" and not ICON_RE.fullmatch(m.group(0)):
                continue
            c[m.group(0)] += 1
    return c


_hangul = None


def hangul_table():
    global _hangul
    if _hangul is None:
        _hangul = load_hangul(HANGUL_TBL)
    return _hangul


def check_chars(ko):
    errs = []
    hangul = hangul_table()
    body = TAG.sub("", ko)
    for ch in body:
        o = ord(ch)
        if ch == "\n" or ch in hangul:
            continue
        if 0xAC00 <= o <= 0xD7A3:
            errs.append("KS X 1001 에 없는 한글 '%s'" % ch)
        elif ch in "、。":
            errs.append("일본식 구두점 '%s' (쉼표·마침표를 쓸 것)" % ch)
        elif 0x3040 <= o <= 0x30FF and ch != "・":
            errs.append("가나 '%s'" % ch)
        elif 0x3400 <= o <= 0x9FFF or ch in "々〆":
            errs.append("한자 '%s'" % ch)
        elif 0xFF61 <= o <= 0xFF9F:
            errs.append("반각 가나/기호 '%s'" % ch)
        elif ch in "\t\r{}":
            errs.append("금지 문자 %r" % ch)
        elif o < 0x20:
            errs.append("제어 문자 %r" % ch)
        elif o >= 0x80:
            try:
                b = ch.encode("cp932")
            except UnicodeEncodeError:
                errs.append("게임 글꼴에 없는 문자 '%s' (U+%04X)" % (ch, o))
                continue
            if len(b) != 2:
                errs.append("인코딩 불가 문자 '%s'" % ch)
    return errs


def check_unit(u, ko):
    """-> (오류 목록, 경고 목록)"""
    errs, warns = [], []
    errs += check_chars(ko)
    if GLYPH_RE.search(ko):
        errs.append("한자·가나 글리프 태그가 남음 (%s)" % GLYPH_RE.search(ko).group(0))
    esc = re.findall(r"\{ESC:([HKk])\}", ko)
    if u.kind == "ruby":
        pass
    elif esc:
        errs.append("{ESC:..} 태그는 쓰지 않는다")
    for m in TAG.finditer(ko):
        if m.group(1) in ("05", "B", "E"):
            errs.append("스크립트 태그 %s 를 넣으면 안 됨" % m.group(0))
    # 태그 구성
    jv, kv = tag_counter(u.jp, ("V",)), tag_counter(ko, ("V",))
    if kv - jv:
        errs.append("원문에 없는 변수 %s" % sorted((kv - jv).elements()))
    elif jv - kv:
        warns.append("변수 생략 %s" % sorted((jv - kv).elements()))
    for names, what in ((("C",), "색 태그"), (("U",), "버튼 아이콘"), (("X", "A", "h"), "특수 태그")):
        a, b = tag_counter(u.jp, names), tag_counter(ko, names)
        if a != b:
            errs.append("%s 불일치 원문%s 번역%s" % (what, sorted(a.elements()), sorted(b.elements())))
    # 조사 (색 태그로 감싼 변수 {C:25b}{V:..}{C:32b} 뒤도 본다)
    plain_ko = re.sub(r"\{C:[^}]*\}", "", ko)
    m = PARTICLE_AFTER_VAR.search(plain_ko)
    if m:
        errs.append("변수 바로 뒤 조사 '%s' (받침을 알 수 없음)" % m.group(1))
    # 서술격 「다」「예요」도 받침에 따라 바뀐다 (「입니다」「인」「다운」은 괜찮음)
    m = COPULA_AFTER_VAR.search(plain_ko)
    if m:
        errs.append("변수 바로 뒤 서술격 '%s' (받침을 알 수 없음: 「입니다」 등으로)" % m.group(1))
    # 줄 수
    lines = ko.split("\n")
    n = len(lines)
    op, lim = u.lines_rule
    if op == "==" and n != lim:
        errs.append("줄 수 %d (원문과 같은 %d줄이어야 함)" % (n, lim))
    elif op == "<=" and n > lim:
        errs.append("줄 수 %d > 최대 %d" % (n, lim))
    # 폭
    if u.width is not None:
        for ln in lines:
            w = body_width(ln, u.hang)
            lim = u.width
            wp = getattr(u, "width_plain", None)
            if wp is not None and "{V:" not in ln:
                lim = wp
            if w > lim:
                errs.append("폭 초과 %d > %d: %r" % (w, lim, ln))
    if u.kind in ("dlg", "help", "desc", "bio", "bar", "msg"):
        for ln in lines:
            if ln != ln.rstrip(" "):
                warns.append("줄 끝 공백: %r" % ln)
    if ko.strip() == "" and u.jp.strip() != "" and u.kind not in ("name",):
        errs.append("빈 번역")
    return errs, warns


def line_widths(s):
    return [line_width(x) for x in s.split("\n")]
