# -*- coding: utf-8 -*-
"""PS2 PSS(MPEG-2 프로그램 스트림) 분석·재구성 도구.

구조: 팩(00 00 01 BA, MPEG-2 팩 헤더 14바이트 + 스터핑) 뒤에 PES 패킷
      영상 = 스트림 E0 (MPEG-2 ES), 음성 = 사설 스트림 BD (PS2 ADPCM, 첫 패킷에 SShd/SSbd 헤더)
      끝 = 00 00 01 B9
"""
import struct
import sys


def read_scr(b):
    """MPEG-2 팩 헤더의 SCR base (90kHz)."""
    return (((b[0] >> 3) & 7) << 30) | ((b[0] & 3) << 28) | (b[1] << 20) | (((b[2] >> 3) & 0x1F) << 15) | \
           ((b[2] & 3) << 13) | (b[3] << 5) | (b[4] >> 3)


def read_ts(b):
    """PES PTS/DTS 5바이트 -> 90kHz."""
    return (((b[0] >> 1) & 7) << 30) | (b[1] << 22) | ((b[2] >> 1) << 15) | (b[3] << 7) | (b[4] >> 1)


def parse(data):
    """-> 목록: ('pack', off, scr) / ('pes', off, sid, total_len, hdr_len, pts, dts, payload_off, payload_len) / ('end', off)"""
    out = []
    i, n = 0, len(data)
    while i + 4 <= n:
        if data[i:i + 3] != b"\0\0\1":
            # 팩 사이 0 패딩 건너뛰기
            j = data.find(b"\0\0\1", i)
            if j < 0:
                break
            i = j
            continue
        sid = data[i + 3]
        if sid == 0xBA:
            stuff = data[i + 13] & 7
            out.append(("pack", i, read_scr(data[i + 4:i + 9]), data[i + 10:i + 13]))
            i += 14 + stuff
        elif sid == 0xB9:
            out.append(("end", i))
            i += 4
        elif sid == 0xBB or sid == 0xBE or sid == 0xBF:
            L = struct.unpack_from(">H", data, i + 4)[0]
            out.append(("other", i, sid, 6 + L))
            i += 6 + L
        elif sid in (0xBD,) or 0xC0 <= sid <= 0xEF:
            L = struct.unpack_from(">H", data, i + 4)[0]
            flags = data[i + 7]
            hl = data[i + 8]
            pts = dts = None
            if flags & 0x80:
                pts = read_ts(data[i + 9:i + 14])
            if flags & 0x40:
                dts = read_ts(data[i + 14:i + 19])
            po = i + 9 + hl
            pl = 6 + L - (9 + hl)
            out.append(("pes", i, sid, 6 + L, hl, pts, dts, po, pl))
            i += 6 + L
        else:
            i += 1
    return out


def summary(path):
    data = open(path, "rb").read()
    items = parse(data)
    from collections import Counter
    c = Counter()
    sizes = Counter()
    first = {}
    packs = [x for x in items if x[0] == "pack"]
    for x in items:
        if x[0] == "pes":
            c[x[2]] += 1
            sizes[(x[2], x[3])] += 1
            first.setdefault(x[2], x)
        elif x[0] == "other":
            c[x[2]] += 1
    print(path, "bytes", len(data), "packs", len(packs))
    print("  stream counts", {hex(k): v for k, v in c.items()})
    print("  common PES sizes", [(hex(k[0]), k[1], v) for k, v in sizes.most_common(6)])
    # 팩 간격
    offs = [p[1] for p in packs]
    gaps = Counter(b - a for a, b in zip(offs, offs[1:]))
    print("  pack spacing", gaps.most_common(4))
    print("  mux rate bytes", packs[0][3].hex(), "SCR first/last", packs[0][2], packs[-1][2])
    for sid, x in first.items():
        po, pl = x[7], x[8]
        print("  first PES %s at 0x%X hdr %d pts %s dts %s payload[:32]=%s" % (hex(sid), x[1], x[4], x[5], x[6],
                                                                             data[po:po + 32].hex(" ")))
    ends = [x for x in items if x[0] == "end"]
    print("  end codes at", [hex(e[1]) for e in ends][:3], "last data", hex(max(x[1] for x in items)))
    return items


if __name__ == "__main__":
    for p in sys.argv[1:]:
        summary(p)


def demux(path):
    """-> (영상 ES bytes, 음성 PES 목록[(off, raw bytes, pts)], 항목 목록)"""
    data = open(path, "rb").read()
    items = parse(data)
    v = bytearray()
    a = []
    for x in items:
        if x[0] != "pes":
            continue
        _, off, sid, total, hl, pts, dts, po, pl = x
        if sid == 0xE0:
            v += data[po:po + pl]
        elif sid == 0xBD:
            a.append((off, data[off:off + total], pts))
    return bytes(v), a, items
