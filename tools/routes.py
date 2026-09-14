#!/usr/bin/env python3
"""교통편 상세 — 무엇을 타고 · 어디서 타서 · 몇 정거장 가서 · 어디서 내리는지.

`move` 는 "메트로 20~25분" 처럼 **수단과 시간만** 적혀 있어서, 정작 현장에서
필요한 것(어느 역에서 타고 몇 번째에 내리는지)이 없었습니다. 그래서 항목에
`route` 를 얹습니다.

    "route": {
      "legs": [
        {"m": "walk",  "min": 5, "note": "호텔 → Urquinaona역"},
        {"m": "metro", "l": "L4", "dir": "Trinitat Nova 방면",
         "f": "Urquinaona", "t": "Passeig de Gràcia", "n": 1, "min": 2}
      ],
      "alt": ["24번 버스 — Pl. Catalunya 승차 → …"]
    }

    m    수단 (walk·metro·bus·tram·train·boat·taxi·car)
    l    노선 이름 그대로 (L3 · 22번 · A선 · Cinque Terre Express)
    dir  방면 — 승강장을 고르는 기준이라 정거장 수만큼 중요합니다
    f/t  타는 곳 / 내리는 곳
    n    정거장 수 (내리는 역까지 몇 번 서는지)
    min  그 구간만의 소요 시간

`move` 와 짝이 되게 **도착하는 항목**에 붙입니다 (화면에서 둘 다 직전 항목
아래에 붙어 "여기서 저기로 어떻게 가는가" 한 덩어리가 됩니다).

시트를 다시 읽은 뒤에도 되살릴 수 있게 표를 코드에 둡니다.

    python3 tools/routes.py            # data.json 에 얹기
    python3 tools/routes.py --check    # 얹힌 상태만 확인 (고치지 않음)

날짜·시각으로 항목을 찾고, 이름이 표와 다르면 **얹지 않고 경고**합니다 —
시트가 바뀌어 항목이 딴 데로 밀렸는데 옛 경로를 붙이면 엉뚱한 역으로
보내게 됩니다 (relayer.py 가 place·move 를 다루는 방식과 같습니다).
"""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data.json"

W = lambda mn, note: {"m": "walk", "min": mn, "note": note}


def ride(m, l, f, t, *, dir=None, n=None, min=None, note=None):
    leg = {"m": m, "l": l, "f": f, "t": t}
    if dir:  leg["dir"]  = dir
    if n:    leg["n"]    = n
    if min:  leg["min"]  = min
    if note: leg["note"] = note
    return leg


