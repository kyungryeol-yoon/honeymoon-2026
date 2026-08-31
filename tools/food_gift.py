# -*- coding: utf-8 -*-
"""시트 아래쪽의 도시별 표(꼭 먹어볼 음식 · 추천 식당 · 기념품·쇼핑)를 읽습니다.

sheet_rebuild.py 가 부릅니다. 단독으로 돌리면 무엇이 나오는지 찍어봅니다.

  python3 tools/food_gift.py <시트를_받아둔_json>

시트 배치가 도시마다 다릅니다 —
  바르셀로나·스위스·프라하  한 칸에 한 섹션 (음식 | 식당 | 체험 | 기념품 | 주의)
  이탈리아 세 도시          한 칸에 다섯 섹션이 모두 (베네치아 | 피렌체 | 로마)
그래서 칸 위치가 아니라 **본문의 섹션 제목**으로 가릅니다.
"""
import json, re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
from sheet_parse import squash, SEP, MOJI      # noqa: E402
from sheet_sync import clean                    # noqa: E402

CITY_OF = {'바르셀로나': 'bcn', '스위스': 'swi', '베네치아': 'vce',
           '피렌체': 'flr', '로마': 'rom', '프라하': 'prg'}

# 섹션 제목 — 이모지가 깨져 들어오므로 한글 낱말로만 찾습니다.
# '체험' 은 쓰지 않지만 **반드시 잘라내야** 합니다. 안 그러면 앞 섹션(식당)에
# 딸려 들어가 "베네치아 체험" 이 식당 목록에 섞입니다.
CITY_RE = r'(?:바르셀로나|스위스|베네치아|피렌체|로마|프라하)'
SECTION = [
    ('eat',   re.compile(r'(?:필수|꼭 먹어볼)\s*음식')),
    ('spots', re.compile(r'추천\s*식당')),
    ('exp',   re.compile(CITY_RE + r'\s*(?:추천\s*)?체험')),
    ('buy',   re.compile(r'기념품')),
    ('tips',  re.compile(r'(?:식당\s*팁|주의\s*사항)')),
]
LATIN = re.compile(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9'’&.\- ]{2,}")


def cells(path):
    """표의 모든 칸 — 항목 경계(여러 칸 공백)를 SEP 로 살려서."""
    content = json.load(open(path, encoding='utf-8'))['fileContent']
    for row in content.split('\n'):
        if not row.startswith('|'):
            continue
        yield [squash(c) for c in row.strip('|').split('|')]


def split_sections(cell):
    """한 칸 → {섹션키: 본문}. 제목이 나온 지점부터 다음 제목 앞까지."""
    marks = []
    for key, pat in SECTION:
        for m in pat.finditer(cell):
            marks.append((m.start(), key))
    marks.sort()
    out = {}
    for i, (pos, key) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(cell)
        out.setdefault(key, '')
        out[key] += ' ' + cell[pos:end]
    return out


def rows_of(text):
    """섹션 본문 → [(그룹, 이름, 설명, 별)]. 항목은 '\\-' 로 시작합니다."""
    out, group = [], None
    for seg in text.split(SEP):
        seg = seg.strip()
        if not seg:
            continue
        if '\\-' not in seg:
            g = clean(seg)
            # 섹션 제목 줄은 그룹이 아닙니다
            if g and not any(p.search(g) for _, p in SECTION) and len(g) <= 24:
                group = g
            continue
        head, *items = seg.split('\\-')
        head = clean(head)
        if head and not any(p.search(head) for _, p in SECTION) and len(head) <= 24:
            group = head
        for raw in items:
            star = '⭐' in raw or '★' in raw
            t = clean(raw)
            if not t:
                continue
            # "이름 (부연) - 설명"
            m = re.match(r'^(.{2,60}?)\s*[-—]\s*(.+)$', t)
            name, desc = (m.group(1), m.group(2)) if m else (t, '')
            sub = ''
            m2 = re.match(r'^(.+?)\s*\(([^)]{2,40})\)\s*$', name)
            if m2:
                name, sub = m2.group(1).strip(), m2.group(2).strip()
            out.append((group, name.strip(' ·'), sub, desc.strip(' ·'), star))
    return out


def has_ko(s):
    return any('가' <= ch <= '힣' for ch in s)


def pack_eat(rows):
    """꼭 먹어볼 음식 — 시트에 값이 없어 price 는 넣지 않습니다."""
    out = []
    for group, n, sub, d, star in rows:
        if not n or len(n) > 40:
            continue
        x = {'n': n}
        # 원어 이름은 설명 앞에 붙여 둡니다 (지도 검색용이 아니라 읽기용)
        parts = [p for p in (sub, d) if p]
        if parts:
            x['d'] = ' · '.join(parts)[:70]
        if star:
            x['star'] = True
        out.append(x)
    return out


def pack_spots(rows):
    """지도로 보내는 줄 — 이름이 한글이면 검색이 안 되므로 q 를 만들어 줍니다."""
    groups, seen = [], set()
    for group, n, sub, d, star in rows:
        if not n or len(n) > 44 or n in seen:
            continue
        x = {'n': n}
        if has_ko(n):
            m = LATIN.search(n) or LATIN.search(sub) or LATIN.search(d)
            if not m:
                continue                      # 지도로 보낼 수 없으면 버립니다
            x['q'] = m.group(0).strip()
        seen.add(n)
        if sub:
            x['a'] = sub[:30]
        if d:
            x['d'] = d[:60]
        if star:
            x['star'] = True
        g = next((y for y in groups if y['g'] == (group or '')), None)
        if not g:
            g = {'g': group or '', 'list': []}
            groups.append(g)
        g['list'].append(x)
    for g in groups:
        if not g['g']:
            del g['g']
    return groups


def pack_buy(rows):
    groups = []
    for group, n, sub, d, star in rows:
        if not n or len(n) > 40:
            continue
        x = {'n': n}
        parts = [p for p in (sub, d) if p]
        if parts:
            x['d'] = ' · '.join(parts)[:60]
        if star:
            x['star'] = True
        g = next((y for y in groups if y['g'] == (group or '기념품')), None)
        if not g:
            g = {'g': group or '기념품', 'list': []}
            groups.append(g)
        g['list'].append(x)
    return groups


TAIL_TITLE = re.compile(r'\s*(?:' + CITY_RE + r'\s*)?(?:주의\s*사항|기념품|추천\s*식당'
                        r'|필수\s*음식|추천\s*체험|체험)\s*$')


def pack_tips(rows):
    """마지막 항목에는 다음 섹션 제목이 꼬리로 붙습니다 (칸이 이어 붙어서)."""
    out = []
    for group, n, sub, d, star in rows:
        t = ' · '.join(p for p in (n, sub, d) if p)
        t = TAIL_TITLE.sub('', t).strip(' ·')
        if 6 <= len(t) <= 80:
            out.append(t)
    return out[:8]


def parse_tables(path):
    """→ (food, gift). 도시 id 로 찾으므로 없는 도시는 빠집니다."""
    buckets = {}          # cid → {키: 본문}
    for row in cells(path):
        for cell in row:
            if len(cell) < 120:
                continue
            # 이 칸이 어느 도시 이야기인가 — 본문에 나오는 도시 이름
            cid = None
            for kw, c in CITY_OF.items():
                if re.search(kw + r'\s*(?:필수|추천|체험|기념품|주의)', cell):
                    cid = c
                    break
            if not cid:
                continue
            for key, body in split_sections(cell).items():
                buckets.setdefault(cid, {}).setdefault(key, '')
                buckets[cid][key] += ' ' + body

    food, gift = {}, {}
    names = {c: k for k, c in CITY_OF.items()}
    for cid, sec in buckets.items():
        eat   = pack_eat(rows_of(sec.get('eat', '')))
        spots = pack_spots(rows_of(sec.get('spots', '')))
        tips  = pack_tips(rows_of(sec.get('tips', '')))
        if eat or spots:
            food[cid] = {'name': names[cid]}
            if eat:
                food[cid]['eat'] = eat
            if spots:
                food[cid]['spots'] = spots
            if tips:
                food[cid]['tips'] = tips
        buy = pack_buy(rows_of(sec.get('buy', '')))
        if buy:
            gift[cid] = {'name': names[cid], 'buy': buy}
    return food, gift


if __name__ == '__main__':
    f, g = parse_tables(sys.argv[1])
    for cid in f:
        n_sp = sum(len(x['list']) for x in f[cid].get('spots', []))
        print(f"food[{cid}]  먹을것 {len(f[cid].get('eat', [])):>2} · "
              f"식당 {n_sp:>2} · 팁 {len(f[cid].get('tips', []))}")
    for cid in g:
        print(f"gift[{cid}]  {sum(len(x['list']) for x in g[cid]['buy'])}개")
