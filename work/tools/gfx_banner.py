# -*- coding: utf-8 -*-
"""그림 글자 배너(전략/진행 페이즈, 트라이얼 스테이지 제목)를 한국어로 바꾼다.

배너 = 두 층(각 256x256 8비트 LZSS 블록). 블록의 윗 128줄 = 배너 왼쪽 절반, 아랫 128줄 = 오른쪽 절반
  (게임은 두 절반을 옆으로 붙여 512x128 로 그린다). 한 층은 흰 글자 + 부드러운 빛, 다른 층은 굵은 테두리.
방법: 원본에서 '두 층 모두 밝은 곳(≥200)' = 글자 획으로 보고, 각 층의 밝기를 획까지의 부호 있는 거리 함수로 잰 뒤
      한국어 글자(서울한강체 EB)를 그려 같은 거리 함수를 적용해 두 층을 새로 만든다.

python gfx_banner.py [--preview]
  출력: work/patched/G_MAPGRP.S9 (페이즈 배너 4블록), work/patched/GR_TRI1|2/G_PH*.S9
        work/gfx/preview/*.png (원본/새 배너 비교)
"""
import os
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "title"))
import s9lz  # noqa: E402
from gamedec import game_decode  # noqa: E402

WORK = os.path.normpath(os.path.join(HERE, ".."))
ROOT = os.path.dirname(WORK)
FONT = os.path.join(ROOT, "SeoulHangangEB.ttf")
SAN9 = os.path.join(WORK, "san9pk")
GRTRI = os.path.join(WORK, "gr_tri")          # ISO 의 GR_TRI1/2 폴더에서 뽑아 둔 원본
PATCHED = os.path.join(WORK, "patched")
PREVIEW = os.path.join(WORK, "gfx", "preview")
SS = 4

# G_MAPGRP.S9 안의 페이즈 배너 묶음: 0x847F0 부터 4블록 (묶음 시작 = ELF 0x2F7684, 다음 묶음 0x939E0).
# 묶음 안 블록 위치는 ELF 0x2F76D0 의 표 [0, 0x3180, 0x7A10, 0xAAC0] 로 고정 → 각 블록을 원래 자리에 넣는다
# (자리를 옮기면 게임이 엉뚱한 곳을 풀어 진행 페이즈 배너가 깨진다. 에뮬레이터 확인).
# GR_TRI 파일의 두 번째 블록 위치도 ELF 0x392720~ 표에 고정이라 원래 자리에 넣는다.
MAPGRP_GROUP = (0x847F0, 0x939E0)
MAPGRP_SUBOFFS = (0x0, 0x3180, 0x7A10, 0xAAC0)
ELF_SUBOFF_TABLE = 0x2F76D0
MAPGRP_TEXTS = ["전략 페이즈", "진행 페이즈"]