# (날짜, 시각): (항목 이름 확인용, move 새로 쓸 것 or None, legs, alt)
ROUTES = {
 # ── 서울 ─────────────────────────────────────────────────────────────
 ("2026-09-13", "22:00"): ("인천공항 T1 도착", "6770 공항버스 · 약 1시간 30분", [
    ride("bus", "6770", "광명역 4번출구", "인천공항 T1", dir="인천공항 방면", n=1, min=90,
         note="중간 정차 없음 · T1 먼저 서고 T2 가 종점 — T1 에서 내릴 것"),
 ], ["T1 하차 지점 = 1층 8번 게이트 앞"]),

 # ── 바르셀로나 ───────────────────────────────────────────────────────
 ("2026-09-14", "16:30"): ("Aerobús → 카탈루냐 광장", "공항버스 A1 · 4정거장 · 35분", [
    W(5, "T1 도착층 나와서 바로 앞 Aerobús 정류장"),
    ride("bus", "A1 Aerobús", "BCN 공항 T1", "Plaça Catalunya (종점)",
         dir="Plaça Catalunya 방면", n=4, min=35,
         note="Pl. Espanya · Gran Via · Pl. Universitat 다음이 종점 · 왕복 €12.85/인"),
 ], ["A2 는 T2 전용 — T1 에서는 A1 만 탑니다"]),

 ("2026-09-14", "17:15"): ("HCC 몽블랑 체크인", "카탈루냐 광장에서 도보 10분", [
    W(10, "Plaça Catalunya → Via Laietana 61 · 큰길 따라 직진"),
 ], []),

 ("2026-09-15", "09:10"): ("구엘 공원 도착",
                           "메트로 4정거장 (L4→L3) · Lesseps 하차 · 오르막 도보 15~20분", [
    W(5, "호텔 → Urquinaona역 (Via Laietana 바로 위)"),
    ride("metro", "L4", "Urquinaona", "Passeig de Gràcia",
         dir="Trinitat Nova 방면", n=1, min=2, note="한 정거장 · T-Familiar 태그"),
    ride("metro", "L3", "Passeig de Gràcia", "Lesseps",
         dir="Trinitat Nova 방면", n=3, min=6, note="Diagonal · Fontana 다음이 Lesseps"),
    W(18, "Travessera de Dalt 오르막 → 공원 정문 (Carrer d'Olot)"),
 ], [
    "언덕이 부담되면 24번 버스 — Pl. Catalunya 승차 → 'Ctra del Carmel - Parc Güell' 하차 "
    "(약 30분) · 공원 옆문 바로 앞이라 오르막이 없습니다",
    "L3 를 Vallcarca 까지 (4정거장) 타면 Baixada de la Glòria 야외 에스컬레이터로 도보 10~15분",
 ]),

 ("2026-09-15", "12:15"): ("구엘 퇴장 → 사그라다 이동",
                           "메트로 4정거장 (L3→L5) · 20~25분", [
    W(12, "공원 정문 → Lesseps역 (내리막)"),
    ride("metro", "L3", "Lesseps", "Diagonal",
         dir="Zona Universitària 방면", n=2, min=4, note="Fontana 다음이 Diagonal"),
    ride("metro", "L5", "Diagonal", "Sagrada Família",
         dir="Vall d'Hebron 방면", n=2, min=4, note="Verdaguer 다음"),
    W(5, "역에서 나오면 성당 · 입구는 Carrer de la Marina 쪽"),
 ], ["92번 버스 — 공원 앞 Ctra del Carmel 승차 → 사그라다 파밀리아 앞 하차 (환승 없이 20~25분)"]),

 ("2026-09-17", "03:40"): ("BCN T1 도착", "공항버스 A1 · 3정거장 · 새벽 35분", [
    W(3, "호텔 → Plaça Catalunya 정류장"),
    ride("bus", "A1 Aerobús", "Plaça Catalunya", "BCN 공항 T1 (종점)",
         dir="T1 방면", n=3, min=35,
         note="Sepúlveda-Urgell · Pl. Espanya 다음이 T1 · 심야 20분 간격"),
 ], ["T2 로 가는 A2 와 정류장이 붙어 있습니다 — 차체의 T1 표시 확인"]),

 # ── 베네치아 ─────────────────────────────────────────────────────────
 ("2026-09-22", "15:30"): ("기차로 본섬 이동", "기차 1정거장 · 10분 · €1.45", [
    W(1, "호텔 → Venezia Mestre역"),
    ride("train", "Regionale", "Venezia Mestre", "Venezia Santa Lucia (종착)",
         dir="Venezia Santa Lucia 방면", n=1, min=10,
         note="다리 건너 바로 다음 역이 종착 · 종이표는 승강장 각인기에 각인"),
 ], []),

 ("2026-09-22", "22:00"): ("기차로 메스트레 복귀", "기차 1정거장 · 10분", [
    ride("train", "Regionale", "Venezia Santa Lucia", "Venezia Mestre",
         dir="Mestre · Padova 방면", n=1, min=10, note="산타루치아에서 첫 정차역이 메스트레"),
    W(1, "역 나와서 호텔"),
 ], []),

 ("2026-09-23", "08:20"): ("Venezia Mestre → 산타루치아역", "기차 1정거장 · 10분", [
    W(1, "호텔 → Venezia Mestre역"),
    ride("train", "Regionale", "Venezia Mestre", "Venezia Santa Lucia (종착)",
         dir="Venezia Santa Lucia 방면", n=1, min=10),
 ], []),

 ("2026-09-23", "09:00"): ("Line 12 승선", "3번 배 · 무라노 직행 20~25분", [
    W(2, "역 나오면 바로 앞 Ferrovia 선착장"),
    ride("boat", "3번", "Ferrovia", "Murano Colonna", dir="Murano 방면", n=1, min=25,
         note="무라노 직행 · 유리공방은 Colonna 쪽에 몰려 있습니다"),
 ], [
    "4.1번 — Ferrovia 승차 → Fondamente Nove 거쳐 Murano Faro 하차 (40~45분)",
    "12번은 Fondamente Nove · Murano Faro 에서만 출발 — 산타루치아에서는 못 탑니다",
 ]),

 ("2026-09-23", "11:00"): ("무라노 → 부라노", "12번 배 2정거장 · 35~40분", [
    W(10, "Colonna → Faro 선착장 (운하 따라 걸어서)"),
    ride("boat", "12번", "Murano Faro", "Burano", dir="Burano · Torcello 방면", n=2, min=40,
         note="Mazzorbo 다음이 부라노 · 30분 간격"),
 ], []),

 ("2026-09-23", "14:00"): ("부라노 → Fondamente Nove", "12번 배 3정거장 · 45분", [
    ride("boat", "12번", "Burano (C 선착장)", "Fondamente Nove (종점)",
         dir="Fondamente Nove 방면", n=3, min=45,
         note="Mazzorbo · Murano Faro 거쳐 종점 · 도착은 B, 출발은 C 선착장"),
 ], []),

 ("2026-09-23", "18:30"): ("Vaporetto 1번선 대운하 야경 크루즈", None, [
    ride("boat", "1번", "San Marco Vallaresso", "Ferrovia", dir="Piazzale Roma 방면",
         n=14, min=40,
         note="대운하 전 구간 · 리알토 · 아카데미아 다 지납니다 · 24시간권 포함"),
 ], ["돌아올 땐 같은 1번을 Lido 방면으로 타면 됩니다"]),

 ("2026-09-23", "22:00"): ("산타루치아역 → Mestre 복귀", "배 25분 + 기차 1정거장", [
    ride("boat", "2번", "San Marco (Vallaresso)", "Ferrovia", dir="Ferrovia · P.le Roma 방면",
         min=27, note="1번보다 정차가 적어 빠릅니다 · 24시간권은 내일 08:20 까지"),
    ride("train", "Regionale", "Venezia Santa Lucia", "Venezia Mestre",
         dir="Mestre · Padova 방면", n=1, min=10),
 ], []),

 # ── 피렌체 · 피사 · 친퀘테레 ─────────────────────────────────────────
 ("2026-09-26", "07:51"): ("Pisa Centrale 도착 — 같은 역 환승", "RV 4011 · 약 50분", [
    ride("train", "RV 4011", "Firenze S.M.Novella", "Pisa Centrale",
         dir="Pisa 방면", min=51, note="중간 정차 있음 · 종착이 아닐 수 있으니 역명 확인"),
 ], []),

 ("2026-09-26", "08:05"): ("Pisa S. Rossore 도착", "지역열차 1정거장 · 5분", [
    ride("train", "R 19336", "Pisa Centrale", "Pisa S. Rossore", n=1, min=5,
         note="바로 다음 역 — 5분이라 놓치기 쉽습니다, 문 앞에서 대기"),
 ], []),

 ("2026-09-26", "08:15"): ("캄포 데이 미라콜리 도착", "S. Rossore역에서 도보 10분", [
    W(10, "역 → 성벽 문 → 두오모 광장 (400m)"),
 ], ["Pisa Centrale 에서 갈 때는 LAM Rossa 버스 → 'Torre 1' 하차 (10~15분) 또는 도보 20~25분"]),

 ("2026-09-26", "11:10"): ("리오마조레", "친퀘테레 익스프레스 1정거장 · 9분", [
    ride("train", "Cinque Terre Express", "La Spezia Centrale", "Riomaggiore",
         dir="Levanto 방면", n=1, min=9, note="다섯 마을 중 첫 마을 · 카드 개시"),
 ], []),

 ("2026-09-26", "12:00"): ("마나롤라", "기차 1정거장 · 3분", [
    ride("train", "Cinque Terre Express", "Riomaggiore", "Manarola",
         dir="Levanto 방면", n=1, min=3),
 ], ["비아 델 아모레 해안 산책로로 걸어가면 15분 (카드에 포함, 평지)"]),

 ("2026-09-26", "14:35"): ("베르나차 도착", "기차 2정거장 · 10분", [
    ride("train", "Cinque Terre Express", "Manarola", "Vernazza",
         dir="Levanto 방면", n=2, min=10, note="코르닐리아 다음이 베르나차"),
 ], ["코르닐리아는 역에서 계단 382개 — 내리지 않습니다"]),

 ("2026-09-26", "16:40"): ("베르나차 → La Spezia", "기차 4정거장 · 20분", [
    ride("train", "Cinque Terre Express", "Vernazza", "La Spezia Centrale",
         dir="La Spezia 방면", n=4, min=20, note="코르닐리아 · 마나롤라 · 리오마조레 다음"),
 ], []),

 # ── 로마 ─────────────────────────────────────────────────────────────
 ("2026-09-28", "08:40"): ("도착해서 근처 카페 대기 권장", "메트로 A선 5정거장 · 10분", [
    W(3, "호텔 → Repubblica역"),
    ride("metro", "A선", "Repubblica", "Ottaviano", dir="Battistini 방면", n=5, min=10,
         note="Barberini · Spagna · Flaminio · Lepanto 다음 · Tap & Go €1.50/인"),
    W(5, "개찰구 → 왼쪽 첫 출구 → 오른쪽 계단 → OKAIDI 간판"),
 ], []),

 ("2026-09-28", "22:00"): ("호텔 복귀", "메트로 A선 2정거장 · 5분", [
    W(3, "스페인 광장 → Spagna역"),
    ride("metro", "A선", "Spagna", "Repubblica", dir="Anagnina 방면", n=2, min=5,
         note="Barberini 다음 · Tap & Go"),
 ], []),

 ("2026-09-29", "08:50"): ("콜로세움 투어 미팅", "메트로 B선 2정거장 · 5분", [
    W(8, "호텔 → 테르미니역"),
    ride("metro", "B선", "Termini", "Colosseo", dir="Laurentina 방면", n=2, min=5,
         note="Cavour 다음 · Tap & Go €1.50/인"),
    W(3, "역에서 나오면 콜로세움 바로 앞 · 인포 포인트"),
 ], []),

 ("2026-09-29", "17:00"): ("보르게세 미술관", "메트로 4정거장 (B→A) + 도보 15분 · 25분", [
    W(5, "몬티 → Cavour역"),
    ride("metro", "B선", "Cavour", "Termini", dir="Rebibbia · Jonio 방면", n=1, min=2),
    ride("metro", "A선", "Termini", "Spagna", dir="Battistini 방면", n=3, min=6,
         note="Repubblica · Barberini 다음"),
    W(15, "Spagna역 'Villa Borghese' 출구(무빙워크) → 공원 가로질러 미술관"),
 ], [
    "시간이 빠듯하면 택시 15분 (€12~15) — 17:00 슬롯은 늦으면 입장 거부입니다",
    "910번 버스 — 테르미니 승차 → 'Pinciana/Museo Borghese' 하차, 미술관 코앞",
 ]),

 ("2026-09-30", "10:00"): ("FCO 공항 도착", "레오나르도 익스프레스 무정차 32분", [
    W(8, "호텔 → 테르미니역 24번 플랫폼 (역 끝이라 멉니다)"),
    ride("train", "Leonardo Express", "Roma Termini", "Fiumicino Aeroporto",
         dir="Fiumicino Aeroporto 방면", n=1, min=32,
         note="중간 정차 없음 · 15분 간격 · €14/인"),
 ], []),

 # ── 프라하 ───────────────────────────────────────────────────────────
 ("2026-10-01", "08:50"): ("프라하성 도착", "메트로 1정거장 + 트램 2정거장 · 25분", [
    W(8, "Celetná → Staroměstská역 (A선)"),
    ride("metro", "A선", "Staroměstská", "Malostranská", dir="Nemocnice Motol 방면",
         n=1, min=2, note="강 건너 한 정거장 · 39 CZK 30분권"),
    ride("tram", "22번", "Malostranská", "Pražský hrad", dir="Bílá Hora 방면", n=2, min=5,
         note="Královský letohrádek 다음 · 오렌지 단말기에 카드 태그로도 구매"),
    W(5, "하차 후 왼쪽 → 북문 → 2번 안뜰"),
 ], [
    "환승이 싫으면 Národní divadlo 에서 22번을 타고 7정거장 (약 15분)",
    "2026년 상반기 궤도공사로 Pražský hrad · Královský letohrádek 정류장이 닫힌 적 있음 "
    "→ 당일 안내 확인, 닫혔으면 대체 정류장 하차",
 ]),

 ("2026-10-02", "07:25"): ("지하철 B선 4정거장", None, [
    W(5, "호텔 → Náměstí Republiky역 (B선)"),
    ride("metro", "B선", "Náměstí Republiky", "Anděl", dir="Zličín 방면", n=4, min=7,
         note="Můstek · Národní třída · Karlovo náměstí 다음 · 컨택리스 불가, 자판기에서 39 CZK"),
 ], []),

 ("2026-10-02", "07:40"): ("Na Knížecí 버스정류장", "Anděl역에서 도보 2~3분", [
    W(3, "Anděl역 'Na Knížecí' 출구 → 버스터미널 플랫폼 1"),
 ], []),

 ("2026-10-02", "21:00"): ("지하철 B선 → 구시가", "지하철 B선 4정거장 · 7분", [
    W(3, "Na Knížecí → Anděl역"),
    ride("metro", "B선", "Anděl", "Náměstí Republiky", dir="Černý Most 방면", n=4, min=7,
         note="Karlovo náměstí · Národní třída · Můstek 다음"),
    W(5, "역 → Celetná 숙소"),
 ], []),
}

