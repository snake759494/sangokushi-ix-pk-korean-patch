# -*- coding: utf-8 -*-
"""실행파일 안에서 '참조되는 주소' 집합을 구한다.

1) 데이터 속 32비트 포인터 (0x100000~0x17FD800 범위의 값)
2) 코드의 lui + addiu/ori/lw/lb/lbu/sw... 짝으로 만든 주소 (같은 레지스터, 20명령 이내)
"""
import struct

BASE_V, BASE_F = 0x100000, 0x80
CODE_END = 0x2F0000 + 0x80


def refs(d):
    n = (len(d) - BASE_F) // 4
    words = struct.unpack_from("<%dI" % n, d, BASE_F)
    out = set()
    lo_v, hi_v = BASE_V, BASE_V + len(d)
    for w in words:
        if lo_v <= w < hi_v:
            out.add(w)
    code_n = (CODE_END - BASE_F) // 4
    for i in range(code_n):
        w = words[i]
        if (w >> 26) != 0x0F:
            continue
        rt = (w >> 16) & 31
        hi = (w & 0xFFFF) << 16
        for j in range(i + 1, min(i + 24, code_n)):
            w2 = words[j]
            op = w2 >> 26
            rs = (w2 >> 21) & 31
            rt2 = (w2 >> 16) & 31
            imm = w2 & 0xFFFF
            if rs == rt and op in (0x09, 0x08, 0x19, 0x18):          # addiu/addi/daddiu/daddi
                simm = imm - 0x10000 if imm & 0x8000 else imm
                out.add((hi + simm) & 0xFFFFFFFF)
            elif rs == rt and op == 0x0D:                            # ori
                out.add(hi | imm)
            elif rs == rt and op in (0x20, 0x21, 0x23, 0x24, 0x25, 0x28, 0x29, 0x2B, 0x37, 0x3F, 0x1E, 0x1F):
                simm = imm - 0x10000 if imm & 0x8000 else imm
                out.add((hi + simm) & 0xFFFFFFFF)
            if rt2 == rt and op not in (0x2B, 0x29, 0x28, 0x3F, 0x1F):   # rt 가 덮어써지면 중단
                if op not in (0x04, 0x05):
                    break
    return out


def v2o(v):
    return v - BASE_V + BASE_F


def o2v(o):
    return o - BASE_F + BASE_V