GRTRI_TEXTS = {
    "GR_TRI1/G_PHCLER.S9": "스테이지 클리어",
    "GR_TRI1/G_PHTIME.S9": "시간 초과",
    "GR_TRI1/G_PHGI01.S9": "설욕전",
    "GR_TRI1/G_PHGI02.S9": "위제 토벌전",
    "GR_TRI1/G_PHGI03.S9": "복양 방위전",
    "GR_TRI1/G_PHGI04.S9": "여포 토벌전",
    "GR_TRI1/G_PHGI05.S9": "장수 토벌전",
    "GR_TRI1/G_PHGI06.S9": "화북 최종 결전",
    "GR_TRI1/G_PHGI07.S9": "관도대전",
    "GR_TRI1/G_PHGI08.S9": "허창 최종 결전",
    "GR_TRI1/G_PHGO01.S9": "적벽대전",
    "GR_TRI1/G_PHGO02.S9": "합비 전투",
    "GR_TRI1/G_PHGO03.S9": "강릉 침공전",
    "GR_TRI1/G_PHGO04.S9": "양양 침공전",
    "GR_TRI1/G_PHGO05.S9": "강하 전투",
    "GR_TRI1/G_PHGO06.S9": "조씨 보복전",
    "GR_TRI1/G_PHGO07.S9": "적벽대전Ⅱ",
    "GR_TRI1/G_PHGO08.S9": "이릉대전",
    "GR_TRI2/G_PHSH01.S9": "이릉대전",
    "GR_TRI2/G_PHSH02.S9": "익주 반란 진압전",
    "GR_TRI2/G_PHSH03.S9": "천수 전투",
    "GR_TRI2/G_PHSH04.S9": "남만 평정전",
    "GR_TRI2/G_PHSH05.S9": "장안 침공전",
    "GR_TRI2/G_PHSH06.S9": "이릉대전Ⅱ",
    "GR_TRI2/G_PHSH07.S9": "양양 최종 결전",
    "GR_TRI2/G_PHSH08.S9": "한조 재흥전",
    "GR_TRI2/G_PHRY01.S9": "하비 탈출전",
    "GR_TRI2/G_PHRY02.S9": "업 쟁탈전",
    "GR_TRI2/G_PHRY03.S9": "관도 보복전",
    "GR_TRI2/G_PHRY04.S9": "건업 최종 결전",
    "GR_TRI2/G_PHBA01.S9": "위수 전투",
    "GR_TRI2/G_PHBA02.S9": "한중 공략전",
    "GR_TRI2/G_PHBA03.S9": "장안 정토전",
    "GR_TRI2/G_PHBA04.S9": "낙양 최종 결전",
}


# ------------------------------------------------------------------ 블록
def decode_block(data, off):
    t, u = struct.unpack_from("<2I", data, off)
    out, info = game_decode(data, off, maxout=u + 64)
    end = off + max(info["lits_end"], info["end_code_at"] + 2)
    return np.frombuffer(out[:u], np.uint8).reshape(256, 256), end


def to_wide(a):
    return np.concatenate([a[:128], a[128:]], 1)


def from_wide(w):
    return np.ascontiguousarray(np.concatenate([w[:, :256], w[:, 256:]], 0))


# ------------------------------------------------------------------ 모양 재기
def signed_distance(core):
    out = ndimage.distance_transform_edt(~core)
    inn = ndimage.distance_transform_edt(core)
    return np.where(core, -inn + 0.5, out - 0.5)


BINS = np.arange(-10.0, 48.0, 0.5)


def profile(layer, sd):
    """층 밝기를 부호 있는 거리의 함수로 (0.5px 간격 평균)."""
    vals = np.full(len(BINS), np.nan)
    for k, b in enumerate(BINS):
        m = (sd >= b - 0.25) & (sd < b + 0.25)
        if m.sum() >= 8:
            vals[k] = layer[m].mean()
    ok = ~np.isnan(vals)
    vals = np.interp(BINS, BINS[ok], vals[ok])
    return vals


def core_of(w0, w1):
    return (w0 >= 200) & (w1 >= 200)


# ------------------------------------------------------------------ 한국어 그리기
_fonts = {}


def font(px):
    if px not in _fonts:
        _fonts[px] = ImageFont.truetype(FONT, px)
    return _fonts[px]


