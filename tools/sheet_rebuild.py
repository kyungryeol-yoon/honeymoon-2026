# -*- coding: utf-8 -*-
"""구글 시트만 보고 data.json 을 **처음부터** 다시 만듭니다.

  python3 tools/sheet_rebuild.py <시트를_받아둔_json>
  python3 tools/enrich.py
  ./tools/release.sh

sheet_sync.py 와 다른 점: 이전 data.json 을 **전혀 읽지 않습니다.**
sheet_sync 는 매칭된 항목의 이름·place·move 를 앱에서 이어받는데(CARRY),
그게 "초기화" 와는 맞지 않습니다. 여기서는 시트에 있는 것만 씁니다.

시트에 없지만 앱이 못 돌아가는 것(trip · cities · 날짜↔도시)은 아래
STRUCT 에 둡니다. 도시 색·랜드마크 아이콘은 디자인 자산이고, cities[].tz 는
한국시간 병기의 기준이라 데이터가 아니라 구조로 봅니다.

따라서 이 도구를 돌리면 다음이 **사라집니다** (시트에 없음):
  phrases 한마디 · place 지도검색어 · move 이동수단 · chips 하루주의 ·
  star 하이라이트 · food.eat 의 가격
"""
import json, re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
from sheet_parse import load, parse_day, trim_name, mm, SEP, MOJI   # noqa: E402
from sheet_sync import clean, split_notes, chips, cut, OPT_ID, RECOMMENDED, ORDER  # noqa: E402


# ── 시트에 없는 앱 구조 ────────────────────────────────────
TRIP = {"title": "Honeymoon 2026", "couple": "Kyungryeol & Hojeong",
        "start": "2026-09-13", "end": "2026-10-04"}

# 여행 기간(9/13~10/4)에는 유럽이 전부 CEST(+2). 전환은 10/25 라 여행 뒤입니다.
CITIES = [
    {"id": "bcn", "name": "바르셀로나", "short": "BCN", "flag": "ES",
     "color": "#D4744A", "colorLight": "#B85A32", "icon": "sagrada",
     "map": "Barcelona, Spain", "lang": "es", "country": "스페인", "tz": 120},
    {"id": "swi", "name": "스위스", "short": "CH", "flag": "CH",
     "color": "#5B94C4", "colorLight": "#3C74A6", "icon": "alps",
     "map": "Switzerland", "lang": "de", "country": "스위스", "tz": 120},
    {"id": "vce", "name": "베네치아", "short": "VCE", "flag": "IT",
     "color": "#8AA05A", "colorLight": "#677F3C", "icon": "gondola",
     "map": "Venezia, Italy", "lang": "it", "country": "이탈리아", "tz": 120},
    {"id": "flr", "name": "피렌체", "short": "FLR", "flag": "IT",
     "color": "#8AA05A", "colorLight": "#677F3C", "icon": "duomo",
     "map": "Firenze, Italy", "lang": "it", "country": "이탈리아", "tz": 120},
    {"id": "rom", "name": "로마", "short": "ROM", "flag": "IT",
     "color": "#8AA05A", "colorLight": "#677F3C", "icon": "colosseo",
     "map": "Roma, Italy", "lang": "it", "country": "이탈리아", "tz": 120},
    {"id": "prg", "name": "프라하", "short": "PRG", "flag": "CZ",
     "color": "#B0576B", "colorLight": "#963E53", "icon": "charles",
     "map": "Praha, Czechia", "lang": "cs", "country": "체코", "tz": 120},
    {"id": "sel", "name": "서울", "short": "SEL", "flag": "KR",
     "color": "#A78BB5", "colorLight": "#7D5E8E", "icon": "namsan",
     "map": "Seoul, South Korea", "home": True, "tz": 540},
]

# 이동일은 **도착지**가 그 날의 도시입니다 (헤더 색·랜드마크가 여기서 나옴).
DAY_CITY = {
    '2026-09-13': 'sel', '2026-09-14': 'bcn', '2026-09-15': 'bcn', '2026-09-16': 'bcn',
    '2026-09-17': 'swi', '2026-09-18': 'swi', '2026-09-19': 'swi', '2026-09-20': 'swi',
    '2026-09-21': 'swi', '2026-09-22': 'vce', '2026-09-23': 'vce', '2026-09-24': 'flr',
    '2026-09-25': 'flr', '2026-09-26': 'flr', '2026-09-27': 'rom', '2026-09-28': 'rom',
    '2026-09-29': 'rom', '2026-09-30': 'prg', '2026-10-01': 'prg', '2026-10-02': 'prg',
    '2026-10-03': 'prg', '2026-10-04': 'sel',
}

