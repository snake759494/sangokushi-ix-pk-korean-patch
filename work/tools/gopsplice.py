# -*- coding: utf-8 -*-
"""고정 양자화 인코딩 여러 벌에서 GOP 마다 하나를 골라 이어 붙인다 (원본 PSS 의 영상 패킷 일정에 맞춤).

왜: ffmpeg 의 1패스 CBR 은 VBV 에 묶여 I 프레임을 굶겨(원본 67KB → 15KB) GOP(0.6초)마다 화질이 출렁였다.
방법: 같은 GOP 구조(닫힌 GOP 18장, B 2장, I 위치 원본과 같음)로 q 를 달리해 여러 벌 인코딩 → GOP 안은 고정 q 라
      I/P/B 배분이 자연스럽다. GOP 마다 원본 패킷 자리에 넣어 보며(psmux.remux 의 배치 규칙: 앞서면 패딩, 늦으면 지연)
      원본보다 LAG_MAX 프레임 넘게 늦지 않는 벌을 고른다. 고르는 기준은 GOP 단위 비트율 제어:
        1) 이번 GOP 와 다음 GOP(가장 고운 가능한 벌) 중 더 거친 쪽을 최소로 (어려운 장면 앞에서 미리 여유를 만든다)
        2) 두 GOP 의 거칠기 합이 작게
        3) 앞 GOP 에서 MAX_STEP 칸 넘게 움직이지 않게 (GOP 마다 화질이 크게 바뀌면 깜박여 보임)
        4) GOP 끝에서 원본보다 TARGET_BEHIND 프레임 늦은 상태에 가깝게 (앞서면 패딩으로 자리가 버려짐)
"""
import bisect

import psmux
import pss

LAG_MAX = 4           # 원본 일정보다 늦어도 되는 최대 프레임 수
LEAD = psmux.LEAD     # 원본보다 이만큼 넘게 앞서면 패딩
TARGET_BEHIND = 1.0
MAX_STEP = 2


class Schedule:
    """원본 PSS 의 영상 패킷 자리(용량)와, 각 자리 시작에서 원본 영상이 도달한 그림 번호."""

    def __init__(self, orig_pss):
        vslots = [x for x in pss.parse(orig_pss) if x[0] == "pes" and x[2] == 0xE0]
        oes = bytearray()
        opos = []
        self.caps = []
        for x in vslots:
            _, off, sid, total, hl, pts, dts, po, pl = x
            opos.append(len(oes))
            oes += orig_pss[po:po + pl]
            self.caps.append(total - 9 - hl)
        ooffs = [p[0] for p in psmux.pictures(bytes(oes))]
        self.npics = len(ooffs)
        self.of = [max(0, bisect.bisect_right(ooffs, pos) - 1) for pos in opos]

    def run(self, k, p, offs, pic_base, end):
        """자리 k, 새 영상 위치 p 에서 시작해 end 바이트까지 배치.
        offs = 이번 조각 그림들의 (전체 영상 기준) 시작 위치, pic_base = 그 첫 그림 번호.
        -> (k, p, 최대 지연) / 자리 부족이면 None"""
        lag = 0
        caps, of_ = self.caps, self.of
        while p < end:
            if k >= len(caps):
                return None
            nf = pic_base + bisect.bisect_right(offs, p) - 1
            of = of_[k]
            if nf > of + LEAD:
                k += 1                      # 앞섬 → 이 자리는 패딩
                continue
            if of - nf > lag:
                lag = of - nf
            p += caps[k]
            k += 1
        return k, p, lag


class Version:
    """한 벌의 인코딩: GOP 조각(시퀀스 헤더부터 다음 시퀀스 헤더 앞까지)과 조각 안 그림 위치."""

    def __init__(self, es):
        self.es = es
        starts = []
        i = es.find(b"\0\0\1\xb3")
        while i >= 0:
            starts.append(i)
            i = es.find(b"\0\0\1\xb3", i + 4)
        if not starts or starts[0] != 0:
            raise ValueError("시퀀스 헤더로 시작하지 않음")
        bounds = starts + [len(es)]
        pics = [p[0] for p in psmux.pictures(es)]
        self.chunks = []
        self.pic_offs = []
        for a, b in zip(bounds, bounds[1:]):
            self.chunks.append(es[a:b])
            self.pic_offs.append([o - a for o in pics if a <= o < b])


