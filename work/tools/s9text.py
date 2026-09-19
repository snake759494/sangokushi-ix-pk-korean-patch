# -*- coding: utf-8 -*-
"""삼국지9 PK 텍스트 코덱 (M_MSG.S9 / M_RTDN.S9 본문).

decode(bytes) -> 태그 문자열,  encode(태그 문자열) == 원래 bytes  (무손실 왕복)

바이트 규칙과 태그
  81-9F,E0-FC xx  Shift-JIS 2바이트. 한자/전각기호는 문자 그대로.
                  2바이트 가나 -> {S:xxxx}, 사용자정의(F040~ 외자·버튼아이콘) -> {U:xxxx},
                  SJIS 로 해석 불가 -> {X:xxxx}
  A6-AF,B1-DD     1바이트 가나 (+DE 탁점, DF 반탁점 결합). ESC H/k 모드면 히라가나, ESC K 모드면
                  가타카나 문자로 표기. 결합 불가능한 단독 DE/DF -> {h:DE}/{h:DF}
  A1-A5,B0        반각 기호 ｡｢｣､･ｰ (전각 SJIS 기호와 구분하려고 반각 유니코드로 표기)
  1B xx           {ESC:H} {ESC:K} {ESC:k} (가나 모드), 그 밖의 {E:xx}
  02 8C 숫자 영문  {C:10b} 형태 (글자 색)
  02 xx yy        {V:xxyy} (변수·스크립트 참조. 이름 삽입 등)
  05              {05} (항목/분기 구분)
  0A              줄바꿈
  그 밖 제어바이트 {B:xx},  ASCII 는 그대로 ('{','}' 는 {A:7B}/{A:7D})

번역문(한글)은 hangul.tbl 의 SJIS 슬롯(889F~94FC)으로 인코딩된다.
"""
import re
import unicodedata

from s9lex import var_len

# ---------------------------------------------------------------- 가나 표
_KANA_H = {}   # (bytes) -> 히라가나 문자열
_KANA_K = {}   # (bytes) -> 가타카나 문자열
for b in list(range(0xA6, 0xB0)) + list(range(0xB1, 0xDE)):
    k = unicodedata.normalize("NFKC", bytes([b]).decode("cp932"))
    _KANA_K[bytes([b])] = k
    for mark, comb in ((0xDE, "゙"), (0xDF, "゚")):
        c = unicodedata.normalize("NFC", k + comb)
        if len(c) == 1:
            _KANA_K[bytes([b, mark])] = c


def _hira(s):
    return "".join(chr(ord(c) - 0x60) if 0x30A1 <= ord(c) <= 0x30F6 else c for c in s)


for _b, _k in _KANA_K.items():
    _KANA_H[_b] = _hira(_k)
_REV = {"H": {v: k for k, v in _KANA_H.items()}, "K": {v: k for k, v in _KANA_K.items()}}
_REV["k"] = _REV["H"]
assert len(_REV["H"]) == len(_KANA_H) and len(_REV["K"]) == len(_KANA_K)

_HALF_PUNCT = {0xA1: "｡", 0xA2: "｢", 0xA3: "｣", 0xA4: "､", 0xA5: "･", 0xB0: "ｰ"}
_HALF_PUNCT_REV = {v: k for k, v in _HALF_PUNCT.items()}


def _is_lead(b):
    return 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC


