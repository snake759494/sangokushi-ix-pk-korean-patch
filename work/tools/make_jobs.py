# -*- coding: utf-8 -*-
"""아직 번역되지 않은 단위를 작업(job) 파일로 나눈다.

출력 (work/trans/jobs/)
  <작업>.txt       번역할 원문 + 단위별 제한 + 이 작업에 나오는 고유명사·용어
  <작업>.map.tsv   대표 단위ID -> 같은 원문·같은 제한의 다른 단위ID (쉼표 구분)
  index.tsv        작업 목록
번역 결과는 work/trans/jobs/out/<작업>.tsv (단위ID<TAB>번역, 줄바꿈 ⏎) 에 적고
python check_job.py <작업> 으로 검사, python merge_jobs.py 로 trans/ko/units/ 에 합친다.

사용법: python make_jobs.py [작업당 글자 수(기본 9000)]
"""
import glob
import os
import re
import sys
from collections import OrderedDict

from build_all import load_all_units, load_translations
from make_central import load_label_tsv
from units import TAG, WORK

JOBS = os.path.join(WORK, "trans", "jobs")
KO = os.path.join(WORK, "trans", "ko")

KIND_ORDER = [("desc", "s"), ("help", "h"), ("bar", "b"), ("msg", "b"), ("label", "b"), ("dlg", "d"), ("bio", "r")]
KIND_DESC = {
    "dlg": "대사창 (한 줄 %d칸 이하, 줄 수는 원문과 같게)",
    "help": "도움말 쪽 (한 줄 %d칸 이하 + 줄 끝 문장부호 하나, 13줄 이하, 줄바꿈 위치 자유)",
    "desc": "개요 상자 (한 줄 %d칸 이하 + 줄 끝 문장부호 하나, 13줄 이하, 줄바꿈 위치 자유)",
    "bar": "화면 아래 한 줄 도움말 (%d칸 이하, 1줄)",
    "msg": "한 줄 메시지 (%d칸 이하, 1줄)",
    "label": "라벨 (%d칸 이하)",
    "bio": "무장 열전 (한 줄 %d칸 이하, 4줄 이하, 줄바꿈 위치 자유)",
}


def plain_len(s):
    return len(TAG.sub("x", s).replace("\n", ""))


def build_dict(units, tr):
    """원문 -> 번역 사전. (고유명사 사전, 게임 용어 사전)"""
    d = {}
    t = {}
    by_entry = {}
    for u in units.values():
        if u.src == "M":
            by_entry.setdefault(u.entry, []).append(u)

    def ko_of(idx, k=0):
        lst = sorted(by_entry.get(idx, []), key=lambda x: x.k)
        if k < len(lst) and lst[k].uid in tr:
            return lst[k].jp, tr[lst[k].uid]
        return None, None

    # 무장 (성+이름, 자)
    for line in open(os.path.join(WORK, "trans", "names_person.tsv"), encoding="utf-8"):
        if line.startswith("#"):
            continue
        k, js, jg, ja, ks, kg, ka = line.rstrip("\n").split("\t")
        if 693 <= int(k) <= 701:
            continue           # 盗賊/文官/兵士/男/女/老人/子供/○氏 등 일반 인물
        if jg:
            d[js + jg] = ks + kg
        if ja and len(TAG.sub("x", ja)) >= 2:
            d.setdefault(ja, ka)
    # 지명·도시·아이템·관작·관직·국호
    for lo, hi in ((136, 566), (723, 823), (1398, 1750), (1785, 1801), (5355, 5509), (5606, 5646)):
        for idx in range(lo, hi, 2):
            jp, ko = ko_of(idx)
            if jp and ko and plain_len(jp) >= 2 and jp not in ("なし",):
                d.setdefault(jp, ko)
    # 라벨·용어
    for jp, ko in load_label_tsv().items():
        if plain_len(jp) <= 8 and not re.search(r"[。、！？「」]", jp) and plain_len(jp) >= 2:
            t.setdefault(jp, ko)
    for line in open(os.path.join(KO, "glossary.tsv"), encoding="utf-8"):
        if line.startswith("#") or not line.strip():
            continue
        c = line.rstrip("\n").split("\t")
        if plain_len(c[0]) >= 2:
            t.setdefault(c[0], c[1])
    # 자주 쓰는 호칭·용어 (규칙서 4장과 같음)
    extra = {
        "殿": "주공(군주 호칭) / 〇〇殿 = 〇〇 님·〇〇 공", "陛下": "폐하", "様": "님", "主君": "주군",
        "戦略フェイズ": "전략 페이즈", "進行フェイズ": "진행 페이즈", "一騎討ち": "일기토", "計略": "계략",
        "特技": "특기", "守兵": "수비병", "戦争": "전쟁", "帰還": "귀환", "進軍": "진군", "都督": "도독",
        "軍団長": "군단장", "太守": "태수", "同盟": "동맹", "停戦": "정전", "朝廷": "조정", "天子": "천자",
        "漢室": "한실", "逆賊": "역적", "奸雄": "간웅", "義兄弟": "의형제",
    }
    for k, v in extra.items():
        t.setdefault(k, v)
    for k in list(t):
        if k in d:
            del t[k]
    return d, t


