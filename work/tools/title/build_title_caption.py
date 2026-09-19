# -*- coding: utf-8 -*-
"""Build work/patched/G_TITLE.S9 with the Korean caption '파워업키트' under パワーアップキット.

Blocks of G_TITLE.S9 (offsets hard-coded in the ELF table at 0x4611D0):
  0      : 1024x512 PSMT8 title texture (screen 640x448 at 0,0; PRESS START frames 5x 272x32 at 640,k*32)
  1..8   : 256x1024 flare-animation frames; tiles drawn opaquely at (267,7),(523,7),(267,263),(523,263)
  9      : 3 identical 256-colour CLUTs (CSM1 order)
PRESS START sprite is drawn opaquely at (184,338).
"""
import os, sys, struct
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gamedec import game_decode
from s9enc import encode
from caption import render_masks, Caption
from apply_all import apply_all
from compose import compose, to_rgb, disp480

WORK = os.path.normpath(os.path.join(HERE, "..", ".."))
SRC = os.path.join(WORK, "san9pk", "G_TITLE.S9")
DST = os.path.join(WORK, "patched", "G_TITLE.S9")
OFFS = [0x0, 0x27290, 0x390D0, 0x4AFC0, 0x5CFB0, 0x6F040, 0x80FD0, 0x92E80, 0xA4DA0, 0xB6C40]

# caption design
SIZE, STROKE, TRACK = 22, 2.0, 2.0
CX, TOP = 328, 316
WHITE_IDX = 255                 # unused palette entry -> pure white
WHITE = (255, 255, 255)

idx = np.arange(256)
SW = (idx & 0xE7) | ((idx & 0x08) << 1) | ((idx & 0x10) >> 1)   # CSM1 swizzle (involution)


def main(write=True):
    orig = open(SRC, 'rb').read()
    raws = []
    for i, o in enumerate(OFFS):
        u = struct.unpack_from('<I', orig, o + 4)[0]
        out, info = game_decode(orig, o, maxout=u + 64)
        assert info.get('n') == u and 'end_code_at' in info, (i, info)
        raws.append(out)
    base = np.frombuffer(raws[0], np.uint8).reshape(512, 1024)
    frames = [np.frombuffer(raws[i], np.uint8).reshape(1024, 256) for i in range(1, 9)]
    clut_raw = np.frombuffer(raws[9], np.uint8).reshape(3, 256, 4)
    pal = clut_raw[0][SW].astype(int)                  # logical palette
    # sanity: WHITE_IDX unused everywhere
    used = np.zeros(256, bool)
    for a in [base] + frames:
        used |= np.bincount(a.ravel(), minlength=256) > 0
    assert not used[WHITE_IDX], 'palette index %d is in use' % WHITE_IDX
    pal2 = pal.copy(); pal2[WHITE_IDX] = list(WHITE) + [128]
    clut_new = clut_raw.copy()
    clut_new[:, SW[WHITE_IDX]] = list(WHITE) + [128]

    fl, o, gh = render_masks(SIZE, STROKE, TRACK)
    h, w = o.shape
    left = CX - w // 2
    cap = Caption(fl, o, left, TOP, pal2, white=WHITE)
    b2, f2, st = apply_all(cap, base, frames)
    print('caption glyph height %d px, box %dx%d at (%d,%d)-(%d,%d); pixels base %d, ps %s, frames %s'
          % (gh, w, h, left, TOP, left + w - 1, TOP + h - 1, st['base'], st['ps'], st['fr']))

    new_raws = [b2.tobytes()] + [f.tobytes() for f in f2] + [clut_new.tobytes()]
    out = bytearray(orig)
    for i, (rn, ro) in enumerate(zip(new_raws, raws)):
        if rn == ro:
            print('block %d unchanged' % i)
            continue
        blob, info = encode(rn, verbose=False)
        slot = (OFFS[i + 1] if i + 1 < len(OFFS) else len(orig)) - OFFS[i]
        if len(blob) > slot:
            raise SystemExit('block %d too big: %d > %d' % (i, len(blob), slot))
        out[OFFS[i]:OFFS[i] + slot] = blob + b'\0' * (slot - len(blob))
        print('block %d re-encoded: %d / %d bytes (original %d)' % (i, len(blob), slot,
              game_decode(orig, OFFS[i], maxout=len(ro) + 64)[1]['lits_end']))
    out = bytes(out)
    assert len(out) == len(orig)
    # verify with the exact game-decoder model
    for i, o in enumerate(OFFS):
        dec, info = game_decode(out, o, maxout=len(new_raws[i]) + 64)
        assert dec == new_raws[i] and info.get('n') == len(new_raws[i]) and 'end_code_at' in info, (i, info)
    print('verified all %d blocks with game decoder model' % len(OFFS))

    # previews
    for tag, bb, ff, pp in (('before', base, frames, pal), ('after', b2, f2, pal2)):
        rgb = to_rgb(bb[0:448, 0:640], pp)
        Image.fromarray(rgb[200:360, 140:520]).resize((760, 320), Image.NEAREST).save(os.path.join(HERE, 'logo_%s_texture.png' % tag))
        scr = compose(bb, ff[5], 1)
        d480 = disp480(to_rgb(scr, pp))
        Image.fromarray(d480).save(os.path.join(HERE, 'screen_%s_sim.png' % tag))
        Image.fromarray(d480[200:420, 120:540]).resize((840, 440), Image.LANCZOS).save(os.path.join(HERE, 'logo_%s_crop.png' % tag))
    if write:
        open(DST, 'wb').write(out)
        print('written', DST, len(out))
    else:
        open(os.path.join(HERE, 'G_TITLE_new.S9'), 'wb').write(out)
        print('written (scratch only)', len(out))


if __name__ == '__main__':
    main(write='--write' in sys.argv)