def render_mask(text, ref_box):
    """한국어 글자 마스크(4배)를 원본 글자 상자에 맞춰 그린다. -> (4배 bool 배열 128*SS x 512*SS, 실제 상자)"""
    x0, y0, x1, y1 = ref_box
    ref_h = y1 - y0 + 1
    ref_w = x1 - x0 + 1
    cx = (x0 + x1 + 1) / 2
    cy = (y0 + y1 + 1) / 2
    probe = font(100 * SS)
    hb = probe.getbbox("한")
    h100 = (hb[3] - hb[1]) / SS                    # 글꼴 크기 100 일 때 한글 높이(1배 px)
    size = ref_h * 0.95 / h100 * 100
    max_w = min(512 - 2 * 26, max(ref_w * 1.12, ref_w + 30))
    while True:
        f = font(int(round(size * SS)))
        bb = f.getbbox(text)
        w = (bb[2] - bb[0]) / SS
        if w <= max_w or size < 20:
            break
        size *= 0.97
    # 원본 폭에 가깝도록 글자 사이를 넓힌다 (최대 0.2em, 띄어쓰기 옆은 넓히지 않고 띄어쓰기도 좁게)
    gaps = max(1, sum(1 for a, b in zip(text, text[1:]) if a != " " and b != " "))
    track = min(max(0.0, (min(max_w, ref_w * 0.9) - w) / gaps), 0.2 * size)

    def advances():
        out = []
        for i, ch in enumerate(text):
            adv = f.getlength(ch)
            if ch == " ":
                adv = adv * 0.8 + track * SS
            elif i + 1 < len(text) and text[i + 1] != " ":
                adv += track * SS
            out.append(adv)
        return out
    adv = advances()
    W, H = 512 * SS, 128 * SS
    img = Image.new("L", (W, H), 0)
    hb = f.getbbox("한")
    first = f.getbbox(text[0])
    last = f.getbbox(text[-1])
    total = sum(adv[:-1]) + last[2] - first[0]
    x = cx * SS - total / 2 - first[0]
    oy = cy * SS - (hb[1] + hb[3]) / 2
    d = ImageDraw.Draw(img)
    for ch, a in zip(text, adv):
        d.text((x, oy), ch, font=f, fill=255)
        x += a
    m = np.asarray(img) >= 128
    ys, xs = np.where(m)
    box = (xs.min() / SS, ys.min() / SS, xs.max() / SS, ys.max() / SS)
    return m, box, size