def job_terms(text, d):
    found = []
    for jp in sorted(d, key=lambda s: -len(s)):
        if jp in text:
            found.append(jp)
    found.sort(key=lambda s: text.index(s))
    return [(j, d[j]) for j in found]


def unit_header(u):
    if u.kind in ("help", "desc", "bio"):
        return "[%s 폭%d+문장부호 %s%d줄]" % (u.kind, u.width, "" if u.lines_rule[0] == "==" else "최대", u.lines_rule[1])
    return "[%s 폭%d %d줄]" % (u.kind, u.width, u.lines_rule[1])


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    target = int(sys.argv[1]) if len(sys.argv) > 1 else 9000
    units = load_all_units()
    tr, _ = load_translations()
    d = build_dict(units, tr)
    os.makedirs(os.path.join(JOBS, "out"), exist_ok=True)
    for f in glob.glob(os.path.join(JOBS, "*.txt")) + glob.glob(os.path.join(JOBS, "*.map.tsv")):
        os.remove(f)
    todo = [u for u in units.values() if u.uid not in tr and u.kind in KIND_DESC]
    todo.sort(key=lambda u: (u.src, u.entry, u.k))
    # 같은 원문·같은 제한은 한 번만
    groups = OrderedDict()
    for u in todo:
        key = (u.kind, u.jp, u.width, u.lines_rule, u.hang)
        groups.setdefault(key, []).append(u)
    # 종류별로 작업 나누기 (항목 순서 유지)
    by_prefix = OrderedDict()
    for kind, prefix in KIND_ORDER:
        by_prefix.setdefault(prefix, [])
    for key, us in groups.items():
        prefix = dict(KIND_ORDER)[key[0]]
        by_prefix[prefix].append(us)
    index = []
    for prefix, glist in by_prefix.items():
        jobs, cur, size = [], [], 0
        for us in glist:
            n = plain_len(us[0].jp)
            # 같은 항목은 한 작업 안에
            if cur and size + n > target and us[0].entry != cur[-1][0].entry:
                jobs.append(cur)
                cur, size = [], 0
            cur.append(us)
            size += n
        if cur:
            jobs.append(cur)
        for ji, job in enumerate(jobs, 1):
            name = "%s%02d" % (prefix, ji)
            write_job(name, job, d, units, tr)
            chars = sum(plain_len(us[0].jp) for us in job)
            index.append((name, len(job), chars, job[0][0].uid, job[-1][0].uid))
    with open(os.path.join(JOBS, "index.tsv"), "w", encoding="utf-8", newline="\n") as f:
        f.write("# 작업\t단위수\t글자수\t처음\t끝\n")
        for row in index:
            f.write("\t".join(str(x) for x in row) + "\n")
    print("작업 %d개" % len(index))
    for row in index:
        print("  %s  단위 %4d  %6d자  %s ~ %s" % row)


BY_ENTRY = {}


def write_job(name, job, d, units, tr):
    if not BY_ENTRY:
        for x in units.values():
            BY_ENTRY.setdefault((x.src, x.entry), []).append(x)
    text = "\n".join(us[0].jp for us in job)
    names = job_terms(text, d[0])
    terms = job_terms(text, d[1])
    lines = []
    lines.append("# 작업 %s" % name)
    lines.append("# 먼저 work/trans/번역규칙.md 를 끝까지 읽고 그대로 따른다.")
    lines.append("# 결과 파일: work/trans/jobs/out/%s.tsv  (한 줄에 하나: 단위ID<TAB>번역, 줄바꿈은 ⏎)" % name)
    lines.append("# 검사: python work/tools/check_job.py %s   (오류가 0이 될 때까지 고친다)" % name)
    lines.append("")
    lines.append("## 고유명사 (원문 = 번역, 반드시 이대로 쓴다)")
    for jp, ko in names:
        lines.append("%s = %s" % (jp, ko))
    lines.append("")
    lines.append("## 게임 화면의 용어 표기 (게임 용어로 쓰였으면 이대로, 일반 낱말로 쓰였으면 문맥에 맞게)")
    for jp, ko in terms:
        lines.append("%s = %s" % (jp, ko))
    lines.append("")
    lines.append("## 원문")
    last_entry = None
    for us in job:
        u = us[0]
        if (u.src, u.entry) != last_entry:
            last_entry = (u.src, u.entry)
            lines.append("")
            head = "### %s%s" % (u.src, ("%05d" % u.entry) if u.src == "M" else ("%03d" % u.entry))
            # 앞 항목이 번역된 제목이면 참고로 보여 준다
            prev = [x for x in BY_ENTRY.get((u.src, u.entry - 1), []) if x.uid in tr]
            if prev and prev[0].kind == "label" and u.kind in ("help", "desc"):
                head += "   (제목: %s = %s)" % (prev[0].jp, tr[prev[0].uid])
            lines.append(head)
        extra = "" if len(us) == 1 else "   (같은 원문 %d곳)" % len(us)
        lines.append("@%s %s%s" % (u.uid, unit_header(u), extra))
        lines.append(u.jp)
    with open(os.path.join(JOBS, name + ".txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    with open(os.path.join(JOBS, name + ".map.tsv"), "w", encoding="utf-8", newline="\n") as f:
        for us in job:
            f.write("%s\t%s\n" % (us[0].uid, ",".join(x.uid for x in us[1:])))


if __name__ == "__main__":
    main()
