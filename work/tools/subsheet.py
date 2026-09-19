# -*- coding: utf-8 -*-
"""받아쓰기용 자막 모음 이미지: python subsheet.py 출력.png 이름 [이름...]  (카드 번호 표시)"""
import glob
import os
import sys

from PIL import Image, ImageDraw

WORK = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
CROPS = os.path.join(WORK, "movie", "subs", "crops")


def main():
    out = sys.argv[1]
    ims = []
    import json
    for name in sys.argv[2:]:
        js = json.load(open(os.path.join(WORK, "movie", "subs", name + ".json"), encoding="utf-8"))
        for c in js["cards"]:
            f = os.path.join(CROPS, "%s_%02d.png" % (name, c["id"]))
            im = Image.open(f).convert("RGB")
            lab = os.path.basename(f)[:-4]
            d = ImageDraw.Draw(im)
            d.rectangle((0, 0, 7 * len(lab) + 4, 11), fill=(0, 0, 90))
            d.text((2, 0), lab, fill=(255, 255, 0))
            ims.append(im)
    W = max(i.width for i in ims)
    H = sum(i.height + 3 for i in ims)
    sheet = Image.new("RGB", (W, H), (60, 60, 60))
    y = 0
    for im in ims:
        sheet.paste(im, (0, y))
        y += im.height + 3
    sheet.save(out)
    print(out, sheet.size, len(ims))


if __name__ == "__main__":
    main()
