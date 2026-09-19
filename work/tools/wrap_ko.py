# -*- coding: utf-8 -*-
"""번역문을 어절(공백) 단위로 줄바꿈한다.

사용법: python wrap_ko.py 입력.txt 출력.txt 폭 [최대줄수] [--hang]
입력: '@번호' 줄 + 다음 줄에 번역문 (⏎ = 강제 줄바꿈). 출력은 같은 형식에 ⏎ 가 들어간다.
--hang: 줄 끝 문장부호 하나는 폭을 넘어 걸칠 수 있다 (시나리오 개요·도움말의 원문 규칙).
줄 수가 최대를 넘으면 표시한다 (번역문을 줄여야 함).
"""
import sys

from build_text import body_width, line_width


def wrap_para(text, width, hang):
    """⏎ = 강제 줄바꿈. 전각 공백(　)으로 시작하는 문단은 이어지는 줄도 같은 들여쓰기를 둔다."""
    lines = []
    for para in text.split("⏎"):
        indent = "　" if para.startswith("　") else ""
        words = para[len(indent):].split(" ")
        cur = indent
        for w in words:
            cand = w if cur == indent and cur == "" else (cur + w if cur == indent else cur + " " + w)
            if body_width(cand, hang) <= width:
                cur = cand
            else:
                if cur.strip("　"):
                    lines.append(cur)
                cur = indent + w
                if body_width(cur, hang) > width:
                    print("  경고: 한 어절이 폭을 넘음: %r" % w)
        lines.append(cur)
    return lines


def main():
    args = [a for a in sys.argv[1:] if a != "--hang"]
    hang = "--hang" in sys.argv
    src, dst, width = args[0], args[1], int(args[2])
    maxl = int(args[3]) if len(args) > 3 else 99
    lines = open(src, encoding="utf-8").read().split("\n")
    out = []
    k = 0
    while k < len(lines):
        if lines[k].startswith("@"):
            head, text = lines[k], lines[k + 1]
            wrapped = wrap_para(text, width, hang)
            flag = "" if len(wrapped) <= maxl else "  <-- %d줄 (최대 %d)" % (len(wrapped), maxl)
            print("%s %d줄%s" % (head, len(wrapped), flag))
            out += [head, "⏎".join(wrapped)]
            k += 2
        else:
            k += 1
    open(dst, "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
