"""원본 ISO 의 해시를 확인하고 xdelta 를 적용한 뒤 결과 해시까지 검사한다.

사용:
  python tools/apply_release.py --xdelta <xdelta3.exe> --source <원본 ISO> --patch <xdelta> --output <새 ISO>

기대 해시는 저장소 루트의 release_manifest.json 에서 읽는다 (전체판·동영상 제외판 모두).
기존 출력 파일은 덮어쓰지 않는다. 원본·패치·결과 중 하나라도 해시가 다르면 실패로 끝낸다.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys

MANIFEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "release_manifest.json")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 24), b""):
            h.update(block)
    return h.hexdigest()


def check(label, path, size, digest):
    n = os.path.getsize(path)
    if size is not None and n != size:
        print(f"{label}: 크기 {n:,} != {size:,}")
        return False
    d = sha256(path)
    if d != digest:
        print(f"{label}: SHA-256 불일치\n  실제 {d}\n  기대 {digest}")
        return False
    print(f"{label}: OK ({n:,} B)")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xdelta", required=True, help="xdelta3 실행 파일")
    ap.add_argument("--source", required=True, help="수정되지 않은 일본판 ISO")
    ap.add_argument("--patch", required=True, help="릴리즈 xdelta (전체판 또는 동영상 제외판)")
    ap.add_argument("--output", required=True, help="만들 ISO (기존 파일이면 중단)")
    a = ap.parse_args()
    m = json.load(open(MANIFEST, encoding="utf-8"))
    if os.path.exists(a.output):
        print(f"출력 파일이 이미 있습니다: {a.output}")
        sys.exit(1)
    ph = sha256(a.patch)
    asset = next((x for x in m["assets"] if x["patch"]["sha256"] == ph), None)
    if asset is None:
        print(f"release_manifest.json 에 없는 패치입니다 (SHA-256 {ph})")
        sys.exit(1)
    print(f"패치: {asset['file']} ({'동영상 자막 포함' if asset['movies'] else '동영상 제외'}) OK")
    src = m["source_iso"]
    if not check("원본", a.source, src["size"], src["sha256"]):
        sys.exit(1)
    r = subprocess.run([a.xdelta, "-d", "-s", a.source, a.patch, a.output])
    if r.returncode != 0:
        print(f"xdelta 실패 (exit {r.returncode})")
        sys.exit(1)
    out = asset["output_iso"]
    if not check("결과", a.output, out["size"], out["sha256"]):
        sys.exit(1)
    print("완료:", a.output)


if __name__ == "__main__":
    main()
