# -*- coding: utf-8 -*-
"""자막 번역 표 쓰기 도우미: 검출 결과(카드 순서)에 맞춰 trans/ko/movie/<이름>.tsv 를 만든다.

python movtrans.py 입력.txt
  입력 형식:  [이름] 줄 다음에 카드 순서대로 '일본어 <TAB> 한국어' 줄
검사: 카드 수 일치, 한 줄 폭(글꼴 13px 기준 608px 이하), 일본식 문장부호(、。・) 없음
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import subrender as R  # noqa: E402

WORK = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SUBS = os.path.join(WORK, "movie", "subs")
TRANS = os.path.join(WORK, "trans", "ko", "movie")


def main():
    blocks = {}
    cur = None
    for line in open(sys.argv[1], encoding="utf-8"):
        line = line.rstrip("\n")
        if not line.strip() or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            cur = line[1:-1]
            blocks[cur] = []
            continue
        jp, ko = line.split("\t")
        blocks[cur].append((jp.strip(), ko.strip()))
    bad = 0
    for name, rows in blocks.items():
        js = json.load(open(os.path.join(SUBS, name + ".json"), encoding="utf-8"))
        ids = [c["id"] for c in js["cards"]]
        if len(ids) != len(rows):
            print("!! %s: 카드 %d 장, 번역 %d 줄" % (name, len(ids), len(rows)))
            bad += 1
            continue
        for jp, ko in rows:
            w = R.text_width(ko)
            if w > R.W - 2 * R.MARGIN:
                print("!! %s 폭 초과 %.0f: %s" % (name, w, ko))
                bad += 1
            for ch in "、。・":
                if ch in ko:
                    print("!! %s 일본식 부호 %s: %s" % (name, ch, ko))
                    bad += 1
        os.makedirs(TRANS, exist_ok=True)
        with open(os.path.join(TRANS, name + ".tsv"), "w", encoding="utf-8") as f:
            f.write("# id\t일본어\t한국어\n")
            for i, (jp, ko) in zip(ids, rows):
                f.write("%d\t%s\t%s\n" % (i, jp, ko))
        print("%s: %d 장 기록 (최대 폭 %.0fpx)" % (name, len(ids), max(R.text_width(k) for _, k in rows)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
