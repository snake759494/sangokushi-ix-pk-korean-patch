# -*- coding: utf-8 -*-
"""KOEI S9 LZSS 블록 압축기 (종류 0~3 모두). title/s9enc.py(종류 1 전용)를 일반화한 것.

블록 = [u32 종류][u32 풀린 크기][u32 코드 위치][u32 리터럴 위치] + 플래그(u64, 최상위 비트부터 1=리터럴)
       + 코드(u16: pos = v & (창-1), len = (v >> 창비트) + 3) + 리터럴
종류 t: 창비트 = 10 + t  (0=1KB 창·최대 길이 66, 1=2KB·34, 2=4KB·18, 3=8KB·10)
게임 해제 함수는 크기 검사가 없고 pos == 0 코드에서만 멈추므로 끝 코드(0x0000)를 반드시 넣는다.
"""
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "title"))
from gamedec import game_decode  # noqa: E402


def a16(v):
    return (v + 15) & ~15


def find_matches(x, pb):
    n_win = 1 << pb
    maxl = (0xFFFF >> pb) + 3
    maxd = n_win - maxl
    n = len(x)
    best_len = np.zeros(n, np.int32)
    best_d = np.zeros(n, np.int32)
    ar = np.arange(n, dtype=np.int32)
    for d in range(1, min(maxd, n - 1) + 1):
        m = n - d
        eq = x[d:] == x[:m]
        arr = np.where(eq, m, ar[:m])
        nf = np.minimum.accumulate(arr[::-1])[::-1]
        run = nf - ar[:m]
        np.minimum(run, maxl, out=run)
        run[n_win - 1::n_win] = 0        # 원본 위치 s % 창 == 창-1 은 pos 0(=끝)이 되므로 못 씀
        bl = best_len[d:]
        upd = run > bl
        bl[upd] = run[upd]
        best_d[d:][upd] = d
    return best_len, best_d, maxl


def parse(best_len, n, maxl, lit_cost=9, match_cost=17):
    bl = best_len.tolist()
    cost = [0] * (n + 1 + maxl)
    choice = [0] * n
    for i in range(n - 1, -1, -1):
        c = lit_cost + cost[i + 1]
        ch = 0
        L = bl[i]
        if L >= 3:
            L = min(L, n - i)
            seg = cost[i + 3:i + L + 1]
            m = min(seg)
            if match_cost + m < c:
                c = match_cost + m
                ch = 3 + len(seg) - 1 - seg[::-1].index(m)
        cost[i] = c
        choice[i] = ch
    toks = []
    i = 0
    while i < n:
        L = choice[i]
        toks.append((i, L))
        i += L if L else 1
    return toks


def build(x, toks, best_d, typ):
    pb = 10 + typ
    mask = (1 << pb) - 1
    flags = bytearray()
    codes = bytearray()
    lits = bytearray()
    word = nb = 0
    for t in list(toks) + [None]:
        word <<= 1
        if t is None:
            codes += b"\0\0"
        elif t[1] == 0:
            word |= 1
            lits.append(x[t[0]])
        else:
            i, L = t
            pos = (i + 1 - int(best_d[i])) & mask
            assert pos != 0
            codes += struct.pack("<H", ((L - 3) << pb) | pos)
        nb += 1
        if nb == 64:
            flags += struct.pack("<Q", word)
            word = nb = 0
    if nb:
        flags += struct.pack("<Q", word << (64 - nb))
    co = a16(16 + len(flags))
    lo = a16(co + len(codes))
    out = bytearray(struct.pack("<4I", typ, len(x), co, lo))
    out += flags
    out += b"\0" * (co - len(out))
    out += codes
    out += b"\0" * (lo - len(out))
    out += lits
    return bytes(out)


def encode(raw, typ):
    x = np.frombuffer(bytes(raw), np.uint8)
    bl, bd, maxl = find_matches(x, 10 + typ)
    toks = parse(bl, len(x), maxl)
    blob = build(x.tobytes(), toks, bd, typ)
    out, info = game_decode(blob + b"\0" * 64, 0, maxout=len(raw) + 64)
    assert out == bytes(raw) and info["n"] == len(raw) and "end_code_at" in info, "검증 실패"
    return blob


def encode_best(raw, types=(0, 1, 2)):
    """여러 종류로 압축해 가장 작은 것 (게임 해제 함수 모형으로 검증됨)."""
    best = None
    for t in types:
        b = encode(raw, t)
        if best is None or len(b) < len(best):
            best = b
    return best
