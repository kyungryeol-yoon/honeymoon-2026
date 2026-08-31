# -*- coding: utf-8 -*-
"""구글 시트("HoneyMoon") 일정칸을 읽어 공통 일정과 선택지로 나눕니다.

시트를 다시 읽을 때마다 처음부터 파싱합니다 — 이전 결과와의 차이를 쫓는 대신
매번 원문을 기준으로 삼습니다. 시트 서식은 자주 바뀌므로(글머리 '-' 가 사라진
적도 있습니다) 여기 규칙도 그때그때 손봐야 합니다.

  python3 tools/sheet_parse.py <시트를_받아둔_json> [날짜 …]

입력은 Drive 커넥터가 돌려준 {"fileContent": "...마크다운 표..."} 파일입니다.
"""
import json, re, sys

# ── 표에서 하루치 행 뽑기 ────────────────────────────────
DATE_CELL = re.compile(r'^\d{1,2}/\d{1,2} \(')


# 시트는 한 칸 안에서 줄바꿈 대신 **공백 여러 칸**으로 항목을 나눕니다.
#   "⚠️ 재입장 불가        도마뱀 분수 (엘 드락)        물결 벤치"
# 예전엔 \s+ → ' ' 로 뭉개서 이 경계를 잃었고, 그 결과 설명이 통째로 한 문장이
# 되고 이름에까지 딸려 들어갔습니다. 뭉개기 전에 경계를 기호로 바꿔 둡니다.
SEP = '\x1f'


def squash(s):
    s = re.sub(r'[ \t ]{2,}', SEP, s)      # 2칸 이상 = 항목 경계
    return re.sub(r'[ \t]+', ' ', s).strip()


def load(path):
    """{날짜: {loc, sched, note}} — sched 안의 \\x1f 는 항목 경계입니다."""
    content = json.load(open(path, encoding='utf-8'))['fileContent']
    out = {}
    for row in content.split('\n'):
        if not row.startswith('|'):
            continue
        cells = [c.strip() for c in row.strip('|').split('|')]
        if len(cells) < 6 or not DATE_CELL.match(cells[2] or ''):
            continue
        m, dd = re.match(r'^(\d{1,2})/(\d{1,2})', cells[2]).groups()
        out[f"2026-{int(m):02d}-{int(dd):02d}"] = {
            'loc':   re.sub(r'\s+', ' ', cells[1]).replace('\\-', '-').strip(),
            'sched': squash(cells[3]),
            'note':  squash(cells[5]),
        }
    return out


# ── 구간 나누기 ─────────────────────────────────────────
# 라벨에 숫자가 들어갈 수 있으므로("약 3시간") 다음 시각 표시 전까지를 라벨로 봅니다
OPT_RE = re.compile(r'\[(?:옵션|루트|선택지)\s*([ABCD])\]\s*(.{0,60}?)(?=\s\d{1,2}:\d{2}\s|$)')
SEC_RE = re.compile(r'━+\s*([^━]{1,40}?)\s*━+')

# [옵션 X] 표기 없이 섹션 제목만으로 선택지를 나타낸 곳
SECTION_AS_OPTION = {
    '융프라우 취소 시 대안': ('B', '융프라우 취소 — 계곡 저지대'),
}


def blocks(sched):
    """(kind, label, text) — kind = 'common' | 'option'"""
    s = sched.replace('\\', '')
    marks = []
    for m in SEC_RE.finditer(s):
        t = m.group(1)
        if t in SECTION_AS_OPTION:
            marks.append((m.start(), m.end(), 'option', SECTION_AS_OPTION[t]))
        else:
            marks.append((m.start(), m.end(), 'section', t))
    for m in OPT_RE.finditer(s):
        marks.append((m.start(), m.end(), 'option', (m.group(1), m.group(2).strip(' ·-'))))
    marks.sort()

    out, cur, pos = [], ('common', None), 0
    for st, en, kind, lab in marks:
        chunk = s[pos:st].strip()
        if chunk:
            out.append((cur[0], cur[1], chunk))
        if kind == 'option':
            cur = ('option', lab)
        elif '공통' in lab:            # ━━━ 공통 ━━━ 은 옵션 구간을 끝냅니다
            cur = ('common', None)
        pos = en
    tail = s[pos:].strip()
    if tail:
        out.append((cur[0], cur[1], tail))
    return out


