import numpy as np
from compose import FX, FY, PX, PY
def apply_all(cap, base, frames):
    """base: (512,1024) idx; frames: list of (1024,256) idx arrays. Returns modified copies + stats."""
    b = base.copy()
    st = {}
    st['base'] = cap.apply(b[0:448, 0:640], 0, 0)
    # PRESS START sprite frames: 5 x (272x32) at texture (640, k*32), drawn at screen (PX, PY)
    st['ps'] = [cap.apply(b[k * 32:(k + 1) * 32, 640:912], PX, PY) for k in range(5)]
    fr2 = []
    st['fr'] = []
    for fr in frames:
        f = fr.copy()
        n = 0
        n += cap.apply(f[0:256, 0:256], FX, FY)
        n += cap.apply(f[256:512, 0:104], FX + 256, FY)
        n += cap.apply(f[512:632, 0:256], FX, FY + 256)
        n += cap.apply(f[768:888, 0:104], FX + 256, FY + 256)
        fr2.append(f); st['fr'].append(n)
    return b, fr2, st
