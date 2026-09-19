# -*- coding: utf-8 -*-
"""원본 ISO 를 복사한 뒤 work/patched/ 의 수정 파일을 써 넣어 테스트 ISO 를 만든다.

- 파일 테이블 등록 파일(F_FONT.S9, M_MSG.S9 등): 게임은 SLPM_656.73 의 파일 테이블(LBA·섹터 수)로
  읽으므로, 패치된 SLPM_656.73 이 있으면 그 테이블 위치에 쓴다. 테이블을 바꿔 재배치한 파일
  (예: 커진 M_MSG.S9)은 원래 비어 있던 영역에만 둘 수 있다.
- 그 밖의 ISO 파일(SLPM_656.73, MOVIE/*.PSS, MOVIESOP/*.PSS 등): ISO9660 디렉터리 레코드 위치에 기록
  (크기가 같아야 함. 동영상은 파일 테이블에도 있지만 원래 자리·크기 그대로라 테이블은 손대지 않는다)

사용법: python build_iso.py [--check] [--no-movie] [출력 ISO 경로]
       (기본: 원본 ISO 와 같은 폴더, --check = 검사만, --no-movie = 동영상 자막 파일을 빼고 만듦)
"""
import os
import shutil
import sys

import pycdlib

from extract_san9pk import SECTOR, read_table

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
SRC_ISO = os.path.join(ROOT, "Sangokushi IX with Power-Up Kit (Japan).iso")
ELF = os.path.join(ROOT, "work", "iso", "SLPM_656.73")
PATCHED = os.path.join(ROOT, "work", "patched")
DEFAULT_OUT = os.path.join(os.path.dirname(SRC_ISO), "San9PK_KR_test.iso")
FREE_AREAS = [(1121523, 1125000)]     # 원본 ISO 에서 모두 0 인 빈 섹터 구간 [시작, 끝)


def norm(name):
    return name.lstrip("\\/").split(";")[0].replace("\\", "/").upper()


def iso_extents():
    ext = {}
    iso = pycdlib.PyCdlib()
    iso.open(SRC_ISO)
    for dirname, _, files in iso.walk(iso_path="/"):
        for f in files:
            rec = iso.get_record(iso_path=dirname.rstrip("/") + "/" + f)
            ext[norm(dirname.rstrip("/") + "/" + f)] = (rec.extent_location(), rec.data_length)
    iso.close()
    return ext


def locations(ext):
    """정규화된 경로 -> (LBA, 할당 바이트, 크기 고정 여부)"""
    loc = {k: (lba, size, True) for k, (lba, size) in ext.items()}
    patched_elf = os.path.join(PATCHED, "SLPM_656.73")
    elf = open(patched_elf if os.path.exists(patched_elf) else ELF, "rb").read()
    for name, lba, _, secs in read_table(elf):
        key = norm(name)
        if key in ext and ext[key][0] == lba:
            continue        # 독립 ISO 파일(동영상 등)이 원래 자리 그대로 → ISO 크기와 같아야 함
        loc[key] = (lba, secs * SECTOR, False)   # 게임은 테이블 LBA/섹터 수로 읽음
    return loc


def check_placement(key, lba, nsec, ext):
    """재배치 검사: SAN9PK.BIN 안이거나(원래 자리) 빈 영역 안이어야 한다."""
    s, e = lba, lba + nsec
    pk_lba, pk_size = ext["SAN9PK.BIN"]
    pk_end = pk_lba + (pk_size + SECTOR - 1) // SECTOR
    if pk_lba <= s and e <= pk_end:
        return
    if any(a <= s and e <= b for a, b in FREE_AREAS):
        for k, (l2, sz) in ext.items():
            if s < l2 + (sz + SECTOR - 1) // SECTOR and l2 < e:
                sys.exit("%s: ISO 파일 %s 와 겹침" % (key, k))
        return
    sys.exit("%s: 허용되지 않은 위치 LBA %d~%d" % (key, s, e - 1))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    check_only = "--check" in sys.argv
    no_movie = "--no-movie" in sys.argv       # 동영상 자막 없이 (가벼운 패치용)
    out = os.path.abspath(args[0]) if args else DEFAULT_OUT
    if os.path.normcase(out) == os.path.normcase(os.path.abspath(SRC_ISO)):
        sys.exit("출력 경로가 원본 ISO 와 같음 - 중단")
    ext = iso_extents()
    loc = locations(ext)

    patches = []
    for dirpath, _, files in os.walk(PATCHED):
        for f in files:
            path = os.path.join(dirpath, f)
            key = norm(os.path.relpath(path, PATCHED))
            if no_movie and key.split("/")[0] in ("MOVIE", "MOVIESOP"):
                continue
            if key not in loc:
                sys.exit("위치를 모르는 파일: %s" % key)
            lba, alloc, exact = loc[key]
            data = open(path, "rb").read()
            if exact and len(data) != alloc:
                sys.exit("%s: 크기가 원본(%d)과 다름(%d)" % (key, alloc, len(data)))
            if len(data) > alloc:
                sys.exit("%s: 할당 섹터 초과 (%d > %d)" % (key, len(data), alloc))
            if not exact:
                check_placement(key, lba, alloc // SECTOR, ext)
                data += b"\0" * (alloc - len(data))
            patches.append((key, lba, data))
    if not patches:
        sys.exit("work/patched 에 파일이 없음")
    spans = sorted((lba, lba + len(d) // SECTOR, k) for k, lba, d in patches)
    for (a1, e1, k1), (a2, e2, k2) in zip(spans, spans[1:]):
        if a2 < e1:
            sys.exit("패치 파일끼리 겹침: %s / %s" % (k1, k2))

    if check_only:
        for key, lba, data in sorted(patches, key=lambda x: x[1]):
            print("  %-20s LBA %8d  %9d bytes" % (key, lba, len(data)))
        print("검사만 함: 패치 %d 개 문제 없음" % len(patches))
        return 0
    os.makedirs(os.path.dirname(out), exist_ok=True)
    print("복사 중:", out)
    shutil.copyfile(SRC_ISO, out)

    with open(out, "r+b") as iso:
        for key, lba, data in patches:
            iso.seek(lba * SECTOR)
            iso.write(data)
        iso.flush()
        for key, lba, data in patches:
            iso.seek(lba * SECTOR)
            if iso.read(len(data)) != data:
                sys.exit("검증 실패: %s" % key)
            print("  %-20s LBA %8d  %9d bytes  OK" % (key, lba, len(data)))

    print("완료: %s (%d bytes)" % (out, os.path.getsize(out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
