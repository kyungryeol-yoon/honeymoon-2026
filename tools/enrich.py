# -*- coding: utf-8 -*-
"""시트에 없고 앱에서만 쓰는 정보를 채웁니다 (이미 있는 항목은 건드리지 않음).

  python3 tools/enrich.py

  kind    일정 종류 — 이름 앞 이모지를 고릅니다
  map     장소가 아닌 항목의 지도 링크 끄기
  food/say/gift  칩 플래그

sheet_sync.py 로 시트를 다시 읽은 뒤에 돌리면, 새로 생긴 항목만 채워집니다.
"""
import json, re, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

# 위에서부터 처음 걸리는 것이 종류가 됩니다. 이름으로 먼저 보고, 이름이
# 아무것도 말해주지 않을 때만 설명을 봅니다 — 합쳐서 보면 설명 속 단어가
# 종류를 정해버립니다 ("Giessbach 폭포" 가 설명의 열차 이야기 때문에 train 이 되는 식).
RULES = [
    ('wedding', r'결혼식'),
    ('flight',  r'항공|ICN|DOH|BCN → |FCO → |PRG → |탑승 수속|위탁 수하물|출국심사|입국심사'
                r'|면세점|게이트|보안검사|체크인 · 위탁|짐 수취|짐 찾기|수하물'),
    ('boat',    r'바포레토|승선|곤돌라 탑승|수상|Line \d+|무라노|부라노|Fondamente|선착장|유람|본섬'),
    ('church',  r'성당|대성당|교회|수도원|바실리카|Basilica|사그라다|두오모|성 비투스|프라리'
                r'|산 마르코|검은 성모|세례당|대신도회당|산 피에트로 인 빈콜리|산 루이지'
                r'|산타 마리아|산 조르조|산 로코'),
    ('train',   r'열차|기차|메트로|지하철|Metro|Regionale|Leonardo Express|RegioJet|EC \d'
                r'|톱니바퀴|SMN|Termini|Mestre|푸니쿨라|La Spezia|Rossore|Pisa Centrale'
                r'|Centrale 도착|하차|승차|플랫폼'),
    ('taxi',    r'택시|Bolt|Uber|우버'),
    ('cable',   r'곤돌라|케이블카|리프트|Gondelbahn|융프라우요흐|Männlichen|묀리헨'),
    ('bus',     r'버스|Aerobús|Aerobus|6770|셔틀'),
    ('car',     r'렌터카|Hertz|주유|반납|드라이브|고갯길|터널 통과|Pass\b|출발 →'),
    ('tour',    r'투어|가이드|미팅|모임'),
    ('stay',    r'체크인|체크아웃|캠프 셋업|텐트 셋업|텐트 철수|캠프 정리|숙소|호텔 복귀|캠프 복귀'),
    ('meal',    r'조식|점심|저녁|디너|브런치|식사|맛집|레스토랑|트라토리아|치케티|젤라또|카페|간식|요기'),
    ('museum',  r'미술관|박물관|갤러리|Accademia|우피치|보르게세|Uffizi'),
    ('ruins',   r'콜로세움|포로 로마노|유적|판테온|Pantheon|성벽|고성|성 외관|castel|Castel'
                r'|왕궁|궁전|황금소로|산탄젤로|카를교|크룸로프 성|Bellinzona 성|프라하성'
                r'|얼음 궁전|치비타'),
    ('nature',  r'호수|폭포|협곡|빙하|공원|전망대|조망|해변|호숫가|Falls|see$|See\b|평원'),
    ('photo',   r'사진|풍경길|평원 감상|포토'),
    ('walk',    r'산책|도보|골목|거리|광장|시장|구경|야경|다리$|다리 '),
    ('shop',    r'마트|쇼핑|구매|기념품|Migros|Coop|ATM|환전|인출|환급'),
    ('rest',    r'기상|취침|휴식|낮잠|빨래|장비 정리|짐 정리|짐 점검|알람|세면|충전|옷 갈아입기|내일 준비'),
]

# 눌렀을 때 갈 데가 없는 항목 — 지도 링크를 만들지 않습니다
NOT_A_PLACE = re.compile(
    r'기상|취침|휴식|세면|백팩|짐|캐리어|점검|정리|준비|확인|조식|점심|저녁|디너|간식|요기'
    r'|출발|이동|복귀|도착|하산|승차|하차|탑승|퇴장|입장|보안검사|출국심사|입국심사|수하물'
    r'|면세점|게이트|구매|인출|환급|산책|구경|종료|시작|셋업|철수|체크인|체크아웃|주유|카페$')
# 위에 걸려도 이름 안에 진짜 지명이 있어 남겨야 하는 것
KEEP_PLACE = re.compile(
    r'구엘|사그라다|몬세라트|지로나|세례당|두오모|Mercato|판테온|Bellinzona|Furka|Grimsel'
    r'|Badestelle|Neuhaus|Iseltwald|Klementinum|황금소로|구 왕궁|카를교|리오마조레|마나롤라'
    r'|피엔차|나보나|루가노 호수|Trümmelbach|Blausee|Wengen|Oeschinensee')

MEAL_CHIP = re.compile(r'점심|저녁|디너|요기|치케티|젤라또')


def classify(it):
    if it.get('meet'):
        return 'tour'
    for source in (it.get('name', ''), it.get('desc', '')):
        if not source:
            continue
        for kind, pat in RULES:
            if re.search(pat, source):
                return kind
    return None


def main():
    d = json.loads((ROOT / 'data.json').read_text(encoding='utf-8'))
    menus = {c: [x for x in (p.get('eat') or []) if x.get('price')]
             for c, p in (d.get('food') or {}).items()}
    langs = set(d.get('phrases') or {})
    city_lang = {c['id']: c.get('lang') for c in d['cities']}
    n = dict(kind=0, map=0, food=0, say=0)

    for day in d['days']:
        cid = day['city']
        groups = [day['items']] + [o['items'] for o in (day.get('options') or [])]
        for items in groups:
            for it in items:
                if not it.get('kind'):
                    k = classify(it)
                    if k:
                        it['kind'] = k
                        n['kind'] += 1
                if it.get('map') is not False and not it.get('place'):
                    if NOT_A_PLACE.search(it['name']) and not KEEP_PLACE.search(it['name']):
                        it['map'] = False
                        n['map'] += 1
                if it.get('kind') == 'meal' and MEAL_CHIP.search(it['name']) \
                        and '캠프' not in it['name']:
                    if not it.get('food') and menus.get(cid):
                        it['food'] = True
                        n['food'] += 1
                    if not it.get('say') and city_lang.get(cid) in langs:
                        it['say'] = True
                        n['say'] += 1
                # 데이터가 없는 도시에 칩이 붙으면 빈 카드가 됩니다
                if it.get('food') and not menus.get(cid if it['food'] is True else it['food']):
                    it.pop('food')
                if it.get('say') and city_lang.get(cid) not in langs:
                    it.pop('say')

    ORDER = ('time', 'end', 'name', 'kind', 'booked', 'food', 'gift', 'say', 'desc',
             'place', 'map', 'move', 'meet', 'prep', 'refs', 'star', 'links',
             'tz', 'tzl', 'endTz')
    for day in d['days']:
        day['items'] = [{k: it[k] for k in ORDER if k in it} for it in day['items']]
        for o in day.get('options') or []:
            o['items'] = [{k: it[k] for k in ORDER if k in it} for it in o['items']]

    (ROOT / 'data.json').write_text(
        json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')
    print("새로 채움 — " + " · ".join(f"{k} {v}" for k, v in n.items()))


if __name__ == '__main__':
    main()