# 9/13 은 아직 한국이지만 여행 1일차입니다 (여정선 맨 앞 서울이 "여기")
ORIGIN = '2026-09-13'

# 하루 안에 시계가 바뀌는 날만 항목별로 적습니다. 나머지는 cities[].tz.
# (분 단위 UTC 오프셋 / tzl 은 시각 옆 알약 / endTz 는 도착지 시계)
FLIGHT_TZ = {
    ('2026-09-14', '00:00'): {'tz': 540, 'tzl': 'KST'},
    ('2026-09-14', '00:50'): {'tz': 540, 'tzl': 'KST'},
    ('2026-09-14', '01:20'): {'tz': 540, 'tzl': 'KST', 'endTz': 180},
    ('2026-09-14', '05:20'): {'tz': 180, 'tzl': 'GMT+3'},
    ('2026-09-14', '08:35'): {'tz': 180, 'tzl': 'GMT+3', 'endTz': 120},
    ('2026-09-14', '14:40'): {'tz': 120, 'tzl': 'CEST'},
    ('2026-09-14', '15:00'): {'tz': 120, 'tzl': 'CEST'},
    ('2026-09-14', '16:00'): {'tz': 120, 'tzl': 'CEST'},
    ('2026-09-14', '16:30'): {'tz': 120, 'tzl': 'CEST'},
    ('2026-09-14', '17:15'): {'tz': 120, 'tzl': 'CEST'},
    ('2026-09-14', '18:00'): {'tz': 120, 'tzl': 'CEST'},
    ('2026-09-14', '18:45'): {'tz': 120, 'tzl': 'CEST'},
    ('2026-09-14', '19:30'): {'tz': 120, 'tzl': 'CEST'},
    ('2026-09-14', '21:00'): {'tz': 120, 'tzl': 'CEST'},
    ('2026-10-04', '13:20'): {'tz': 540, 'tzl': 'KST'},
    ('2026-10-04', '14:30'): {'tz': 540, 'tzl': 'KST'},
    ('2026-10-04', '15:00'): {'tz': 540, 'tzl': 'KST'},
}


# ── 민감정보 ──────────────────────────────────────────────
# 저장소가 public 입니다. 시트에는 예약번호·티켓번호·PNR 이 그대로 적혀 있고
# 동기화할 때마다 딸려 들어옵니다 (실제로 PNR 2건이 히스토리에 남아 지웠습니다).
# release.sh 2단계가 막지만, 그건 마지막 그물이고 여기서 먼저 걷어냅니다.
SECRET = [
    (re.compile(r'((?:PNR|예약번호|주문번호|확인번호|예약코드|티켓번호|바우처)'
                r'\s*[:：]?\s*)[A-Z0-9]{5,14}\b'), r'\1메일에서 확인'),
    (re.compile(r'(?<![#\d])\b\d{8,}\b'), '메일에서 확인'),
    # 라벨이 없어도 영문+숫자 8자 이상은 확인번호로 봅니다 (Hertz L678EFF41E7).
    # 편명은 5자 이하라(QR859) 안 걸립니다.
    (re.compile(r'\(?\b(?=[A-Z0-9]{8,16}\b)(?=[A-Z]*\d)(?=\d*[A-Z])[A-Z0-9]{8,16}\b\)?'),
     '메일에서 확인'),
]


def scrub(s):
    for pat, rep in SECRET:
        s = pat.sub(rep, s)
    # "· 메일에서 확인 · 메일에서 확인 ·" 처럼 줄줄이 남는 것 정리
    s = re.sub(r'(메일에서 확인)(\s*[·/,]\s*메일에서 확인)+', r'\1', s)
    return re.sub(r'\s{2,}', ' ', s).strip(' ·/,')


# ── 시트에서 뽑기 ─────────────────────────────────────────
# 편명·열차번호는 공개 시간표 정보라 가려도 의미가 없습니다.
FLIGHT = re.compile(r'\b([A-Z]{2}\d{2,4})\b')
TRAIN  = re.compile(r'\b(EC ?\d{1,3}|FR ?\d{3,4}|Frecciarossa \d{3,4}|RegioJet)\b')

# "→ 도착" 처럼 이름만으로는 어디인지 모르는 항목에 붙는 종료 시각
END = re.compile(r'(\d{1,2}:\d{2})\s*(?:도착|착)')


