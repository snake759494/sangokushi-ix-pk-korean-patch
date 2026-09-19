# -*- coding: utf-8 -*-
"""SLPM_656.73 MIPS(R5900) 역어셈블 보조.

사용법: python disasm.py 가상주소(hex) [명령어 수]
capstone(MIPS64)이 모르는 R5900 명령(lq/sq/MMI)은 간단히 직접 표기한다.
"""
import struct
import sys

import capstone

ELF = __file__.replace("disasm.py", "../iso/SLPM_656.73")
BASE_V, BASE_F = 0x100000, 0x80
REG = ["zero", "at", "v0", "v1", "a0", "a1", "a2", "a3", "t0", "t1", "t2", "t3", "t4", "t5", "t6", "t7",
       "s0", "s1", "s2", "s3", "s4", "s5", "s6", "s7", "t8", "t9", "k0", "k1", "gp", "sp", "fp", "ra"]


def _r5900(w):
    op = w >> 26
    rs, rt, imm = (w >> 21) & 31, (w >> 16) & 31, w & 0xFFFF
    simm = imm - 0x10000 if imm & 0x8000 else imm
    if op == 0x1E:
        return "lq", "$%s, %d($%s)" % (REG[rt], simm, REG[rs])
    if op == 0x1F:
        return "sq", "$%s, %d($%s)" % (REG[rt], simm, REG[rs])
    if op == 0x1C:
        return "mmi", "0x%08X" % w
    return ".word", "0x%08X" % w


def dis(vaddr, count=40, out=print):
    d = open(ELF, "rb").read()
    md = capstone.Cs(capstone.CS_ARCH_MIPS, capstone.CS_MODE_MIPS64 + capstone.CS_MODE_LITTLE_ENDIAN)
    for k in range(count):
        a = vaddr + k * 4
        off = a - BASE_V + BASE_F
        w = struct.unpack_from("<I", d, off)[0]
        op = w >> 26
        ins = None
        if op not in (0x1C, 0x1E, 0x1F):
            ins = next(md.disasm_lite(d[off:off + 4], a), None)
        if ins:
            mn, ops = ins[2], ins[3]
        else:
            mn, ops = _r5900(w)
        out("%08X  %-8s %s" % (a, mn, ops))


if __name__ == "__main__":
    dis(int(sys.argv[1], 16), int(sys.argv[2]) if len(sys.argv) > 2 else 40)
