/* ===========================================================
   Honeymoon 2026 — Service Worker
   · 정적 셸: 오프라인 우선 (cache-first + 백그라운드 갱신)
   · data.json: 네트워크 우선 → 실패 시 캐시
     (일정이 바뀌면 바로 반영돼야 하므로. 오프라인에서는 캐시로 동작)
   배포 시 VERSION 만 올리면 캐시가 통째로 교체됩니다.
   =========================================================== */

const VERSION = 'v62';
const CACHE   = `honeymoon-2026-${VERSION}`;

const SHELL = [
  './',
  './index.html',
  './data.json',
  './manifest.json',
  './icons/favicon.svg',
  './icons/apple-touch-icon.png',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/icon-maskable-192.png',
  './icons/icon-maskable-512.png',
];

const DATA_URL = new URL('./data.json', self.registration.scope).pathname;

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    // 하나라도 실패하면 전체가 실패하는 addAll 대신 개별 처리
    await Promise.all(SHELL.map(async (url) => {
      try{
        const res = await fetch(new Request(url, { cache: 'reload' }));
        if(res.ok) await cache.put(url, res);
      }catch(e){ /* 해당 파일만 건너뜀 */ }
    }));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)));
    if(self.registration.navigationPreload){
      try{ await self.registration.navigationPreload.disable(); }catch(e){}
    }
    await self.clients.claim();
  })());
});

self.addEventListener('message', (event) => {
  if(event.data === 'SKIP_WAITING') self.skipWaiting();
});

/* ---------- 전략 ---------- */

/* 응답이 안 오고 매달려 있으면 페이지가 통째로 멈추므로 시간을 끊습니다.

   타이머만으로 끊으면 원래 fetch 는 그대로 살아 있습니다 — 로밍 중에
   응답 없는 요청이 백그라운드에서 계속 데이터를 먹으므로 AbortController 로
   연결 자체를 끊습니다. */
const NET_TIMEOUT = 4000;

function timedFetch(request, ms){
  const ac = new AbortController();
  const t = setTimeout(() => ac.abort(), ms);
  return fetch(request, { signal: ac.signal })
    .finally(() => clearTimeout(t));
}

/* keep(promise) — 응답은 기다리지 않되 SW 가 유휴 종료되지 않게 붙잡아 둡니다.
   (respondWith 만으로는 응답 반환 이후의 cache.put 이 잘릴 수 있습니다) */
async function cacheFirst(request, keep){
  const cache = await caches.open(CACHE);
  const hit = await cache.match(request, { ignoreSearch: false });

  const update = timedFetch(request, NET_TIMEOUT).then(async res => {
    if(res && res.ok && res.type !== 'opaque'){
      try{ await cache.put(request, res.clone()); }catch(e){}
    }
    return res;
  }).catch(() => null);

  if(hit){
    keep(update); // 백그라운드 갱신 — 결과는 안 기다리지만 끝까지 살려둡니다
    return hit;
  }
  const res = await update;
  return res || new Response('', { status: 504, statusText: 'Offline' });
}

async function networkFirst(request){
  const cache = await caches.open(CACHE);
  try{
    const res = await timedFetch(request, NET_TIMEOUT);
    // 여기서 기다려야 오프라인 폴백이 보장됩니다 — data.json 캐싱이 잘리면
    // 다음번 오프라인에 일정이 통째로 안 뜹니다.
    // 캐시 쓰기가 실패해도 받아온 응답은 그대로 돌려줍니다.
    if(res && res.ok){
      try{ await cache.put(request, res.clone()); }catch(e){}
    }
    return res;
  }catch(e){
    const hit = await cache.match(request, { ignoreSearch: true });
    if(hit) return hit;
    return new Response('', { status: 504, statusText: 'Offline' });
  }
}

/* 화면(HTML)은 오프라인 우선 — 캐시를 먼저 띄우고 뒤에서 갱신.
   새 버전은 VERSION 을 올리면 SW 교체 → 페이지가 자동 새로고침됩니다. */
async function handleNavigation(request, keep){
  const cache = await caches.open(CACHE);

  const update = timedFetch(request, NET_TIMEOUT).then(async res => {
    if(res && res.ok){
      try{ await cache.put('./index.html', res.clone()); }catch(e){}
    }
    return res;
  }).catch(() => null);

  const hit = (await cache.match('./index.html')) || (await cache.match('./'));
  if(hit){
    keep(update);
    return hit;
  }
  return (await update) || new Response(
    '<!doctype html><meta charset="utf-8"><p style="font-family:sans-serif;padding:24px">오프라인입니다. 온라인 상태에서 한 번 열어주세요.</p>',
    { status: 200, headers: { 'Content-Type': 'text/html; charset=utf-8' } }
  );
}

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if(req.method !== 'GET') return;

  const url = new URL(req.url);
  if(url.origin !== self.location.origin) return; // 외부 요청은 그대로

  // respondWith 로 넘긴 약속이 살아 있는 동안만 waitUntil 을 더 걸 수 있으므로
  // 아래에서 event.waitUntil(p) 를 먼저 걸어두고, 백그라운드 갱신을 이어 붙입니다.
  const keep = (p) => { try{ event.waitUntil(p); }catch(e){} };

  if(req.mode === 'navigate'){
    const p = handleNavigation(req, keep);
    event.respondWith(p);
    event.waitUntil(p);
    return;
  }
  if(url.pathname === DATA_URL){
    const p = networkFirst(req);
    event.respondWith(p);
    event.waitUntil(p);
    return;
  }
  const p = cacheFirst(req, keep);
  event.respondWith(p);
  event.waitUntil(p);
});
