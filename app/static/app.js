/* Core: state, API, i18n, router, shell, forms. Other files add routes with R() and actions on A. */
'use strict';
const S = { user: null, member: null, info: null, settings: null, unread: 0, lang: (localStorage.getItem('club_lang') || 'ml'), membersCache: null };
const A = {};                      // actions referenced from markup: onclick="A.name(...)"
const ROUTES = [];
const R = (pattern, fn) => ROUTES.push([new RegExp('^' + pattern.replace(/:(\w+)/g, '(?<$1>[^/]+)') + '$'), fn]);

// ---------- i18n ----------
function t(k, vars) { let s = (I18N[S.lang] && I18N[S.lang][k]) || I18N.en[k] || k; if (vars) for (const v in vars) s = s.replace('{' + v + '}', vars[v]); return s; }
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
  items.push({ h: '#/library', l: t('library') }); if (m) { items.push({ h: '#/library/mine', l: t('my_books') }); items.push({ h: '#/payments', l: t('payments') }); }
  items.push({ h: '#/documents', l: t('documents') }); items.push({ h: '#/bookings', l: t('bookings') }); items.push({ h: '#/polls', l: t('polls') });
  if (S.judging) items.push({ h: '#/judging', l: t('judging') });
  const office = [];
  if (can('members.view') || can('library.manage') || can('posts.manage') || (u.convenes || []).length) office.push({ h: '#/scan', l: t('scan') });
  if (can('members.manage')) office.push({ h: '#/applications', l: t('applications') });
  if (can('members.view')) office.push({ h: '#/members', l: t('members') });
  if (can('broadcast.send')) office.push({ h: '#/broadcast', l: t('broadcast') });
  if (can('outbox.view')) office.push({ h: '#/outbox', l: t('outbox') });
  if (can('library.manage')) { office.push({ h: '#/library/circulation', l: t('circulation') }); office.push({ h: '#/library/reading-room', l: t('reading_room') }); office.push({ h: '#/library/periodicals', l: t('periodicals') }); office.push({ h: '#/assets', l: t('assets') }); }
  if (can('finance.view')) { office.push({ h: '#/finance', l: t('accounts') }); office.push({ h: '#/finance/dues', l: t('dues') }); }
  if (can('reports.view')) office.push({ h: '#/reports', l: t('reports') });
  if (can('users.manage')) office.push({ h: '#/users', l: t('users') });
  if (can('settings.manage')) { office.push({ h: '#/settings', l: t('settings') }); office.push({ h: '#/audit', l: t('audit') }); }
  return { items, office };
}
function shell(bodyHtml, title) {
  const { items, office } = navItems(); const cur = location.hash || '#/';
  const link = i => `<a href="${i.h}" class="${(i.h === '#/' ? cur === '#/' : cur.startsWith(i.h)) ? 'on' : ''}" onclick="document.querySelector('.side').classList.remove('open')">${esc(i.l)}${i.badge ? `<span class="badge">${i.badge}</span>` : ''}</a>`;
  const info = S.info || {};
  return `<div class="shell"><aside class="side"><div class="brand">${esc(S.lang === 'ml' ? (info.club_name_ml || info.club_name_en) : info.club_name_en)}<small>${esc(S.lang === 'ml' ? info.club_place_ml || info.club_place_en || '' : info.club_place_en || '')}</small></div>
  <nav class="nav">${items.map(link).join('')}${office.length ? `<div class="grp">${t('office')}</div>${office.map(link).join('')}` : ''}</nav>
  <div class="foot">${esc(S.user.name)} · ${esc(t(S.user.role))}<br>${langBtn()} <button class="lang-sw" onclick="A.logout()">${t('sign_out')}</button><br><br>${esc(info.footer_credit || '')}</div></aside>
  <div class="main"><div class="top"><button onclick="document.querySelector('.side').classList.toggle('open')">☰</button><div class="ttl">${esc(title || info.club_short || '')}</div>${langBtn()}</div><div id="main">${bodyHtml}</div></div></div>`;
}
A.logout = async () => { await post('/api/auth/logout'); S.user = null; S.member = null; S.membersCache = null; nav('#/'); };

