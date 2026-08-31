# -*- coding: utf-8 -*-
"""구글 시트를 다시 읽어 data.json 에 반영합니다.

  python3 tools/sheet_sync.py <시트를_받아둔_json>

시트를 볼 때마다 **처음부터 다시 파싱**합니다. 이전 결과와의 차이를 쫓지 않습니다.

무엇을 어디서 가져오는가
  시트에서 — 시각 · 항목의 있고 없음 · 설명 · 주의사항 · 선택지 구조
  앱에서   — 이름 · 지도 검색어 · 이동수단 · 종류 · 예약상태 · 칩 플래그 · 시간대

  이름을 앱 쪽에서 쓰는 이유: 시트는 "이름 설명 설명" 을 한 줄로 적어 두어
  어디까지가 이름인지 알려주지 않습니다. 글머리 '-' 로 자르던 규칙도
  2026-08 개정에서 무력해졌습니다. 앱의 이름은 여러 차례 다듬은 것이라
  매칭된 항목은 그쪽을 씁니다. 새로 생긴 항목만 시트에서 이름을 뽑고,
  그건 사람이 확인해야 합니다 (실행하면 목록으로 찍어줍니다).
"""
import json, re, sys, difflib, unicodedata, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
from sheet_parse import load, parse_day, mm, MOJI, trim_name, SEP  # noqa: E402

# 앱에서만 관리하는 필드 — 시트에는 없으므로 반드시 이어받아야 합니다
CARRY = ('place', 'map', 'move', 'prep', 'refs', 'tz', 'tzl', 'endTz', 'meet',
         'links', 'end', 'kind', 'booked', 'food', 'gift', 'say')

OPT_ID = {
    ('2026-09-17', 'A'): ('thun', '툰 호수 · 슈피츠'),
    ('2026-09-17', 'B'): ('aare', '아레 협곡'),
    ('2026-09-17', 'C'): ('blausee', 'Blausee'),
    ('2026-09-18', 'A'): ('jungfrau', '융프라우 진행'),
    ('2026-09-18', 'B'): ('valley', '취소 · 계곡 저지대'),
    ('2026-09-19', 'A'): ('iseltwald', 'Iseltwald'),
    ('2026-09-19', 'B'): ('rosenlaui', 'Rosenlaui 협곡'),
    ('2026-09-19', 'C'): ('rest', '캠프 휴식'),
    ('2026-09-20', 'A'): ('oeschinensee', 'Oeschinensee'),
    ('2026-09-20', 'B'): ('giessbach', 'Giessbach + 묀리헨'),
    ('2026-09-20', 'C'): ('rest', '캠프 휴식'),
    ('2026-09-21', 'A'): ('gotthard', 'Gotthard 터널'),
    ('2026-09-21', 'B'): ('passes', 'Furka · Grimsel 고갯길'),
    ('2026-09-23', 'A'): ('frari', '프라리 성당'),
    ('2026-09-23', 'B'): ('accademia', '아카데미아 미술관'),
    ('2026-09-23', 'C'): ('rest', '그냥 쉬기'),
    ('2026-09-25', 'A'): ('out', '바로 나오기 · 여유 점심'),
    ('2026-09-25', 'B'): ('stay', '우피치 자유관람 연장'),
    ('2026-10-01', 'A'): ('klementinum', '클레멘티눔 투어'),
    ('2026-10-01', 'C'): ('oldtown', '바로 구시가로'),
}
RECOMMENDED = {(d, 'A') for d in ('2026-09-17', '2026-09-18', '2026-09-19',
                                  '2026-09-20', '2026-09-21', '2026-09-23',
                                  '2026-09-25', '2026-10-01')}

ORDER = ('time', 'end', 'name', 'kind', 'booked', 'food', 'gift', 'say', 'desc',
         'place', 'map', 'move', 'meet', 'prep', 'refs', 'star', 'links',
         'tz', 'tzl', 'endTz')

# 화면에서 kind 이모지·star 표식이 대신하므로 데이터에 둘 이유가 없는 것들.
# → 와 ↔ 는 경로를 나타내므로 남깁니다.
# ⚠☐⛔💡 는 split_notes() 가 설명·주의를 가르는 표식이라 **그 전까지는** 살아
# 있어야 합니다. clean() 은 가르고 난 뒤에 부르므로 여기서 지워도 됩니다.
# (안 지우면 옵션 요약과 기념품 그룹 이름에 그대로 남습니다)
JUNK = re.compile('[⭐★✅❌⏱✨⚠☐⛔💡⛽⛲⛪⛰⛴✈🍽🍴🏛🎫🚆🛍🏨🚗🚌🚕🛥🚡🖼📷🛏💒🚶🛒️]')


def clean(s):
    s = MOJI.sub('', s).replace('\\', '')
    s = JUNK.sub('', s).replace(SEP, ' ')
    return re.sub(r'\s+', ' ', s).strip(' ·-')



def split_notes(raw):
    """시트의 항목 경계(SEP)와 글머리 표시로 설명·주의를 나눕니다.
       경계를 살리지 않으면 설명이 통째로 한 문장이 되어 화면에서 안 읽힙니다."""
    body = MOJI.sub('', raw).replace('\\', '')
    out_d, out_w = [], []
    for piece in body.split(SEP)[1:]:            # 첫 조각은 이름
        for chunk in re.split(r'(?=[-⚠※☐⛔💡])', piece):
            text = clean(chunk.lstrip('-⚠※☐⛔💡 '))
            if not text:
                continue
            (out_w if chunk[:1] in '⚠※⛔' else out_d).append(text)
    return out_d, out_w


def norm(s):
    return re.sub(r'[\s·\-—()\[\]]+', '', unicodedata.normalize('NFKC', s)).lower()