def refs_of(name, raw):
    out = []
    for m in dict.fromkeys(FLIGHT.findall(name)):
        out.append({'label': '편명', 'value': m})
    for m in dict.fromkeys(TRAIN.findall(name)):
        out.append({'label': '열차', 'value': m.replace('  ', ' ')})
    return out


# 시트는 예약·발권이 끝난 항목에 ✅ 를 붙입니다 (일정 칸에 22건).
# 어떤 종류인지는 본문 낱말로 가릅니다.
def booked_of(raw):
    if '✅' not in raw:
        return None
    if '발권' in raw:
        return '발권'
    if '온라인 체크인' in raw:
        return '온라인'
    if '24시간 운행' in raw or '상시' in raw:
        return '상시'
    return '예약'


MEET = re.compile(r'미팅\s*장소\s*[:·-]?\s*([^\x1f·]{3,50})')
CASH = re.compile(r'(?:현장\s*)?현금\s*((?:€|CHF|CZK|\$)\s?[\d,.]+(?:\s*/인)?)')


def meet_of(raw, time):
    m = MEET.search(raw)
    if not m:
        return None
    where = clean(m.group(1)).strip(' ·-()')
    return {'time': time, 'where': where[:44]} if where else None


# 시트 "나라" 열 — "스위스 - 라우터브룬넨" / "그린델발트 → 루가노" 처럼
# 그날의 거점을 적어 둡니다. 도시 이름과 다르면 헤더에 크게 띄웁니다.
#
# 이동일에는 "이탈리아 (프라하 공항)" 처럼 나라와 공항만 적혀 있어 쓸 수
# 없습니다. 나라 이름과 역·공항은 걸러내고, 도시 이름과 같아도 뺍니다
# (헤더에 "로마 / 로마" 가 겹쳐 뜹니다).
COUNTRY = {'대한민국', '한국', '스페인', '스위스', '이탈리아', '체코'}
ARROW = re.compile(r'[→>]|✈|[\ufffd\u00f0][^\s]*')


def label_of(loc, city_name):
    s = ARROW.split(loc)[-1]
    s = re.sub(r'[\ufe0f\u200d\u2600-\u27bf]', '', s)   # 이모지 변형자 잔해
    s = re.sub(r'\([^)]*\)', '', s)
    s = re.sub(r'\s+', ' ', s).split(' - ')[-1].strip(' -·')
    s = re.sub(r'(역|공항)$', '', s).strip()
    if not s or s in COUNTRY or s == city_name or len(s) > 12:
        return None
    return s


# 숙소 — 시트는 일정 칸의 "체크인" 항목과 예산표에 적어 둡니다.
# 이름이 없는 체크인("호텔 체크인")은 예산표 쪽 이름을 씁니다.
GENERIC_STAY = {'flr': 'Hotel Nella Firenze', 'prg': 'Golden Angel Suites'}
NOT_STAY = re.compile(r'항공|위즈에어|카타르|대한항공|스위스항공')
STAY_CUT = re.compile(r'\s*(?:현장\s*)?체크인.*$')


def stay_of(items, cid):
    """그날 체크인한 숙소 — 없으면 None.

    시트가 "도보 8분 → 마그니피코 로마" / "체크인" 을 두 항목으로 쪼개 적기도
    해서, 체크인 항목에 이름이 없으면 바로 앞 항목에서 가져옵니다."""
    for i, it in enumerate(items):
        nm = it['name']
        if '체크인' not in nm or NOT_STAY.search(nm):
            continue
        name = STAY_CUT.sub('', nm).strip(' ·→-')
        name = re.sub(r'^도보\s*\d+분\s*→\s*', '', name).strip()
        if (not name or name == '호텔') and i > 0:
            prev = items[i - 1]['name']
            if '→' in prev:
                name = re.sub(r'^.*→\s*', '', prev).strip()
        if not name or name == '호텔':
            name = GENERIC_STAY.get(cid)
        if not name:
            continue
        stay = {'name': name[:34]}
        if not any('가' <= ch <= '힣' for ch in name):
            stay['place'] = name[:44]
        return stay
    return None


CITY_NAME = {c['id']: c['name'] for c in CITIES}
CITY_MAP  = {c['id']: c['map'] for c in CITIES}