// ---------- public screens ----------
function pubShell(body) {
  const info = S.info || {};
  return `<div class="pub"><header><div class="brand">${esc(S.lang === 'ml' ? (info.club_name_ml || info.club_name_en) : info.club_name_en)}<small>${esc(S.lang === 'ml' ? info.club_place_ml || info.club_place_en || '' : info.club_place_en || '')}</small></div>
  ${langBtn()} <a class="btn" href="/site?lang=${S.lang}">${t('website')}</a><a class="btn" href="#/login">${t('sign_in')}</a>${info.public_registration === '1' ? `<a class="btn accent" href="#/apply">${t('apply')}</a>` : ''}</header><main>${body}</main><footer>${esc(info.footer_credit || '')}</footer></div>`;
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
  const info = S.info; const types = info.membership_types.map(x => [x.key, (S.lang === 'ml' ? x.ml : x.en) + (x.admission || x.annual ? ` (${t('admission')} ₹${x.admission}, ${t('annual')} ₹${x.annual})` : '')]);
  const fam = () => `<div class="card fam-row" style="padding:10px 12px;margin-top:8px"><div class="form">${F.text('f_name_en', t('name_en'), '', { req: true })}${F.text('f_name_ml', t('name_ml'))}${F.select('f_relation', t('relation'), '', info.relations)}${F.date('f_dob', t('dob'))}${F.select('f_blood_group', t('blood_group'), '', info.blood_groups.map(b => [b, b]))}${F.text('f_phone', t('phone'))}${F.text('f_education', t('education'))}${F.text('f_occupation', t('occupation'))}</div><button type="button" class="btn ghost sm" style="margin-top:6px" onclick="this.parentNode.remove()">${t('remove')}</button></div>`;
  render(pubShell(`<div class="card" style="max-width:860px;margin:0 auto"><h1>${t('apply_title')}</h1><p class="muted">${t('apply_intro')}</p>
  <form id="apply-f" class="form" onsubmit="return false">
  ${F.text('name_en', t('name_en'), '', { req: true })}${F.text('name_ml', t('name_ml'))}${F.select('gender', t('gender'), '', ['male', 'female', 'other'])}${F.date('dob', t('dob'))}
  ${F.text('phone', t('phone'), '', { req: true, type: 'tel', attrs: 'inputmode="tel" pattern="[0-9 +-]{10,15}"' })}${F.text('whatsapp', t('whatsapp'), '', { type: 'tel' })}${F.text('email', t('email'), '', { type: 'email' })}${F.select('blood_group', t('blood_group'), '', info.blood_groups.map(b => [b, b]))}
  ${F.text('house_en', t('house') + ' (English)')}${F.text('house_ml', t('house') + ' (മലയാളം)')}${F.area('address_en', t('address') + ' (English)', '', { full: false, rows: 2 })}${F.area('address_ml', t('address') + ' (മലയാളം)', '', { full: false, rows: 2 })}
  ${info.wards.length ? F.select('ward', t('ward'), '', info.wards.map(w => [w, w])) : F.text('ward', t('ward'))}${F.text('pincode', t('pincode'))}${F.text('occupation', t('occupation'))}${F.text('education', t('education'))}
  ${F.select('membership_type', t('membership_type'), 'ordinary', types, { blank: false })}${F.text('interests', t('interests'))}${F.text('id_proof', t('id_proof'))}${F.select('lang', t('lang_pref'), S.lang, [['ml', 'മലയാളം'], ['en', 'English']], { blank: false })}
  <div class="full"><h3>${t('family_members')}</h3><div id="fam"></div><button type="button" class="btn ghost sm" id="add-fam" style="margin-top:8px">+ ${t('add_family')}</button></div>
  ${F.file('photo_file', t('take_photo'), { attrs: 'capture="user"' })}
  ${F.text('password', t('choose_password'), '', { req: true, type: 'password', attrs: 'minlength="8" autocomplete="new-password"' })}${F.text('password2', t('confirm_password'), '', { req: true, type: 'password', attrs: 'autocomplete="new-password"' })}
  <div class="full"><h3>${t('preferences')}</h3><div class="chks">${F.chk('notify_whatsapp', t('notify_whatsapp'), 1)}${F.chk('notify_sms', t('notify_sms'), 1)}${F.chk('notify_email', t('notify_email'), 1)}${F.chk('show_phone', t('show_phone'), 1)}</div></div>
  <div class="full actions"><button class="btn accent" id="apply-b">${t('apply')}</button><a class="btn ghost" href="#/">${t('cancel')}</a></div></form></div>`));
  document.getElementById('add-fam').onclick = () => document.getElementById('fam').insertAdjacentHTML('beforeend', fam());
  document.getElementById('apply-b').onclick = async () => {
    const f = document.getElementById('apply-f'); if (!f.reportValidity()) return; const b = readForm(f);
    if (b.password !== b.password2) return toast(t('pw_mismatch'), 'bad');
    b.family = [...document.querySelectorAll('.fam-row')].map(r => { const o = {}; r.querySelectorAll('[name]').forEach(el => o[el.name.replace(/^f_/, '')] = el.value); return o; });
    for (const k of Object.keys(b)) if (k.startsWith('f_')) delete b[k];
    const pf = f.querySelector('[name=photo_file]');
    try { if (pf && pf.files[0]) { const fd = new FormData(); fd.append('file', pf.files[0]); b.photo = (await api('POST', '/api/public/photo', fd)).path; } } catch (e) { return; }
    try { await post('/api/public/apply', b); render(pubShell(`<div class="card center" style="max-width:560px;margin:0 auto"><h1>✓</h1><p>${t('apply_done')}</p><a class="btn" href="#/">${t('back')}</a></div>`)); } catch (e) {}
  };
}

