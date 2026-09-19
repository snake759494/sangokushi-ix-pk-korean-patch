# -*- coding: utf-8 -*-
"""원본 PSS 의 틀(팩·음성 패킷 위치·크기)을 그대로 두고 영상 패킷 자리에 새 MPEG-2 영상을 채워 넣는다.

- 음성(BD)·시스템 헤더·팩 헤더·끝 코드는 원본 그대로 → 음성은 바이트 단위로 동일
- 영상(E0) 패킷 자리는 크기 그대로, 내용만 새 영상 ES 로 채우고 PTS/DTS 새로 계산
- 새 영상이 원본 일정보다 LEAD 프레임 넘게 앞서면 그 자리를 패딩(BE) 패킷으로 채워 원본 인터리브 유지
- 결과 파일 크기 = 원본 크기 (디스크 위치·파일 테이블 수정 불필요)
"""
import struct

import pss

LEAD = 3


def pictures(es):
    """ES 속 그림 목록 (디코드 순서): [(offset, type, display_index)]"""
    pics = []
    gop_base = 0
    gop_count = 0
    i = es.find(b"\0\0\1")
    while i >= 0 and i + 6 <= len(es):
        code = es[i + 3]
        if code == 0xB8:                       # GOP
            gop_base += gop_count
            gop_count = 0
        elif code == 0x00:                     # picture
            tr = (es[i + 4] << 2) | (es[i + 5] >> 6)
            pt = (es[i + 5] >> 3) & 7
            pics.append([i, pt, gop_base + tr])
            gop_count += 1
        i = es.find(b"\0\0\1", i + 3)
    return pics


def enc_ts(prefix, ts):
    return bytes([(prefix << 4) | (((ts >> 30) & 7) << 1) | 1, (ts >> 22) & 0xFF, (((ts >> 15) & 0x7F) << 1) | 1,
                  (ts >> 7) & 0xFF, ((ts & 0x7F) << 1) | 1])


def pes_header(first, hl, pts, dts, ext=b""):
    """영상 PES 헤더(시작코드~헤더 데이터 끝). hl = 헤더 데이터 길이(원본 10 또는 13)."""
    if pts is None:
        flags, body = 0x00, b""
    elif dts is None or dts == pts:
        flags, body = 0x80, enc_ts(2, pts)
    else:
        flags, body = 0xC0, enc_ts(3, pts) + enc_ts(1, dts)
    if ext:
        flags |= 0x01
        body += ext
    body += b"\xff" * (hl - len(body))
    assert len(body) == hl, (hl, len(body))
    return bytes([0x83, flags, hl]) + body


def padding_pes(total):
    return b"\0\0\1\xbe" + struct.pack(">H", total - 6) + b"\xff" * (total - 6)


def remux(orig, new_es, lead=LEAD, log=print):
    items = pss.parse(orig)
    vslots = [x for x in items if x[0] == "pes" and x[2] == 0xE0]
    # 원본 영상 ES 위치 → 그림 번호, PTS/DTS 기준값
    oes = bytearray()
    slot_opos = []
    base_pts = base_dts = None
    for x in vslots:
        _, off, sid, total, hl, pts, dts, po, pl = x
        slot_opos.append(len(oes))
        oes += orig[po:po + pl]
    opics = pictures(bytes(oes))
    # 원본 첫 그림(디코드 0)의 DTS, 표시 0 의 PTS 구하기: 첫 영상 PES 기준
    first = vslots[0]
    fpts, fdts = first[5], first[6]
    p0 = opics[0]
    base_pts = fpts - 3000 * p0[2]
    base_dts = (fdts if fdts is not None else fpts) - 0
    ooffs = [p[0] for p in opics]

    import bisect

    def pic_at(offs, pos):
        return max(0, bisect.bisect_right(offs, pos) - 1)

    npics = pictures(new_es)
    noffs = [p[0] for p in npics]
    if len(npics) != len(opics):
        raise ValueError("그림 수가 다름: 원본 %d, 새 영상 %d" % (len(opics), len(npics)))

    caps = [x[3] - 9 - x[4] for x in vslots]
    rest_cap = [0] * (len(caps) + 1)          # rest_cap[k] = k 번째 자리부터 끝까지 용량
    for k in range(len(caps) - 1, -1, -1):
        rest_cap[k] = rest_cap[k + 1] + caps[k]
    out = bytearray(orig)
    p = 0
    np_i = 0            # 다음에 PTS 를 붙일 새 그림 번호
    pads = 0
    behind = 0
    for k, x in enumerate(vslots):
        _, off, sid, total, hl, pts, dts, po, pl = x
        ext = b""
        if hl == 13:                            # 첫 패킷: P-STD 확장 3바이트 유지
            ext = orig[off + 9 + 10:off + 9 + 13]
        cap = total - 9 - hl
        if p >= len(new_es):
            out[off:off + total] = padding_pes(total)
            continue
        nf = pic_at(noffs, p)
        of = pic_at(ooffs, slot_opos[k])
        if nf > of + lead and len(new_es) - p <= rest_cap[k + 1]:
            out[off:off + total] = padding_pes(total)
            pads += 1
            continue
        behind = max(behind, of - nf)
        chunk = new_es[p:p + cap]
        # 이 패킷에서 시작하는 첫 그림
        tpts = tdts = None
        while np_i < len(npics) and npics[np_i][0] < p:
            np_i += 1
        if np_i < len(npics) and npics[np_i][0] < p + len(chunk):
            j = np_i
            tpts = base_pts + 3000 * npics[j][2]
            tdts = base_dts + 3000 * j
            if npics[j][1] == 3:                # B 그림: DTS 생략
                tdts = None
        if len(chunk) == cap:
            body = b"\0\0\1\xe0" + struct.pack(">H", total - 6) + pes_header(True, hl, tpts, tdts, ext) + chunk
        else:
            rest = cap - len(chunk)
            if rest >= 8:
                vt = total - rest
                body = b"\0\0\1\xe0" + struct.pack(">H", vt - 6) + pes_header(True, hl, tpts, tdts, ext) + chunk
                body += padding_pes(rest)
            else:
                body = b"\0\0\1\xe0" + struct.pack(">H", total - 6) + pes_header(True, hl + rest, tpts, tdts, ext) + chunk
        assert len(body) == total
        out[off:off + total] = body
        p += len(chunk)
    if p < len(new_es):
        raise ValueError("새 영상이 들어가지 않음: %d 바이트 남음" % (len(new_es) - p))
    log("  remux: 영상 %d 바이트 / 자리 %d 바이트, 패딩 %d 개, 최대 지연 %d 프레임" %
        (len(new_es), sum(x[3] - 9 - x[4] for x in vslots), pads, behind))
    return bytes(out)


def verify(orig, new, new_es):
    """새 PSS 에서 영상 ES 를 다시 뽑아 같은지, 음성 패킷이 원본과 같은지."""
    a = [x for x in pss.parse(orig) if x[0] == "pes" and x[2] == 0xBD]
    b = [x for x in pss.parse(new) if x[0] == "pes" and x[2] == 0xBD]
    assert len(a) == len(b), "음성 패킷 수 다름"
    for x, y in zip(a, b):
        assert x[1] == y[1] and orig[x[1]:x[1] + x[3]] == new[y[1]:y[1] + y[3]], "음성 패킷 다름 @%X" % x[1]
    v = bytearray()
    for x in pss.parse(new):
        if x[0] == "pes" and x[2] == 0xE0:
            v += new[x[7]:x[7] + x[8]]
    assert bytes(v) == new_es, "영상 ES 불일치"
    assert len(orig) == len(new)
    return True
