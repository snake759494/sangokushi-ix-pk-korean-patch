# -*- coding: utf-8 -*-
"""중앙 번역(고유명사·라벨·읽기) -> work/trans/ko/units_central.tsv  (단위ID<TAB>번역)

- 무장: trans/names_person.tsv (성·이름·자) + 읽기(한글 성명)
- 지명·도시·아이템·관작·관직·국호·일반 무장·병사 발탁용 이름 후보: 이 파일의 표
- 지역 구분 라벨(楽浪・東 등): 지명 사전 + 방위
- 그 밖의 라벨·짧은 문장: trans/ko/labels_*.tsv (원문이 같은 label/msg 단위에 적용)
- 읽기(루비) 단위: 바로 앞 항목 번역의 한글 (공백 제거)
"""
import glob
import os
import re

from ko_names import raw_reading, to_hanja, word_reading
from make_names import CITIES, PLACES
from units import TAG, load_units

HERE = os.path.dirname(os.path.abspath(__file__))
TR = os.path.join(HERE, "..", "trans")
OUT = os.path.join(TR, "ko", "units_central.tsv")

ITEMS = {
    "赤兎馬": "적토마", "的盧": "적로", "爪黄飛電": "조황비전", "絶影": "절영", "大宛馬": "대완마", "四輪車": "사륜거",
    "七星宝刀": "칠성보도", "倚天の剣": "의천검", "青{U:F069}の剣": "청강검", "方天画戟": "방천화극",
    "青龍偃月刀": "청룡언월도", "蛇矛": "사모", "鉄脊蛇矛": "철척사모", "雌雄一対の剣": "자웅일대검",
    "古錠刀": "고정도", "三尖刀": "삼첨도", "双鉄戟": "쌍철극", "大斧": "대부", "鉄鞭": "철편",
    "鉄{U:F09A}藜骨朶": "철질려골타", "流星鎚": "유성추", "眉尖刀": "미첨도", "銅鎚": "동추", "鉄鎖": "철쇄",
    "飛刀": "비도", "短戟": "단극", "手戟": "수극", "袖箭": "수전", "養由基の弓": "양유기궁", "李広の弓": "이광궁",
    "孫子の兵法書": "손자병법서", "兵法二十四編": "병법이십사편", "六韜": "육도", "三略": "삼략", "司馬法": "사마법",
    "呉子": "오자", "孫濱兵法": "손빈병법", "魏公子兵法": "위공자병법", "尉繚子": "울료자", "墨子": "묵자",
    "孟徳新書": "맹덕신서", "管子": "관자", "晏子春秋": "안자춘추", "商君書": "상군서", "韓非子": "한비자",
    "周書陰符": "주서음부", "四民月令": "사민월령", "春秋左氏伝": "춘추좌씨전", "史記": "사기", "漢書": "한서",
    "戦国策": "전국책", "列女伝": "열녀전", "呂氏春秋": "여씨춘추", "呉越春秋": "오월춘추", "淮南子": "회남자",
    "論語": "논어", "詩経": "시경", "書経": "서경", "易経": "역경", "礼記": "예기", "老子": "노자", "荘子": "장자",
    "論語集解": "논어집해", "典論": "전론", "博奕論": "박혁론", "時要論": "시요론", "治論": "치론",
    "弁道論": "변도론", "乾象暦注": "건상역주", "孝経伝": "효경전", "仇国論": "구국론", "西蜀地形図": "서촉지형도",
    "平蛮指掌図": "평만지장도", "太平清領道": "태평청령도", "青嚢書": "청낭서", "傷寒雑病論": "상한잡병론",
    "遁甲天書": "둔갑천서", "太平要術の書": "태평요술서", "山海経": "산해경", "玉璽": "옥새", "九錫": "구석",
    "銅雀": "동작", "羽扇": "우선", "和氏の璧": "화씨벽", "長信宮燈": "장신궁등", "博山炉": "박산로",
    "龍の方壷": "용방호", "金象嵌の壷": "금상감호", "牛灯": "우등", "神獣の硯": "신수연", "玉龍紋璧": "옥룡문벽",
    "漆塗りの鼎": "옻칠 솥", "青釉穀倉罐": "청유곡창관", "算盤": "주판", "酒盃": "술잔", "茶": "차",
    "呂氏鏡": "여씨경", "金耳墜": "금이추", "羅綺香嚢": "나기향낭", "琴": "칠현금", "神剣草薙": "초치검",
    "東胡飛弓": "동호비궁", "金馬槊": "금마삭", "大鋸歯刀": "대거치도", "操象鞭": "조상편", "朝鮮人参": "조선인삼",
    "桂花の護符": "계화 호부", "芍薬の護符": "작약 호부", "駿馬の護符": "준마 호부", "跳鯉の護符": "도리 호부",
    "官人の護符": "관인 호부", "尚書の護符": "상서 호부", "文昌の護符": "문창 호부", "鍾馗の護符": "종규 호부",
    "追加アイテム": "추가 아이템",
}
RANKS = {"皇帝": "황제", "王": "왕", "公": "공", "大司馬": "대사마", "大将軍": "대장군", "中郎将": "중랑장",
         "州刺史": "주자사", "州牧": "주목"}
