#!/usr/bin/env bash
# 배포 전 준비 — 커밋하기 전에 이걸 한 번 돌리면 됩니다.
#
#   ./tools/release.sh
#
#  1. data.json 문법 검사
#  2. 예약번호·이메일 같은 민감정보가 섞여 들어갔는지 검사 (저장소가 public)
#  3. index.html 안의 인라인 백업 데이터 갱신
#  4. service-worker.js 의 VERSION 자동 증가
#     ← 이게 안 올라가면 캐시가 교체되지 않아 폰에 옛날 화면이 그대로 뜹니다
set -euo pipefail
cd "$(dirname "$0")/.."

echo "1) data.json 검사"
python3 - <<'PY'
import json, sys
d = json.load(open('data.json', encoding='utf-8'))
assert d['trip']['start'] and d['trip']['end'], 'trip 날짜 없음'
assert d['cities'] and d['days'], 'cities/days 비어 있음'
seen = set()
for day in d['days']:
    assert day['date'] not in seen, f"날짜 중복: {day['date']}"
    seen.add(day['date'])
    assert day['items'], f"{day['date']} 일정 없음"
    ids = {c['id'] for c in d['cities']}
    assert day['city'] in ids, f"{day['date']} 알 수 없는 도시: {day['city']}"
    times = [i['time'] for i in day['items']]
    assert times == sorted(times), f"{day['date']} 일정이 시간순이 아님"
    # 선택 가능한 일정
    opts = day.get('options') or []
    assert sum(1 for o in opts if o.get('recommended')) <= 1, \
        f"{day['date']} 추천 옵션이 둘 이상"
    ids = [o['id'] for o in opts]
    assert len(ids) == len(set(ids)), f"{day['date']} 옵션 id 중복"
    for o in opts:
        assert o.get('label') and o.get('items'), f"{day['date']}/{o.get('id')} label·items 필요"
        mt = sorted(day['items'] + o['items'], key=lambda i: i['time'])
        mts = [i['time'] for i in mt]
        assert mts == sorted(mts), f"{day['date']}/{o['id']} 병합 후 시간 역순"

# 먹을 곳 · 기념품 — 도시 id 로 찾으므로 오타가 나면 그 도시만 조용히 사라집니다
ids = {c['id'] for c in d['cities']}
n_eat = n_buy = 0
for key, groups in (('food', ('spots',)), ('gift', ('buy',))):
    for cid, pack in (d.get(key) or {}).items():
        assert cid in ids, f"{key}: 알 수 없는 도시 {cid}"
        assert pack.get('name'), f"{key}/{cid} name 없음"
        # 칩 목록 (food.eat 는 평평, gift.buy 는 그룹)
        flat = pack.get('eat') or []
        for g in pack.get('buy') or []:
            flat += g.get('list') or []
        for x in flat:
            assert x.get('n'), f"{key}/{cid} 이름 없는 항목"
        # 지도로 보내는 줄
        rows = []
        for g in pack.get('spots') or []:
            rows += (g.get('list') or []) if isinstance(g, dict) and 'list' in g else [g]
        for x in rows:
            assert x.get('n'), f"{key}/{cid} 이름 없는 장소"
            q = x.get('q') or x['n']
            assert not any('가' <= ch <= '힣' for ch in q), \
                f"{key}/{cid} 지도 검색어에 한글: {q!r} → q 에 현지 표기를 적으세요"
        n_eat += len(flat); n_buy += len(rows)
print(f"   OK — {len(d['days'])}일 / {sum(len(x['items']) for x in d['days'])}개 일정"
      f" / 먹을거리·물건 {n_eat} · 장소 {n_buy}")
PY

echo "2) 민감정보 검사"
python3 - <<'PY'
import json, re, sys
d = json.load(open('data.json', encoding='utf-8'))
raw = open('data.json', encoding='utf-8').read()

# 편명·열차번호는 공개 시간표 정보라 가릴 필요가 없습니다
SAFE_LABELS = {'편명', '열차', '좌석', '터미널', '게이트'}
hits = []

for day in d['days']:
    for it in day['items']:
        for r in it.get('refs', []):
            v = r.get('value')
            if not v or r.get('mask'):
                continue
            if r.get('label') in SAFE_LABELS:
                continue
            hits.append(f"{day['date']} {it['time']} · {r.get('label','?')}: {v}"
                        "  → mask:true 를 붙이거나 값을 빼세요")

for m in set(re.findall(r'[\w.+-]+@[\w.-]+\.\w+', raw)):
    hits.append(f"이메일 노출: {m}")

# 색상 코드(#RRGGBB)를 뺀 긴 숫자열 = 예약번호일 가능성
for m in set(re.findall(r'(?<!#)\b\d{8,}\b', raw)):
    hits.append(f"8자리 이상 숫자: {m}")

if hits:
    print("   경고 — 저장소가 public 입니다:")
    for h in hits: print("     ", h)
    sys.exit(1)
print("   OK — 노출된 예약번호·이메일 없음")
PY

echo "3) 인라인 백업 갱신"
python3 tools/build-fallback.py | sed 's/^/   /'

echo "4) service-worker VERSION 증가"
cur=$(grep -o "const VERSION = 'v[0-9]*'" service-worker.js | grep -o '[0-9]*')
next=$((cur + 1))
sed -i '' "s/const VERSION = 'v${cur}';/const VERSION = 'v${next}';/" service-worker.js
echo "   v${cur} → v${next}"

echo
echo "완료. 이제 커밋·푸시하세요."
