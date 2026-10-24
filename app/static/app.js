/* Core: state, API, i18n, router, shell, forms. Other files add routes with R() and actions on A. */
'use strict';
const S = { user: null, member: null, info: null, settings: null, unread: 0, lang: (localStorage.getItem('club_lang') || 'ml'), membersCache: null };
const A = {};                      // actions referenced from markup: onclick="A.name(...)"
const ROUTES = [];
const R = (pattern, fn) => ROUTES.push([new RegExp('^' + pattern.replace(/:(\w+)/g, '(?<$1>[^/]+)') + '$'), fn]);

// ---------- i18n ----------
function t(k, vars) { const ov = S.info && S.info.org_kind === 'association' && window.I18N_ASSOC && ((I18N_ASSOC[S.lang] && I18N_ASSOC[S.lang][k]) || I18N_ASSOC.en[k]); let s = ov || (I18N[S.lang] && I18N[S.lang][k]) || I18N.en[k] || k; if (vars) for (const v in vars) s = s.replace('{' + v + '}', vars[v]); return s; }
const bil = (row, f) => row ? ((row[f + '_' + S.lang] || row[f + '_' + (S.lang === 'ml' ? 'en' : 'ml')] || '')) : '';
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const MONTHS = { en: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'], ml: ['ജനു', 'ഫെബ്', 'മാർ', 'ഏപ്രി', 'മേയ്', 'ജൂൺ', 'ജൂലൈ', 'ഓഗ', 'സെപ്', 'ഒക്ടോ', 'നവം', 'ഡിസം'] };
function fmtDate(s) { if (!s) return ''; const d = new Date(s.length <= 10 ? s + 'T00:00' : s); if (isNaN(d)) return s; return `${d.getDate()} ${MONTHS[S.lang][d.getMonth()]} ${d.getFullYear()}`; }
function fmtDT(s) { if (!s) return ''; if (s.length <= 10) return fmtDate(s); const d = new Date(s); if (isNaN(d)) return s; let h = d.getHours(), m = d.getMinutes(), ap = h >= 12 ? 'PM' : 'AM'; h = h % 12 || 12; return `${fmtDate(s)} · ${h}:${String(m).padStart(2, '0')} ${ap}`; }
function fmtTs(ts) { if (!ts) return ''; const d = new Date(ts * 1000); return `${d.getDate()} ${MONTHS[S.lang][d.getMonth()]} ${d.getFullYear()}`; }
const money = n => '₹' + Number(n || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 });
const today = () => new Date().toISOString().slice(0, 10);
const nameOf = m => m ? (bil(m, 'name') || m.name || '') : '';
const initials = s => (s || '?').trim().split(/\s+/).slice(0, 2).map(w => w[0]).join('').toUpperCase();
const avatar = (m, cls = '') => `<div class="avatar ${cls}">${m && m.photo ? `<img src="/uploads/${esc(m.photo)}" alt="">` : esc(initials(m ? (m.name_en || m.name) : ''))}</div>`;
const can = p => !!(S.user && S.user.perms.includes(p));
const statusPill = s => { const cls = { active: 'ok', published: 'ok', paid: 'ok', done: 'ok', held: 'ok', approved: 'ok', sent: 'ok', present: 'ok', available: 'ok', registered: 'ok',
  applied: 'warn', draft: 'warn', pending: 'warn', due: 'warn', in_progress: 'warn', waitlisted: 'warn', demo: 'warn', scheduled: 'brand', open: 'brand', issued: 'brand', waiting: 'warn', ready: 'ok',
  rejected: 'bad', failed: 'bad', cancelled: 'bad', suspended: 'bad', overdue: 'bad', absent: 'bad', lost: 'bad', dropped: '' }[s] || ''; return `<span class="pill ${cls}">${esc(t(s))}</span>`; };

// ---------- API ----------
async function api(method, url, body, opts = {}) {
  const r = await fetch(url, { method, headers: { 'X-Club': '1', ...(body && !(body instanceof FormData) ? { 'Content-Type': 'application/json' } : {}) },
    body: body ? (body instanceof FormData ? body : JSON.stringify(body)) : undefined, credentials: 'same-origin' });
  if (r.status === 401 && S.user && !opts.quiet) { S.user = null; nav('#/login'); throw new Error('sign in'); }
  let data = null; const ct = r.headers.get('content-type') || '';
  data = ct.includes('json') ? await r.json() : await r.text();
  if (r.status === 402 && S.user) { await App.me(); App.route(); }  // the club just became read-only: show the banner
  if (!r.ok) { const msg = (data && data.error) || r.statusText || t('error'); if (!opts.quiet) toast(msg, 'bad'); throw new Error(msg); }
  return data;
}
const get = (u, o) => api('GET', u, null, o), post = (u, b, o) => api('POST', u, b, o), put = (u, b) => api('PUT', u, b), del = u => api('DELETE', u);
async function upload(folder, file) { const fd = new FormData(); fd.append('file', file); return api('POST', `/api/upload/${folder}`, fd); }

