#!/usr/bin/env python3
"""data.json → index.html 안의 인라인 백업 블록 생성.

네트워크도 죽고 캐시도 날아간 최악의 상황에서 쓰는 최소 일정입니다.
용량을 줄이려고 설명·준비물·예약번호는 빼고 시각·이름·장소만 남깁니다.
(예약번호를 빼는 건 용량 문제만이 아니라, 저장소가 public 이기 때문이기도 합니다)

  python3 tools/build-fallback.py
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data.json"
HTML = ROOT / "index.html"
MARK_ID = "fallback-data"

def slim(src: dict) -> dict:
    out = {
        "trip": src["trip"],
        "cities": [
            {k: v for k, v in c.items() if k in
             ("id", "name", "short", "flag", "color", "colorLight", "icon", "map", "home",
              "lang")}
            for c in src["cities"]
        ],
        "days": [],
    }
    # 현지어 프리셋은 남깁니다 — 말이 안 통하는 상황은 오프라인일 때 더 자주 옵니다
    if src.get("phrases"):
        out["phrases"] = src["phrases"]
    for d in src["days"]:
        day = {"date": d["date"], "city": d["city"], "dayNo": d["dayNo"]}
        if d.get("label"): day["label"] = d["label"]
        if d.get("map"):   day["map"]   = d["map"]
        if d.get("cash"):  day["cash"]  = {"amount": d["cash"]["amount"]}
        # 숙소는 남깁니다 — 길 잃고 오프라인일 때 제일 급한 한 줄입니다
        if d.get("stay"):  day["stay"]  = d["stay"]
        items = []
        for it in d["items"]:
            o = {"time": it["time"], "name": it["name"]}
            if it.get("end"):   o["end"]   = it["end"]
            if it.get("place"): o["place"] = it["place"]
            if it.get("move"):  o["move"]  = it["move"]   # 길 잃었을 때 제일 필요한 정보
            if it.get("map") is False: o["map"] = False
            if it.get("meet"):  o["meet"]  = {"where": it["meet"]["where"],
                                              **({"time": it["meet"]["time"]} if it["meet"].get("time") else {})}
            items.append(o)
        day["items"] = items
        out["days"].append(day)
    return out

def main() -> int:
    src = json.loads(DATA.read_text(encoding="utf-8"))
    payload = json.dumps(slim(src), ensure_ascii=False, separators=(",", ":"))

    html = HTML.read_text(encoding="utf-8")
    pattern = re.compile(
        r'(<script type="application/json" id="%s">)(.*?)(</script>)' % MARK_ID,
        re.S,
    )
    if not pattern.search(html):
        print(f"error: index.html 에 #{MARK_ID} 블록이 없습니다", file=sys.stderr)
        return 1

    html = pattern.sub(lambda m: m.group(1) + payload + m.group(3), html, count=1)
    HTML.write_text(html, encoding="utf-8")

    print(f"인라인 백업 갱신: {len(payload):,} bytes "
          f"({len(src['days'])}일 / {sum(len(d['items']) for d in src['days'])}개 일정)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