# 이름이 사실과 어긋나 있던 것 — 정거장 수는 세어서 고칩니다
RENAME = {
 ("2026-10-02", "07:25"): ("지하철 B선 5정거장", "지하철 B선 4정거장",
                           "(약 8분) → Anděl역", "(약 7분) → Anděl역"),
}
# 엉뚱한 데서 온 이동 설명 — 지우는 편이 낫습니다
DROP_MOVE = {
 # 이미 캄포 데이 미라콜리(=사탑 광장) 안에 서 있는데 "버스 LAM Rossa 10분" 이
 # 붙어 있었습니다. 첸트랄레에서 올 때 쓰는 말이라 08:15 항목의 대안으로 옮겼습니다.
 ("2026-09-26", "08:20"): "피사의 사탑 · 두오모 · 세례당",
}


def find(days, date, time):
    for d in days:
        if d["date"] != date:
            continue
        pool = d["items"] + [i for o in (d.get("options") or []) for i in o["items"]]
        for it in pool:
            if it["time"] == time:
                return it
    return None


def apply(data, check=False):
    days, miss, done = data["days"], [], 0

    for (date, time), (old, new, old_desc, new_desc) in RENAME.items():
        it = find(days, date, time)
        if not it:
            miss.append(f"{date} {time} — 항목 없음 (이름 정정)")
        elif it["name"] not in (old, new):
            miss.append(f"{date} {time} — 이름이 {it['name']!r} 이라 정정 안 함")
        elif not check:
            it["name"] = new
            if it.get("desc") == old_desc:
                it["desc"] = new_desc

    for (date, time), name in DROP_MOVE.items():
        it = find(days, date, time)
        if it and it["name"] == name and not check:
            it.pop("move", None)

    for (date, time), (name, move, legs, alt) in ROUTES.items():
        it = find(days, date, time)
        if not it:
            miss.append(f"{date} {time} {name!r} — 그 시각에 항목이 없습니다")
            continue
        if it["name"] != name:
            miss.append(f"{date} {time} — 이름이 {it['name']!r} 이라 안 얹었습니다 (표: {name!r})")
            continue
        done += 1
        if check:
            if it.get("route") != {"legs": legs, **({"alt": alt} if alt else {})}:
                miss.append(f"{date} {time} {name!r} — route 가 표와 다릅니다")
            continue
        if move:
            it["move"] = move
        it["route"] = {"legs": legs, **({"alt": alt} if alt else {})}
    return done, miss


def main() -> int:
    check = "--check" in sys.argv
    data = json.loads(DATA.read_text(encoding="utf-8"))
    done, miss = apply(data, check=check)
    if not check:
        DATA.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    legs = sum(len(v[2]) for v in ROUTES.values())
    print(f"교통편 {done}/{len(ROUTES)}개 항목 · 구간 {legs}개" + (" (확인만)" if check else " 얹음"))
    if miss:
        print(f"\n※ 확인하세요 — {len(miss)}건")
        for m in miss:
            print("  ", m)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
