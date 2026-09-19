# -*- coding: utf-8 -*-
"""동영상에 한국어 자막 한 줄을 입혀 PSS 로 다시 만든다.

python movenc.py SOP_H02 [EVENT02 ...]      (all = 번역 파일이 있는 전부)

입력: work/movie/orig/<폴더>/<이름>.PSS, work/movie/subs/<이름>.json (자막 구간),
      trans/ko/movie/<이름>.tsv (id <TAB> 일본어 <TAB> 한국어)
출력: work/patched/<폴더>/<이름>.PSS (원본과 같은 크기), work/movie/enc/<이름>.m2v

인코딩: 자막 합성 프레임을 고정 양자화(q 후보 14가지)·닫힌 GOP 18장(I 위치 원본과 같음)·B 2장으로 여러 벌 인코딩한 뒤,
        GOP 마다 원본 패킷 일정(4프레임 넘게 늦지 않음)에 맞는 벌을 골라 이어 붙인다 (gopsplice.py: GOP 단위 비트율 제어).
        (예전 1패스 CBR 은 I 프레임을 굶겨 0.6초마다 화질이 출렁였음 — 2026-09-19 사용자 지적)
"""
import hashlib
import io
import json
import os
import subprocess
import sys
import time
from collections import Counter

import av
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gopsplice  # noqa: E402
import psmux  # noqa: E402
import pss  # noqa: E402
import subrender as R  # noqa: E402

WORK = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ORIG = os.path.join(WORK, "movie", "orig")
SUBS = os.path.join(WORK, "movie", "subs")
TRANS = os.path.join(WORK, "trans", "ko", "movie")
ENC = os.path.join(WORK, "movie", "enc")
PATCHED = os.path.join(WORK, "patched")
FFMPEG = None


def ffmpeg():
    global FFMPEG
    if FFMPEG is None:
        import imageio_ffmpeg
        FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
    return FFMPEG


def folder(name):
    return "MOVIESOP" if name.startswith("SOP") else "MOVIE"


def load_trans(name):
    path = os.path.join(TRANS, name + ".tsv")
    tr = {}
    if not os.path.exists(path):
        return tr
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 3 and parts[2].strip():
            tr[int(parts[0])] = parts[2].strip()
    return tr


def seq_bitrate(es):
    i = es.find(b"\0\0\1\xb3")
    b = es[i + 4:i + 12]
    v = (b[4] << 10) | (b[5] << 2) | (b[6] >> 6)
    return v * 400


def overlays(name):
    """프레임 번호 -> [(fa, oa, x, y, alpha)]"""
    js = json.load(open(os.path.join(SUBS, name + ".json"), encoding="utf-8"))
    tr = load_trans(name)
    per = {}
    for c in js["cards"]:
        text = tr.get(c["id"])
        if not text:
            continue
        fa, oa, top = R.render_line(text)
        w = R.text_width(text)
        if w > R.W - 2 * R.MARGIN:
            raise ValueError("%s #%d: 한 줄 폭 초과 %.0fpx: %s" % (name, c["id"], w, text))
        # 일본어 자막은 늘 화면 가운데, 아랫줄 바닥 y≈399 에 맞춰져 있다 → 한국어 줄은 그 아래 고정 위치
        x, y = R.place(fa, R.W / 2, R.JP_BOTTOM + R.GAP - top + 1)
        for t, a in c["alpha"].items():
            per.setdefault(int(t), []).append((fa, oa, x, y, float(a)))
    return per


QS = (1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0, 3.4, 3.9, 4.5, 5.3, 6.5, 8.5, 12.0)   # 고정 양자화 후보 (고운 것부터)
TMP = os.path.join(WORK, "movie", "tmp")
VER = os.path.join(WORK, "movie", "ver")      # q 별 인코딩 (다시 고를 때 재사용)
JOBS = 3


def source_key(name):
    """인코딩 입력을 정하는 것들(자막 구간·번역·그리기 설정·q 후보)의 지문."""
    h = hashlib.sha256()
    for path in (os.path.join(SUBS, name + ".json"), os.path.join(TRANS, name + ".tsv"),
                 os.path.join(os.path.dirname(os.path.abspath(__file__)), "subrender.py")):
        h.update(open(path, "rb").read())
    h.update(repr(QS).encode())
    return h.hexdigest()


def make_yuv(name, es, path):
    """자막을 합성한 프레임을 raw yuv420p 파일로. -> 프레임 수, 자막 프레임 수"""
    per = overlays(name)
    c = av.open(io.BytesIO(es), format="mpegvideo")
    n = 0
    with open(path, "wb") as f:
        for t, fr in enumerate(c.decode(video=0)):
            yuv = fr.to_ndarray(format="yuv420p")
            if t in per:
                yuv = yuv.copy()
                for fa, oa, x, y, a in per[t]:
                    R.composite(yuv, fa, oa, x, y, a)
            f.write(yuv.tobytes())
            n += 1
    c.close()
    return n, len(per)


