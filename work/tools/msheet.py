# -*- coding: utf-8 -*-
"""동영상에서 일정 간격으로 장면을 뽑아 한 장의 모음 이미지로 만든다.

python msheet.py 입력.PSS 출력.png [간격초=3] [열=6] [축소=0.4]
"""
import sys

import av
from PIL import Image, ImageDraw


def frames(path, step):
    c = av.open(path)
    vs = c.streams.video[0]
    nxt = 0.0
    for fr in c.decode(vs):
        t = float(fr.pts * vs.time_base) if fr.pts is not None else 0.0
        if t >= nxt:
            yield t, fr.to_image()
            nxt = t + step
    c.close()


def main():
    src, out = sys.argv[1], sys.argv[2]
    step = float(sys.argv[3]) if len(sys.argv) > 3 else 3.0
    cols = int(sys.argv[4]) if len(sys.argv) > 4 else 6
    sc = float(sys.argv[5]) if len(sys.argv) > 5 else 0.4
    ims = []
    for t, im in frames(src, step):
        w, h = int(im.width * sc), int(im.height * sc)
        im = im.resize((w, h))
        d = ImageDraw.Draw(im)
        d.text((3, 2), "%.1f" % t, fill=(255, 255, 0))
        ims.append(im)
    w, h = ims[0].size
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (w * cols, h * rows))
    for k, im in enumerate(ims):
        sheet.paste(im, ((k % cols) * w, (k // cols) * h))
    sheet.save(out)
    print(out, len(ims), sheet.size)


if __name__ == "__main__":
    main()