// ---------- UI helpers ----------
let toastTimer;
function toast(msg, kind = '') { const el = document.getElementById('toast'); el.textContent = msg; el.className = 'toast show ' + kind; clearTimeout(toastTimer); toastTimer = setTimeout(() => el.className = 'toast', 2800); }
function sheet(html, title = '') { const el = document.getElementById('sheet'); el.innerHTML = `<div class="panel"><button class="x" onclick="closeSheet()">✕</button>${title ? `<h2>${esc(title)}</h2>` : ''}${html}</div>`; el.classList.add('open'); el.onclick = e => { if (e.target === el) closeSheet(); }; const f = el.querySelector('input,select,textarea'); if (f && window.innerWidth > 700) setTimeout(() => f.focus(), 50); }
function closeSheet() { const el = document.getElementById('sheet'); el.classList.remove('open'); el.innerHTML = ''; }
function confirmDlg(msg) { return new Promise(res => { sheet(`<p>${esc(msg)}</p><div class="actions"><button class="btn danger" id="cf-yes">${t('yes')}</button><button class="btn ghost" onclick="closeSheet()">${t('cancel')}</button></div>`); document.getElementById('cf-yes').onclick = () => { closeSheet(); res(true); }; }); }
function nav(h) { if (location.hash === h) App.route(); else location.hash = h; }
function render(html) { const m = document.getElementById('main'); if (m) { m.innerHTML = html; window.scrollTo(0, 0); } else document.getElementById('app').innerHTML = html; }
function page(title, sub, actions, body) { return `<div class="page-head"><div><h1>${esc(title)}</h1>${sub ? `<p>${sub}</p>` : ''}</div><div class="row">${actions || ''}</div></div>${body}`; }
const empty = (msg) => `<div class="empty">${esc(msg || t('nothing_here'))}</div>`;
function tabs(items, cur) { return `<div class="tabs">${items.map(([h, l]) => `<a href="${h}" class="${h === cur ? 'on' : ''}">${esc(l)}</a>`).join('')}</div>`; }
function tbl(cols, rows, rowAttr) {
  if (!rows.length) return empty();
  return `<div class="tbl-wrap"><table class="tbl"><thead><tr>${cols.map(c => `<th class="${c.num ? 'num' : ''}">${esc(c.h)}</th>`).join('')}</tr></thead><tbody>${rows.map(r =>
    `<tr ${rowAttr ? rowAttr(r) : ''}>${cols.map(c => `<td class="${c.num ? 'num' : ''}">${c.f(r)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}
// forms
const F = {
  wrap: (name, label, inner, { req, full, help } = {}) => `<label class="f ${req ? 'req' : ''} ${full ? 'full' : ''}" data-f="${name}"><span>${esc(label)}</span>${inner}${help ? `<div class="help">${help}</div>` : ''}</label>`,
  text: (name, label, val = '', o = {}) => F.wrap(name, label, `<input class="in" name="${name}" type="${o.type || 'text'}" value="${esc(val)}" ${o.req ? 'required' : ''} ${o.attrs || ''} placeholder="${esc(o.ph || '')}">`, o),
  num: (name, label, val = '', o = {}) => F.text(name, label, val, { ...o, type: 'number', attrs: `step="${o.step || 'any'}" inputmode="decimal" ${o.attrs || ''}` }),
  date: (name, label, val = '', o = {}) => F.text(name, label, val, { ...o, type: 'date' }),
  dt: (name, label, val = '', o = {}) => F.text(name, label, (val || '').slice(0, 16), { ...o, type: 'datetime-local' }),
  area: (name, label, val = '', o = {}) => F.wrap(name, label, `<textarea class="in" name="${name}" ${o.rows ? `rows="${o.rows}"` : ''}>${esc(val)}</textarea>`, { full: true, ...o }),
  select: (name, label, val, options, o = {}) => F.wrap(name, label, `<select class="in" name="${name}" ${o.attrs || ''}>${o.blank !== false ? `<option value="">${esc(o.blank || '—')}</option>` : ''}${options.map(op => { const [v, l] = Array.isArray(op) ? op : [op, t(op)]; return `<option value="${esc(v)}" ${String(v) === String(val ?? '') ? 'selected' : ''}>${esc(l)}</option>`; }).join('')}</select>`, o),
  chk: (name, label, val, o = {}) => `<label class="chk ${o.full ? 'full' : ''}"><input type="checkbox" name="${name}" ${val ? 'checked' : ''}> ${esc(label)}</label>`,
  bi: (name, label, row = {}, o = {}) => `<div class="full bi" data-bi="${name}">${(o.area ? F.area : F.text)(name + '_en', label + ' (English)', row[name + '_en'] || '', { ...o, full: false })}${(o.area ? F.area : F.text)(name + '_ml', label + ' (മലയാളം)', row[name + '_ml'] || '', { ...o, req: false, full: false })}</div>`,
  member: (name, label, val, o = {}) => F.wrap(name, label, `<input class="in" list="members-dl" name="${name}" data-member value="${esc(val || '')}" placeholder="${t('type_to_search')}" autocomplete="off">`, o),
  hidden: (name, val) => `<input type="hidden" name="${name}" value="${esc(val ?? '')}">`,
  file: (name, label, o = {}) => F.wrap(name, label, `<input class="in" type="file" name="${name}" accept="${o.accept || 'image/*'}" ${o.attrs || ''}>`, o),
};
function readForm(form) {
  const out = {};
  for (const el of form.querySelectorAll('[name]')) {
    if (el.type === 'checkbox') out[el.name] = el.checked ? 1 : 0;
    else if (el.type === 'file') continue;
    else if (el.dataset.member !== undefined) out[el.name] = memberIdFromLabel(el.value);
    else if (el.type === 'number') out[el.name] = el.value === '' ? '' : Number(el.value);
    else out[el.name] = el.value;
  }
  return out;
}
function formSheet(title, fieldsHtml, onSave, { saveLabel, extra } = {}) {
  sheet(`<form class="form" id="sf" onsubmit="return false">${fieldsHtml}<div class="full actions"><button class="btn" id="sf-save">${esc(saveLabel || t('save'))}</button><button class="btn ghost" type="button" onclick="closeSheet()">${t('cancel')}</button>${extra || ''}</div></form>`, title);
  const f = document.getElementById('sf'), b = document.getElementById('sf-save');
  b.onclick = async () => { if (!f.reportValidity()) return; b.disabled = true; try { await onSave(readForm(f), f); } catch (e) { /* toast already shown */ } finally { b.disabled = false; } };
  return f;
}
// members datalist (for pickers)
async function membersForPick() {
  if (S.membersCache) return S.membersCache;
  try { S.membersCache = can('members.view') ? await get('/api/members?status=active', { quiet: true }) : await get('/api/members/directory', { quiet: true }); } catch (e) { S.membersCache = []; }
  let dl = document.getElementById('members-dl'); if (!dl) { dl = document.createElement('datalist'); dl.id = 'members-dl'; document.body.appendChild(dl); }
  dl.innerHTML = S.membersCache.map(m => `<option value="${esc(memberLabel(m))}">`).join('');
  return S.membersCache;
}
const memberLabel = m => `${m.member_no || ''} · ${m.name_en}${m.name_ml ? ' · ' + m.name_ml : ''}`.replace(/^ · /, '');
function memberIdFromLabel(v) { if (!v) return null; const m = (S.membersCache || []).find(x => memberLabel(x) === v) || (S.membersCache || []).find(x => v.includes(x.name_en) || (x.member_no && v.includes(x.member_no))); return m ? m.id : null; }
function memberLabelById(id) { const m = (S.membersCache || []).find(x => x.id === id); return m ? memberLabel(m) : ''; }

// ---------- language / theme ----------
async function setLang(l) { S.lang = l; localStorage.setItem('club_lang', l); document.documentElement.lang = l; if (S.user) post('/api/auth/lang', { lang: l }, { quiet: true }).catch(() => {}); App.route(); }
A.toggleLang = () => setLang(S.lang === 'ml' ? 'en' : 'ml');
const langBtn = () => `<button class="lang-sw" onclick="A.toggleLang()" title="${t('language')}">${S.lang === 'ml' ? 'English' : 'മലയാളം'}</button>`;

// ---------- shell ----------
function navItems() {
  const u = S.user, m = !!(u && u.member_id); const items = [];
  items.push({ h: '#/', l: t('home') }); items.push({ h: '#/posts', l: t('news') });
  if (m) { items.push({ h: '#/me', l: t('me') }); items.push({ h: '#/notifications', l: t('notifications'), badge: S.unread }); }
  if (m || can('members.view')) items.push({ h: '#/directory', l: t('directory') });
  items.push({ h: '#/committees', l: t('committees') }); items.push({ h: '#/meetings', l: t('meetings') }); items.push({ h: '#/actions', l: t('actions') }); items.push({ h: '#/plans', l: t('plans') });
  const ft = (S.info && S.info.features) || { library: true }; if (ft.library) items.push({ h: '#/library', l: t('library') }); if (m) { if (ft.library) items.push({ h: '#/library/mine', l: t('my_books') }); items.push({ h: '#/payments', l: t('payments') }); }
  if (ft.helpdesk && (m || can('helpdesk.manage'))) items.push({ h: '#/helpdesk', l: t('helpdesk') }); if (ft.units && m && !can('members.view')) items.push({ h: '#/units', l: t('units') });
  items.push({ h: '#/documents', l: t('documents') }); items.push({ h: '#/bookings', l: t('bookings') }); items.push({ h: '#/polls', l: t('polls') });
  if (S.judging) items.push({ h: '#/judging', l: t('judging') });
  const office = [];
  if (can('members.view') || can('library.manage') || can('posts.manage') || (u.convenes || []).length) office.push({ h: '#/scan', l: t('scan') });
  if (can('members.manage')) office.push({ h: '#/applications', l: t('applications') });
  if (can('members.view')) office.push({ h: '#/members', l: t('members') }); if (ft.units && can('members.view')) office.push({ h: '#/units', l: t('units') });
  if (can('broadcast.send')) office.push({ h: '#/broadcast', l: t('broadcast') });
  if (can('outbox.view')) office.push({ h: '#/outbox', l: t('outbox') });
  if (ft.library && can('library.manage')) { office.push({ h: '#/library/circulation', l: t('circulation') }); office.push({ h: '#/library/reading-room', l: t('reading_room') }); office.push({ h: '#/library/periodicals', l: t('periodicals') }); office.push({ h: '#/assets', l: t('assets') }); }
  if (can('finance.view')) { office.push({ h: '#/finance', l: t('accounts') }); if (ft.maintenance) office.push({ h: '#/maintenance', l: t('maintenance') }); office.push({ h: '#/finance/dues', l: t('dues') }); }
  if (can('reports.view')) office.push({ h: '#/reports', l: t('reports') });
  if (can('users.manage')) office.push({ h: '#/users', l: t('users') });
  if (can('settings.manage')) { office.push({ h: '#/settings', l: t('settings') }); if (S.info && S.info.plan && !S.info.plan.exempt) office.push({ h: '#/plan', l: t('subscription_plan') }); office.push({ h: '#/audit', l: t('audit') }); }
  return { items, office };
}
function shell(bodyHtml, title) {
  const { items, office } = navItems(); const cur = location.hash || '#/';
  const link = i => `<a href="${i.h}" class="${(i.h === '#/' ? cur === '#/' : cur.startsWith(i.h)) ? 'on' : ''}" onclick="document.querySelector('.side').classList.remove('open')">${esc(i.l)}${i.badge ? `<span class="badge">${i.badge}</span>` : ''}</a>`;
  const info = S.info || {};
  return `<div class="shell"><aside class="side"><div class="brand">${brandLogo()}<div>${esc(S.lang === 'ml' ? (info.club_name_ml || info.club_name_en) : info.club_name_en)}<small>${esc(S.lang === 'ml' ? info.club_place_ml || info.club_place_en || '' : info.club_place_en || '')}</small></div></div>
  <nav class="nav">${items.map(link).join('')}${office.length ? `<div class="grp">${t('office')}</div>${office.map(link).join('')}` : ''}</nav>
  <div class="foot">${esc(S.user.name)} · ${esc(t(S.user.role))}<br>${langBtn()} <button class="lang-sw" onclick="A.logout()">${t('sign_out')}</button><br><a href="/help?lang=${S.lang}" target="_blank" style="color:inherit;opacity:.85">📖 ${t('handbook')}</a><br><br>${esc(info.footer_credit || '')}</div></aside>
  <div class="main"><div class="top"><button onclick="document.querySelector('.side').classList.toggle('open')">☰</button><div class="ttl">${esc(title || info.club_short || '')}</div>${langBtn()}</div>${typeof planBanner === "function" ? planBanner() : ""}<div id="main">${bodyHtml}</div></div></div>`;
}
function brandLogo() { const b = (S.info && S.info.brand) || {}; return b.logo ? `<img src="${esc(b.logo)}" alt="">` : ''; }
// The club's colours, title and icon: inlined by the server on first paint, refreshed here after a settings change.
function applyBrand() {
  const b = (S.info && S.info.brand) || {}; document.title = b.app_name || S.info.club_short || '';
  let st = document.getElementById('brand'); if (!st) { st = document.createElement('style'); st.id = 'brand'; } document.head.appendChild(st); if (b.css && st.textContent !== b.css) st.textContent = b.css;
  const tc = document.querySelector('meta[name=theme-color]'); if (tc && b.primary) tc.content = b.primary;
  const ic = document.querySelector('link[rel=icon]'); if (ic && b.favicon && !ic.href.endsWith(b.favicon)) ic.href = b.favicon;
}
A.logout = async () => { await post('/api/auth/logout'); S.user = null; S.member = null; S.membersCache = null; nav('#/'); };

// ---------- public screens ----------
function pubShell(body) {
  const info = S.info || {};
  return `<div class="pub"><header><div class="brand">${brandLogo()}<div>${esc(S.lang === 'ml' ? (info.club_name_ml || info.club_name_en) : info.club_name_en)}<small>${esc(S.lang === 'ml' ? info.club_place_ml || info.club_place_en || '' : info.club_place_en || '')}</small></div></div>
  ${langBtn()} <a class="btn" href="/site?lang=${S.lang}">${t('website')}</a><a class="btn" href="/help?lang=${S.lang}">${t('help')}</a><a class="btn" href="#/login">${t('sign_in')}</a>${info.public_registration === '1' ? `<a class="btn accent" href="#/apply">${t('apply')}</a>` : ''}</header><main>${body}</main><footer>${esc(info.footer_credit || '')}<br><a href="/terms?lang=${S.lang}" target="_blank">${t('terms')}</a> · <a href="/privacy?lang=${S.lang}" target="_blank">${t('privacy')}</a></footer></div>`;
}
async function viewLanding() {
  const posts = await get('/api/public/posts');
  render(pubShell(`<div class="hero"><div class="card"><h1>${t('welcome')}</h1><p>${t('apply_intro')}</p><div class="actions"><a class="btn accent" href="#/apply">${t('apply')}</a><a class="btn ghost" href="#/login">${t('sign_in')}</a></div></div>
  <div class="card login">${loginFormHtml()}</div></div>
  <h2>${t('public_news')}</h2>${posts.length ? `<div class="news-grid">${posts.map(newsCard).join('')}</div>` : empty()}`));
  bindLogin();
}
function newsCard(p) { return `<div class="news-card" onclick="${S.user ? `nav('#/posts/${p.id}')` : `location.href='/p/${p.id}?lang=${S.lang}'`}">${p.cover ? `<img src="/uploads/${esc(p.cover)}" alt="">` : ''}<div class="b"><div class="t">${esc(bil(p, 'title'))}</div><div class="s">${esc(t(p.kind === 'news' ? 'news_item' : p.kind))}${p.starts_at ? ' · ' + esc(fmtDT(p.starts_at)) : ''}${bil(p, 'venue') ? ' · ' + esc(bil(p, 'venue')) : ''}</div></div></div>`; }
function loginFormHtml() { return `<h2>${t('sign_in')}</h2><form id="login-f" class="stack" onsubmit="return false">${F.text('login', t('login'), '', { req: true, attrs: 'autocomplete="username"' })}${F.text('password', t('password'), '', { req: true, type: 'password', attrs: 'autocomplete="current-password"' })}<button class="btn block" id="login-b">${t('sign_in')}</button><div class="small"><a href="#" onclick="A.forgot();return false">${t('forgot')}</a></div>${S.info && S.info.public_registration === '1' ? `<div class="small">${t('no_account')} <a href="#/apply">${t('apply')}</a></div>` : ''}</form>`; }
function bindLogin() { const f = document.getElementById('login-f'); if (!f) return; document.getElementById('login-b').onclick = async () => { if (!f.reportValidity()) return; const b = readForm(f); try { await post('/api/auth/login', b); await App.me(); nav('#/'); } catch (e) {} }; }
A.forgot = () => formSheet(t('forgot'), `<p class="full small muted">${t('forgot_intro')}</p>${F.text('login', t('login'), '', { req: true, full: true })}`, async b => {
  const r = await post('/api/auth/forgot', b); closeSheet();
  formSheet(t('forgot'), `<p class="full small muted">${t('code_sent')}</p>${F.text('code', t('code'), '', { req: true, full: true, attrs: 'inputmode="numeric" autocomplete="one-time-code"' })}${F.text('password', t('new_password'), '', { req: true, full: true, type: 'password', attrs: 'minlength="8" autocomplete="new-password"' })}`,
    async b2 => { await post('/api/auth/reset', { ...b2, ticket: r.ticket }); closeSheet(); toast(t('reset_done'), 'ok'); await App.me(); nav('#/'); }, { saveLabel: t('sign_in') });
}, { saveLabel: t('send_code') });
async function viewLogin() { render(pubShell(`<div class="card" style="max-width:440px;margin:0 auto">${loginFormHtml()}</div>`)); bindLogin(); }
async function viewApply() {
  const info = S.info; let AP; try { AP = JSON.parse(sessionStorage.getItem('club_apply') || 'null'); } catch (e) { AP = null; }
  AP = AP && AP.data ? AP : { step: 0, data: { membership_type: 'ordinary', lang: S.lang, notify_whatsapp: 1, notify_sms: 1, notify_email: 1, show_phone: 1 }, family: [], photo: null, photoName: '' };
  S.ap = AP; renderApply();
}
const AP_STEPS = ['step_personal', 'step_contact', 'step_family', 'step_photo', 'step_account', 'step_review'];
function apSave() { const { photo, ...rest } = S.ap; try { sessionStorage.setItem('club_apply', JSON.stringify({ ...rest, photo: photo && photo.length < 400000 ? photo : null })); } catch (e) {} }
function apCollect() { const f = document.getElementById('ap-f'); if (!f) return true; if (!f.reportValidity()) return false; Object.assign(S.ap.data, readForm(f)); return true; }
function renderApply() {
  const AP = S.ap, info = S.info, d = AP.data, step = AP.step; const types = info.membership_types.map(x => [x.key, (S.lang === 'ml' ? x.ml : x.en) + (x.admission || x.annual ? ` (₹${x.admission} + ₹${x.annual}/yr)` : '')]);
  const bar = `<div class="steps-bar">${AP_STEPS.map((k, i) => `<span class="${i === step ? 'on' : i < step ? 'done' : ''}">${i === step ? `${i + 1}. ${t(k)}` : i < step ? '✓' : i + 1}</span>`).join('')}</div><div class="small muted" style="margin:-8px 0 12px">${step + 1} / ${AP_STEPS.length}</div>`;
  let body = '';
  if (step === 0) body = `<form class="form" id="ap-f" onsubmit="return false">${F.text('name_en', t('name_en'), d.name_en, { req: true, attrs: 'autocomplete="name"' })}${F.text('name_ml', t('name_ml'), d.name_ml)}${F.select('gender', t('gender'), d.gender, ['male', 'female', 'other'])}${F.date('dob', t('dob'), d.dob)}${F.select('blood_group', t('blood_group'), d.blood_group, info.blood_groups.map(b => [b, b]))}${F.select('membership_type', t('membership_type'), d.membership_type || 'ordinary', types, { blank: false })}${F.text('occupation', t('occupation'), d.occupation)}${F.text('education', t('education'), d.education)}${F.text('interests', t('interests'), d.interests, { full: true })}</form>`;
  else if (step === 1) body = `<form class="form" id="ap-f" onsubmit="return false">${F.text('phone', t('phone'), d.phone, { req: true, type: 'tel', attrs: 'inputmode="tel" pattern="[0-9 +\\-]{10,15}" autocomplete="tel"' })}${F.text('whatsapp', t('whatsapp'), d.whatsapp, { type: 'tel' })}${F.text('email', t('email'), d.email, { type: 'email', attrs: 'autocomplete="email"' })}${info.wards.length ? F.select('ward', t('ward'), d.ward, info.wards.map(w => [w, w])) : F.text('ward', t('ward'), d.ward)}${info.features && info.features.units ? `${F.text('unit_no', t('unit_no'), d.unit_no, { req: true })}${F.select('occupancy', t('occupancy'), d.occupancy || 'owner', [['owner', t('owner')], ['tenant', t('tenant')], ['family', t('family_occ')]], { blank: false })}${(info.unit_types || []).length ? F.select('unit_type', t('unit_type'), d.unit_type, info.unit_types.map(x => [x, x])) : ''}` : `${F.text('house_en', t('house') + ' (English)', d.house_en)}${F.text('house_ml', t('house') + ' (മലയാളം)', d.house_ml)}`}${F.area('address_en', t('address') + ' (English)', d.address_en, { full: false, rows: 2 })}${F.area('address_ml', t('address') + ' (മലയാളം)', d.address_ml, { full: false, rows: 2 })}${F.text('pincode', t('pincode'), d.pincode, { attrs: 'inputmode="numeric"' })}${F.text('id_proof', t('id_proof'), d.id_proof)}</form>`;
  else if (step === 2) body = `<div class="stack"><div class="row"><span class="small muted">${t('quick_add')}:</span><div class="chips">${['spouse', 'son', 'daughter', 'father', 'mother'].map(r => `<span class="chip" onclick="A.apFamily(null,'${r}')">+ ${t(r)}</span>`).join('')}<span class="chip" onclick="A.apFamily(null,'')">+ ${t('other')}</span></div></div>
    ${AP.family.length ? AP.family.map((f, i) => `<div class="fam-card"><div class="avatar">${esc(initials(f.name_en))}</div><div class="body"><div class="t">${esc(f.name_en)}${f.name_ml ? ` <span class="muted small">${esc(f.name_ml)}</span>` : ''}</div><div class="s">${esc(t(f.relation || 'other'))}${f.dob ? ' · ' + esc(fmtDate(f.dob)) : ''}${f.blood_group ? ' · ' + esc(f.blood_group) : ''}${f.phone ? ' · ' + esc(f.phone) : ''}</div></div><button class="btn ghost sm" onclick="A.apFamily(${i})">${t('edit_family')}</button><button class="btn ghost sm" onclick="S.ap.family.splice(${i},1);apSave();renderApply()">✕</button></div>`).join('') : `<div class="notice info">${t('no_family_yet')}</div>`}</div>`;
  else if (step === 3) body = `<p class="muted">${t('photo_hint')}</p><div class="photo-pick">${AP.photo ? `<img class="pv" src="${AP.photo}">` : `<div class="pv">📷</div>`}<div class="stack"><label class="btn">📸 ${t('selfie')}<input type="file" accept="image/*" capture="user" hidden onchange="A.apPhoto(this.files[0])"></label><label class="btn ghost">🖼 ${t('from_gallery')}<input type="file" accept="image/*,.heic" hidden onchange="A.apPhoto(this.files[0])"></label>${AP.photo ? `<button class="btn ghost sm" onclick="S.ap.photo=null;apSave();renderApply()">${t('retake')}</button>` : ''}</div></div>`;
  else if (step === 4) body = `<form class="form" id="ap-f" onsubmit="return false">${F.text('password', t('choose_password'), d.password || '', { req: true, type: 'password', attrs: 'minlength="8" autocomplete="new-password"' })}${F.text('password2', t('confirm_password'), d.password2 || '', { req: true, type: 'password', attrs: 'autocomplete="new-password"' })}${F.select('lang', t('lang_pref'), d.lang || S.lang, [['ml', 'മലയാളം'], ['en', 'English']], { blank: false })}
    <div class="full"><h3>${t('preferences')}</h3><div class="chks">${F.chk('notify_whatsapp', t('notify_whatsapp'), d.notify_whatsapp)}${F.chk('notify_sms', t('notify_sms'), d.notify_sms)}${F.chk('notify_email', t('notify_email'), d.notify_email)}</div>${F.chk('show_phone', t('show_phone'), d.show_phone)}</div>
    <div class="full">${F.chk('consent_true', t('consent_true'), d.consent_true)}${F.chk('consent_msgs', t('consent_msgs'), d.consent_msgs)}<div class="small muted" style="margin-top:6px"><a href="/privacy?lang=${S.lang}" target="_blank">${t('privacy')}</a></div></div></form>`;
  else body = `<p class="muted">${t('review_hint')}</p><div class="grid2"><div class="card"><div class="row">${AP.photo ? `<img src="${AP.photo}" style="width:72px;height:88px;object-fit:cover;border-radius:10px">` : avatar({ name_en: d.name_en })}<div><b>${esc(d.name_en)}</b>${d.name_ml ? `<div>${esc(d.name_ml)}</div>` : ''}<div class="small muted">${esc(t(d.membership_type))}${d.dob ? ' · ' + esc(fmtDate(d.dob)) : ''}${d.blood_group ? ' · ' + esc(d.blood_group) : ''}</div></div></div>
    <dl class="kv" style="margin-top:10px"><dt>${t('phone')}</dt><dd>${esc(d.phone)}${d.whatsapp ? ' · WA ' + esc(d.whatsapp) : ''}</dd><dt>${t('email')}</dt><dd>${esc(d.email || '-')}</dd><dt>${t('address')}</dt><dd>${esc([d.house_en || d.house_ml, d.address_en || d.address_ml, d.ward ? t('ward') + ' ' + d.ward : '', d.pincode].filter(Boolean).join(', ') || '-')}</dd><dt>${t('occupation')}</dt><dd>${esc(d.occupation || '-')}</dd></dl></div>
    <div class="card"><h3>${t('family_members')} (${AP.family.length})</h3>${AP.family.map(f => `<div class="small">${esc(f.name_en)} · ${esc(t(f.relation || 'other'))}${f.dob ? ' · ' + esc(fmtDate(f.dob)) : ''}</div>`).join('') || `<div class="small muted">-</div>`}<h3 style="margin-top:12px">${t('preferences')}</h3><div class="small">${['notify_whatsapp', 'notify_sms', 'notify_email'].filter(k => d[k]).map(k => t(k)).join(', ') || t('none')} · ${d.lang === 'ml' ? 'മലയാളം' : 'English'}</div></div></div>`;
  const nav_ = `<div class="actions" style="justify-content:space-between"><div>${step > 0 ? `<button class="btn ghost" onclick="A.apGo(${step - 1})">‹ ${t('prev')}</button>` : `<a class="btn ghost" href="#/">${t('cancel')}</a>`}</div><div class="row"><span class="small muted">${t('draft_saved')}</span>${step < 5 ? `<button class="btn" onclick="A.apGo(${step + 1})">${t('next')} ›</button>` : `<button class="btn accent" id="ap-submit" onclick="A.apSubmit()">${t('submit_application')}</button>`}</div></div>`;
  render(pubShell(`<div class="card" style="max-width:860px;margin:0 auto"><h1>${t('apply_title')}</h1>${bar}${body}${nav_}</div>`));
}
A.apGo = n => { if (n > S.ap.step && !apCollect()) return; if (S.ap.step === 4 && n > 4) { const d = S.ap.data; if (d.password !== d.password2) return toast(t('pw_mismatch'), 'bad'); if (!d.consent_true) return toast(t('consent_true'), 'bad'); } S.ap.step = n; apSave(); renderApply(); };
A.apFamily = (i, rel) => { const f = i == null ? { relation: rel || '' } : S.ap.family[i]; const info = S.info;
  formSheet(i == null ? t('add_family') : t('edit_family'), `${F.text('name_en', t('name_en'), f.name_en, { req: true })}${F.text('name_ml', t('name_ml'), f.name_ml)}${F.select('relation', t('relation'), f.relation, info.relations)}${F.select('gender', t('gender'), f.gender, ['male', 'female', 'other'])}${F.date('dob', t('dob'), f.dob)}${F.select('blood_group', t('blood_group'), f.blood_group, info.blood_groups.map(b => [b, b]))}${F.text('phone', t('phone'), f.phone, { type: 'tel' })}${F.text('education', t('education'), f.education)}${F.text('occupation', t('occupation'), f.occupation)}`,
    async b => { if (i == null) S.ap.family.push(b); else S.ap.family[i] = b; apSave(); closeSheet(); renderApply(); }); };
A.apPhoto = file => { if (!file) return; const r = new FileReader(); r.onload = () => { const im = new Image(); im.onload = () => { const max = 900, sc = Math.min(1, max / Math.max(im.width, im.height)); const c = document.createElement('canvas'); c.width = Math.round(im.width * sc); c.height = Math.round(im.height * sc); c.getContext('2d').drawImage(im, 0, 0, c.width, c.height); S.ap.photo = c.toDataURL('image/jpeg', .85); S.ap.photoName = file.name; apSave(); renderApply(); }; im.onerror = () => toast(t('error'), 'bad'); im.src = r.result; }; r.readAsDataURL(file); };
A.apSubmit = async () => {
  const AP = S.ap, b = { ...AP.data, family: AP.family, unit_block: AP.data.ward }; delete b.password2; delete b.consent_true; delete b.consent_msgs; const btn = document.getElementById('ap-submit'); btn.disabled = true;
  try {
    if (AP.photo) { const bin = atob(AP.photo.split(',')[1]); const arr = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i); const fd = new FormData(); fd.append('file', new Blob([arr], { type: 'image/jpeg' }), 'photo.jpg'); b.photo = (await api('POST', '/api/public/photo', fd)).path; }
    await post('/api/public/apply', b); sessionStorage.removeItem('club_apply');
    render(pubShell(`<div class="card" style="max-width:600px;margin:0 auto"><h1 class="center">✓</h1><p class="center">${t('apply_done')}</p><h3>${t('what_next')}</h3><div class="steps"><div class="step">${t('next_1')}</div><div class="step">${t('next_2')}</div><div class="step">${t('next_3')}</div></div><div class="actions"><a class="btn" href="#/">${t('back')}</a></div></div>`));
  } catch (e) { btn.disabled = false; }
};

// ---------- home ----------
async function viewHome() {
  const d = await get('/api/dashboard'); const o = d.office; const m = S.user.member_id;
  const tile = (k, v, h, cls = '') => `<div class="tile ${cls}" onclick="nav('${h}')"><div class="v">${v}</div><div class="k">${esc(t(k))}</div></div>`;
  let html = `<h1>${t('welcome')}, ${esc(S.user.name.split(' ')[0])}</h1>`;
  const ft = S.info.features || { library: true }, ax = d.assoc || {};
  if (m) html += `<div class="tiles">${tile('notifications', d.unread || 0, '#/notifications', d.unread ? 'warn' : '')}${tile('my_actions', d.my_actions || 0, '#/actions?mine=1', d.my_actions ? 'warn' : '')}${ft.library ? tile('my_books', (d.my_books || []).length, '#/library/mine') : ''}${ft.maintenance ? tile('maint_due', money(ax.my_maint_due || 0), '#/payments', ax.my_maint_due ? 'bad' : 'ok') : ''}${tile('dues', money(d.my_dues || 0), '#/payments', d.my_dues ? 'bad' : 'ok')}${ft.helpdesk ? tile('my_tickets', ax.my_tickets || 0, '#/helpdesk?mine=1', ax.my_tickets ? 'warn' : '') : ''}</div>`;
  if (o) html += `<h2>${t('office')}</h2><div class="tiles">${tile('members_active', o.members_active, '#/members')}${tile('pending_apps', o.applications, '#/applications', o.applications ? 'warn' : '')}${tile('new_this_month', o.new_this_month, '#/members')}${tile('family_count', o.family, '#/members')}
    ${tile('meetings_month', o.meetings_month, '#/meetings')}${tile('mom_drafts', o.mom_drafts, '#/meetings', o.mom_drafts ? 'warn' : '')}${tile('actions_open', o.actions_open, '#/actions')}${tile('overdue', o.actions_overdue, '#/actions', o.actions_overdue ? 'bad' : '')}
    ${ft.library ? `${tile('books_total', o.books, '#/library')}${tile('books_out', o.books_out, '#/library/circulation')}${tile('books_overdue', o.books_overdue, '#/library/circulation?overdue=1', o.books_overdue ? 'bad' : '')}${tile('rr_today', o.reading_room_today, '#/library/reading-room')}` : ''}${ft.units ? `${tile('units', ax.units || 0, '#/units')}${tile('vacant', ax.units_vacant || 0, '#/units?status=vacant')}` : ''}${ft.maintenance ? `${tile('maint_due', money(ax.maint_due_amount || 0), '#/maintenance?tab=defaulters', ax.maint_due_amount ? 'warn' : '')}` : ''}${ft.helpdesk ? tile('tickets_open', ax.tickets_open || 0, '#/helpdesk', ax.tickets_open ? 'warn' : '') : ''}
    ${tile('dues_members', o.dues_members, '#/finance/dues', o.dues_members ? 'warn' : '')}${tile('outstanding', money(o.dues_amount), '#/finance/dues')}${tile('receipts_month', money(o.receipts_month), '#/finance')}${tile('payments_month', money(o.payments_month), '#/finance')}
    ${tile('outbox_pending', o.outbox_pending + (o.outbox_demo ? ` <span class="small muted">+${o.outbox_demo} demo</span>` : ''), '#/outbox', o.outbox_pending ? 'warn' : '')}${tile('outbox_failed', o.outbox_failed, '#/outbox?status=failed', o.outbox_failed ? 'bad' : '')}</div>`;
  html += `<div class="grid2"><div class="card"><h2>${t('upcoming')}</h2>${d.upcoming.length ? `<div class="list">${d.upcoming.map(p => `<div class="item click" onclick="nav('#/posts/${p.id}')"><div class="body"><div class="t">${esc(bil(p, 'title'))}</div><div class="s">${esc(t(p.kind === 'news' ? 'news_item' : p.kind))} · ${esc(fmtDT(p.starts_at))}${bil(p, 'venue') ? ' · ' + esc(bil(p, 'venue')) : ''}</div></div>${p.reg_open ? `<span class="pill accent">${t('reg_open')}</span>` : ''}</div>`).join('')}</div>` : empty()}</div>
  <div class="card"><h2>${t('latest_news')}</h2>${d.latest.length ? `<div class="list">${d.latest.map(p => `<div class="item click" onclick="nav('#/posts/${p.id}')">${p.cover ? `<img src="/uploads/${esc(p.cover)}" style="width:64px;height:48px;object-fit:cover;border-radius:8px">` : ''}<div class="body"><div class="t">${esc(bil(p, 'title'))}</div><div class="s">${esc(fmtTs(p.published_at))}</div></div></div>`).join('')}</div>` : empty()}</div>
  ${m ? `<div class="card"><h2>${t('my_meetings')}</h2>${(d.my_meetings || []).length ? `<div class="list">${d.my_meetings.map(x => `<div class="item click" onclick="nav('#/meetings/${x.id}')"><div class="body"><div class="t">${esc(bil(x, 'title'))}</div><div class="s">${esc(bil(x, 'committee'))} · ${esc(fmtDT(x.scheduled_at))}</div></div></div>`).join('')}</div>` : empty()}</div>` : ''}
  ${d.birthdays.length ? `<div class="card"><h2>🎂 ${t('birthdays_today')}</h2><div class="list">${d.birthdays.map(b => `<div class="item"><div class="body"><div class="t">${esc(nameOf(b))}</div></div></div>`).join('')}</div></div>` : ''}</div>`;
  render(html);
}

// ---------- me ----------
async function viewMe(tab) {
  const m = await get(`/api/members/${S.user.member_id}`); S.member = m;
  const T = tabs([['#/me', t('me')], ['#/me/family', t('family')], ['#/me/preferences', t('preferences')], ['#/me/password', t('change_password')]], location.hash.split('?')[0]);
  let body = '';
  const cardD = !tab ? await get(`/api/members/${m.id}/card.json`, { quiet: true }).catch(() => null) : null;
  if (!tab) body = (cardD ? ecardBlock(m.id, cardD) : '') + `<div class="card"><div class="row">${avatar(m)}<div><h2 style="margin:0">${esc(nameOf(m))}</h2><div class="muted">${esc(m.member_no)} · ${esc(t(m.membership_type))} · ${statusPill(m.status)}</div></div><div class="grow"></div><a class="btn ghost sm" target="_blank" href="/api/members/${m.id}/card?lang=${S.lang}">${t('card')}</a><button class="btn sm" onclick="A.editMe()">${t('edit')}</button></div>
    <dl class="kv" style="margin-top:14px"><dt>${t('phone')}</dt><dd>${esc(m.phone)}</dd><dt>${t('whatsapp')}</dt><dd>${esc(m.whatsapp || '-')}</dd><dt>${t('email')}</dt><dd>${esc(m.email || '-')}</dd><dt>${t('dob')}</dt><dd>${esc(fmtDate(m.dob) || '-')}</dd><dt>${t('blood_group')}</dt><dd>${esc(m.blood_group || '-')}</dd>
    <dt>${t('house')}</dt><dd>${esc(bil(m, 'house') || '-')}</dd><dt>${t('address')}</dt><dd>${esc(bil(m, 'address') || '-')}</dd><dt>${t('ward')}</dt><dd>${esc(m.ward || '-')}</dd><dt>${t('occupation')}</dt><dd>${esc(m.occupation || '-')}</dd><dt>${t('joined_on')}</dt><dd>${esc(fmtDate(m.joined_on))}</dd></dl>
    ${m.committees.length ? `<h3 style="margin-top:14px">${t('committees')}</h3>${m.committees.map(c => `<div><a href="#/committees/${c.committee_id}">${esc(bil(c, 'committee'))}</a> · ${esc(bil(c, 'designation') || t(c.role))}</div>`).join('')}` : ''}</div>`;
  else if (tab === 'family') body = familyHtml(m, true);
  else if (tab === 'preferences') body = `<div class="card"><form class="form" id="pref-f" onsubmit="return false"><div class="full chks">${F.chk('notify_whatsapp', t('notify_whatsapp'), m.notify_whatsapp)}${F.chk('notify_sms', t('notify_sms'), m.notify_sms)}${F.chk('notify_email', t('notify_email'), m.notify_email)}</div>${F.chk('show_phone', t('show_phone'), m.show_phone, { full: true })}${F.select('lang', t('lang_pref'), m.lang, [['ml', 'മലയാളം'], ['en', 'English']], { blank: false })}<div class="full actions"><button class="btn" onclick="A.savePrefs()">${t('save')}</button></div></form>
    <h3 style="margin-top:16px">${t('push_notifications')}</h3><div id="push-box" class="row"><span class="muted">…</span></div></div>`;
  else if (tab === 'password') body = `<div class="card" style="max-width:480px"><form class="form" id="pw-f" onsubmit="return false">${F.text('current', t('current_password'), '', { type: 'password', req: true, full: true })}${F.text('new', t('new_password'), '', { type: 'password', req: true, full: true, attrs: 'minlength="8"' })}<div class="full actions"><button class="btn" onclick="A.changePw()">${t('save')}</button></div></form></div>`;
  render(page(t('me'), '', '', T + body));
  fitCards();
  if (tab === 'preferences') renderPushBox();
}
function pushSupported() { return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window; }
async function renderPushBox() {
  const box = document.getElementById('push-box'); if (!box) return;
  if (!pushSupported()) { box.innerHTML = `<span class="muted small">${t('push_unsupported')}</span>`; return; }
  const reg = await navigator.serviceWorker.getRegistration(); const sub = reg ? await reg.pushManager.getSubscription() : null;
  box.innerHTML = sub ? `<span class="pill ok">${t('push_on')}</span> <button class="btn ghost sm" onclick="A.pushToggle(false)">${t('push_disable')}</button>` : `<span class="pill">${t('push_off')}</span> <button class="btn sm" onclick="A.pushToggle(true)">${t('push_enable')}</button>`;
}
A.pushToggle = async on => {
  try {
    const reg = await navigator.serviceWorker.register('/sw.js'); await navigator.serviceWorker.ready;
    if (on) {
      if ((await Notification.requestPermission()) !== 'granted') return toast(t('push_unsupported'), 'bad');
      const key = (await get('/api/push/key')).key; const raw = atob(key.replace(/-/g, '+').replace(/_/g, '/')); const arr = new Uint8Array([...raw].map(c => c.charCodeAt(0)));
      const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: arr });
      await post('/api/push/subscribe', sub.toJSON()); toast(t('push_on'), 'ok');
    } else { const sub = await reg.pushManager.getSubscription(); if (sub) { await post('/api/push/unsubscribe', { endpoint: sub.endpoint }); await sub.unsubscribe(); } }
  } catch (e) { toast(e.message, 'bad'); }
  renderPushBox();
};
function familyHtml(m, own) {
  const rows = m.family || [];
  return `<div class="card"><div class="row between"><h2>${t('family_members')}</h2><button class="btn sm" onclick="A.editFamily(${m.id})">+ ${t('add_family')}</button></div>
  ${rows.length ? tbl([{ h: t('name'), f: r => `<b>${esc(nameOf(r))}</b>${r.name_ml && r.name_en && S.lang === 'en' ? `<div class="small muted">${esc(r.name_ml)}</div>` : ''}` }, { h: t('relation'), f: r => esc(t(r.relation || 'other')) }, { h: t('dob'), f: r => esc(fmtDate(r.dob)) }, { h: t('blood_group'), f: r => esc(r.blood_group) }, { h: t('phone'), f: r => esc(r.phone) }, { h: t('education') + ' / ' + t('occupation'), f: r => esc([r.education, r.occupation].filter(Boolean).join(' · ')) },
    { h: '', f: r => `${r.verified ? `<span class="pill ok">${t('verified')}</span>` : `<span class="pill warn">${t('unverified')}</span>`} <button class="btn ghost sm" onclick="A.editFamily(${m.id},${r.id})">${t('edit')}</button> <button class="btn ghost sm" onclick="A.delFamily(${m.id},${r.id})">${t('delete')}</button>${!r.verified && can('members.manage') ? ` <button class="btn sm" onclick="A.verifyFamily(${m.id},${r.id})">${t('verify')}</button>` : ''}` }], rows) : empty()}</div>`;
}
A.editFamily = (mid, fid) => {
  const m = S.member && S.member.id === mid ? S.member : (S.viewMember || {}); const r = (m.family || []).find(x => x.id === fid) || {}; const info = S.info;
  formSheet(fid ? t('edit') : t('add_family'), `${F.text('name_en', t('name_en'), r.name_en, { req: true })}${F.text('name_ml', t('name_ml'), r.name_ml)}${F.select('relation', t('relation'), r.relation, info.relations)}${F.select('gender', t('gender'), r.gender, ['male', 'female', 'other'])}${F.date('dob', t('dob'), r.dob)}${F.select('blood_group', t('blood_group'), r.blood_group, info.blood_groups.map(b => [b, b]))}${F.text('phone', t('phone'), r.phone, { type: 'tel' })}${F.text('education', t('education'), r.education)}${F.text('occupation', t('occupation'), r.occupation)}${F.text('notes', t('notes'), r.notes)}`,
    async b => { await post(`/api/members/${mid}/family`, { ...b, id: fid }); closeSheet(); toast(t('saved'), 'ok'); App.route(); });
};
A.delFamily = async (mid, fid) => { if (await confirmDlg(t('confirm'))) { await del(`/api/members/${mid}/family/${fid}`); App.route(); } };
A.verifyFamily = async (mid, fid) => { await post(`/api/members/${mid}/family/${fid}/verify`); App.route(); };
A.editMe = () => memberForm(S.member, false);
A.savePrefs = async () => { const b = readForm(document.getElementById('pref-f')); await put(`/api/members/${S.user.member_id}`, b); toast(t('saved'), 'ok'); if (b.lang !== S.lang) setLang(b.lang); };
A.changePw = async () => { const f = document.getElementById('pw-f'); if (!f.reportValidity()) return; await post('/api/auth/password', readForm(f)); toast(t('password_changed'), 'ok'); nav('#/me'); };
async function memberForm(m, office) {
  const info = S.info; m = m || {}; if (office && info.features && info.features.units) S.unitsCache = await get('/api/units', { quiet: true }).catch(() => []); const types = info.membership_types.map(x => [x.key, S.lang === 'ml' ? x.ml : x.en]);
  const fields = `${F.text('name_en', t('name_en'), m.name_en, { req: true })}${F.text('name_ml', t('name_ml'), m.name_ml)}${F.select('gender', t('gender'), m.gender, ['male', 'female', 'other'])}${F.date('dob', t('dob'), m.dob)}
  ${F.text('phone', t('phone'), m.phone, { type: 'tel', req: office })}${F.text('whatsapp', t('whatsapp'), m.whatsapp, { type: 'tel' })}${F.text('email', t('email'), m.email, { type: 'email' })}${F.select('blood_group', t('blood_group'), m.blood_group, info.blood_groups.map(b => [b, b]))}
  ${F.text('house_en', t('house') + ' (English)', m.house_en)}${F.text('house_ml', t('house') + ' (മലയാളം)', m.house_ml)}${F.area('address_en', t('address') + ' (English)', m.address_en, { full: false, rows: 2 })}${F.area('address_ml', t('address') + ' (മലയാളം)', m.address_ml, { full: false, rows: 2 })}
  ${info.wards.length ? F.select('ward', t('ward'), m.ward, info.wards.map(w => [w, w])) : F.text('ward', t('ward'), m.ward)}${F.text('pincode', t('pincode'), m.pincode)}${F.text('occupation', t('occupation'), m.occupation)}${F.text('education', t('education'), m.education)}${F.text('interests', t('interests'), m.interests)}${F.text('id_proof', t('id_proof'), m.id_proof)}
  ${office && info.features && info.features.units ? `${F.select('unit_id', t('unit'), m.unit_id || '', (S.unitsCache || []).map(u => [u.id, u.label]))}${F.select('occupancy', t('occupancy'), m.occupancy || '', [['owner', t('owner')], ['tenant', t('tenant')], ['family', t('family_occ')]])}` : ''}
  ${office ? `${F.select('membership_type', t('membership_type'), m.membership_type || 'ordinary', types, { blank: false })}${F.date('joined_on', t('joined_on'), m.joined_on)}${!m.id ? F.text('member_no', t('member_no_auto')) : ''}${!m.id ? F.text('password', t('password') + ' (' + t('optional') + ')', '', { type: 'password' }) : ''}${F.area('notes', t('notes'), m.notes)}` : ''}
  ${F.file('photo_file', t('photo'))}${F.hidden('photo', m.photo || '')}`;
  formSheet(m.id ? t('edit') : t('office_entry'), fields, async (b, f) => {
    const fi = f.querySelector('[name=photo_file]'); if (fi.files[0]) { const u = await upload('members', fi.files[0]); b.photo = u.path; }
    delete b.photo_file;
    if (m.id) { await put(`/api/members/${m.id}`, b); closeSheet(); toast(t('saved'), 'ok'); App.route(); }
    else { const r = await post('/api/members', b); closeSheet(); S.membersCache = null; toast(`${t('approved_msg')} ${r.member_no}`, 'ok'); nav(`#/members/${r.id}`); }
  });
}

