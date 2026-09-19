# -*- coding: utf-8 -*-
"""M_MSG.S9 항목에서 문구를 찾아 항목 번호와 전체 내용을 보여준다 (가나 모드 태그 무시).

사용법: python msg_find.py [-f 파일] 문구 [문구 ...]
"""
import os
import re
import sys

from msg_dump import read_entries
from s9text import decode

HERE = os.path.dirname(os.path.abspath(__file__))


def plain(t):
    return re.sub(r"\{ESC:[HK]\}", "", t)


def main():
    args = sys.argv[1:]
    path = os.path.join(HERE, "..", "san9pk", "M_MSG.S9")
    if args[:1] == ["-f"]:
        path, args = args[1], args[2:]
    ents = read_entries(open(path, "rb").read())
    texts = [decode(raw) for _, raw in ents]
    for q in args:
        hits = [i for i, t in enumerate(texts) if q in plain(t)]
        print("=== %s : %s" % (q, hits[:20]))
        for i in hits[:3]:
            print("  #%d: %s" % (i, texts[i].replace("\n", "⏎")[:300]))


if __name__ == "__main__":
    main()