TITLES = {
    "丞相": "승상", "司空": "사공", "太尉": "태위", "司徒": "사도", "大都督": "대도독", "衛将軍": "위장군",
    "驃騎将軍": "표기장군", "車騎将軍": "거기장군", "光禄勲": "광록훈", "大司農": "대사농", "衛尉": "위위",
    "廷尉": "정위", "征東将軍": "정동장군", "征南将軍": "정남장군", "征西将軍": "정서장군", "征北将軍": "정북장군",
    "尚書令": "상서령", "太僕": "태복", "太常": "태상", "光禄大夫": "광록대부", "鎮東将軍": "진동장군",
    "鎮南将軍": "진남장군", "鎮西将軍": "진서장군", "鎮北将軍": "진북장군", "中書令": "중서령",
    "御史中丞": "어사중승", "執金吾": "집금오", "少府": "소부", "安東将軍": "안동장군", "安南将軍": "안남장군",
    "安西将軍": "안서장군", "安北将軍": "안북장군", "秘書令": "비서령", "侍中": "시중", "留府長史": "유부장사",
    "太学博士": "태학박사", "左将軍": "좌장군", "右将軍": "우장군", "前将軍": "전장군", "後将軍": "후장군",
    "謁者僕射": "알자복야", "都尉": "도위", "黄門侍郎": "황문시랑", "太史令": "태사령", "軍師将軍": "군사장군",
    "安国将軍": "안국장군", "破虜将軍": "파로장군", "討逆将軍": "토역장군", "郎中": "낭중", "従事中郎": "종사중랑",
    "長史": "장사", "司馬": "사마", "威東将軍": "위동장군", "威南将軍": "위남장군", "威西将軍": "위서장군",
    "威北将軍": "위북장군", "太楽令": "태악령", "大倉令": "대창령", "武庫令": "무고령", "衛士令": "위사령",
    "牙門将軍": "아문장군", "護軍": "호군", "偏将軍": "편장군", "裨将軍": "비장군", "主簿": "주부",
    "諫議大夫": "간의대부", "侍郎": "시랑", "中郎": "중랑", "忠義校尉": "충의교위", "昭信校尉": "소신교위",
    "儒林校尉": "유림교위", "建議校尉": "건의교위", "奮威校尉": "분위교위", "宣信校尉": "선신교위",
    "破賊校尉": "파적교위", "武衛校尉": "무위교위", "なし": "없음",
}
NATIONS = {"魏": "위", "蜀": "촉", "呉": "오", "成": "성", "倭": "왜", "烏丸": "오환", "羌": "강", "山越": "산월",
           "南蛮": "남만", "黄巾": "황건", "燕": "연", "趙": "조", "斉": "제", "宋": "송", "楚": "초", "涼": "양",
           "越": "월", "秦": "진", "韓": "한", "晋": "진"}
DIRS = {"東": "동", "西": "서", "南": "남", "北": "북", "南東": "남동", "南西": "남서", "北東": "북동",
        "北西": "북서", "中央": "중앙"}


def load_label_tsv():
    tr = {}
    for fn in sorted(glob.glob(os.path.join(TR, "ko", "labels_*.tsv"))):
        for line in open(fn, encoding="utf-8"):
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            jp, ko = line.split("\t", 1)
            tr[jp] = ko.replace("⎵", " ")
    return tr