# ── 한 구간 → 일정 항목들 ────────────────────────────────
TIME = re.compile(r'(?<![0-9:])(\d{1,2}:\d{2})\s+')
# 인코딩이 깨져 들어오는 이모지 잔해.
# · (U+00B7) 은 설명 구분자라 반드시 제외 — 같이 지워서 설명 76개가
# 통째로 한 문장이 된 적이 있습니다.
# 🍽(F0 9F 8D BD) 같은 4바이트 이모지가 라틴-1 로 잘못 읽히면 "ð½" 이 되고,
# 앞의 ð 가 셀 분리 과정에서 떨어져 나가면 "½" "´" "¨" 만 남습니다.
MOJI = re.compile('[�ð][-ÿ̀-ͯ]*'
                  '|(?<![0-9A-Za-z])[¡-¶¸-¿×÷ßÿ](?![0-9A-Za-z])')
# 이름 앞에 붙는 장식 — 종류는 kind 가 대신 그리므로 이름에서 뺍니다
LEAD = re.compile(r'^[\s·\-—️✈⛪⛴⛰⛲⛽🍽🍴🏛🎫🚆🛍🏨🚗🚌🚕🛥🚡🖼📷🛏💒🚶🛒⭐★⏱✅❌✨]+')

# 이름이 어디서 끝나는지 — 값·시각·주의 표시가 나오면 그 앞까지가 이름입니다.
# (시트가 글머리 '-' 를 빼면서 설명이 이름에 붙는 일이 생겨 넣었습니다)
NAME_END = re.compile(
    r'\s+(?=[-⚠️※★⭐💡☐⛔]'                       # 글머리·주의 표시
    r'|[€$]\s?\d|CHF \d|CZK \d|\d[\d,]*\s*(?:원|CZK)'  # 값
    r'|\d{1,2}:\d{2}\b'                              # 본문 속 시각
    r'|약 \d|소요 \d|해발 \d|왕복 |편도 '              # 수치 설명
    r'|[A-Z]\d{3}\b|보잉 |에어버스 )'                  # 기종
)
# 자르고 남은 꼬리 — "A350 /" 의 슬래시처럼 매달린 기호
TRAIL = re.compile(r'[\s·\-—/,(]+$')


def items_of(text):
    parts = TIME.split(text.replace(SEP, SEP + ' '))
    got = []
    for i in range(1, len(parts), 2):
        t = parts[i]
        body = (parts[i + 1] if i + 1 < len(parts) else '').strip(' ·-')
        if not body:
            continue
        head = body.split(SEP, 1)[0]          # 첫 경계까지가 이름 후보
        head = NAME_END.split(head, maxsplit=1)[0]
        head = re.sub(r'\s*✅.*$', '', head)
        head = MOJI.sub('', head)
        head = LEAD.sub('', head)
        head = TRAIL.sub('', head).strip(' ·-')
        if not head:
            continue
        got.append({'time': t, 'name': head[:58], 'raw': body})
    return got


def mm(t):
    h, m = t.split(':')
    return int(h) * 60 + int(m)


def fold(items):
    """되돌아가는 시각 = 본문 속 참조 → 앞 항목에 합침 (진짜 자정넘김은 예외)"""
    out = []
    for i, it in enumerate(items):
        if out and mm(it['time']) < mm(out[-1]['time']):
            tail = [x['time'] for x in items[i:]]
            asc = all(mm(tail[j]) <= mm(tail[j + 1]) for j in range(len(tail) - 1))
            if asc and mm(it['time']) < 6 * 60:
                out.append(it)                      # 진짜 자정 넘김
                continue
            # 어느 쪽이 이탈자인가 — 직전 항목을 떼면 순서가 복구되는 경우
            if len(out) >= 2 and mm(it['time']) >= mm(out[-2]['time']):
                note = out.pop()
                out[-1]['raw'] += ' ' + note['time'] + ' ' + note['raw']
                out.append(it)
                continue
            out[-1]['raw'] += ' ' + it['time'] + ' ' + it['raw']
            continue
        out.append(it)
    return out


