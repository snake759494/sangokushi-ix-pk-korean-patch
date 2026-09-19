import struct
def decode_gen(d, o, pbits, r0=1, minlen=3, maxout=None):
    t, u, co, lo = struct.unpack_from('<4I', d, o)
    N = 1 << pbits; M = N - 1
    fp = o + 16; cp = o + co; lp = o + lo
    ring = bytearray(N); r = r0 & M
    out = bytearray(); bits = 0; nb = 0
    n = len(d)
    while len(out) < u:
        if nb == 0:
            if fp + 8 > o + co: return None
            bits = int.from_bytes(d[fp:fp+8], 'little'); fp += 8; nb = 64
        nb -= 1
        if (bits >> nb) & 1:
            if lp >= n: return None
            c = d[lp]; lp += 1
            out.append(c); ring[r] = c; r = (r + 1) & M
        else:
            if cp + 2 > o + lo: return None
            v = d[cp] | (d[cp+1] << 8); cp += 2
            pos = v & M
            for k in range((v >> pbits) + minlen):
                c = ring[(pos + k) & M]; out.append(c); ring[r] = c; r = (r + 1) & M
    return t, u, co, lo, bytes(out[:u]), fp - o, cp - o, lp - o
