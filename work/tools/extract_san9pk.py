# -*- coding: utf-8 -*-
"""SLPM_656.73 의 파일 테이블을 읽어 SAN9PK.BIN 내부 파일을 추출한다.

테이블 엔트리(32바이트): name_ptr, 0, start_lba, 0, end_lba, 0, sectors, 0
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ISO_DIR = os.path.join(HERE, "..", "iso")
OUT_DIR = os.path.join(HERE, "..", "san9pk")

ELF_TABLE = 0x32D130      # 파일 테이블 시작 (ELF 파일 오프셋)
SAN9PK_LBA = 1100000      # ISO 상의 SAN9PK.BIN 시작 LBA
SECTOR = 2048


def v2o(vaddr):
    return vaddr - 0x100000 + 0x80


def read_table(elf):
    entries = []
    i = 0
    while True:
        namep, _, s, _, e, _, n, _ = struct.unpack_from("<8I", elf, ELF_TABLE + i * 32)
        if not (0x400000 <= namep < 0x480000):
            break
        o = v2o(namep)
        name = elf[o:elf.index(b"\0", o)].decode("ascii")
        entries.append((name, s, e, n))
        i += 1
    return entries


def main():
    elf = open(os.path.join(ISO_DIR, "SLPM_656.73"), "rb").read()
    pk = open(os.path.join(ISO_DIR, "SAN9PK.BIN"), "rb").read()
    os.makedirs(OUT_DIR, exist_ok=True)
    pk_secs = len(pk) // SECTOR
    entries = read_table(elf)
    for name, s, e, n in entries:
        inpk = SAN9PK_LBA <= s < SAN9PK_LBA + pk_secs
        tag = "[SAN9PK +0x%X]" % ((s - SAN9PK_LBA) * SECTOR) if inpk else ""
        print("%-32s lba=%8d end=%8d secs=%5d %s" % (name, s, e, n, tag))
        if inpk:
            fn = name.lstrip("\\").split(";")[0]
            rel = (s - SAN9PK_LBA) * SECTOR
            with open(os.path.join(OUT_DIR, fn), "wb") as f:
                f.write(pk[rel:rel + n * SECTOR])
    print(len(entries), "entries")


if __name__ == "__main__":
    sys.exit(main())
