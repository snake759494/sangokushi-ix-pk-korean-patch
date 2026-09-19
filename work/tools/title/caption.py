# -*- coding: utf-8 -*-
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
FONT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "SeoulHangangB.ttf"))
TEXT = "파워업키트"

def render_masks(size, stroke, track=0.0, ss=8, text=TEXT):
    """(fill, outline) coverage arrays (0..1) at 1x, cropped to the outline bbox; glyph height."""
    f = ImageFont.truetype(FONT, int(round(size * ss)))
    sw = int(round(stroke * ss))
    adv = [f.getlength(ch) for ch in text]
    total = sum(adv) + track * ss * (len(text) - 1)
    W = int(total + 4 * sw + 8 * ss); H = int(size * ss * 1.6 + 4 * sw)
    fill = Image.new('L', (W, H), 0); outl = Image.new('L', (W, H), 0)
    df = ImageDraw.Draw(fill); do = ImageDraw.Draw(outl)
    x = 2 * sw + 4 * ss; y = 2 * sw
    for ch, a in zip(text, adv):
        do.text((x, y), ch, font=f, fill=255, stroke_width=sw, stroke_fill=255)
        df.text((x, y), ch, font=f, fill=255)
        x += a + track * ss
    o = np.array(outl, np.float64) / 255.0
    fl = np.array(fill, np.float64) / 255.0
    ys, xs = np.nonzero(o > 0)
    y0 = (ys.min() // ss) * ss; y1 = ((ys.max() // ss) + 1) * ss
    x0 = (xs.min() // ss) * ss; x1 = ((xs.max() // ss) + 1) * ss
    o = o[y0:y1, x0:x1]; fl = fl[y0:y1, x0:x1]
    h, w = o.shape[0] // ss, o.shape[1] // ss
    o = o.reshape(h, ss, w, ss).mean((1, 3))
    fl = fl.reshape(h, ss, w, ss).mean((1, 3))
    fy = np.nonzero(fl.max(1) > 0.5)[0]
    return fl, o, (fy.max() - fy.min() + 1 if len(fy) else 0)

class Caption:
    def __init__(self, fl, o, left, top, pal, white=(216, 216, 216), black=(0, 0, 0), allowed=None, thr=0.02):
        self.fl, self.o, self.left, self.top = fl, o, left, top
        self.pal = pal
        self.W = np.array(white, np.float64); self.B = np.array(black, np.float64)
        if allowed is None:
            allowed = [k for k in range(256) if pal[k][3] == 128]
        self.allowed = np.array(allowed)
        self.P = pal[self.allowed][:, :3].astype(np.float64)
        rgb = pal[self.allowed][:, :3]
        neutral = (rgb.max(1) - rgb.min(1)) <= 8
        self.allowed_n = self.allowed[neutral]
        self.Pn = self.P[neutral]
        self.thr = thr

    def apply(self, layer, lx, ly):
        """layer: 2D index array drawn at screen (lx, ly). Modified in place where the caption intersects."""
        h, w = self.o.shape
        H, Wd = layer.shape
        # intersection in screen coords
        sx0 = max(self.left, lx); sy0 = max(self.top, ly)
        sx1 = min(self.left + w, lx + Wd); sy1 = min(self.top + h, ly + H)
        if sx0 >= sx1 or sy0 >= sy1:
            return 0
        o = self.o[sy0 - self.top:sy1 - self.top, sx0 - self.left:sx1 - self.left]
        fl = self.fl[sy0 - self.top:sy1 - self.top, sx0 - self.left:sx1 - self.left]
        reg = layer[sy0 - ly:sy1 - ly, sx0 - lx:sx1 - lx]
        bg = self.pal[reg][..., :3].astype(np.float64)
        tgt = bg * (1 - o[..., None]) + self.B * (o - fl)[..., None] + self.W * fl[..., None]
        d = ((tgt[..., None, :] - self.P[None, None]) ** 2).sum(-1)
        q = self.allowed[np.argmin(d, -1)]
        # letter body and its white/black transition: neutral greys only (no cream/red tints)
        dn = ((tgt[..., None, :] - self.Pn[None, None]) ** 2).sum(-1)
        qn = self.allowed_n[np.argmin(dn, -1)]
        q = np.where(fl > 0.02, qn, q)
        m = o > self.thr
        reg[m] = q[m]
        return int(m.sum())
