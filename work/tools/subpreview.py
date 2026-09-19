# -*- coding: utf-8 -*-
"""자막 미리보기: 각 카드 대표 프레임에 한국어 줄을 그려 모음 이미지로 저장 (인코딩 없이 확인용)

python subpreview.py 출력.png 이름 [이름...]
"""
import io
import json
import os
import sys

import av
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import movenc  # noqa: E402
import pss  # noqa: E402
import subrender as R  # noqa: E402


def main():
    out = sys.argv[1]
    rows = []
    for name in sys.argv[2:]:
        js = json.load(open(os.path.join(movenc.SUBS, name + ".json"), encoding="utf-8"))
        tr = movenc.load_trans(name)
        keys = {c["key"]: c for c in js["cards"]}
        es, _, _ = pss.demux(os.path.join(movenc.ORIG, movenc.folder(name), name + ".PSS"))
        c = av.open(io.BytesIO(es), format="mpegvideo")
        for t, fr in enumerate(c.decode(video=0)):
            if t not in keys:
                continue
            card = keys[t]
            yuv = fr.to_ndarray(format="yuv420p").copy()
            text = tr.get(card["id"])
            if text:
                fa, oa, top = R.render_line(text)
                x, y = R.place(fa, R.W / 2, R.JP_BOTTOM + R.GAP - top + 1)
                R.composite(yuv, fa, oa, x, y, 1.0)
            im = av.VideoFrame.from_ndarray(yuv, format="yuv420p").to_image().crop((0, 318, 640, 432))
            d = ImageDraw.Draw(im)
            d.text((2, 0), "%s #%d" % (name, card["id"]), fill=(255, 255, 0))
            rows.append(im)
        c.close()
    sheet = Image.new("RGB", (640, sum(r.height for r in rows)))
    y = 0
    for r in rows:
        sheet.paste(r, (0, y))
        y += r.height
    sheet.save(out)
    print(out, sheet.size, len(rows))


if __name__ == "__main__":
    main()
