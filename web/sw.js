const CACHE_NAME = 'observaatt-pe-v14';
const API_CACHE = 'observaatt-pe-api-v14';
const MANIFEST_URL = '/manifest.json?v=observaatt-pe-v14';
const HISTORICAL_SQL_URL = '/DUMP_ATT_VIVA.sql';
const ASSETS = [
  '/', MANIFEST_URL,
  '/launcher-home-v9-192.png?v=9',
  '/launcher-home-v9-512.png?v=9',
  '/launcher-home-v9-maskable-192.png?v=9',
  '/launcher-home-v9-maskable-512.png?v=9',
  '/sw.js', HISTORICAL_SQL_URL,
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'
];
let historicalPromise = null;

function parseSqlValueList(text) {
  const values = []; let i = 0;
  while (i < text.length) {
    while (i < text.length && /[ ,\n\r\t]/.test(text[i])) i++;
    if (i >= text.length) break;
    if (text.startsWith('NULL', i)) { values.push(null); i += 4; continue; }
    if (text[i] === "'") {
      i++; let value = '';
      while (i < text.length) {
        if (text[i] === "'") {
          if (text[i + 1] === "'") { value += "'"; i += 2; continue; }
          i++; break;
        }
        value += text[i++];
      }
      values.push(value); continue;
    }
    let j = i; while (j < text.length && text[j] !== ',') j++;
    values.push(text.slice(i, j).trim()); i = j;
  }
  return values;
}

async function loadHistoricalRecords() {
  if (historicalPromise) return historicalPromise;
  historicalPromise = fetch(HISTORICAL_SQL_URL, { cache: 'no-store' })
    .then((r) => r.ok ? r.text() : '')
    .then((sql) => {
      if (!sql) return [];
      const records = [];
      const re = /INSERT INTO\s+"[^"]+"\s*\([^)]*\)\s*VALUES\s*\(([\s\S]*?)\);/g;
      let match;
      while ((match = re.exec(sql)) !== null) {
        const v = parseSqlValueList(match[1]);
        if (v.length < 14) continue;
        records.push({
          id: `historical-${v[0]}`,
          dataHora: `${v[11] || ''} ${v[12] || ''}`.trim(),
          municipioNotificacao: v[3] || v[1] || '-',
          veiculoUsuario: v[4] || '-',
          tempoRegistroSegundos: 0,
          endereco: v[3] || '-',
          _historical: true
        });
      }
      return records;
    }).catch(() => []);
  return historicalPromise;
}

function transformForRecordsView(items, historical) {
  const merged = []; const seen = new Set();
  for (const item of historical || []) {
    const key = String(item.id || '');
    if (!key || seen.has(key)) continue;
    seen.add(key); merged.push(item);
  }
  for (const item of items || []) {
    const copy = { ...item };
    const key = String(copy.id || '');
    if (key && seen.has(key)) {
      const idx = merged.findIndex((x) => String(x.id) === key);
      if (idx >= 0) merged[idx] = copy;
    } else {
      if (copy.endereco) copy.municipioNotificacao = copy.endereco;
      merged.push(copy); if (key) seen.add(key);
    }
  }
  return merged.sort((a, b) => String(a.dataHora || '').localeCompare(String(b.dataHora || '')));
}

async function mergeAccidentsResponse(response) {
  try {
    const live = await response.clone().json();
    if (!Array.isArray(live)) return response;
    const merged = transformForRecordsView(live, await loadHistoricalRecords());
    return new Response(JSON.stringify(merged), {
      status: response.status, statusText: response.statusText,
      headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' }
    });
  } catch (_) { return response; }
}

function injectRecordsLayout(html) {
  const style = `<style id="historical-records-layout">
    #table th:nth-child(1), #table td:nth-child(1) { width:27%; }
    #table th:nth-child(2), #table td:nth-child(2) { width:39%; }
    #table th:nth-child(3), #table td:nth-child(3) { width:24%; }
    #table th:nth-child(4), #table td:nth-child(4) { display:none !important; }
  </style>`;
  const script = `<script id="historical-records-layout-script">
  (() => {
    const apply = () => {
      const table = document.getElementById('table'); if (!table) return;
      const headers = table.querySelectorAll('thead th');
      if (headers.length >= 4) {
        headers[0].textContent = 'Data';
        headers[1].textContent = 'Local';
        headers[2].textContent = 'Tipo de acidente';
        headers[3].style.display = 'none';
      }
      table.querySelectorAll('tbody tr').forEach((tr) => {
        const cells = tr.querySelectorAll('td');
        if (cells.length >= 4) {
          const text = cells[0].textContent || '';
          const match = text.match(/^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}(?::\d{2})?)/);
          if (match) cells[0].innerHTML = match[1] + '<br>' + match[2];
        }
      });
    };
    const observer = new MutationObserver(apply);
    observer.observe(document.documentElement, { childList:true, subtree:true });
    document.addEventListener('DOMContentLoaded', apply, { once:true });
    setInterval(apply, 1000);
  })();
  </script>`;
  return html.replace('</head>', style + '</head>').replace('</body>', script + '</body>');
}

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then(async (cache) => {
    for (const asset of ASSETS) { try { await cache.add(asset); } catch (_) {} }
    await loadHistoricalRecords();
  }));
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(
    keys.filter((key) => key !== CACHE_NAME && key !== API_CACHE).map((key) => caches.delete(key))
  )).then(() => self.clients.claim()));
});

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') self.skipWaiting();
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  const reqUrl = new URL(event.request.url);
  const isNavigation = event.request.mode === 'navigate';

  if (reqUrl.pathname === '/manifest.json') {
    event.respondWith(fetch(event.request).then((response) => {
      const copy = response.clone();
      caches.open(CACHE_NAME).then((cache) => {
        cache.put('/manifest.json', copy.clone()); cache.put(MANIFEST_URL, copy);
      }); return response;
    }).catch(() => caches.match(event.request) || caches.match(MANIFEST_URL) || caches.match('/manifest.json')));
    return;
  }

  if (isNavigation) {
    event.respondWith(caches.match('/').then((cached) => {
      const networkFetch = fetch(event.request).then(async (response) => {
        const text = await response.clone().text();
        const transformed = new Response(injectRecordsLayout(text), {
          status: response.status, statusText: response.statusText, headers: response.headers
        });
        caches.open(CACHE_NAME).then((cache) => cache.put('/', transformed.clone()));
        return transformed;
      }).catch(() => cached || caches.match(event.request));
      if (cached) { event.waitUntil(networkFetch); return cached; }
      return networkFetch;
    }));
    return;
  }

  if (reqUrl.pathname === '/api/accidents') {
    event.respondWith(fetch(event.request).then(async (response) => {
      const merged = await mergeAccidentsResponse(response);
      const copy = merged.clone();
      caches.open(API_CACHE).then((cache) => cache.put(event.request, copy));
      return merged;
    }).catch(() => caches.match(event.request)));
    return;
  }

  if (reqUrl.pathname.startsWith('/api/')) {
    event.respondWith(fetch(event.request).then((response) => {
      const copy = response.clone();
      caches.open(API_CACHE).then((cache) => cache.put(event.request, copy));
      return response;
    }).catch(() => caches.match(event.request)));
    return;
  }

  event.respondWith(caches.match(event.request).then((cached) => {
    if (cached) return cached;
    return fetch(event.request).then((response) => {
      const copy = response.clone();
      caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
      return response;
    }).catch(() => caches.match('/'));
  }));
});
