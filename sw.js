// Chạy offline: lấy bản mới khi có mạng, mất mạng thì dùng bản đã lưu.
const KHO = 'cuahang-v2';
const SAN = ['./', 'index.html', 'nhan.html', 'lib/supabase.min.js', 'manifest.json', 'icons/icon-192.png', 'icons/favicon.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(KHO).then(c => c.addAll(SAN)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== KHO).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const u = new URL(e.request.url);
  if (e.request.method !== 'GET' || u.origin !== location.origin) return; // Supabase, CDN: để trình duyệt tự xử lý
  e.respondWith(
    fetch(e.request).then(r => {
      if (r.ok) { const b = r.clone(); caches.open(KHO).then(c => c.put(e.request, b)); }
      return r;
    }).catch(() => caches.match(e.request, { ignoreSearch: true }))
  );
});
