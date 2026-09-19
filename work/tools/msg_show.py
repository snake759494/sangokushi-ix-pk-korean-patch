# -*- coding: utf-8 -*-
"""M_MSG.S9 항목을 번역 작업용 형태로 출력한다 (ESC H/K 태그 제거, 줄바꿈 = ⏎).

사용법: python msg_show.py 번호|시작-끝 [...]
"""
import os
import re
import sys

from msg_dump import read_entries
from s9text import decode

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ents = read_entries(open(os.path.join(HERE, "..", "san9pk", "M_MSG.S9"), "rb").read())
    for arg in sys.argv[1:]:
        if "-" in arg:
            a, b = arg.split("-")
            rng = range(int(a), int(b) + 1)
        else:
            rng = [int(arg)]
        for i in rng:
            t = re.sub(r"\{ESC:[HK]\}", "", decode(ents[i][1]))
            print("#%d\t%s" % (i, t.replace("\n", "⏎")))


if __name__ == "__main__":
    main()