def sd_from_mask(mask_ss):
    out = ndimage.distance_transform_edt(~mask_ss)
    inn = ndimage.distance_transform_edt(mask_ss)
    sd = np.where(mask_ss, -inn, out) / SS
    h, w = sd.shape
    return sd.reshape(h // SS, SS, w // SS, SS).mean((1, 3))


def make_layers(w0, w1, text):
    core = core_of(w0, w1)
    sd = signed_distance(core)
    p0 = profile(w0.astype(float), sd)
    p1 = profile(w1.astype(float), sd)
    ys, xs = np.where(core)
    ref_box = (xs.min(), ys.min(), xs.max(), ys.max())
    m, box, size = render_mask(text, ref_box)
    sdk = sd_from_mask(m)
    n0 = np.interp(sdk, BINS, p0)
    n1 = np.interp(sdk, BINS, p1)
    n0 = np.clip(np.round(n0), 0, 255).astype(np.uint8)
    n1 = np.clip(np.round(n1), 0, 255).astype(np.uint8)
    return n0, n1, ref_box, box, size


# ------------------------------------------------------------------ 파일
def build_mapgrp(previews):
    src = open(os.path.join(SAN9, "G_MAPGRP.S9"), "rb").read()
    start, limit = MAPGRP_GROUP
    blocks = []
    off = start
    for _ in range(4):
        a, end = decode_block(src, off)
        blocks.append(a)
        off = (end + 15) & ~15
    assert off == limit, hex(off)
    new_raw = []
    for k, text in enumerate(MAPGRP_TEXTS):
        wA, wB = to_wide(blocks[2 * k]), to_wide(blocks[2 * k + 1])
        nA, nB, rb, kb, size = make_layers(wA, wB, text)
        print("  G_MAPGRP %-12s 원본 상자 %s -> %s (글꼴 %.1f)" % (text, rb, tuple(round(v) for v in kb), size))
        new_raw += [from_wide(nA), from_wide(nB)]
        previews.append(("MAPGRP_%d" % k, wA, wB, nA, nB))
    elf = open(os.path.join(WORK, "iso", "SLPM_656.73"), "rb").read()
    table = struct.unpack_from("<4I", elf, ELF_SUBOFF_TABLE)
    if table != MAPGRP_SUBOFFS:
        raise SystemExit("ELF 블록 위치 표가 예상과 다름: %s" % (table,))
    out = bytearray(src)
    out[start:limit] = b"\0" * (limit - start)
    bounds = list(MAPGRP_SUBOFFS) + [limit - start]
    for k, raw in enumerate(new_raw):
        blob = s9lz.encode_best(raw.tobytes(), types=(0, 1))
        slot = bounds[k + 1] - bounds[k]
        if len(blob) > slot:
            raise SystemExit("G_MAPGRP 배너 블록 %d 가 자리보다 큼: %d > %d" % (k, len(blob), slot))
        pos = start + bounds[k]
        out[pos:pos + len(blob)] = blob
        print("  G_MAPGRP 블록 %d @+0x%X  %d / %d 바이트" % (k, bounds[k], len(blob), slot))
    # 게임과 같은 방식(표의 위치에서 해제)으로 다시 풀어 확인
    for k, raw in enumerate(new_raw):
        a, _ = decode_block(bytes(out), start + MAPGRP_SUBOFFS[k])
        assert (a == raw).all()
    return bytes(out)


def build_grtri(key, text, previews):
    src = open(os.path.join(GRTRI, os.path.basename(key)), "rb").read()
    a0, e0 = decode_block(src, 0)
    b1 = (e0 + 15) & ~15
    a1, e1 = decode_block(src, b1)
    elf = open(os.path.join(WORK, "iso", "SLPM_656.73"), "rb").read()
    if struct.pack("<II", 0, b1) not in elf[0x392720:0x392840]:
        raise SystemExit("%s: 두 번째 블록 위치 0x%X 가 ELF 표에 없음" % (key, b1))
    w0, w1 = to_wide(a0), to_wide(a1)
    n0, n1, rb, kb, size = make_layers(w0, w1, text)
    previews.append((os.path.basename(key)[:-3], w0, w1, n0, n1))
    t0 = struct.unpack_from("<I", src, 0)[0]
    t1 = struct.unpack_from("<I", src, b1)[0]
    blob0 = s9lz.encode_best(from_wide(n0).tobytes(), types=(0, 1))
    blob1 = s9lz.encode_best(from_wide(n1).tobytes(), types=(0, 1))
    if len(blob0) > b1:
        raise SystemExit("%s: 첫 블록이 원래 자리(%d)보다 큼 %d" % (key, b1, len(blob0)))
    if b1 + len(blob1) > len(src):
        raise SystemExit("%s: 두 번째 블록이 파일 크기를 넘음 %d > %d" % (key, b1 + len(blob1), len(src)))
    out = bytearray(len(src))
    out[0:len(blob0)] = blob0
    out[b1:b1 + len(blob1)] = blob1
    x0, _ = decode_block(bytes(out), 0)
    x1, _ = decode_block(bytes(out), b1)
    assert (x0 == from_wide(n0)).all() and (x1 == from_wide(n1)).all()
    print("  %-22s %-16s 블록 %5d/%5d  %5d/%5d  (종류 %d,%d 원본 %d,%d)" % (
        key, text, len(blob0), b1, len(blob1), len(src) - b1, blob0[0], blob1[0], t0, t1))
    return bytes(out)


def save_previews(previews):
    os.makedirs(PREVIEW, exist_ok=True)
    rows = []
    for name, w0, w1, n0, n1 in previews:
        top = np.concatenate([w0, w1], 1)
        bot = np.concatenate([n0, n1], 1)
        rows.append(np.concatenate([top, bot], 0))
    for k in range(0, len(rows), 6):
        s = np.concatenate(rows[k:k + 6], 0)
        Image.fromarray(s).save(os.path.join(PREVIEW, "banners_%02d.png" % (k // 6)))


def main():
    previews = []
    data = build_mapgrp(previews)
    open(os.path.join(PATCHED, "G_MAPGRP.S9"), "wb").write(data)
    for key, text in GRTRI_TEXTS.items():
        data = build_grtri(key, text, previews)
        dst = os.path.join(PATCHED, key.replace("/", os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, "wb").write(data)
    save_previews(previews)
    print("완료: 배너 %d 개" % len(previews))


if __name__ == "__main__":
    main()
