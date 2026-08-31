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
from sheet_sync import norm, same, cut      # noqa: E402

# 이름까지 같아야 얹는 것 — 엉뚱한 항목에 붙으면 사람을 딴 데로 보냅니다
STRICT = ('place', 'move', 'links', 'meet', 'refs', 'end')
# 시각만 같아도 안전한 것
LOOSE = ('star', 'booked', 'kind', 'food', 'say', 'gift')


def akin(k1, k2):
    """같은 말인가. 예약번호는 라벨이 달라도("PNR: 메일에서 확인" /
       "예약번호는 메일에서 확인") 같은 뜻이라 한 번만 남깁니다."""
    if k1 in k2 or k2 in k1:
        return True
    return k1.endswith('메일에서확인') and k2.endswith('메일에서확인')


def head_token(s):
    m = re.match(r'[A-Za-zÀ-ÿ]{4,}|[가-힣]{2,}', s.strip())
    return m.group(0).lower() if m else ''


def same_by_place(old_it, new_it):
    """이름 말고 다른 신호로 같은 항목인지 — 첫 낱말이 같거나,
       옛 place 가 새 이름의 앞머리와 이어지거나."""
    a, b = head_token(old_it['name']), head_token(new_it['name'])
    if a and a == b:
        return True
    pl = head_token(old_it.get('place') or '')
    return bool(pl) and bool(b) and (pl.startswith(b) or b.startswith(pl))


def merge_desc(a, b):
    """옛 설명 + 새 설명. 시트가 더 짧게 쓴 경우가 많아("막차" vs
       "막차 · 8월 말 예매 필수") 새 것만 두면 내용이 깎입니다.
       겹치는 조각은 **더 긴 쪽**을 남깁니다."""
    parts = []                              # [(열쇠, 원문)]
    for src in (b, a):                      # 새 것 먼저 (시트가 기준)
        for t in (src or '').split(' · '):
            t = t.strip()
            k = same(t)
            if not k:
                continue
            hit = next((i for i, (k2, _) in enumerate(parts) if akin(k, k2)), None)
            if hit is None:
                parts.append((k, t))
            elif len(t) > len(parts[hit][1]):
                parts[hit] = (k, t)
    return cut(' · '.join(t for _, t in parts), 180)


def merge_prep(a, b, desc):
    """옛 칩 + 새 칩. 옛것이 사람이 다듬은 순서라 앞에 둡니다."""
    out = []                                # [(열쇠, 원문)]
    for t in list(a or []) + list(b or []):
        t = t.strip()
        k = same(t)
        if not k or len(t) < 5:
            continue
        if desc and k in same(desc):        # 설명에 이미 있는 말
            continue
        hit = next((i for i, (k2, _) in enumerate(out) if akin(k, k2)), None)
        if hit is None:
            out.append((k, cut(t, 38)))
        elif len(t) > len(out[hit][1]):
            out[hit] = (k, cut(t, 38))
    # 한 번 훑는 것으로는 부족합니다 — 나중에 들어온 긴 조각이 앞의 여러
    # 조각을 한꺼번에 덮는 경우가 있어(9/28 트레비) 다시 한 번 걷어냅니다.
    return dedup([t for _, t in out])[:5]


def dedup(items):
    out = []
    for t in items:
        k = same(t)
        if any(akin(k, same(y)) for y in out):
            out = [y if not akin(k, same(y)) or len(y) >= len(t) else t for y in out]
            continue
        out.append(t)
    return out

ORDER = ('time', 'end', 'name', 'kind', 'booked', 'food', 'gift', 'say', 'desc',
         'place', 'map', 'move', 'meet', 'prep', 'refs', 'star', 'links',
         'tz', 'tzl', 'endTz')


def allit(day):
    return day['items'] + [i for o in (day.get('options') or []) for i in o['items']]


def main(old_path):
    new = json.loads((ROOT / 'data.json').read_text(encoding='utf-8'))
    old = json.loads(pathlib.Path(old_path).read_text(encoding='utf-8'))
    O = {x['date']: x for x in old['days']}
    n = dict(place=0, move=0, meet=0, refs=0, end=0, star=0, booked=0,
             desc=0, prep=0, chips=0, price=0, skipped=0)
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
            # 이름이 정확히 같지 않아도, 한쪽이 다른 쪽에 통째로 들어 있으면
            # 같은 항목입니다 — 재생성이 이름에서 값을 떼어냈을 뿐입니다.
            #   옛 "몬세라트 대성당 €9/인 = €18"  새 "몬세라트 대성당"
            # 반대로 9/19 는 옵션 순서가 달라 "Iseltwald 도착" 과
            # "Rosenlaui 빙하 협곡" 이 만나는데, 포함 관계가 아니라 안 걸립니다.
            if hit is None:
                hit = next((j for j, x in enumerate(pool)
                            if j not in used and x['time'] == it['time']
                            and len(norm(it['name'])) >= 2
                            and (norm(it['name']) in norm(x['name'])
                                 or norm(x['name']) in norm(it['name']))), None)
            # 이름이 겹치지 않아도 같은 항목인 경우가 있습니다.
            # 9/19 옵션 B 는 옛 이름이 "Iseltwald 도착" 으로 **잘못** 적혀
            # 있었지만 place 는 "Rosenlauischlucht" 로 맞았습니다. 새 이름
            # "Rosenlaui 빙하 협곡" 과 place 가 이어지므로 같은 항목입니다.
            if hit is None:
                hit = next((j for j, x in enumerate(pool)
                            if j not in used and x['time'] == it['time']
                            and same_by_place(x, it)), None)
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
                # 설명·칩은 합칩니다 (시트가 더 짧게 쓴 경우가 많습니다)
                d2 = merge_desc(src.get('desc'), it.get('desc'))
                if d2:
                    if d2 != (it.get('desc') or ''):
                        n['desc'] = n.get('desc', 0) + 1
                    it['desc'] = d2
                # 빈 목록이 나오면 **지워야** 합니다 — 설명에 이미 들어간
                # 말이 칩으로 또 뜨면 화면에서 같은 문장이 두 번 보입니다.
                p2 = merge_prep(src.get('prep'), it.get('prep'), d2)
                if p2 != (it.get('prep') or []):
                    n['prep'] = n.get('prep', 0) + 1
                if p2:
                    it['prep'] = p2
                else:
                    it.pop('prep', None)
            elif any(f in src for f in STRICT):
                n['skipped'] += 1
                skipped.append((day['date'], it['time'], src['name'], it['name']))
            for f in LOOSE:
                if f in src and f not in it:
                    it[f] = src[f]
                    n[f] = n.get(f, 0) + 1

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
