# -*- coding: utf-8 -*-
"""M_MSG 바이트열 토큰 분석기 (번역 단위 추출용).

토큰 종류
  ('txt',  bytes)   표시 텍스트 (SJIS 2바이트 글자, 1바이트 가나, ASCII, 줄바꿈 0A, 반각기호)
  ('var',  bytes)   02 xx [yy]  (길이: V3 집합은 3바이트, 나머지 2바이트)
  ('col',  bytes)   02 8C 숫자 영문  (글자 색)
  ('esc',  bytes)   1B xx       (가나 모드)
  ('sep',  bytes)   05
  ('cmd',  bytes)   01 로 시작하는 스크립트 명령 (인자 포함)
  ('cond', bytes)   04 로 시작하는 조건/식 (연산자·피연산자 포함)
  ('ctl',  bytes)   그 밖의 제어 바이트
"""
V3 = {0x01, 0x02, 0x03, 0x04, 0x05, 0x15, 0x1F, 0x20, 0x33, 0x34, 0x3D, 0x3E, 0x47, 0x48, 0x49, 0x4A}
OPS = b"=}{<>!&|"


def is_lead(b):
    return 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC


def var_len(data, i):
    """data[i] == 0x02 인 코드의 길이."""
    if i + 1 >= len(data):
        return 1
    xx = data[i + 1]
    if xx == 0x8C:
        j = i + 2
        while j < len(data) and 0x30 <= data[j] <= 0x39:
            j += 1
        if j < len(data) and (0x41 <= data[j] <= 0x5A or 0x61 <= data[j] <= 0x7A):
            j += 1
        return j - i
    if xx in V3:
        # 인자 바이트가 다음 코드의 시작(02/04/05)이면 인자 없는 2바이트 형태 (스크립트 식 안)
        if i + 2 >= len(data) or data[i + 2] in (0x02, 0x04, 0x05):
            return 2
        return 3
    return 2


def operand_len(data, i):
    """조건식의 피연산자 길이: [%]숫자들 | 변수 | 문자 1개."""
    j = i
    if j < len(data) and data[j] == 0x02:
        return var_len(data, j)
    if j < len(data) and data[j] == 0x25:        # %
        j += 1
    k = j
    while k < len(data) and 0x30 <= data[k] <= 0x39:
        k += 1
    return k - i


def lex(data):
    toks = []
    i, n = 0, len(data)
    txt_start = None

    def flush(end):
        nonlocal txt_start
        if txt_start is not None and end > txt_start:
            toks.append(("txt", data[txt_start:end]))
        txt_start = None

    while i < n:
        b = data[i]
        if b == 0x02:
            flush(i)
            L = var_len(data, i)
            toks.append(("col" if i + 1 < n and data[i + 1] == 0x8C else "var", data[i:i + L]))
            i += L
        elif b == 0x1B:
            flush(i)
            toks.append(("esc", data[i:i + 2]))
            i += 2
        elif b == 0x05:
            flush(i)
            toks.append(("sep", data[i:i + 1]))
            i += 1
        elif b == 0x01:
            flush(i)
            c = data[i + 1] if i + 1 < n else 0
            if c == 0x53:                       # S : 02 CA 25 <숫자>
                j = i + 2
                if j < n and data[j] == 0x02:
                    j += var_len(data, j)
                j += operand_len(data, j)
                toks.append(("cmd", data[i:j]))
                i = j
            elif c == 0x4A:                     # J : 인자 2바이트
                toks.append(("cmd", data[i:i + 4]))
                i += 4
            else:                               # 기타: 명령문자 + (식)
                toks.append(("cmd", data[i:i + 2]))
                i += 2
        elif b == 0x04:
            flush(i)
            j = i + 1
            # 04 <피연산자> [04 <연산자> <피연산자>]  또는  04 <연산자> <피연산자>
            if j < n and data[j] == 0x02:
                j += var_len(data, j)
                if j < n and data[j] == 0x04 and j + 1 < n and data[j + 1] in OPS:
                    j += 2
                    j += operand_len(data, j)
            elif j < n and data[j] in OPS:
                j += 1
                j += operand_len(data, j)
            else:
                j += 1                          # 04 xx (J 인자 등 기타)
            toks.append(("cond", data[i:j]))
            i = j
        elif b == 0x06 and i + 1 < n and data[i + 1] == 0x26:
            # 06 '&' <변수> [04 <연산자> <피연산자>] : 스크립트 AND 조건
            flush(i)
            j = i + 2
            if j < n and data[j] == 0x02:
                j += var_len(data, j)
                if j + 1 < n and data[j] == 0x04 and data[j + 1] in OPS:
                    j += 2
                    j += operand_len(data, j)
            toks.append(("cond", data[i:j]))
            i = j
        elif b in (0x0A,) or b >= 0x20:
            if txt_start is None:
                txt_start = i
            if is_lead(b) and i + 1 < n:
                i += 2
            else:
                i += 1
        else:
            flush(i)
            toks.append(("ctl", data[i:i + 1]))
            i += 1
    flush(n)
    return toks