def version_paths(name):
    d = os.path.join(VER, name)
    return {q: os.path.join(d, "q%s.m2v" % q) for q in QS}


def encode_versions(yuv, paths):
    """q 후보마다 닫힌 GOP 고정 양자화 인코딩 (동시에 JOBS 개). paths = {q: 출력 경로}"""
    procs = []
    for q in QS:
        path = paths[q]
        os.makedirs(os.path.dirname(path), exist_ok=True)
        cmd = [ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
               "-f", "rawvideo", "-pix_fmt", "yuv420p", "-s", "640x448", "-r", "30", "-i", yuv,
               "-c:v", "mpeg2video", "-q:v", str(q),
               "-g", "1000", "-force_key_frames", "expr:eq(mod(n,18),0)",   # 원본과 같은 자리(18장마다) I
               "-bf", "2", "-sc_threshold", "1000000000", "-flags", "+cgop",
               "-non_linear_quant", "1", "-qmax", "28", "-intra_vlc", "1",
               "-mbd", "rd", "-trellis", "1", "-cmp", "2", "-subcmp", "2",
               "-f", "mpeg2video"]
        procs.append(subprocess.Popen(cmd + [path + ".part"]))
        while sum(1 for pr in procs if pr.poll() is None) >= JOBS:
            time.sleep(0.2)
    for pr in procs:
        if pr.wait() != 0:
            raise RuntimeError("ffmpeg 실패")
    for q in QS:
        os.replace(paths[q] + ".part", paths[q])


def encode(name, log=print):
    t0 = time.time()
    src = os.path.join(ORIG, folder(name), name + ".PSS")
    orig = open(src, "rb").read()
    es, _, _ = pss.demux(src)
    os.makedirs(TMP, exist_ok=True)
    os.makedirs(ENC, exist_ok=True)
    paths = version_paths(name)
    stamp = os.path.join(VER, name, "source.txt")          # 자막이 바뀌면 다시 인코딩
    key = source_key(name)
    have = os.path.exists(stamp) and open(stamp, encoding="utf-8").read() == key
    nsub = len(overlays(name))
    if not (have and all(os.path.exists(pth) for pth in paths.values())):
        yuv = os.path.join(TMP, name + ".yuv")
        make_yuv(name, es, yuv)
        encode_versions(yuv, paths)
        os.remove(yuv)
        open(stamp, "w", encoding="utf-8").write(key)
    versions = {q: gopsplice.Version(open(pth, "rb").read()) for q, pth in paths.items()}
    n = sum(len(x) for x in versions[QS[0]].pic_offs)
    sched = gopsplice.Schedule(orig)
    choice, worst, forced = gopsplice.choose(sched, versions, list(QS), log=log)
    new_es = gopsplice.splice(versions, choice)
    out_es = os.path.join(ENC, name + ".m2v")
    open(out_es, "wb").write(new_es)
    cnt = Counter(choice)
    log("%s: %d 프레임(자막 %d), GOP %d 개 q 분포 %s, 최대 지연 %d, 강제 %d, ES %d → %d (%.0f%%, %.0fs)" % (
        name, n, nsub, len(choice), " ".join("%s:%d" % (q, cnt[q]) for q in QS if cnt[q]),
        worst, forced, len(es), len(new_es), 100.0 * len(new_es) / len(es), time.time() - t0))
    new = psmux.remux(orig, new_es, log=log)
    psmux.verify(orig, new, new_es)
    dst = os.path.join(PATCHED, folder(name), name + ".PSS")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, "wb").write(new)
    # 프레임 수 확인
    c = av.open(io.BytesIO(new_es), format="mpegvideo")
    m = sum(1 for _ in c.decode(video=0))
    c.close()
    if m != n:
        raise RuntimeError("프레임 수 다름 %d != %d" % (m, n))
    log("  -> %s OK (%d bytes)" % (dst, len(new)))
    return dst


def main():
    names = sys.argv[1:]
    if names == ["all"]:
        names = sorted(f[:-4] for f in os.listdir(TRANS) if f.endswith(".tsv"))
    failed = []
    for nm in names:
        try:
            encode(nm)
        except Exception as e:      # noqa: BLE001
            print("!! %s 실패: %r" % (nm, e))
            failed.append(nm)
        sys.stdout.flush()
    print("완료. 실패:", failed or "없음")


if __name__ == "__main__":
    main()
