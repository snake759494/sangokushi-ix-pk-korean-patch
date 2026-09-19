# -*- coding: utf-8 -*-
"""G_TITLE.S9 container helpers: block table (same as ELF table at 0x4611D0), decode, re-encode."""
import struct, hashlib, os
import numpy as np
from s9gen import decode_gen
from s9enc import encode

SRC = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "san9pk", "G_TITLE.S9"))
OFFS = [0x0, 0x27290, 0x390D0, 0x4AFC0, 0x5CFB0, 0x6F040, 0x80FD0, 0x92E80, 0xA4DA0, 0xB6C40]
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'enc_cache')


def load():
    d = open(SRC, 'rb').read()
    raws = []
    for o in OFFS:
        t, u, co, lo, raw, fe, ce, le = decode_gen(d, o, 11)
        assert t == 1
        raws.append(raw)
    return d, raws


def slot_size(i, filelen):
    return (OFFS[i + 1] if i + 1 < len(OFFS) else filelen) - OFFS[i]


def enc_cached(raw):
    os.makedirs(CACHE, exist_ok=True)
    h = hashlib.sha1(raw).hexdigest()
    p = os.path.join(CACHE, h + '.bin')
    if os.path.exists(p):
        return open(p, 'rb').read()
    blob, info = encode(raw)
    open(p, 'wb').write(blob)
    return blob


def rebuild(orig, raws_new, raws_orig):
    out = bytearray(orig)
    report = []
    for i, (rn, ro) in enumerate(zip(raws_new, raws_orig)):
        if rn == ro:
            report.append((i, 'unchanged'))
            continue
        blob = enc_cached(rn)
        slot = slot_size(i, len(orig))
        if len(blob) > slot:
            raise SystemExit('block %d does not fit: %d > %d' % (i, len(blob), slot))
        out[OFFS[i]:OFFS[i] + slot] = blob + b'\0' * (slot - len(blob))
        report.append((i, 'reencoded %d/%d bytes (slack %d)' % (len(blob), slot, slot - len(blob))))
    # verify
    for i, rn in enumerate(raws_new):
        res = decode_gen(bytes(out), OFFS[i], 11)
        assert res is not None and res[4] == rn, 'verify failed block %d' % i
    return bytes(out), report
