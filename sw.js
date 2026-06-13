// Self-destroying service worker.
// Chirpy(PWA) 시절 등록된 옛 서비스 워커를 제거하기 위한 스크립트.
// 브라우저가 SW 업데이트를 확인할 때 이 워커가 설치되어 모든 캐시를 비우고
// 자기 자신을 등록 해제한 뒤, 열려 있는 탭을 새로고침한다. 한 번 실행되면 SW는 사라진다.
self.addEventListener('install', function () {
  self.skipWaiting();
});

self.addEventListener('activate', function (event) {
  event.waitUntil((async function () {
    try {
      if (self.caches && caches.keys) {
        var keys = await caches.keys();
        await Promise.all(keys.map(function (k) { return caches.delete(k); }));
      }
      await self.registration.unregister();
      var clients = await self.clients.matchAll({ type: 'window' });
      clients.forEach(function (client) { client.navigate(client.url); });
    } catch (e) {}
  })());
});