def main(path):
    sh = load(path)
    days, carry = [], {}

    for date in sorted(DAY_CITY):
        if date not in sh:
            print(f"   ! 시트에 {date} 없음 — 건너뜀")
            continue
        common, opts = parse_day(sh, date)

        # 9/13 은 자정을 넘겨 9/14 새벽까지 한 칸에 적혀 있습니다
        if date == '2026-09-13':
            common = [c for c in common if mm(c['time']) >= 6 * 60]
        if date == '2026-09-14':
            c13, _ = parse_day(sh, '2026-09-13')
            early = [c for c in c13 if mm(c['time']) < 6 * 60]
            have = {c['time'] for c in common}
            common = [c for c in early if c['time'] not in have] + common
        # 9/18 본문 전체가 '융프라우 진행' 루트입니다
        if date == '2026-09-18':
            a = [c for c in common if '06:30' <= c['time'] <= '18:00']
            common = [c for c in common if c not in a]
            opts.insert(0, {'letter': 'A', 'title': '융프라우 진행', 'items': a})

        day = {'date': date, 'city': DAY_CITY[date], 'dayNo': len(days) + 1}
        if date == ORIGIN:
            day['origin'] = True
        day['items'] = [build(s, date) for s in common]

        new_opts = []
        for x in opts:
            key = (date, x['letter'])
            oid, label = OPT_ID.get(key, (x['letter'].lower(), clean(x['title'])[:24]))
            o = {'id': oid, 'label': label}
            if key in RECOMMENDED:
                o['recommended'] = True
            summary = clean(x['title']).strip(' —·-')
            if summary:
                o['summary'] = summary[:60]
            o['items'] = [build(s, date) for s in x['items']]
            new_opts.append(o)
        if new_opts:
            day['options'] = new_opts

        name_bare(day['items'])
        add_end(day['items'])
        for o in new_opts:
            name_bare(o['items'])
            add_end(o['items'])

        lab = label_of(sh[date]['loc'], CITY_NAME[DAY_CITY[date]])
        if lab:
            day['label'] = lab
            day['map'] = f"{lab}, {CITY_MAP[DAY_CITY[date]]}"

        # 숙소 — 체크인한 날부터 다음 체크인 전날까지 이어집니다.
        # 밤늦게 택시에서 보여줄 한 줄이라 묵는 날마다 붙여야 합니다.
        st = stay_of(day['items'], DAY_CITY[date])
        if st:
            carry['stay'] = st
        elif '체크아웃' in ' '.join(i['name'] for i in day['items']) and carry.get('stay'):
            pass                     # 체크아웃하는 날도 짐을 맡기므로 그대로 둡니다
        if carry.get('stay') and date != '2026-10-04':
            day['stay'] = carry['stay']

        # 그날 현장에서 낼 현금 — 본문에서 처음 나오는 금액
        cash = day_cash(common, new_opts)
        if cash:
            day['cash'] = cash
        days.append(day)

    d = {'trip': TRIP, 'cities': CITIES, 'days': days,
         'contacts': CONTACTS, 'food': {}, 'gift': {}}
    return d


def build(src, date):
    it = {'time': src['time']}
    desc, warn = split_notes(src['raw'])

    # 시트 이름은 "가벼운 저녁 (기내식 있으니 간단히)" 처럼 부연이 붙어 있습니다.
    # trim_name 이 이름만 남기는데, 잘려나간 쪽도 설명으로 쓸 내용입니다.
    full = clean(src['name'])
    name = trim_name(full)[:58]
    it['name'] = name
    tail = ''
    if full.startswith(name) and len(full) > len(name):
        tail = full[len(name):].strip(' ·—–-()').strip()

    # 별표는 붙이지 않습니다. 시트의 ⭐ 는 항목 강조가 아니라 본문 주석
    # 표시라("⭐ 9월 하순 수온 20~22℃") 그대로 옮기면 뜻이 뒤집힙니다.
    # 예전 data.json 은 441개 중 126개(28%)가 별표라 강조 구실을 못 했습니다.
    b = booked_of(src['raw'])
    if b:
        it['booked'] = b

    parts = ([tail] if tail else []) + desc
    if parts:
        t = scrub(cut(' · '.join(parts), 180))
        if t:
            it['desc'] = t

    tz = FLIGHT_TZ.get((date, src['time']))
    if tz:
        it.update(tz)

    r = refs_of(name, src['raw'])
    if r:
        it['refs'] = r

    m = meet_of(src['raw'], src['time'])
    if m:
        it['meet'] = m

    # 칩이 40자를 넘으면 두 줄로 흘러 안 읽힙니다 (release.sh 가 막습니다).
    # 토큰 한가운데서 자르지 않게 cut() 으로 줄입니다.
    got = [cut(scrub(x), 38) for x in chips(warn, it.get('desc') or '', [])]
    got = [x for x in got if len(x) >= 5]
    if got:
        it['prep'] = got
    return {k: it[k] for k in ORDER if k in it}


