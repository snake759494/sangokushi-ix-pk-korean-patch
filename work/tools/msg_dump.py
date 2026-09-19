# -*- coding: utf-8 -*-
"""M_MSG.S9 / M_RTDN.S9 형식(u16 개수 + u32 오프셋[개수] + 본문)을 텍스트로 덤프한다.

사용법: python msg_dump.py 입력.S9 출력.txt
각 항목: '#번호 0x오프셋' 줄 다음에 디코드 문자열(s9text.decode)
"""
import struct
import sys

from s9text import decode


def read_entries(data):
    n = struct.unpack_from("<H", data, 0)[0]
    offs = list(struct.unpack_from("<%dI" % n, data, 2))
    # 마지막 항목 끝 = 마지막 0x05 연속 뒤
    e = offs[-1]
    while data[e] != 0x05:
        e += 1
    while e < len(data) and data[e] == 0x05:
        e += 1
    ends = offs[1:] + [e]
    return [(o, data[o:en]) for o, en in zip(offs, ends)]


def main():
    data = open(sys.argv[1], "rb").read()
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        for i, (o, raw) in enumerate(read_entries(data)):
            f.write("#%05d 0x%06X\n%s\n" % (i, o, decode(raw)))


if __name__ == "__main__":
    main()