def same(s):
    """구분기호·공백 차이를 무시한 비교용 열쇠. 시트는 같은 말을
       ' · ' 유무만 다르게 두 번 적는 일이 잦습니다."""
    return re.sub(r'[\s·→=\-—]+', '', s)


def cut(s, n):
    """n 자에서 자르되 토큰 한가운데를 끊지 않습니다.
       그냥 [:180] 으로 자르면 설명이 '… 성 베드로 대성당 3.' 처럼 끝납니다."""
    if len(s) <= n:
        return s
    head = s[:n]
    return (head.rsplit(' · ', 1)[0] if ' · ' in head else head.rsplit(' ', 1)[0]).rstrip(' ·,/(=')


CHIP_MAX = 34      # 이보다 길면 칩이 두 줄로 흘러 안 읽힙니다


def chips(warn, desc, have):
    """주의 문구 → 칩. 설명에 이미 있는 말과 자기들끼리 겹치는 말을 걷어냅니다."""
    out = list(have)
    for w in warn:
        w = w.strip()
        if len(w) < 5:                       # '3박' '여권' '무료' — 혼자서는 뜻이 없습니다
            continue
        if desc and same(w) in same(desc):   # 바로 위 설명에 이미 있는 말
            continue
        hit = next((y for y in out if same(w) in same(y) or same(y) in same(w)), None)
        if hit is None:
            out.append(w)
        else:                                # 겹치면 긴 쪽, 단 너무 길어졌으면 짧은 쪽
            pick = min(w, hit, key=len) if max(len(w), len(hit)) > CHIP_MAX else max(w, hit, key=len)
            out[out.index(hit)] = pick
    return out[:5]


def sim(a, b):
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


def build(src, pool, used, fresh):
    """시트 항목 하나 → data.json 항목."""
    it = {'time': src['time']}
    desc, warn = split_notes(src['raw'])
    if desc:
        it['desc'] = cut(' · '.join(desc), 180)
    if '⭐' in src['raw'] or '★' in src['raw']:
        it['star'] = True

    best, bi, bs = None, -1, 0.0
    sheet_name = clean(src['name'])
    for i, old in enumerate(pool):
        if i in used:
            continue
        sc = sim(sheet_name, old['name'])
        if old['time'] == src['time']:
            sc += 0.35
        if sc > bs:
            best, bi, bs = old, i, sc

    if best and bs > 0.60:
        used.add(bi)
        it['name'] = best['name']            # ← 다듬어 온 이름을 씁니다
        for k in CARRY:
            if k in best:
                it[k] = best[k]
        if not it.get('desc') and best.get('desc'):
            it['desc'] = best['desc']
        if best.get('star'):
            it['star'] = True
    else:
        it['name'] = trim_name(sheet_name)[:58]
        fresh.append((src['time'], it['name']))

    got = chips(warn, it.get('desc') or '', it.get('prep') or [])
    if got:
        it['prep'] = got
    else:
        it.pop('prep', None)
    return {k: it[k] for k in ORDER if k in it}


def main(path):
    sh = load(path)
    D = json.loads((ROOT / 'data.json').read_text(encoding='utf-8'))
    fresh_all, rows = [], []

    for day in D['days']:
        date = day['date']
        common, opts = parse_day(sh, date)

        # 9/13 은 자정을 넘겨 9/14 새벽까지 서술돼 있습니다
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

        pool = list(day['items']) + [i for o in (day.get('options') or []) for i in o['items']]
        used, fresh = set(), []
        day['items'] = [build(s, pool, used, fresh) for s in common]

        new_opts = []
        old_opts = {o['id']: o for o in (day.get('options') or [])}
        for x in opts:
            key = (date, x['letter'])
            oid, label = OPT_ID.get(key, (x['letter'].lower(), clean(x['title'])[:24]))
            o = {'id': oid, 'label': label}
            if key in RECOMMENDED:
                o['recommended'] = True
            prev = old_opts.get(oid) or {}
            o['summary'] = (clean(x['title']).strip(' —·-') or prev.get('summary', ''))[:60]
            if prev.get('cash'):
                o['cash'] = prev['cash']
            o['items'] = [build(s, pool, used, fresh) for s in x['items']]
            new_opts.append(o)
        if new_opts:
            day['options'] = new_opts
        else:
            day.pop('options', None)

        n = len(day['items']) + sum(len(o['items']) for o in new_opts)
        rows.append((date, n, len(used), len(pool), len(fresh)))
        fresh_all += [(date, t, nm) for t, nm in fresh]

    # 이름·설명에 남은 장식 정리
    for day in D['days']:
        for it in day['items'] + [i for o in (day.get('options') or []) for i in o['items']]:
            for f in ('name', 'desc'):
                if it.get(f):
                    it[f] = clean(it[f])
            if it.get('prep'):
                it['prep'] = [clean(x) for x in it['prep'] if clean(x)]

    (ROOT / 'data.json').write_text(
        json.dumps(D, ensure_ascii=False, indent=1), encoding='utf-8')

    print(f"{'날짜':<12}{'항목':>4}  이어받음/기존  새 항목")
    for d, n, u, p, f in rows:
        print(f"{d:<12}{n:>4}  {u:>6}/{p:<6} {f if f else ''}")
    print(f"\n합계 {sum(r[1] for r in rows)}개 · 이어받음 {sum(r[2] for r in rows)}"
          f"/{sum(r[3] for r in rows)}")
    if fresh_all:
        print(f"\n※ 시트에서 이름을 새로 뽑은 항목 {len(fresh_all)}개 — 확인이 필요합니다")
        for d, t, nm in fresh_all:
            print(f"   {d} {t}  {nm}")


if __name__ == '__main__':
    main(sys.argv[1])
