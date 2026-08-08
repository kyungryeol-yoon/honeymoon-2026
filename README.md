# Honeymoon 2026

Kyungryeol & Hojeong · 2026.09.14 – 10.04 신혼여행 일정 PWA.

- 배포: https://kyungryeol-yoon.github.io/honeymoon-2026/
- 홈 화면에 추가하면 오프라인에서도 일정이 열립니다.

## 구성

```
index.html          화면 전체 (CSS · JS 인라인)
data.json           여행 데이터 — 일정 수정은 여기만 고치면 됩니다
manifest.json       PWA 매니페스트
service-worker.js   오프라인 캐싱
icons/              앱 아이콘 (SVG 원본 + PNG)
```

## 일정 수정하기

`data.json` 만 고치고 커밋하면 됩니다.

### 하루 추가

```json
{
  "date": "2026-09-14",
  "city": "bcn",
  "dayNo": 1,
  "chips": [
    { "t": "현금 €50", "warn": true },
    { "t": "여권 지참" }
  ],
  "items": [
    { "time": "10:30", "name": "인천 출발", "desc": "KE915", "map": false,
      "refs": [{ "label": "예약번호", "value": "ABC123" }] },
    { "time": "17:40", "name": "사그라다 파밀리아", "end": "19:00",
      "place": "Sagrada Família" }
  ]
}
```

| 필드 | 설명 |
|---|---|
| `date` | `YYYY-MM-DD`. 오늘 날짜와 일치하면 "오늘"로 표시됩니다 |
| `city` | `cities[].id` 중 하나 (`bcn` `swi` `vce` `flr` `rom` `prg` `sel`) — 여정 라인의 노드 |
| `dayNo` | 여행 N일차 — 여정 라인의 진행도에 쓰입니다 |
| `label` | 헤더에 크게 뜨는 지명. 없으면 도시 이름. 스위스처럼 한 노드 안에서 거점이 바뀔 때 씁니다 (`라우터브룬넨` `그린델발트` `루가노`) |
| `map` | `place` 가 없는 일정의 지도 검색에 붙는 지역. 없으면 도시의 `map` |
| `chips` | 상단 알림. `warn: true` 면 도시 색으로 강조 |
| `items[].time` / `end` | `HH:MM`. `end` 가 없으면 다음 일정 시작까지로 봅니다 |
| `items[].name` | 탭하면 구글맵이 열립니다 |
| `items[].place` | 지도 검색어. **적으면 그대로 검색합니다** |
| `items[].map` | `false` 면 지도 링크를 만들지 않습니다 (이동·식사 등) |
| `items[].refs` | 편명·열차번호 등. 탭하면 클립보드로 복사됩니다 |

`items` 는 시간순으로 적어주세요. `days` 는 순서가 섞여 있어도 날짜순으로 정렬됩니다.

**`place` 는 그 자체로 찾아지는 검색어여야 합니다.** 도시명을 자동으로 붙이지 않습니다 —
이동일에는 하루 안에 도시가 두 개라 (`로마 테르미니` 아침 / `카를교` 밤) 붙이면 오히려
엉뚱한 곳이 나오기 때문입니다. 그래서 여러 도시에 같은 이름이 있는 곳은
`"Pantheon, Roma"`, `"Palazzo Ducale, Venezia"` 처럼 직접 적어뒀습니다.

### 도시 색

`cities[].color` 는 다크 모드, `colorLight` 는 라이트 모드용입니다.
라이트에서는 배경이 밝아지므로 명도를 한 단계 낮춘 값을 씁니다.
`home: true` 인 도시(서울)는 여정 라인 문구가 "Seoul → 서울 → Seoul" 대신 "· 완주"로 바뀝니다.

### 예약번호

저장소가 public 이라 **예약번호·PNR·실명·이메일은 `data.json` 에 넣지 않았습니다.**
`refs` 에 들어있는 건 편명·열차번호뿐입니다 (공개 시간표 정보).
실제 예약번호는 구글 시트에서 확인하세요.

## 동작

- **여행 전** — 출발까지 D-day와 실시간 카운트다운을 보여줍니다.
- **여행 중** — 오늘 일정에서 현재 진행 중인 항목을 NOW 카드와 타임라인에 표시합니다.
- **여행 후** — 마지막 날 일정으로 남습니다.

날짜 판정은 기기의 로컬 시간 기준입니다. 현지에서 시간대를 바꾸면 그 시간대로 동작합니다.

## 테마

시스템 설정(`prefers-color-scheme`)을 따라가고, 헤더 우측 버튼으로 직접 바꿀 수 있습니다.
한 번 직접 고르면 `localStorage` 에 저장되어 그 선택이 유지됩니다.

## 오프라인

- 화면·아이콘 등 정적 파일: 캐시 우선 (오프라인에서 바로 열림)
- `data.json`: 네트워크 우선 → 실패하면 캐시
  (일정 수정이 바로 반영돼야 해서. 오프라인에서는 마지막으로 받은 일정을 씁니다)

**일정을 고쳐 배포한 뒤에는 `service-worker.js` 의 `VERSION` 을 올려주세요.**
그래야 캐시가 통째로 교체되고 열려 있는 화면이 자동으로 새로고침됩니다.

## 로컬에서 보기

```sh
python3 -m http.server 8765
# http://127.0.0.1:8765
```

`file://` 로 열면 service worker 와 `fetch` 가 막히므로 반드시 서버로 띄워야 합니다.

## 아이콘 다시 만들기

`icons/icon.svg` · `icons/icon-maskable.svg` 를 고친 뒤:

```sh
./tools/render-icons.sh
```

Chrome 헤드리스로 렌더링합니다. ImageMagick 내장 SVG 렌더러는 stroke 와 `H`/`V`
path 명령을 빠뜨려서 아이콘이 깨집니다.

## 배포

`main` 에 푸시하면 GitHub Pages(Deploy from a branch · `main` / root)가 자동으로 반영합니다.