// ---------- home ----------
async function viewHome() {
  const d = await get('/api/dashboard'); const o = d.office; const m = S.user.member_id;
  const tile = (k, v, h, cls = '') => `<div class="tile ${cls}" onclick="nav('${h}')"><div class="v">${v}</div><div class="k">${esc(t(k))}</div></div>`;
  let html = `<h1>${t('welcome')}, ${esc(S.user.name.split(' ')[0])}</h1>`;
  if (m) html += `<div class="tiles">${tile('notifications', d.unread || 0, '#/notifications', d.unread ? 'warn' : '')}${tile('my_actions', d.my_actions || 0, '#/actions?mine=1', d.my_actions ? 'warn' : '')}${tile('my_books', (d.my_books || []).length, '#/library/mine')}${tile('dues', money(d.my_dues || 0), '#/payments', d.my_dues ? 'bad' : 'ok')}</div>`;
  if (o) html += `<h2>${t('office')}</h2><div class="tiles">${tile('members_active', o.members_active, '#/members')}${tile('pending_apps', o.applications, '#/applications', o.applications ? 'warn' : '')}${tile('new_this_month', o.new_this_month, '#/members')}${tile('family_count', o.family, '#/members')}
    ${tile('meetings_month', o.meetings_month, '#/meetings')}${tile('mom_drafts', o.mom_drafts, '#/meetings', o.mom_drafts ? 'warn' : '')}${tile('actions_open', o.actions_open, '#/actions')}${tile('overdue', o.actions_overdue, '#/actions', o.actions_overdue ? 'bad' : '')}
    ${tile('books_total', o.books, '#/library')}${tile('books_out', o.books_out, '#/library/circulation')}${tile('books_overdue', o.books_overdue, '#/library/circulation?overdue=1', o.books_overdue ? 'bad' : '')}${tile('rr_today', o.reading_room_today, '#/library/reading-room')}
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
  if (!tab) body = `<div class="card"><div class="row">${avatar(m)}<div><h2 style="margin:0">${esc(nameOf(m))}</h2><div class="muted">${esc(m.member_no)} · ${esc(t(m.membership_type))} · ${statusPill(m.status)}</div></div><div class="grow"></div><a class="btn ghost sm" target="_blank" href="/api/members/${m.id}/card?lang=${S.lang}">${t('card')}</a><button class="btn sm" onclick="A.editMe()">${t('edit')}</button></div>
    <dl class="kv" style="margin-top:14px"><dt>${t('phone')}</dt><dd>${esc(m.phone)}</dd><dt>${t('whatsapp')}</dt><dd>${esc(m.whatsapp || '-')}</dd><dt>${t('email')}</dt><dd>${esc(m.email || '-')}</dd><dt>${t('dob')}</dt><dd>${esc(fmtDate(m.dob) || '-')}</dd><dt>${t('blood_group')}</dt><dd>${esc(m.blood_group || '-')}</dd>
    <dt>${t('house')}</dt><dd>${esc(bil(m, 'house') || '-')}</dd><dt>${t('address')}</dt><dd>${esc(bil(m, 'address') || '-')}</dd><dt>${t('ward')}</dt><dd>${esc(m.ward || '-')}</dd><dt>${t('occupation')}</dt><dd>${esc(m.occupation || '-')}</dd><dt>${t('joined_on')}</dt><dd>${esc(fmtDate(m.joined_on))}</dd></dl>
    ${m.committees.length ? `<h3 style="margin-top:14px">${t('committees')}</h3>${m.committees.map(c => `<div><a href="#/committees/${c.committee_id}">${esc(bil(c, 'committee'))}</a> · ${esc(bil(c, 'designation') || t(c.role))}</div>`).join('')}` : ''}</div>`;
  else if (tab === 'family') body = familyHtml(m, true);
  else if (tab === 'preferences') body = `<div class="card"><form class="form" id="pref-f" onsubmit="return false"><div class="full chks">${F.chk('notify_whatsapp', t('notify_whatsapp'), m.notify_whatsapp)}${F.chk('notify_sms', t('notify_sms'), m.notify_sms)}${F.chk('notify_email', t('notify_email'), m.notify_email)}</div>${F.chk('show_phone', t('show_phone'), m.show_phone, { full: true })}${F.select('lang', t('lang_pref'), m.lang, [['ml', 'മലയാളം'], ['en', 'English']], { blank: false })}<div class="full actions"><button class="btn" onclick="A.savePrefs()">${t('save')}</button></div></form>
    <h3 style="margin-top:16px">${t('push_notifications')}</h3><div id="push-box" class="row"><span class="muted">…</span></div></div>`;
  else if (tab === 'password') body = `<div class="card" style="max-width:480px"><form class="form" id="pw-f" onsubmit="return false">${F.text('current', t('current_password'), '', { type: 'password', req: true, full: true })}${F.text('new', t('new_password'), '', { type: 'password', req: true, full: true, attrs: 'minlength="8"' })}<div class="full actions"><button class="btn" onclick="A.changePw()">${t('save')}</button></div></form></div>`;
  render(page(t('me'), '', '', T + body));
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
function memberForm(m, office) {
  const info = S.info; m = m || {}; const types = info.membership_types.map(x => [x.key, S.lang === 'ml' ? x.ml : x.en]);
  const fields = `${F.text('name_en', t('name_en'), m.name_en, { req: true })}${F.text('name_ml', t('name_ml'), m.name_ml)}${F.select('gender', t('gender'), m.gender, ['male', 'female', 'other'])}${F.date('dob', t('dob'), m.dob)}
  ${F.text('phone', t('phone'), m.phone, { type: 'tel', req: office })}${F.text('whatsapp', t('whatsapp'), m.whatsapp, { type: 'tel' })}${F.text('email', t('email'), m.email, { type: 'email' })}${F.select('blood_group', t('blood_group'), m.blood_group, info.blood_groups.map(b => [b, b]))}
  ${F.text('house_en', t('house') + ' (English)', m.house_en)}${F.text('house_ml', t('house') + ' (മലയാളം)', m.house_ml)}${F.area('address_en', t('address') + ' (English)', m.address_en, { full: false, rows: 2 })}${F.area('address_ml', t('address') + ' (മലയാളം)', m.address_ml, { full: false, rows: 2 })}
  ${info.wards.length ? F.select('ward', t('ward'), m.ward, info.wards.map(w => [w, w])) : F.text('ward', t('ward'), m.ward)}${F.text('pincode', t('pincode'), m.pincode)}${F.text('occupation', t('occupation'), m.occupation)}${F.text('education', t('education'), m.education)}${F.text('interests', t('interests'), m.interests)}${F.text('id_proof', t('id_proof'), m.id_proof)}
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
  async me() { const r = await get('/api/auth/me', { quiet: true }); S.user = r.user; S.member = r.member; S.info = r.info; S.settings = r.settings; S.unread = r.unread || 0; S.judging = r.judging || 0; if (S.user && S.user.lang && !localStorage.getItem('club_lang_set')) { S.lang = S.user.lang; localStorage.setItem('club_lang', S.lang); } document.documentElement.lang = S.lang; document.title = S.info.club_short || 'Club'; },
  async start() {
    try { await this.me(); } catch (e) { render(`<div class="empty">${t('error')}<br><button class="btn" onclick="location.reload()">${t('retry')}</button></div>`); return; }
    window.addEventListener('hashchange', () => this.route());
    if ('serviceWorker' in navigator && (location.protocol === 'https:' || ['localhost', '127.0.0.1'].includes(location.hostname))) navigator.serviceWorker.register('/sw.js').catch(() => {});
    this.route();
  },
  async route() {
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