// ---------- notifications ----------
async function viewNotifications() {
  const rows = await get('/api/notifications');
  render(page(t('notifications'), '', `<button class="btn ghost sm" onclick="A.readAll()">${t('mark_all_read')}</button>`, `<div class="card">${rows.length ? `<div class="list">${rows.map(n => `<div class="item ${n.link ? 'click' : ''}" onclick="${n.link ? `nav('${esc(n.link)}')` : ''}" style="${n.read_at ? 'opacity:.65' : ''}"><div class="body"><div class="t">${esc(n.title)}</div><div class="s"><pre class="text">${esc(n.body)}</pre></div><div class="s">${esc(fmtTs(n.created))}</div></div>${n.read_at ? '' : '<span class="pill accent">●</span>'}</div>`).join('')}</div>` : empty()}</div>`));
  if (rows.some(n => !n.read_at)) post('/api/notifications/read', { ids: [] }, { quiet: true }).then(() => { S.unread = 0; }).catch(() => {});
}
A.readAll = async () => { await post('/api/notifications/read', { ids: [] }); S.unread = 0; App.route(); };

// ---------- routes ----------
R('/', () => S.user ? viewHome() : viewLanding());
R('/login', viewLogin);
R('/apply', viewApply);
R('/me', () => viewMe());
R('/me/:tab', ({ tab }) => viewMe(tab));
R('/notifications', viewNotifications);

