import numpy as np
from PIL import Image
FX, FY = 267, 7          # flare frame placement (base texture coords)
PX, PY = 184, 338        # PRESS START sprite placement
def frame_tiles(fr):
    """fr: (1024,256) frame image -> list of (tile, x, y) in screen coords"""
    return [(fr[0:256, 0:256], FX, FY), (fr[256:512, 0:104], FX + 256, FY),
            (fr[512:632, 0:256], FX, FY + 256), (fr[768:888, 0:104], FX + 256, FY + 256)]
def compose(base, frame, ps_idx=0):
    scr = base[0:448, 0:640].copy()
    for t, x, y in frame_tiles(frame):
        h, w = t.shape
        scr[y:y + h, x:x + w] = t
    ps = base[ps_idx * 32:(ps_idx + 1) * 32, 640:912]
    scr[PY:PY + 32, PX:PX + 272] = ps
    return scr
def to_rgb(idx, pal):
    return pal[idx][..., :3].astype(np.uint8)
def disp480(rgb):
    return np.array(Image.fromarray(rgb).resize((640, 480), Image.BILINEAR))
