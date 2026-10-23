// App shell is cached for instant start and an offline page; API calls always go to the network.
const V = 'club-v1';
const SHELL = ['/', '/static/styles.css?v=1', '/static/i18n.js?v=1', '/static/app.js?v=1', '/static/members.js?v=1', '/static/posts.js?v=1', '/static/meetings.js?v=1',
  '/static/library.js?v=1', '/static/finance.js?v=1', '/static/admin.js?v=1', '/static/extras.js?v=1', '/static/polls.js?v=1', '/static/offline.html', '/static/icons/icon.svg'];
self.addEventListener('install', e => { e.waitUntil(caches.open(V).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())); });
self.addEventListener('activate', e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== V).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener('fetch', e => {
  const u = new URL(e.request.url);
  if (e.request.method !== 'GET' || u.pathname.startsWith('/api/') || u.pathname.startsWith('/uploads/')) return;
  e.respondWith(fetch(e.request).then(r => { if (r.ok && u.origin === location.origin) { const cp = r.clone(); caches.open(V).then(c => c.put(e.request, cp)); } return r; })
    .catch(() => caches.match(e.request).then(r => r || (e.request.mode === 'navigate' ? caches.match('/static/offline.html') : Response.error()))));
});

self.addEventListener('push', e => {
  let d = {}; try { d = e.data ? e.data.json() : {}; } catch (err) { d = { title: 'Club', body: e.data ? e.data.text() : '' }; }
  e.waitUntil(self.registration.showNotification(d.title || 'Club', { body: d.body || '', icon: '/static/icons/icon-192.png', badge: '/static/icons/icon-192.png', data: { link: d.link || '' } }));
});
self.addEventListener('notificationclick', e => {
  e.notification.close(); const link = (e.notification.data && e.notification.data.link) || '#/notifications';
  e.waitUntil(clients.matchAll({ type: 'window', includeUncontrolled: true }).then(ws => { const w = ws.find(x => 'focus' in x); if (w) { w.navigate(location.origin + '/' + link); return w.focus(); } return clients.openWindow('/' + link); }));
});
