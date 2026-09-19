# -*- coding: utf-8 -*-
"""G_*.S9 그래픽 파일: LZSS 블록 목록 찾기·풀기 (타이틀 작업에서 밝힌 형식, title/gamedec.py 사용)

python s9gfx.py scan [파일...]     -> 블록 목록 출력, work/gfx/dec/<파일>_<번호>.bin 로 풀어 둠
블록 = [종류][풀린 크기][코드 위치][리터럴 위치] + 플래그/코드/리터럴, 16바이트 정렬로 이어짐
"""
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "title"))
from gamedec import game_decode  # noqa: E402

WORK = os.path.normpath(os.path.join(HERE, ".."))
SRC = os.path.join(WORK, "san9pk")
DEC = os.path.join(WORK, "gfx", "dec")


def scan(data):
    """-> [(offset, type, usize, end)]  end = 블록이 쓰는 마지막 바이트 다음"""
    blocks = []
    o = 0
    n = len(data)
    while o + 16 <= n:
        t, u, co, lo = struct.unpack_from("<4I", data, o)
        if t == 0 and u == 0 and co == 0 and lo == 0:
            o += 16
            continue
        if not (t in (0, 1, 2, 3) and 0 < u <= 0x1000000 and 16 <= co <= lo < n - o + 16):
            break
        out, info = game_decode(data, o, maxout=u + 64)
        if info.get("overflow") or info["n"] != u:
            break
        end = o + max(info["lits_end"], info["end_code_at"] + 2)
        blocks.append((o, t, u, end, out))
        o = (end + 15) & ~15
    return blocks, o


def main():
    cmd = sys.argv[1]
    names = sys.argv[2:] or sorted(f for f in os.listdir(SRC) if f.startswith("G_"))
    os.makedirs(DEC, exist_ok=True)
    meta = {}
    for name in names:
        data = open(os.path.join(SRC, name), "rb").read()
        blocks, stop = scan(data)
        print("%-12s %9d bytes  blocks %3d  scanned to 0x%X%s" % (name, len(data), len(blocks), stop,
              "" if stop >= len(data) - 16 else "  (나머지 비압축/다른 형식?)"))
        meta[name] = []
        for i, (o, t, u, end, out) in enumerate(blocks):
            open(os.path.join(DEC, "%s_%03d.bin" % (name[:-3], i)), "wb").write(out)
            meta[name].append({"i": i, "off": o, "type": t, "usize": u, "end": end})
    old = {}
    mp = os.path.join(WORK, "gfx", "blocks.json")
    if os.path.exists(mp):
        old = json.load(open(mp, encoding="utf-8"))
    old.update(meta)
    json.dump(old, open(mp, "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
