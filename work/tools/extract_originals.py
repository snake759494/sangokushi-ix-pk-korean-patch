# -*- coding: utf-8 -*-
"""원본 ISO 에서 빌드에 필요한 파일을 꺼낸다 (저장소에서 처음부터 다시 빌드할 때 첫 단계).

python work/tools/extract_originals.py ["Sangokushi IX with Power-Up Kit (Japan).iso"]

꺼내는 것 (모두 .gitignore 대상, 배포하지 않음):
  work/iso/SLPM_656.73, work/iso/SAN9PK.BIN   실행파일과 묶음 파일
  work/san9pk/*                                SAN9PK.BIN 안의 파일들 (extract_san9pk.py)
  work/gr_tri/G_PH*.S9                         트라이얼 스토리 제목 그림 (ISO 의 GR_TRI1/2 폴더)
  work/movie/orig/MOVIE/*.PSS, MOVIESOP/*.PSS  동영상
원본 ISO 의 SHA-256 이 README 의 값과 다르면 멈춘다.
"""
import hashlib
import os
import sys

import pycdlib

import extract_san9pk

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.normpath(os.path.join(HERE, ".."))
ROOT = os.path.dirname(WORK)
DEFAULT_ISO = os.path.join(ROOT, "Sangokushi IX with Power-Up Kit (Japan).iso")
ISO_SIZE = 2496921600
ISO_SHA256 = "6de9c4bc8e94d651d27eb5708c6d8bc33e893c5dd8f3f9aae3808d73b8b9a157"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 24), b""):
            h.update(block)
    return h.hexdigest()


def main():
    iso_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ISO
    if os.path.getsize(iso_path) != ISO_SIZE or sha256(iso_path) != ISO_SHA256:
        sys.exit("원본 ISO 가 아님 (크기 또는 SHA-256 불일치): %s" % iso_path)
    iso = pycdlib.PyCdlib()
    iso.open(iso_path)
    jobs = [("/SLPM_656.73;1", os.path.join(WORK, "iso", "SLPM_656.73")),
            ("/SAN9PK.BIN;1", os.path.join(WORK, "iso", "SAN9PK.BIN"))]
    for dirname, _, files in iso.walk(iso_path="/"):
        d = dirname.strip("/")
        for f in files:
            name = f.split(";")[0]
            if d in ("GR_TRI1", "GR_TRI2"):
                jobs.append(("/%s/%s" % (d, f), os.path.join(WORK, "gr_tri", name)))
            elif d in ("MOVIE", "MOVIESOP"):
                jobs.append(("/%s/%s" % (d, f), os.path.join(WORK, "movie", "orig", d, name)))
    for src, dst in jobs:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        iso.get_file_from_iso(dst, iso_path=src)
        print("  %-28s -> %s" % (src, os.path.relpath(dst, ROOT)))
    iso.close()
    extract_san9pk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
