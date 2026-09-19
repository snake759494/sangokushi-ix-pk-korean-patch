# -*- coding: utf-8 -*-
"""work/iso, work/san9pk 의 모든 파일에서 Shift-JIS 문자열을 찾는다.

사용법: python sjis_find.py 문자열 [문자열 ...]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOTS = [os.path.join(HERE, "..", "iso"), os.path.join(HERE, "..", "san9pk")]


def all_files():
    for root in ROOTS:
        for dp, _, fs in os.walk(root):
            for f in fs:
                yield os.path.normpath(os.path.join(dp, f))


def main():
    pats = []
    for s in sys.argv[1:]:
        try:
            pats.append((s, s.encode("cp932")))
        except UnicodeEncodeError:
            print("SJIS 로 표현 불가(외자 포함):", s)
    for path in all_files():
        data = open(path, "rb").read()
        for s, p in pats:
            i = data.find(p)
            hits = []
            while i >= 0 and len(hits) < 8:
                hits.append(i)
                i = data.find(p, i + 1)
            if hits:
                print("%-24s %-40s %s" % (s, os.path.relpath(path, os.path.join(HERE, "..")),
                                          " ".join("0x%X" % h for h in hits)))


if __name__ == "__main__":
    main()