def main():
    ents, us = load_units("M")
    by_entry = {}
    for u in us:
        by_entry.setdefault(u.entry, []).append(u)
    out = {}

    def put(idx, ko, k=0):
        lst = by_entry.get(idx, [])
        if k < len(lst):
            out[lst[k].uid] = ko

    def jp_of(idx):
        lst = by_entry.get(idx, [])
        return lst[0].jp if lst else ""

    # 무장
    persons = {}
    for line in open(os.path.join(TR, "names_person.tsv"), encoding="utf-8"):
        if line.startswith("#"):
            continue
        k, _, _, _, ks, kg, ka = line.rstrip("\n").split("\t")
        persons[int(k)] = (ks, kg, ka)
    for k, (ks, kg, ka) in persons.items():
        b = 1811 + 4 * k
        put(b, ks)
        if kg:
            put(b + 1, kg)
        if ka:
            put(b + 2, ka)
        put(b + 3, "{ESC:k}" + ks + kg)
    # 일반 무장 (男/女 + 번호)
    for idx in range(4751, 5151):
        j = jp_of(idx)
        if j == "男":
            put(idx, "남")
        elif j == "女":
            put(idx, "여")
    # 지명·도시
    place = {}
    for n, ko in enumerate(PLACES):
        place[jp_of(136 + 2 * n)] = ko
    for n, ko in enumerate(CITIES):
        place[jp_of(723 + 2 * n)] = ko
    for idx in range(136, 566, 2):
        j = jp_of(idx)
        ko = place.get(j, "없음" if j == "なし" else None)
        if ko:
            put(idx, ko)
            put(idx + 1, "{ESC:k}" + ko.replace(" ", ""))
    for idx in range(723, 823, 2):
        ko = place[jp_of(idx)]
        put(idx, ko)
        put(idx + 1, "{ESC:k}" + ko)
    # 지역 구분 라벨
    for idx in range(5646, 6031):
        j = jp_of(idx)
        m = re.fullmatch(r"(.+)・(東|西|南|北|南東|南西|北東|北西|中央)", j)
        if m and m.group(1) in place:
            put(idx, place[m.group(1)] + "・" + DIRS[m.group(2)])
        elif j in place:
            put(idx, place[j])
    # 아이템·관작·관직·국호 (+ 읽기)
    for lo, hi, table in ((1398, 1750, ITEMS), (1785, 1801, RANKS), (5355, 5509, TITLES), (5606, 5646, NATIONS)):
        for idx in range(lo, hi, 2):
            j = jp_of(idx)
            if j in table:
                put(idx, table[j])
                put(idx + 1, "{ESC:k}" + table[j].replace(" ", ""))
            elif j:
                print("미번역 이름:", idx, j)
    # 병사 발탁용 이름 후보 (+ 읽기)
    for idx in range(14544, 14648):
        ko = word_reading(jp_of(idx), surname=True)
        put(idx, ko)
        put(idx + 104, "{ESC:k}" + ko)
    for idx in range(14752, 15227):
        ko = raw_reading(to_hanja(jp_of(idx)))
        put(idx, ko)
        put(idx + 475, "{ESC:k}" + ko)
    # 기간 표시 (197年1月～198年12月 -> 197년1월～198년12월)
    for u in us:
        if u.uid not in out and re.fullmatch(r"\d+年\d+月～\d+年\d+月", u.jp):
            out[u.uid] = u.jp.replace("年", "년").replace("月", "월")
    # 개별 보정
    out["M04608.0"] = ""                 # 子供(아이): 이름 없음
    # 라벨 (원문 일치)
    labels = load_label_tsv()
    for u in us:
        if u.uid in out:
            continue
        if u.kind in ("label", "msg", "name") and u.jp in labels:
            out[u.uid] = labels[u.jp]
    # 읽기(루비): 앞 항목 번역의 한글
    for u in us:
        if u.kind != "ruby" or u.uid in out:
            continue
        j = u.jp
        if j == "るび":
            out[u.uid] = "{ESC:k}읽기"
            continue
        if j == "あいてむ":
            out[u.uid] = "{ESC:k}아이템"
            continue
        if j == "色付きあいてむ":
            out[u.uid] = "색{ESC:k}아이템"
            continue
        prev = by_entry.get(u.entry - 1, [])
        if prev and prev[0].uid in out:
            ko = TAG.sub("", out[prev[0].uid]).replace(" ", "")
            out[u.uid] = "{ESC:k}" + ko
    # 읽기(루비)는 반각 가나 전용 글꼴로 그려져 한글을 표시할 수 없다 (에뮬레이터에서 「소패」 위에 「・ミ・ホ」로 깨짐).
    # 그래서 모든 읽기 항목을 비운다. (무장 목록 정렬은 원래 항목 순서 = 일본어 읽기 순서를 따른다)
    for u in us:
        if u.kind == "ruby":
            out[u.uid] = "{ESC:k}"
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        for uid in sorted(out):
            f.write("%s\t%s\n" % (uid, out[uid].replace("\n", "⏎")))
    left = [u for u in us if u.kind in ("name", "ruby", "label") and u.uid not in out]
    print("중앙 번역 %d개 -> %s" % (len(out), OUT))
    print("남은 name/ruby/label 단위 %d개" % len(left))
    for u in left[:60]:
        print("   ", u.uid, u.kind, repr(u.jp[:30]))


if __name__ == "__main__":
    main()
