# -*- coding: utf-8 -*-
"""번역 템플릿 생성·병합.

  python make_template.py tpl  출력.txt 종류 번호|시작-끝 ...   M_MSG 항목의 JP 를 채운 템플릿
  python make_template.py merge 템플릿.txt 번역.txt 출력.txt     번역.txt 의 KO 를 템플릿에 넣는다

번역.txt 형식: '@번호' 줄 다음 줄에 KO (⏎ = 줄바꿈). '@번호!' 는 KO! (태그 불일치 허용)
템플릿의 JP 는 항목 전체(끝의 {05}{05}{05} 제외)이며, 빈 항목·{05}만 있는 항목은 건너뛴다.
"""
import os
import re
import sys

from msg_dump import read_entries
from s9text import decode

HERE = os.path.dirname(os.path.abspath(__file__))


def plain(t):
    return re.sub(r"\{ESC:[HK]\}", "", t)


def tpl(out, kind, specs):
    ents = read_entries(open(os.path.join(HERE, "..", "san9pk", "M_MSG.S9"), "rb").read())
    idx = []
    for s in specs:
        if "-" in s:
            a, b = s.split("-")
            idx += list(range(int(a), int(b) + 1))
        else:
            idx.append(int(s))
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        for i in idx:
            t = plain(decode(ents[i][1]))
            if not t.endswith("{05}{05}{05}"):
                continue
            body = t[:-len("{05}{05}{05}")]
            if not body or "{05}" in body:
                continue
            f.write("[M %d %s]\nJP %s\nKO \n\n" % (i, kind, body.replace("\n", "⏎")))


def merge(tpl_path, ko_path, out):
    ko = {}
    lines = open(ko_path, encoding="utf-8").read().split("\n")
    k = 0
    while k < len(lines):
        m = re.match(r"^@(\d+)(!?)\s*$", lines[k])
        if m:
            ko[int(m.group(1))] = (lines[k + 1], m.group(2) == "!")
            k += 2
        else:
            k += 1
    blocks = open(tpl_path, encoding="utf-8").read().split("\n\n")
    res = []
    used = set()
    for b in blocks:
        if not b.strip():
            continue
        m = re.match(r"^\[M (\d+) (\w+)\]\nJP (.*)\nKO.*$", b.strip(), re.S)
        n = int(m.group(1))
        if n not in ko:
            continue
        text, loose = ko[n]
        used.add(n)
        res.append("[M %d %s]\nJP %s\n%s %s\n" % (n, m.group(2), m.group(3), "KO!" if loose else "KO", text))
    missing = set(ko) - used
    if missing:
        sys.exit("템플릿에 없는 번호: %s" % sorted(missing))
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(res))
    print("%d개 병합 -> %s" % (len(res), out))


if __name__ == "__main__":
    if sys.argv[1] == "tpl":
        tpl(sys.argv[2], sys.argv[3], sys.argv[4:])
    else:
        merge(sys.argv[2], sys.argv[3], sys.argv[4])
