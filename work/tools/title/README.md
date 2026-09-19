# 타이틀 로고 캡션 (G_TITLE.S9)

`python build_title_caption.py --write` → `work/patched/G_TITLE.S9` 를 다시 만든다 (약 2분, `--write` 없으면 이 폴더에 G_TITLE_new.S9 만 씀).

- G_TITLE.S9 = LZSS 10블록. 블록 오프셋은 ELF 0x4611D0 에 고정 → 블록마다 원래 자리에 넣어야 한다
- 블록 헤더 16바이트: 종류(창 크기 0=1KB 1=2KB 2=4KB 3=8KB), 풀린 크기, 코드 위치, 리터럴 위치.
  64비트 플래그(최상위 비트부터, 1=리터럴 1바이트, 0=16비트 코드 pos=v&0x7FF len=(v>>11)+3)
- 게임 해제 함수(ELF 0x23CAA0)는 크기 검사가 없고 pos==0 코드에서만 멈춘다 → **끝 코드 필수**.
  없으면 버퍼를 넘쳐 RAM 의 한글 폰트를 덮어써 메뉴 글자가 깨진다
- 블록 0 = 1024x512 8비트 타이틀 화면(+PRESS START 5프레임), 1~8 = 빛 번짐 애니메이션(불투명),
  9 = 팔레트 3벌. 캡션은 바탕·애니메이션 8프레임·PRESS START 5프레임 모두에 그렸다
- 캡션: 서울한강체B 22px, 흰색(팔레트 255번을 순백으로), 검은 외곽선 2px, 가운데 x=328, 상자 (274,316)~(381,340)
- 메인 메뉴의 작은 로고는 G_START1.S9(비압축 아틀라스, ELF 0x4385B0 스프라이트 0xDB6/0xDB7)로 별개이며 캡션 넣을 빈칸이 없어 손대지 않음

원본: `work/san9pk/G_TITLE.S9`. 도구: gamedec.py(게임 해제 함수 모형), s9enc.py(압축기), caption.py/compose.py/apply_all.py(그리기)
