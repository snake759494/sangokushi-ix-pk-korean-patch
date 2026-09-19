# -*- coding: utf-8 -*-
"""KOEI S9 LZ encoder (type 1: 11-bit position / 5-bit length), optimal parse.

Format (game decoder SLPM_656.73 @0x23C7D0):
  header u32 type(1), u32 usize, u32 codes_off, u32 lits_off   (offsets from block start, 4-aligned)
  flags: u64 LE words from +16, consumed MSB first; 1 = literal, 0 = match
  codes: u16 LE; pos = v & 0x7FF, len = (v >> 11) + 3; pos == 0 terminates decoding (END)
  match source (output index) = (cnt & ~0x7FF) + pos - 1, minus 0x800 if (cnt & 0x7FF) < pos
    -> pos = (cnt + 1 - dist) & 0x7FF  (a match may not start at a source index s with s % 2048 == 2047)
  The decoder has no size check, so the stream MUST end with a 0 flag bit + code 0x0000.
"""
import struct, time
import numpy as np

PB = 11
N = 1 << PB
MASK = N - 1
MINL, MAXL = 3, (0xFFFF >> PB) + 3      # 3..34
MAXD = N - MAXL                          # 2014, same limit as the original encoder


def find_matches(x, maxd=MAXD, maxl=MAXL):
    x = np.asarray(x, np.uint8)
    n = len(x)
    best_len = np.zeros(n, np.int32)
    best_d = np.zeros(n, np.int32)
    ar = np.arange(n, dtype=np.int32)
    for d in range(1, min(maxd, n - 1) + 1):
        m = n - d
        eq = x[d:] == x[:m]
        arr = np.where(eq, m, ar[:m])
        nf = np.minimum.accumulate(arr[::-1])[::-1]
        R = nf - ar[:m]
        np.minimum(R, maxl, out=R)
        R[N - 1::N] = 0          # source index s = j with s % N == N-1 would encode pos 0 (= END)
        bl = best_len[d:]
        upd = R > bl
        bl[upd] = R[upd]
        best_d[d:][upd] = d
    return best_len, best_d


def parse(best_len, n, lit_cost=9, match_cost=17):
    bl = best_len.tolist()
    cost = [0] * (n + 1 + MAXL)
    choice = [0] * n
    for i in range(n - 1, -1, -1):
        c = lit_cost + cost[i + 1]
        ch = 0
        L = bl[i]
        if L >= MINL:
            if L > n - i:
                L = n - i
            seg = cost[i + MINL:i + L + 1]
            m = min(seg)
            if match_cost + m < c:
                c = match_cost + m
                k = len(seg) - 1 - seg[::-1].index(m)
                ch = MINL + k
        cost[i] = c
        choice[i] = ch
    toks = []
    i = 0
    while i < n:
        L = choice[i]
        toks.append((i, L))
        i += L if L else 1
    return toks


def a16(v):
    return (v + 15) & ~15


def build(x, toks, best_d, typ=1):
    x = bytes(x)
    flags = bytearray(); codes = bytearray(); lits = bytearray()
    word = 0; nb = 0
    allt = list(toks) + [None]            # None = END token
    for t in allt:
        word <<= 1
        if t is not None and t[1] == 0:
            word |= 1
            lits.append(x[t[0]])
        elif t is None:
            codes += b'\0\0'
        else:
            i, L = t
            d = int(best_d[i])
            pos = (i + 1 - d) & MASK
            assert pos != 0 and 1 <= d <= MAXD and MINL <= L <= MAXL
            codes += struct.pack('<H', ((L - MINL) << PB) | pos)
        nb += 1
        if nb == 64:
            flags += struct.pack('<Q', word); word = 0; nb = 0
    if nb:
        flags += struct.pack('<Q', word << (64 - nb))
    co = a16(16 + len(flags))
    lo = a16(co + len(codes))
    out = bytearray(struct.pack('<4I', typ, len(x), co, lo))
    out += flags
    out += b'\0' * (co - len(out))
    out += codes
    out += b'\0' * (lo - len(out))
    out += lits
    nm = sum(1 for t in toks if t[1])
    return bytes(out), dict(T=len(toks), nm=nm, nl=len(toks) - nm, co=co, lo=lo, end=len(out))


def encode(x, verbose=True):
    t0 = time.time()
    xa = np.asarray(bytearray(x), np.uint8)
    bl, bd = find_matches(xa)
    t1 = time.time()
    toks = parse(bl, len(xa))
    t2 = time.time()
    blob, info = build(xa.tobytes(), toks, bd)
    if verbose:
        print('  enc: match %.1fs parse %.1fs  %s' % (t1 - t0, t2 - t1, info))
    return blob, info