def choose(sched, versions, qs, log=print):
    """GOP 마다 q 선택. versions = {q: Version}, qs = 고운 것부터. -> (선택 목록, 최대 지연, 강제 수)"""
    ref = versions[qs[0]]
    ngop = len(ref.chunks)
    npg = [len(x) for x in ref.pic_offs]
    for q in qs:
        v = versions[q]
        if len(v.chunks) != ngop or [len(x) for x in v.pic_offs] != npg:
            raise ValueError("q=%s 벌의 GOP 구조가 다름" % q)
    if sum(npg) != sched.npics:
        raise ValueError("그림 수가 원본과 다름")

    def place(g, q, k, p, base, pic_base):
        v = versions[q]
        offs = [base + o for o in v.pic_offs[g]]
        return sched.run(k, p, offs, pic_base, base + len(v.chunks[g]))

    k = p = base = pic_base = 0
    choice = []
    worst = 0
    forced = 0
    prev = None
    for g in range(ngop):
        opts = []
        for i, q in enumerate(qs):
            r = place(g, q, k, p, base, pic_base)
            if r is None or r[2] > LAG_MAX:
                continue
            n = len(versions[q].chunks[g])
            nxt_pic = pic_base + npg[g]
            if g + 1 < ngop:
                j_best = None
                for j, q2 in enumerate(qs):
                    r2 = place(g + 1, q2, r[0], r[1], base + n, nxt_pic)
                    if r2 is not None and r2[2] <= LAG_MAX:
                        j_best = j
                        break
                if j_best is None:
                    continue
                behind = sched.of[r[0]] - nxt_pic if r[0] < len(sched.of) else 0
            else:
                j_best = i
                behind = 0
            far = prev is not None and abs(i - prev) > MAX_STEP
            key = (max(i, j_best), i + j_best, far, abs(behind - TARGET_BEHIND), i)
            opts.append((key, i, q, r, n))
        if opts:
            _, i, q, r, n = min(opts)
        else:                            # 어느 것도 조건을 못 맞추면 가장 거친 벌
            i, q = len(qs) - 1, qs[-1]
            r = place(g, q, k, p, base, pic_base)
            if r is None:
                raise ValueError("GOP %d: 원본 자리에 들어가지 않음" % g)
            n = len(versions[q].chunks[g])
            forced += 1
        k, p, lag = r
        worst = max(worst, lag)
        base += n
        pic_base += npg[g]
        choice.append(q)
        prev = i
    return choice, worst, forced


def splice(versions, choice):
    return patch_seq_headers(b"".join(versions[q].chunks[g] for g, q in enumerate(choice)))


def patch_seq_headers(es, bit_rate_value=7500, vbv_value=56):
    """모든 시퀀스 헤더의 bit_rate_value / vbv_buffer_size_value 를 원본 값(3000kbps, 917504비트)으로.
    (ffmpeg 에 -maxrate/-bufsize 를 주면 고정 양자화에서도 프레임을 깎아 I 프레임이 굶으므로 헤더만 고친다)"""
    out = bytearray(es)
    i = out.find(b"\0\0\1\xb3")
    while i >= 0:
        v = int.from_bytes(out[i + 4:i + 12], "big")
        v &= ~(((1 << 18) - 1) << (63 - 49))          # bit 32..49 bit_rate_value
        v |= (bit_rate_value & ((1 << 18) - 1)) << (63 - 49)
        v |= 1 << (63 - 50)                            # marker
        v &= ~(((1 << 10) - 1) << (63 - 60))           # bit 51..60 vbv_buffer_size_value
        v |= (vbv_value & ((1 << 10) - 1)) << (63 - 60)
        out[i + 4:i + 12] = v.to_bytes(8, "big")
        i = out.find(b"\0\0\1\xb3", i + 4)
    return bytes(out)