// ---------- app ----------
const App = {
  async me() { const r = await get('/api/auth/me', { quiet: true }); S.user = r.user; S.member = r.member; S.info = r.info; S.settings = r.settings; S.unread = r.unread || 0; S.judging = r.judging || 0; if (S.user && S.user.lang && !localStorage.getItem('club_lang_set')) { S.lang = S.user.lang; localStorage.setItem('club_lang', S.lang); } document.documentElement.lang = S.lang; applyBrand(); },
  async start() {
    try { await this.me(); } catch (e) { render(`<div class="empty">${t('error')}<br><button class="btn" onclick="location.reload()">${t('retry')}</button></div>`); return; }
    window.addEventListener('hashchange', () => this.route());
    if ('serviceWorker' in navigator && (location.protocol === 'https:' || ['localhost', '127.0.0.1'].includes(location.hostname))) navigator.serviceWorker.register('/sw.js').catch(() => {});
    this.route();
  },
  async route() {
    if (S.user && S.info && S.info.plan && S.info.plan.read_only) await App.me();  // a reopened club recovers on its next step
    const full = location.hash.slice(1) || '/'; const [path, qs] = full.split('?'); const query = Object.fromEntries(new URLSearchParams(qs || ''));
    for (const [re, fn] of ROUTES) {
      const m = path.match(re); if (!m) continue;
      const params = { ...(m.groups || {}), query };
      if (!S.user && !['/', '/login', '/apply'].includes(path)) { sessionStorage.setItem('club_after', location.hash); return nav('#/login'); }
      if (S.user && (path === '/login' || path === '/apply')) return nav(sessionStorage.getItem('club_after') || '#/');
      sessionStorage.removeItem('club_after');
      try {
        if (S.user) { if (!document.getElementById('main')) document.getElementById('app').innerHTML = shell('<div class="empty">' + t('loading') + '</div>'); else { document.getElementById('app').innerHTML = shell(document.getElementById('main').innerHTML); } }
        await fn(params);
        if (S.user) { const side = document.querySelector('.side'); if (side) { document.querySelectorAll('.nav a').forEach(a => a.classList.toggle('on', a.getAttribute('href') === '#/' ? path === '/' : full.startsWith(a.getAttribute('href').slice(1)))); } }
      } catch (e) { console.error(e); if (!String(e.message).includes('sign in')) render(`<div class="empty">${esc(e.message || t('error'))}</div>`); }
      return;
    }
    render(empty());
  },
};
window.App = App; window.A = A; window.S = S;
