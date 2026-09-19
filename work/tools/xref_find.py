# -*- coding: utf-8 -*-
"""실행파일에서 특정 주소를 만드는 코드(lui+addiu 등)와 데이터 포인터 위치 찾기.
python xref_find.py 파일오프셋...
"""
import os
import struct
import sys

ELF = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "iso", "SLPM_656.73"))
BASE_V, BASE_F = 0x100000, 0x80
CODE_END = 0x2F0000 + 0x80


def main():
    d = open(ELF, "rb").read()
    n = (len(d) - BASE_F) // 4
    words = struct.unpack_from("<%dI" % n, d, BASE_F)
    targets = {int(a, 16) - BASE_F + BASE_V: a for a in sys.argv[1:]}
    code_n = (CODE_END - BASE_F) // 4
    for i, w in enumerate(words):
        if w in targets:
            print("data ptr  -> %s at file 0x%X (va 0x%X)" % (targets[w], BASE_F + i * 4, BASE_V + i * 4))
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
            imm = w2 & 0xFFFF
            simm = imm - 0x10000 if imm & 0x8000 else imm
            addr = None
            if rs == rt and op in (0x09, 0x08, 0x19, 0x18, 0x20, 0x21, 0x23, 0x24, 0x25, 0x28, 0x29, 0x2B, 0x37, 0x3F):
                addr = (hi + simm) & 0xFFFFFFFF
            elif rs == rt and op == 0x0D:
                addr = hi | imm
            if addr in targets:
                print("code      -> %s lui@va 0x%X use@va 0x%X" % (targets[addr], BASE_V + i * 4, BASE_V + j * 4))
            if ((w2 >> 16) & 31) == rt and op in (0x09, 0x0D, 0x0F, 0x23, 0x08):
                break


if __name__ == "__main__":
    main()
