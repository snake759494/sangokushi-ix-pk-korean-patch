# -*- coding: utf-8 -*-
"""한국어 자막 한 줄을 YUV420 프레임 위에 그린다 (흰 글자 + 검은 외곽선, 상자 없음).

글꼴은 본문과 같은 서울한강체 B. 일본어 자막 글자(약 20px)의 절반 정도 크기.
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

WORK = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
FONT = os.path.join(os.path.dirname(WORK), "SeoulHangangB.ttf")
SIZE = 13          # 1배 기준 글꼴 크기(px) → 한글 높이 약 11px
SS = 4             # 슈퍼샘플링 배율
STROKE = 1.25      # 외곽선 두께(px, 1배 기준)
GAP = 6            # 일본어 자막 아래 간격
JP_BOTTOM = 399    # 일본어 자막 아랫줄 바닥
W, H = 640, 448
MARGIN = 16

_font = None


def font():
    global _font
    if _font is None:
        _font = ImageFont.truetype(FONT, SIZE * SS)
    return _font


def text_width(text):
    """1배 기준 픽셀 폭(외곽선 제외)."""
    f = font()
    l, t, r, b = f.getbbox(text)
    return (r - l) / SS


def render_line(text):
    """-> (fill_alpha, outline_alpha) float32 배열(1배 크기), 기준점 오프셋(ox, oy).

    글자 상자 기준: 배열 (0,0) 이 한글 글자 윗부분 위쪽 여백 포함 위치.
    """
    f = font()
    pad = int(np.ceil(STROKE * SS)) + SS
    l, t, r, b = f.getbbox(text)
    # 한글 기준 높이를 일정하게: '한' 글자의 위/아래를 기준으로 세로 위치 고정
    hl, ht, hr, hb = f.getbbox("한")
    top, bot = min(t, ht), max(b, hb)
    w = (r - l) + 2 * pad
    h = (bot - top) + 2 * pad
    w = (w + 2 * SS - 1) // (2 * SS) * (2 * SS)      # 1배에서 짝수 크기
    h = (h + 2 * SS - 1) // (2 * SS) * (2 * SS)
    fill = Image.new("L", (w, h), 0)
    outl = Image.new("L", (w, h), 0)
    org = (pad - l, pad - top)
    ImageDraw.Draw(fill).text(org, text, font=f, fill=255)
    ImageDraw.Draw(outl).text(org, text, font=f, fill=255, stroke_width=int(round(STROKE * SS)), stroke_fill=255)
    fa = np.asarray(fill, np.float32).reshape(h // SS, SS, w // SS, SS).mean((1, 3)) / 255.0
    oa = np.asarray(outl, np.float32).reshape(h // SS, SS, w // SS, SS).mean((1, 3)) / 255.0
    oa = np.maximum(oa, fa)
    # 한글 윗선이 오는 줄(1배) = pad/SS
    return fa, oa, pad / SS


def place(fa, cx, top):
    """글자 배열을 화면에 놓을 왼쪽 위 좌표(짝수로 맞춤)."""
    h, w = fa.shape
    x = int(round(cx - w / 2))
    x = max(MARGIN - 2, min(W - MARGIN + 2 - w, x))
    x -= x & 1
    y = int(round(top))
    y -= y & 1
    y = min(y, H - h - 8)
    return x, y


def composite(yuv, fa, oa, x, y, alpha):
    """yuv: (H*3/2, W) uint8 배열(yuv420p). 제자리 수정."""
    if alpha <= 0:
        return
    h, w = fa.shape
    Y = yuv[:H].astype(np.float32)
    Ub = yuv[H:H + H // 4].reshape(H // 2, W // 2)
    Vb = yuv[H + H // 4:].reshape(H // 2, W // 2)
    a_o = oa * alpha
    a_f = fa * alpha
    reg = Y[y:y + h, x:x + w]
    reg = reg * (1 - a_o) + 16.0 * a_o
    reg = reg * (1 - a_f) + 235.0 * a_f
    Y[y:y + h, x:x + w] = reg
    yuv[:H] = np.clip(np.round(Y), 0, 255).astype(np.uint8)
    # 색차: 무채색(128) 쪽으로
    a2 = a_o.reshape(h // 2, 2, w // 2, 2).mean((1, 3))
    for P in (Ub, Vb):
        r = P[y // 2:y // 2 + h // 2, x // 2:x // 2 + w // 2].astype(np.float32)
        r = r * (1 - a2) + 128.0 * a2
        P[y // 2:y // 2 + h // 2, x // 2:x // 2 + w // 2] = np.clip(np.round(r), 0, 255).astype(np.uint8)
