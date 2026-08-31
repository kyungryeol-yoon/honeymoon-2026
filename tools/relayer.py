# -*- coding: utf-8 -*-
"""시트에 없어서 재생성 때 사라진 층을 예전 data.json 에서 다시 얹습니다.

  python3 tools/relayer.py <예전_data.json>

sheet_rebuild.py 는 시트에 있는 것만 씁니다. 그런데 한마디·음식 가격·지도
검색어·이동수단 같은 것은 시트에 없고 앱에서만 관리해 온 것이라 그냥 두면
"뭐 먹지" · "이 말 하면 돼" 칩이 통째로 꺼집니다.

시트가 진실인 것(이름·설명·주의·옵션·숙소·예약상태)은 **건드리지 않습니다.**

항목 짝짓기는 (날짜, 시각, 이름) 이 모두 같을 때만 place·move 를 얹습니다.
시각만 같고 이름이 다른 항목은 재생성이 이름을 바꾼 쪽이라, 거기에 옛
place 를 붙이면 엉뚱한 장소로 보냅니다. star 는 그 위험이 없어 시각만
같아도 얹습니다.
"""
import json, re, sys, difflib, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
from sheet_sync import norm      # noqa: E402

# 이름까지 같아야 얹는 것 (엉뚱한 장소로 보내면 안 되는 것)
STRICT = ('place', 'move', 'links')
# 시각만 같아도 얹는 것
LOOSE = ('star',)

ORDER = ('time', 'end', 'name', 'kind', 'booked', 'food', 'gift', 'say', 'desc',
         'place', 'map', 'move', 'meet', 'prep', 'refs', 'star', 'links',
         'tz', 'tzl', 'endTz')


def allit(day):
    return day['items'] + [i for o in (day.get('options') or []) for i in o['items']]


def main(old_path):
    new = json.loads((ROOT / 'data.json').read_text(encoding='utf-8'))
    old = json.loads(pathlib.Path(old_path).read_text(encoding='utf-8'))
    O = {x['date']: x for x in old['days']}
    n = dict(place=0, move=0, star=0, chips=0, price=0, skipped=0)
    skipped = []

    for day in new['days']:
        o = O.get(day['date'])
        if not o:
            continue
        pool = allit(o)
        used = set()
        for it in allit(day):
            # 1순위 — 시각도 이름도 같은 항목
            hit = next((j for j, x in enumerate(pool)
                        if j not in used and x['time'] == it['time']
                        and norm(x['name']) == norm(it['name'])), None)
            strict_ok = hit is not None
            if hit is None:
                hit = next((j for j, x in enumerate(pool)
                            if j not in used and x['time'] == it['time']), None)
            if hit is None:
                continue
            used.add(hit)
            src = pool[hit]
            if strict_ok:
                for f in STRICT:
                    if f in src and f not in it:
                        it[f] = src[f]
                        n[f] = n.get(f, 0) + 1
            elif any(f in src for f in STRICT):
                n['skipped'] += 1
                skipped.append((day['date'], it['time'], src['name'], it['name']))
            for f in LOOSE:
                if f in src and f not in it:
                    it[f] = src[f]
                    n[f] += 1

        # 하루 전체에 걸리는 주의 — 항목과 무관하므로 그대로 옮깁니다
        if o.get('chips') and not day.get('chips'):
            day['chips'] = o['chips']
            n['chips'] += len(o['chips'])

    # 한마디 — 시트에 한 글자도 없습니다
    if old.get('phrases'):
        new['phrases'] = old['phrases']

    # 음식 값 — 시트의 음식 표에는 가격이 없어 "뭐 먹지" 카드가 빕니다.
    # 표기가 조금씩 달라("파 암 토마켓" / "빠 암 토마켓") 이름이 정확히 같은
    # 것만 찾으면 절반도 못 붙습니다. 비슷한 이름끼리 이어 줍니다.
    for cid, pack in (new.get('food') or {}).items():
        src = ((old.get('food') or {}).get(cid) or {}).get('eat') or []
        dst = pack.setdefault('eat', [])
        taken = set()
        for x in dst:
            best, br = None, 0.0
            for j, y in enumerate(src):
                if j in taken:
                    continue
                r = difflib.SequenceMatcher(None, norm(x['n']), norm(y['n'])).ratio()
                if r > br:
                    best, br, bj = y, r, j
            if not best or br < 0.62:
                continue
            taken.add(bj)
            for f in ('price', 'where', 'note'):
                if best.get(f) and not x.get(f):
                    x[f] = best[f]
                    if f == 'price':
                        n['price'] += 1
        # 시트 목록에 아예 없는데 값이 적혀 있던 메뉴는 뒤에 붙입니다
        for j, y in enumerate(src):
            if j not in taken and y.get('price'):
                dst.append(y)
                n['added'] = n.get('added', 0) + 1
        for f in ('tips', 'cardNote'):
            s = ((old.get('food') or {}).get(cid) or {}).get(f)
            if s and not pack.get(f):
                pack[f] = s

    # 기념품 — 시트에 없는 '사는 곳'(spots)·주의(tips)
    for cid, pack in (new.get('gift') or {}).items():
        src = (old.get('gift') or {}).get(cid) or {}
        for f in ('spots', 'tips'):
            if src.get(f) and not pack.get(f):
                pack[f] = src[f]

    for day in new['days']:
        day['items'] = [{k: i[k] for k in ORDER if k in i} for i in day['items']]
        for o_ in day.get('options') or []:
            o_['items'] = [{k: i[k] for k in ORDER if k in i} for i in o_['items']]

    (ROOT / 'data.json').write_text(
        json.dumps(new, ensure_ascii=False, indent=1), encoding='utf-8')

    print("다시 얹음 — " + " · ".join(f"{k} {v}" for k, v in n.items() if k != 'skipped'))
    if skipped:
        print(f"\n※ 이름이 달라 place·move 를 안 얹은 항목 {len(skipped)}개 — 확인하세요")
        for d, t, a, b in skipped:
            print(f"   {d} {t}\n      옛 {a[:44]}\n      새 {b[:44]}")


if __name__ == '__main__':
    main(sys.argv[1])
