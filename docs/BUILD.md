# 재빌드 절차

저장소의 소스와 번역 데이터만으로 배포 ISO 를 다시 만드는 순서입니다. 게임 원본과 글꼴은 사용자가 준비해야 하며, 명령은 저장소 루트에서 실행합니다(스크립트가 `work/...` 상대 경로를 씁니다).

## 준비물

| 항목 | 비고 |
| --- | --- |
| Python 3.11 이상 | `pip install -r requirements.txt` (numpy, scipy, Pillow, opencv-python, pycdlib, av, imageio-ffmpeg). 3.13 으로 만들었다 |
| 원본 ISO | README 의 해시와 일치하는 파일을 저장소 루트에 `Sangokushi IX with Power-Up Kit (Japan).iso` 이름으로 둔다. 원본은 읽기만 한다 |
| 서울한강체 `SeoulHangangB.ttf`, `SeoulHangangEB.ttf` | 저장소 루트에. 게임 글꼴(B)·동영상 자막(B)·타이틀 캡션(B)·그림 글자(EB). 서울특별시 배포([글꼴 출처](FONT_CREDITS.md)) |
| ffmpeg | `imageio-ffmpeg` 가 받아 두는 것을 쓴다 (동영상 단계만) |
| xdelta3 | 배포 xdelta 만들기·적용. 3.0.11 로 만들었다 |

## 1. 원본 파일 추출

```powershell
python work/tools/extract_originals.py
```

원본 ISO 의 SHA-256 을 확인한 뒤 `work/iso/SLPM_656.73`, `work/iso/SAN9PK.BIN`, `work/san9pk/*`(SAN9PK 안 파일), `work/gr_tri/G_PH*.S9`, `work/movie/orig/*/*.PSS` 를 만듭니다. 모두 `.gitignore` 대상입니다.

## 2. 한글 글꼴

```powershell
python work/tools/font_build_ko.py
```

`work/san9pk/F_FONT.S9` 의 한자 슬롯(SJIS 0x889F~0x94FC)에 KS X 1001 한글 2,350자를 서울한강체 B 22px 로 그려 `work/patched/F_FONT.S9` 를 만들고, 대응표 `work/font_ko/hangul.tbl` 을 씁니다(저장소의 것과 같아야 함).

## 3. 텍스트와 실행파일

```powershell
python work/tools/build_all.py
```

- 번역 입력: `work/trans/ko/units_central.tsv`, `units_old.tsv`, `units/*.tsv`(M_MSG·M_RTDN 번역 단위), `elf/*.tsv`(실행파일 문자열), `glossary.tsv`, `*.txt`.
- 단위마다 폭·줄 수·태그·변수 뒤 조사·문자 집합을 검사하고 오류가 하나라도 있으면 멈춥니다. 결과 요약은 `work/trans/build_report.txt`(배포판: 21,727 / 21,727 단위, 오류 0).
- 결과: `work/patched/M_MSG.S9`, `M_RTDN.S9`(빈 영역으로 재배치), `SLPM_656.73`(문자열 교체 + 파일 테이블·크기 상수 수정).

## 4. 그림 글자

```powershell
python work/tools/title/build_title_caption.py --write
python work/tools/gfx_banner.py
python work/tools/gfx_radar.py
```

각각 타이틀 캡션(`G_TITLE.S9`), 페이즈 배너(`G_MAPGRP.S9`)와 트라이얼 스테이지 제목 34장(`GR_TRI1/`, `GR_TRI2/`), 능력 그래프(`G_SYSTEM.S9`)를 `work/patched/` 에 만듭니다. 압축 블록은 모두 게임 해제 함수 모형으로 되풀어 확인합니다. 비교용 그림은 `work/gfx/preview/` 에 남습니다.

## 5. 동영상 자막 (오래 걸림)

```powershell
python work/tools/movenc.py all
```

34편마다 자막 합성 → 고정 양자화 14벌 인코딩 → GOP 선택 → 원본 PSS 틀에 다시 묶기를 합니다. 4코어 PC 에서 편당 2~3분, 전체 약 1시간 30분. q 별 인코딩은 `work/movie/ver/` 에 남아 선택만 다시 할 때는 인코딩을 건너뜁니다. 로그 예시는 `validation/movie_encode_log.txt`.

자막 구간(`work/movie/subs/*.json`)을 새로 재려면 `python work/tools/subdetect.py` 를 먼저 돌립니다(받아쓰기용 잘라낸 그림은 `work/movie/subs/crops/`).

## 6. ISO

```powershell
python work/tools/build_iso.py --check
python work/tools/build_iso.py "Sangokushi IX with Power-Up Kit (Korean v1.0).iso"
python work/tools/build_iso.py --no-movie "Sangokushi IX with Power-Up Kit (Korean v1.0, no movie).iso"
```

원본 ISO 를 복사한 뒤 `work/patched/` 의 파일을 제자리(파일 테이블 또는 ISO9660 위치)에 씁니다. 크기가 같아야 하는 파일, 빈 영역 밖으로 나가는 재배치, 파일끼리 겹침을 검사합니다.

## 7. 배포 파일

```powershell
python work/tools/make_release.py --xdelta .\xdelta3.exe --version v1.0 --outdir release
```

두 ISO 를 빌드하고 `xdelta3 -e -9 -S none -A` 로 패치를 만든 뒤, 원본에 되풀어 결과가 완성 ISO 와 같은지 확인하고 `release/release_manifest.json` 에 크기·해시를 적습니다.

## 번역을 고칠 때

번역 규칙은 `work/trans/번역규칙.md` 입니다(폭 계산, 변수 뒤 조사, 말투, 고유명사, 동영상 자막 규칙). 대역표 `translation/*.tsv` 는 `python work/tools/export_tables.py translation` 로 다시 만듭니다. 동영상 자막은 `work/trans/ko/movie/src/*.txt` 를 고친 뒤 `python work/tools/movtrans.py <파일>` 로 한 줄 폭을 검사해 `work/trans/ko/movie/*.tsv` 에 반영합니다.
