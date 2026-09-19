# -*- coding: utf-8 -*-
"""사람이 읽는 대역표(일본어 원문·한국어)를 만든다 (공개 저장소의 translation/ 용).

python export_tables.py <출력 폴더>
  script.tsv          M_MSG·M_RTDN 번역 단위: 단위ID, 종류, 폭 한계, 줄 수 한계, 원문, 번역 (줄바꿈 = ⏎)
  elf_strings.tsv     실행파일 문자열: 파일 오프셋, 원문, 번역 (빌드된 work/patched/SLPM_656.73 과 원본을 비교)
  movie_subtitles.tsv 동영상 자막: 영상, 카드, 시작~끝(초), 원문, 번역
원문 권리는 원 권리자에게 있다 (RIGHTS.md).
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_all  # noqa: E402
import elf_strings  # noqa: E402
from s9text import load_hangul  # noqa: E402
from units import WORK  # noqa: E402


def w(path, header, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        cw = csv.writer(f, delimiter="\t", lineterminator="\n", quoting=csv.QUOTE_NONE, escapechar="\\")
        cw.writerow(header)
        for r in rows:
            cw.writerow([str(x).replace("\n", "⏎").replace("\t", " ") for x in r])
    print(os.path.basename(path), len(rows))


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    units = build_all.load_all_units()
    tr, _ = build_all.load_translations()
    rows = []
    for uid in sorted(units, key=lambda u: (u[0], int(u[1:].split(".")[0]), int(u.split(".")[1]))):
        u = units[uid]
        rows.append((uid, u.kind, u.width, u.lines if u.lines else "", u.jp, tr.get(uid, "")))
    w(os.path.join(out, "script.tsv"), ["id", "kind", "width", "lines", "ja", "ko"], rows)

    orig = open(os.path.join(WORK, "iso", "SLPM_656.73"), "rb").read()
    pat = open(os.path.join(WORK, "patched", "SLPM_656.73"), "rb").read()
    hangul = load_hangul(os.path.join(WORK, "font_ko", "hangul.tbl"))
    rev = {v: k for k, v in hangul.items()}

    def dec(b):
        s, i = [], 0
        while i < len(b):
            c = b[i]
            if (0x81 <= c <= 0x9F or 0xE0 <= c <= 0xFC) and i + 1 < len(b):
                two = bytes(b[i:i + 2])
                s.append(rev.get(two) or two.decode("cp932", "replace"))
                i += 2
            else:
                s.append("{ESC}" if c == 0x1B else chr(c))
                i += 1
        return "".join(s)

    rows = []
    for off, raw in elf_strings.scan(orig):
        if off < 0x300000:
            continue
        end = pat.index(b"\0", off)
        if pat[off:off + len(raw)] == raw and end == off + len(raw):
            continue
        ja = raw.decode("cp932", "replace").replace("\x1b", "{ESC}")      # 원문은 Shift-JIS 그대로
        rows.append(("0x%06X" % off, ja, dec(pat[off:end])))
    w(os.path.join(out, "elf_strings.tsv"), ["offset", "ja", "ko"], rows)

    subs = os.path.join(WORK, "movie", "subs")
    tdir = os.path.join(WORK, "trans", "ko", "movie")
    rows = []
    for fn in sorted(os.listdir(tdir)):
        if not fn.endswith(".tsv"):
            continue
        name = fn[:-4]
        cards = {c["id"]: c for c in json.load(open(os.path.join(subs, name + ".json"), encoding="utf-8"))["cards"]}
        for line in open(os.path.join(tdir, fn), encoding="utf-8"):
            if line.startswith("#") or not line.strip():
                continue
            cid, ja, ko = line.rstrip("\n").split("\t")[:3]
            c = cards[int(cid)]
            rows.append((name, cid, "%.2f" % (c["start"] / 30), "%.2f" % (c["end"] / 30), ja, ko))
    w(os.path.join(out, "movie_subtitles.tsv"), ["movie", "card", "start_s", "end_s", "ja", "ko"], rows)


if __name__ == "__main__":
    main()