# 편명이 붙은 이동 항목 다음이 "…도착" 이면 그게 도착 시각입니다.
# 붙여 두면 "01:20 – 05:20" 처럼 구간으로 보이고, 한국시간도 범위로 환산됩니다.
RIDE = re.compile(r'(?:→|✈).*\b[A-Z]{2}\d{2,4}\b|Frecciarossa|EC ?\d|RegioJet')
ARRIVE = re.compile(r'도착$|도착\b')


# 시트가 "13:00 출발 → Badestelle Neuhaus / 13:30 도착" 처럼 적으면 뒷 항목
# 이름이 "도착" 하나뿐이라 화면에서 어디 도착인지 알 수 없습니다.
# 앞 항목의 화살표 뒤에서 목적지를 빌려옵니다.
BARE = re.compile(r'^(?:도착|출발|하차|승차)$')


def name_bare(items):
    for i, it in enumerate(items):
        if i == 0 or not BARE.match(it['name']):
            continue
        prev = items[i - 1]['name']
        if '→' not in prev:
            continue
        dest = re.sub(r'^.*→\s*', '', prev).strip(' ·-')
        dest = re.sub(r'\s*\([^)]*\)\s*$', '', dest).strip()
        if 2 <= len(dest) <= 34:
            it['name'] = f"{dest} {it['name']}"


def add_end(items):
    for i, it in enumerate(items[:-1]):
        if 'end' in it or not RIDE.search(it['name']):
            continue
        nxt = items[i + 1]
        if ARRIVE.search(nxt['name']) and nxt['time'] > it['time']:
            it['end'] = nxt['time']


def day_cash(common, opts):
    for src in common + [i for o in opts for i in o['items']]:
        m = CASH.search(src.get('raw', ''))
        if m:
            return {'amount': clean(m.group(1))}
    return None


# 시트의 준비물 칸에 적힌 번호 + 각국 공통 긴급번호
CONTACTS = {
    'common': {'name': '어디서나', 'lines': [
        {'label': '영사콜센터', 'tel': '+82-2-3210-0404', 'note': '24시간 · 유료'},
        {'label': 'Visa 카드 분실신고', 'tel': '+1-303-967-1090', 'note': '24시간'},
    ]},
    'ES': {'name': '스페인', 'lines': [
        {'label': '긴급 (경찰·구급·소방)', 'tel': '112'},
        {'label': '주스페인 대사관', 'tel': '+34-91-353-2000', 'note': '근무시간'},
    ]},
    'CH': {'name': '스위스', 'lines': [
        {'label': '긴급 (통합)', 'tel': '112'},
        {'label': '구급차', 'tel': '144'},
        {'label': '경찰', 'tel': '117', 'note': '도난 신고 = 보험 청구용'},
        {'label': '주스위스 대사관', 'tel': '+41-31-356-2444', 'note': '근무시간'},
    ]},
    'IT': {'name': '이탈리아', 'lines': [
        {'label': '긴급 (경찰·구급·소방)', 'tel': '112'},
        {'label': '주이탈리아 대사관', 'tel': '+39-06-808-8769', 'note': '근무시간'},
    ]},
    'CZ': {'name': '체코', 'lines': [
        {'label': '긴급 (경찰·구급·소방)', 'tel': '112'},
        {'label': '구급차', 'tel': '155'},
        {'label': '주체코 대사관', 'tel': '+420-234-090-411', 'note': '근무시간'},
    ]},
}


if __name__ == '__main__':
    D = main(sys.argv[1])
    from food_gift import parse_tables      # noqa: E402
    D['food'], D['gift'] = parse_tables(sys.argv[1])
    (ROOT / 'data.json').write_text(
        json.dumps(D, ensure_ascii=False, indent=1), encoding='utf-8')

    n = sum(len(x['items']) + sum(len(o['items']) for o in (x.get('options') or []))
            for x in D['days'])
    print(f"data.json 새로 씀 — {len(D['days'])}일 / {n}개 일정")
    for x in D['days']:
        no = len(x.get('options') or [])
        print(f"   {x['date']}  {len(x['items']):>3}개"
              f"{'  + 옵션 ' + str(no) if no else ''}")