def decode(data, ko_rev=None, mode="H", want_mode=False):
    """ko_rev: {SJIS 코드(int): 한글} 을 주면 한글 슬롯을 한글로 해석한다 (패치 결과 확인용).
    mode: 시작 가나 모드. want_mode=True 면 (문자열, 끝 모드) 를 돌려준다."""
    out = []
    i, n = 0, len(data)
    while i < n:
        b = data[i]
        if b == 0x1B and i + 1 < n:
            c = data[i + 1]
            if c in (0x48, 0x4B, 0x6B):
                mode = chr(c)
                out.append("{ESC:%s}" % mode)
            else:
                out.append("{E:%02X}" % c)
            i += 2
        elif b == 0x02:
            m = re.match(rb"\x02\x8C([0-9]*[A-Za-z])", data[i:i + 12])
            if m:
                out.append("{C:%s}" % m.group(1).decode("ascii"))
                i += len(m.group(0))
            else:
                L = var_len(data, i)
                out.append("{V:%s}" % data[i + 1:i + L].hex().upper())
                i += L
        elif b == 0x05:
            out.append("{05}")
            i += 1
        elif b == 0x0A:
            out.append("\n")
            i += 1
        elif b in _HALF_PUNCT:
            out.append(_HALF_PUNCT[b])
            i += 1
        elif 0xA6 <= b <= 0xDD:
            tbl = _KANA_K if mode == "K" else _KANA_H
            two = data[i:i + 2]
            if len(two) == 2 and two in tbl:
                out.append(tbl[two])
                i += 2
            else:
                out.append(tbl[data[i:i + 1]])
                i += 1
        elif b in (0xDE, 0xDF):
            out.append("{h:%02X}" % b)
            i += 1
        elif _is_lead(b) and i + 1 < n:
            pair = data[i:i + 2]
            code = int.from_bytes(pair, "big")
            if ko_rev and code in ko_rev:
                out.append(ko_rev[code])
                i += 2
                continue
            try:
                ch = pair.decode("cp932")
                if len(ch) != 1:
                    raise UnicodeDecodeError("cp932", pair, 0, 2, "len")
            except UnicodeDecodeError:
                ch = None
            if ch is None:
                out.append("{X:%04X}" % code)
            elif 0xE000 <= ord(ch) <= 0xF8FF:
                out.append("{U:%04X}" % code)
            elif "ぁ" <= ch <= "ヺ" or ch.encode("cp932") != pair:
                out.append("{S:%04X}" % code)
            else:
                out.append(ch)
            i += 2
        elif 0x20 <= b <= 0x7E:
            out.append("{A:%02X}" % b if b in (0x7B, 0x7D) else chr(b))
            i += 1
        else:
            out.append("{B:%02X}" % b)
            i += 1
    if want_mode:
        return "".join(out), mode
    return "".join(out)


TAG = re.compile(r"\{(ESC|E|C|V|05|S|U|X|h|A|B)(?::([^}]*))?\}")


def load_hangul(tbl_path):
    ko = {}
    with open(tbl_path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line:
                code, ch = line.split("=", 1)
                ko[ch] = bytes.fromhex(code)
    return ko


def encode(text, hangul=None):
    """태그 문자열 -> 바이트. hangul: {한글: SJIS bytes}"""
    hangul = hangul or {}
    out = bytearray()
    mode = "H"
    pos = 0
    for m in list(TAG.finditer(text)) + [None]:
        seg = text[pos:m.start()] if m else text[pos:]
        mode = _encode_plain(seg, mode, hangul, out)
        if m is None:
            break
        name, arg = m.group(1), m.group(2)
        if name == "ESC":
            mode = arg
            out += b"\x1b" + arg.encode("ascii")
        elif name == "E":
            out += b"\x1b" + bytes.fromhex(arg)
        elif name == "C":
            out += b"\x02\x8c" + arg.encode("ascii")
        elif name == "V":
            out += b"\x02" + bytes.fromhex(arg)
        elif name == "05":
            out += b"\x05"
        elif name in ("S", "U", "X", "h", "A", "B"):
            out += bytes.fromhex(arg)
        pos = m.end()
    return bytes(out)


def _encode_plain(s, mode, hangul, out):
    for ch in s:
        if ch == "\n":
            out += b"\x0a"
        elif ch in hangul:
            out += hangul[ch]
        elif ord(ch) < 0x80:
            out += ch.encode("ascii")
        elif ch in _HALF_PUNCT_REV:
            out.append(_HALF_PUNCT_REV[ch])
        elif "ぁ" <= ch <= "ヺ" and ch != "・":
            rev = _REV[mode]
            if ch not in rev:
                raise ValueError("모드 %s 에서 인코딩 불가한 가나: %r" % (mode, ch))
            out += rev[ch]
        else:
            b = ch.encode("cp932")
            if len(b) != 2:
                raise ValueError("인코딩 불가 문자: %r" % ch)
            out += b
    return mode


def mode_at_end(text, start_mode="H"):
    """태그 문자열 끝에서의 가나 모드."""
    mode = start_mode
    for m in re.finditer(r"\{ESC:([HKk])\}", text):
        mode = m.group(1)
    return mode


def display_units(line):
    """줄 폭 (반각 단위). 전각·한글 = 2, ASCII·반각 = 1, 태그 = 0.
    {V:..} 변수(이름 등)는 폭을 알 수 없으므로 별도 인자로 계산한다."""
    w = 0
    pos = 0
    for m in list(TAG.finditer(line)) + [None]:
        seg = line[pos:m.start()] if m else line[pos:]
        for ch in seg:
            if ord(ch) < 0x80 or ch in _HALF_PUNCT_REV:
                w += 1
            else:
                w += 2
        if m is None:
            break
        if m.group(1) in ("S", "U", "X"):
            w += 2
        elif m.group(1) == "A":
            w += 1
        pos = m.end()
    return w