# 시각처럼 보이지만 실은 본문 속 참조라 앞 항목에 붙어야 하는 조각들.
# ("관광 입장 마감 17:30~18:00 가능성" 의 18:00, "예약 슬롯 17:00~19:00 슬롯)" 의 19:00)
# 이름이 이 말들로 시작하면 항목이 아니라 앞 문장의 뒷도막입니다.
FRAGMENT = re.compile(
    r'^(가능성|도착 필수|이후로|정각부터|이전 방문|개장 직후|폐쇄|슬롯\)|기상\)'
    r'|매표소|운행 종료|이 구간|무료 입장|재개장)')


def unclosed(name):
    """항목이 아니라 앞 문장의 뒷도막임을 형태로 알아내는 규칙 두 가지.

    1. 닫는 괄호로 끝나는데 여는 괄호가 없음 —
       "짐 완전히 싸기 (내일 새벽 03:00 체크아웃)" 의 03:00 이 항목으로 잡히면
       이름이 "체크아웃)" 이 됩니다 (9/16 이 이렇게 시간 역순이 됐습니다).
    2. 화살표로 시작 — "마지막 입장 21:00 → 20:30까지 도착 필수" 의 21:00 이
       항목이 되면 이름이 "→ 20:30까지 도착 필수" 가 됩니다.
    낱말을 하나씩 FRAGMENT 에 넣는 것보다 이 규칙이 넓게 걸립니다."""
    t = name.strip()
    return (t.endswith(')') and '(' not in t) or t.startswith(('→', '->'))


def same_time_fold(items):
    """같은 시각이 잇달아 나오거나, 이름이 문장 뒷도막이면 앞 항목에 합칩니다."""
    out = []
    for it in items:
        frag = FRAGMENT.match(it['name']) or unclosed(it['name'])
        same = out and it['time'] == out[-1]['time'] and (
            len(it['name']) <= 8 or it['name'][0] in '()[')
        if out and (frag or same):
            out[-1]['raw'] += ' ' + it['time'] + ' ' + it['raw']
            continue
        out.append(it)
    return out


# 새로 생긴 항목의 이름 다듬기 — 시트는 "이름 (부연) 설명 설명" 을 한 줄로 씁니다
def trim_name(name):
    for sep in (' (', ' — ', ' – '):
        i = name.find(sep)
        # 자르고 남은 쪽이 너무 짧으면 이름 구실을 못 합니다 —
        # "호텔 — 짐 정리" 를 자르면 "호텔" 만 남아 어느 호텔인지도 모릅니다.
        if 4 <= i <= 30:
            return name[:i].strip(' ·-')
    # 괄호가 없을 때의 마지막 수단. 예전엔 24자였는데 그러면 멀쩡한 이름이
    # 잘립니다 ("Camping TCS Lugano-Muzzano 체크인" → "Camping TCS").
    # 40자면 하드컷 당하는 이름이 0이 되고 다듬은 결과도 가장 잘 맞습니다.
    if len(name) <= 40:
        return name
    cut = name[:40].rsplit(' ', 1)[0]
    return (cut or name[:40]).strip(' ·-')


def parse_day(sheet, date):
    common, opts = [], []
    for kind, lab, text in blocks(sheet[date]['sched']):
        its = items_of(text)
        if not its:
            continue
        if kind == 'option':
            letter, title = lab
            ex = next((o for o in opts if o['letter'] == letter), None)
            if ex:
                ex['items'] += its
            else:
                opts.append({'letter': letter, 'title': title, 'items': its})
        else:
            common += its
    # 순서가 중요합니다 — 문장 뒷도막(FRAGMENT)을 먼저 걷어내야 합니다.
    # 안 그러면 fold 가 "18:45 대성당 / 18:00 가능성…" 을 보고 대성당 쪽을
    # 이탈자로 판단해 지워버립니다 (실제로 두 번 그랬습니다).
    common = fold(same_time_fold(common))
    for o in opts:
        o['items'] = fold(same_time_fold(o['items']))
    return common, opts


if __name__ == '__main__':
    sh = load(sys.argv[1])
    for date in (sys.argv[2:] or sorted(sh)):
        c, o = parse_day(sh, date)
        print(f"\n===== {date}  공통 {len(c)} · 옵션 {len(o)}")
        for it in c:
            print(f"   {it['time']}  {it['name']}")
        for x in o:
            print(f"   ┌ [{x['letter']}] {x['title']}  ({len(x['items'])})")
            for it in x['items']:
                print(f"   │  {it['time']}  {it['name']}")
