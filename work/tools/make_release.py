# -*- coding: utf-8 -*-
"""배포 파일 만들기: 완성 ISO 두 가지(전체 / 동영상 제외)를 빌드하고 원본과의 xdelta 를 만든 뒤,
원본 + xdelta → 결과가 완성 ISO 와 같은지 되풀어 확인하고 release_manifest.json 을 쓴다.

python work/tools/make_release.py --xdelta <xdelta3.exe> --version v1.0 --outdir <배포 폴더>

xdelta 옵션: -e -9 -S none -A (2차 압축·파일 경로 헤더 없음 — 다른 xdelta 도구와의 호환용)
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.normpath(os.path.join(HERE, ".."))
ROOT = os.path.dirname(WORK)
SRC_ISO = os.path.join(ROOT, "Sangokushi IX with Power-Up Kit (Japan).iso")
BASE = "Sangokushi_IX_PK_KO"


def hashes(path):
    hs = [hashlib.md5(), hashlib.sha1(), hashlib.sha256()]
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 24), b""):
            for h in hs:
                h.update(block)
    return {"size": os.path.getsize(path), "md5": hs[0].hexdigest(), "sha1": hs[1].hexdigest(),
            "sha256": hs[2].hexdigest()}


def run(cmd):
    print("  $", " ".join('"%s"' % c if " " in c else c for c in cmd))
    sys.stdout.flush()
    r = subprocess.run(cmd)
    if r.returncode != 0:
        sys.exit("실패 (exit %d)" % r.returncode)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xdelta", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--variants", default="full,nomovie", help="만들 판: full, nomovie (쉼표로)")
    a = ap.parse_args()
    want = set(a.variants.split(","))
    os.makedirs(a.outdir, exist_ok=True)
    src = hashes(SRC_ISO)
    print("원본", src)
    path = os.path.join(a.outdir, "release_manifest.json")
    old = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {"assets": []}
    manifest = {"version": a.version, "date": time.strftime("%Y-%m-%d"),
                "game": "Sangokushi IX with Power-Up Kit (Japan) / SLPM-65673 / PS2",
                "xdelta_options": "xdelta3 3.0.11, -e -9 -S none -A (no secondary compression, no application header)",
                "source_iso": src, "assets": []}
    manifest["assets"] = [x for x in old.get("assets", []) if ("full" if x["movies"] else "nomovie") not in want]
    for tag, extra in (("", []), ("_nomovie", ["--no-movie"])):
        if ("nomovie" if tag else "full") not in want:
            continue
        iso = os.path.join(a.outdir, "%s_%s%s.iso" % (BASE, a.version, tag))
        patch = os.path.join(a.outdir, "%s_%s%s.xdelta" % (BASE, a.version, tag))
        if os.path.exists(iso):
            os.remove(iso)
        run([sys.executable, os.path.join(HERE, "build_iso.py")] + extra + [iso])
        out = hashes(iso)
        if os.path.exists(patch):
            os.remove(patch)
        run([a.xdelta, "-e", "-9", "-S", "none", "-A", "-s", SRC_ISO, iso, patch])
        chk = iso + ".check"
        if os.path.exists(chk):
            os.remove(chk)
        run([a.xdelta, "-d", "-s", SRC_ISO, patch, chk])
        back = hashes(chk)
        os.remove(chk)
        if back != out:
            sys.exit("되풀기 결과가 완성 ISO 와 다름: %s" % patch)
        ph = hashes(patch)
        print("  %s: 패치 %d 바이트, 결과 SHA-256 %s (되풀기 일치)" % (os.path.basename(patch), ph["size"], out["sha256"]))
        manifest["assets"].append({"file": os.path.basename(patch), "movies": tag == "", "patch": ph, "output_iso": out})
    elf = os.path.join(WORK, "patched", "SLPM_656.73")
    manifest["patched_elf"] = hashes(elf)
    manifest["original_elf_sha256"] = hashes(os.path.join(WORK, "iso", "SLPM_656.73"))["sha256"]
    manifest["assets"].sort(key=lambda x: not x["movies"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print("완료:", path)


if __name__ == "__main__":
    main()
