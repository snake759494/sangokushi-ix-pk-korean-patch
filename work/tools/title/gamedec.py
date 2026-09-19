# -*- coding: utf-8 -*-
"""Exact model of the game's decompressor (SLPM_656.73 @0x23CAA0 -> 0x23C6E0/7D0/8C0/9B0).
No size check: decoding ends at a match code whose position field is 0.
src = out + (cnt & ~M) + pos - 1 (- N if (cnt & M) < pos); len = (v >> bits) + 3."""
import struct

def game_decode(d, o, maxout=1 << 22, prefix=None):
    t = struct.unpack_from('<I', d, o)[0]
    bits = {0: 10, 1: 11, 2: 12, 3: 13}[t]
    N = 1 << bits; M = N - 1
    co = struct.unpack_from('<I', d, o + 8)[0] & ~3
    lo = struct.unpack_from('<I', d, o + 12)[0] & ~3
    fp = o + 8; cp = o + co; lp = o + lo
    out = bytearray()
    cnt = 0
    mask = 0
    word = 0
    underflow = 0
    while True:
        mask >>= 1
        if mask == 0:
            mask = 1 << 63
            fp += 8
        word = struct.unpack_from('<Q', d, fp)[0]
        if word & mask:
            out.append(d[lp]); lp += 1; cnt += 1
        else:
            v = struct.unpack_from('<H', d, cp)[0]
            pos = v & M
            if pos == 0:
                return bytes(out), dict(type=t, end_code_at=cp - o, flags_at=fp - o, lits_end=lp - o, n=len(out), underflow=underflow)
            src = (cnt & ~M) + pos - 1
            if (cnt & M) < pos:
                src -= N
            L = (v >> bits) + 3
            cp += 2
            cnt += L
            for k in range(L):
                s = src + k
                if s < 0:
                    underflow += 1
                    out.append(0)
                else:
                    out.append(out[s])
        if len(out) > maxout:
            return bytes(out), dict(type=t, overflow=True, n=len(out), lits_end=lp - o)

if __name__ == '__main__':
    import sys
    from title_s9 import OFFS
    for path in sys.argv[1:]:
        d = open(path, 'rb').read()
        for i, o in enumerate(OFFS):
            u = struct.unpack_from('<I', d, o + 4)[0]
            out, info = game_decode(d, o, maxout=u + 0x10000)
            print(i, 'usize', hex(u), info)
