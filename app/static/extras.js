/* Documents, assets, hall booking, QR scanning, judging, annual report. */
'use strict';
const DOC_CAT_LABEL = c => t({ minutes: 'minutes_doc', audit: 'audit_doc' }[c] || c);
async function viewDocuments({ query }) {
  const rows = await get('/api/documents' + (query.category ? '?category=' + query.category : '')); const cats = S.settings.doc_categories;
  const groups = {}; rows.forEach(d => (groups[d.category] = groups[d.category] || []).push(d));
  render(page(t('documents'), '', can('posts.manage') ? `<button class="btn" onclick="A.docForm()">+ ${t('add_document')}</button>` : '', `<div class="tabs">${[['', t('all')], ...cats.map(c => [c, DOC_CAT_LABEL(c)])].map(([c, l]) => `<a href="#/documents${c ? '?category=' + c : ''}" class="${(query.category || '') === c ? 'on' : ''}">${esc(l)}</a>`).join('')}</div>
    ${rows.length ? Object.entries(groups).map(([c, ds]) => `<div class="card"><h2>${esc(DOC_CAT_LABEL(c))}</h2><div class="list">${ds.map(d => `<div class="item"><div class="body"><div class="t">${esc(bil(d, 'title'))}</div><div class="s">${esc([d.year, d.audience === 'public' ? t('public').split(' ')[0] : d.audience === 'committee' ? bil(d, 'committee') : t('members_only'), d.size ? (d.size / 1024 / 1024).toFixed(1) + ' MB' : '', d.note].filter(Boolean).join(' · '))}</div></div><a class="btn ghost sm" target="_blank" href="/uploads/${esc(d.path)}">${t('download')}</a>${can('posts.manage') ? `<button class="btn ghost sm" onclick="A.docForm(${JSON.stringify(d).replace(/"/g, '&quot;')})">${t('edit')}</button><button class="btn ghost sm" onclick="A.docDel(${d.id})">✕</button>` : ''}</div>`).join('')}</div></div>`).join('') : `<div class="card">${empty()}</div>`}`));
}
A.docForm = async (d = {}) => { const coms = await get('/api/committees'); formSheet(d.id ? t('edit') : t('add_document'), `${F.bi('title', t('title'), d, { req: true })}${F.select('category', t('category'), d.category || 'other', S.settings.doc_categories.map(c => [c, DOC_CAT_LABEL(c)]), { blank: false })}${F.text('year', t('year'), d.year)}${F.select('audience', t('audience'), d.audience || 'members', [['members', t('members_only')], ['public', t('public')], ['committee', t('committee_only')]], { blank: false })}${F.select('committee_id', t('committee'), d.committee_id, coms.map(c => [c.id, bil(c, 'name')]))}${F.text('note', t('notes'), d.note, { full: true })}${d.id ? '' : F.file('doc_file', t('file'), { accept: '.pdf,image/*', req: true, full: true })}`,
  async (b, f) => { const fi = f.querySelector('[name=doc_file]'); if (fi && fi.files[0]) { const u = await upload('docs', fi.files[0]); b.path = u.path; b.mime = u.mime; b.size = u.size; } delete b.doc_file; await post('/api/documents', { ...b, id: d.id }); closeSheet(); App.route(); }); };
A.docDel = async id => { if (await confirmDlg(t('confirm'))) { await del(`/api/documents/${id}`); App.route(); } };

// ---------- assets ----------
const ASSET_CAT = c => t(c === 'sports' ? 'sports_cat' : c);
async function viewAssets({ query }) {
  const rows = await get('/api/assets?' + new URLSearchParams(Object.fromEntries(Object.entries(query).filter(([k, v]) => v)))); const manage = can('library.manage');
  render(page(t('assets'), '', manage ? `<button class="btn" onclick="A.assetForm()">+ ${t('add_asset')}</button><button class="btn ghost" onclick="A.remindLoans()">${t('remind_loans')}</button>` : '', `<form class="search" id="af" onsubmit="return false"><input class="in" name="q" placeholder="${t('search')}" value="${esc(query.q || '')}"><select class="in" name="category" style="max-width:200px"><option value="">${t('category')}</option>${S.settings.asset_categories.map(c => `<option value="${c}" ${query.category === c ? 'selected' : ''}>${esc(ASSET_CAT(c))}</option>`).join('')}</select><button class="btn" onclick="(()=>{const b=readForm(document.getElementById('af'));nav('#/assets?'+new URLSearchParams(Object.fromEntries(Object.entries(b).filter(([k,v])=>v))))})()">${t('search')}</button></form>
    <div class="card">${tbl([{ h: t('asset_code'), f: a => `<span class="num">${esc(a.code)}</span>` }, { h: t('name'), f: a => `<b>${esc(bil(a, 'name'))}</b><div class="small muted">${esc(ASSET_CAT(a.category))}${a.location ? ' · ' + esc(a.location) : ''}</div>` }, { h: t('quantity'), num: true, f: a => a.qty }, { h: t('available_qty'), num: true, f: a => `${a.available}${a.out ? ` <span class="pill warn">${a.out} ${t('out').toLowerCase()}</span>` : ''}` }, { h: t('condition'), f: a => esc(t(a.condition)) }], rows, a => `class="click" onclick="nav('#/assets/${a.id}')"`)}</div>`));
}
async function viewAsset({ id }) {
  const a = await get(`/api/assets/${id}`); S.asset = a; const manage = can('library.manage'); await membersForPick();
  render(page(bil(a, 'name'), `${esc(a.code)} · ${esc(ASSET_CAT(a.category))}`, manage ? `<button class="btn ghost" onclick="A.assetForm(S.asset)">${t('edit')}</button><button class="btn" onclick="A.lendForm(${a.id})">${t('lend')}</button>` : '', `<div class="card"><dl class="kv"><dt>${t('quantity')}</dt><dd>${a.qty} · ${t('available_qty')} ${a.available}</dd><dt>${t('condition')}</dt><dd>${esc(t(a.condition))}</dd><dt>${t('rack')}</dt><dd>${esc(a.location || '-')}</dd><dt>${t('price')}</dt><dd>${money(a.cost)} ${a.purchased_on ? '· ' + esc(fmtDate(a.purchased_on)) : ''}</dd>${a.notes ? `<dt>${t('notes')}</dt><dd>${esc(a.notes)}</dd>` : ''}</dl></div>
    <div class="card"><h2>${t('loans')}</h2>${a.loans.length ? tbl([{ h: t('lent_to'), f: l => l.member_id ? `<a href="#/members/${l.member_id}">${esc(nameOf(l))}</a> <span class="small muted num">${esc(l.member_no)}</span>` : `${esc(l.party)} <span class="small muted num">${esc(l.phone)}</span>` }, { h: t('quantity'), num: true, f: l => l.qty }, { h: t('lent_on'), f: l => esc(fmtDate(l.lent_on)) }, { h: t('due'), f: l => `${esc(fmtDate(l.due_on))} ${!l.returned_on && l.due_on && l.due_on < today() ? statusPill('overdue') : ''}` }, { h: t('returned'), f: l => l.returned_on ? esc(fmtDate(l.returned_on)) : (manage ? `<button class="btn sm" onclick="A.returnLoan(${l.id})">${t('return')}</button>` : statusPill('out')) }, { h: t('notes'), f: l => esc(l.note) }], a.loans) : empty()}</div>`));
}
A.assetForm = (a = {}) => formSheet(a.id ? t('edit') : t('add_asset'), `${F.bi('name', t('name'), a, { req: true })}${F.text('code', t('asset_code'), a.code, { ph: 'auto' })}${F.select('category', t('category'), a.category || 'other', S.settings.asset_categories.map(c => [c, ASSET_CAT(c)]), { blank: false })}${F.num('qty', t('quantity'), a.qty ?? 1, { attrs: 'min="0"' })}${F.text('location', t('rack'), a.location)}${F.select('condition', t('condition'), a.condition || 'good', ['good', 'damaged', 'binding'].map(c => [c, t(c)]), { blank: false })}${F.date('purchased_on', t('date'), a.purchased_on)}${F.num('cost', t('price'), a.cost || 0)}${F.area('notes', t('notes'), a.notes)}${a.id ? F.chk('active', t('active'), a.active) : ''}`,
  async b => { const r = await post('/api/assets', { ...b, id: a.id }); closeSheet(); nav(`#/assets/${r.id}`); if (a.id) App.route(); });
A.lendForm = aid => formSheet(t('lend'), `${F.member('member_id', t('member'), '', { full: true })}${F.text('party', t('party_name'))}${F.text('phone', t('phone'), '', { type: 'tel' })}${F.num('qty', t('quantity'), 1, { attrs: 'min="1"' })}${F.date('lent_on', t('lent_on'), today())}${F.date('due_on', t('due'))}${F.text('note', t('notes'), '', { full: true })}`,
  async b => { if (!b.member_id && !b.party) return toast(t('select_member'), 'bad'); await post(`/api/assets/${aid}/lend`, b); closeSheet(); App.route(); }, { saveLabel: t('lend') });
A.returnLoan = lid => formSheet(t('return'), `${F.select('condition', t('condition'), 'good', ['good', 'damaged', 'lost'].map(c => [c, t(c)]), { blank: false, full: true })}${F.text('note', t('notes'), '', { full: true })}`, async b => { await post(`/api/assets/loans/${lid}/return`, b); closeSheet(); App.route(); }, { saveLabel: t('return') });
A.remindLoans = async () => { const r = await post('/api/assets/loans/remind'); toast(`${t('sent')}: ${r.queued}`, 'ok'); };

// ---------- bookings ----------
async function viewBookings({ query }) {
  const month = query.month || new Date().toISOString().slice(0, 7); const office = can('finance.view');
  const [facs, cal, mine] = await Promise.all([get('/api/facilities'), get('/api/bookings/calendar?month=' + month), get('/api/bookings' + (office ? '?month=' + month : '?mine=1'))]);
  const d = new Date(month + '-01'); const prev = new Date(d.getFullYear(), d.getMonth() - 1, 1).toISOString().slice(0, 7), next = new Date(d.getFullYear(), d.getMonth() + 1, 1).toISOString().slice(0, 7);
  const byDay = {}; cal.forEach(b => (byDay[b.starts_at.slice(0, 10)] = byDay[b.starts_at.slice(0, 10)] || []).push(b));
  const days = new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate();
  const grid = Array.from({ length: days }, (_, i) => { const ds = `${month}-${String(i + 1).padStart(2, '0')}`; const bs = byDay[ds] || []; return `<div class="tile" style="padding:6px 8px;min-height:60px;cursor:default"><div class="small muted num">${i + 1}</div>${bs.map(b => `<div class="small" style="line-height:1.25"><span class="pill ${b.status === 'confirmed' ? 'ok' : 'warn'}" style="font-size:.65rem">${esc(bil(b, 'facility'))}</span> ${esc(b.starts_at.slice(11, 16))}–${esc(b.ends_at.slice(11, 16))}${b.purpose ? `<div class="muted">${esc(b.purpose)}</div>` : ''}</div>`).join('')}</div>`; }).join('');
  render(page(t('bookings'), '', `${S.user.member_id || office ? `<button class="btn accent" onclick="A.bookingForm()">${t('book_now')}</button>` : ''}${can('finance.manage') ? `<button class="btn ghost" onclick="A.facilityForm()">+ ${t('add_facility')}</button>` : ''}`,
    `<div class="card"><h2>${t('facilities')}</h2><div class="list">${facs.map(f => `<div class="item"><div class="body"><div class="t">${esc(bil(f, 'name'))} ${!f.active ? statusPill('inactive') : ''}</div><div class="s">${esc(bil(f, 'description'))}${f.rate_hour ? ` · ${money(f.rate_hour)}/h` : ''}${f.rate_day ? ` · ${money(f.rate_day)}/${t('date').toLowerCase()}` : ''}${f.deposit ? ` · ${t('deposit').split(' ')[0]} ${money(f.deposit)}` : ''}${f.capacity ? ` · ${f.capacity} ${t('capacity').toLowerCase()}` : ''}</div></div>${can('finance.manage') ? `<button class="btn ghost sm" onclick="A.facilityForm(${JSON.stringify(f).replace(/"/g, '&quot;')})">${t('edit')}</button>` : ''}</div>`).join('') || empty()}</div></div>
    <div class="card"><div class="row between"><h2>${t('calendar')}</h2><div class="row"><a class="btn ghost sm" href="#/bookings?month=${prev}">‹</a><b>${esc(MONTHS[S.lang][d.getMonth()])} ${d.getFullYear()}</b><a class="btn ghost sm" href="#/bookings?month=${next}">›</a></div></div><div class="tiles" style="grid-template-columns:repeat(auto-fill,minmax(120px,1fr))">${grid}</div></div>
    <div class="card"><h2>${office ? t('all_bookings') : t('my_bookings')}</h2>${mine.length ? tbl([{ h: t('facility'), f: b => `<b>${esc(bil(b, 'facility'))}</b><div class="small muted">${esc(b.purpose)}</div>` }, { h: t('starts'), f: b => esc(fmtDT(b.starts_at)) }, { h: t('ends'), f: b => esc(fmtDT(b.ends_at)) }, ...(office ? [{ h: t('member'), f: b => b.member_id ? `<a href="#/members/${b.member_id}">${esc(nameOf(b))}</a>` : `${esc(b.party)} <span class="small muted num">${esc(b.phone)}</span>` }] : []), { h: t('amount'), num: true, f: b => money(b.amount) }, { h: t('status'), f: b => `${statusPill(b.status)}${b.receipt_id ? ' ' + statusPill('paid') : ''}` },
      { h: '', f: b => `${can('finance.manage') && b.status === 'requested' ? `<button class="btn sm" onclick="A.bookingStatus(${b.id},'confirmed')">${t('confirm_collect')}</button> ` : ''}${can('finance.manage') && b.status === 'confirmed' ? `<button class="btn ghost sm" onclick="A.bookingStatus(${b.id},'done')">${t('done')}</button> ` : ''}${['requested', 'confirmed'].includes(b.status) ? `<button class="btn ghost sm" onclick="A.bookingStatus(${b.id},'cancelled')">${t('cancel')}</button>` : ''}` }], mine) : empty()}</div>`));
  S._facs = facs;
}
A.facilityForm = (f = {}) => formSheet(f.id ? t('edit') : t('add_facility'), `${F.bi('name', t('name'), f, { req: true })}${F.bi('description', t('description'), f)}${F.num('rate_hour', t('rate_hour'), f.rate_hour || 0)}${F.num('rate_day', t('rate_day'), f.rate_day || 0)}${F.num('deposit', t('deposit'), f.deposit || 0)}${F.num('capacity', t('capacity'), f.capacity || 0)}${f.id ? F.chk('active', t('active'), f.active) : ''}`, async b => { await post('/api/facilities', { ...b, id: f.id }); closeSheet(); App.route(); });
A.bookingForm = async () => { const office = can('finance.manage'); if (office) await membersForPick(); const facs = (S._facs || []).filter(f => f.active);
  formSheet(t('book_now'), `${F.select('facility_id', t('facility'), facs[0] && facs[0].id, facs.map(f => [f.id, bil(f, 'name')]), { req: true, blank: false, full: true })}${F.dt('starts_at', t('starts'), '', { req: true })}${F.dt('ends_at', t('ends'), '', { req: true })}${F.text('purpose', t('purpose'), '', { full: true })}${office ? `${F.member('member_id', t('member'), '')}${F.text('party', t('party_name'))}${F.text('phone', t('phone'), '', { type: 'tel' })}${F.num('amount', t('amount') + ' (' + t('optional') + ')', '')}${F.chk('confirm', t('confirmed'), 0)}` : ''}`,
    async b => { const r = await post('/api/bookings', b); closeSheet(); toast(office ? `${money(r.amount)}` : t('booking_sent'), 'ok'); App.route(); }, { saveLabel: t('book_now') }); };
A.bookingStatus = (id, st) => { if (st === 'confirmed') return formSheet(t('confirm_collect'), `${F.chk('collect', t('collect_fee'), 1, { full: true })}${F.select('mode', t('mode_pay'), 'cash', ['cash', 'upi', 'bank', 'cheque'], { blank: false })}${F.text('ref', t('ref'))}${F.text('note', t('notes'), '', { full: true })}`, async b => { await post(`/api/bookings/${id}/status`, { ...b, status: st }); closeSheet(); App.route(); });
  formSheet(t(st), F.text('note', t('notes'), '', { full: true }), async b => { await post(`/api/bookings/${id}/status`, { ...b, status: st }); closeSheet(); App.route(); }); };

// ---------- QR scanning ----------
let scanStream = null, scanTimer = null;
async function viewScan() {
  const [meetings, posts] = await Promise.all([get('/api/meetings').catch(() => []), get('/api/posts?upcoming=1').catch(() => [])]);
  const opts = [];
  if (can('library.manage')) opts.push(['rr', t('reading_room')]);
  meetings.filter(m => m.my_role === 'manage' && m.status === 'scheduled').slice(0, 10).forEach(m => opts.push(['meeting:' + m.id, `${t('meeting')}: ${bil(m, 'title')} (${fmtDate(m.scheduled_at)})`]));
  if (can('posts.manage')) posts.filter(p => p.kind !== 'news').slice(0, 10).forEach(p => opts.push(['post:' + p.id, `${t('event')}: ${bil(p, 'title')}`]));
  render(page(t('scan'), t('scan_intro'), '', `<div class="card"><div class="form">${F.select('ctx', t('scan_for'), opts[0] && opts[0][0], opts, { blank: false, full: true, attrs: 'id="scan-ctx"' })}
    <div class="full"><video id="scan-video" playsinline muted style="width:100%;max-height:320px;background:#000;border-radius:12px;display:none"></video></div>
    <div class="full row"><button class="btn" id="scan-start" onclick="A.scanStart()">${t('start_camera')}</button><button class="btn ghost hidden" id="scan-stop" onclick="A.scanStop()">${t('stop_camera')}</button><span class="small muted" id="scan-msg"></span></div>
    <form class="full row" onsubmit="A.scanCode(document.getElementById('scan-manual').value);return false"><input class="in" id="scan-manual" placeholder="${t('scan_manual')}" style="max-width:260px"><button class="btn ghost">${t('marked')}</button></form></div></div>
    <div class="card"><h2>${t('scanned_list')}</h2><div class="list" id="scan-list">${empty()}</div></div>`));
  if (!('BarcodeDetector' in window)) document.getElementById('scan-msg').textContent = t('camera_unavailable');
  S._scanned = [];
}
A.scanStart = async () => {
  if (!('BarcodeDetector' in window) || !navigator.mediaDevices) return toast(t('camera_unavailable'), 'bad');
  const v = document.getElementById('scan-video'); try { scanStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } }); } catch (e) { return toast(e.message, 'bad'); }
  v.srcObject = scanStream; v.style.display = 'block'; await v.play(); document.getElementById('scan-start').classList.add('hidden'); document.getElementById('scan-stop').classList.remove('hidden');
  const det = new BarcodeDetector({ formats: ['qr_code'] }); let last = '', lastAt = 0;
  scanTimer = setInterval(async () => { try { const codes = await det.detect(v); const c = codes[0] && codes[0].rawValue; if (c && (c !== last || Date.now() - lastAt > 4000)) { last = c; lastAt = Date.now(); A.scanCode(c); } } catch (e) {} }, 500);
};
A.scanStop = () => { clearInterval(scanTimer); if (scanStream) scanStream.getTracks().forEach(tr => tr.stop()); scanStream = null; const v = document.getElementById('scan-video'); if (v) { v.style.display = 'none'; } document.getElementById('scan-start').classList.remove('hidden'); document.getElementById('scan-stop').classList.add('hidden'); };
A.scanCode = async code => {
  if (!code) return; const ctx = (document.getElementById('scan-ctx') || {}).value || ''; let m;
  try { m = await get('/api/scan/' + encodeURIComponent(code)); } catch (e) { return; }
  let what = '';
  try {
    if (ctx === 'rr') { await post('/api/library/reading-room', { member_id: m.id }); what = t('reading_room'); }
    else if (ctx.startsWith('meeting:')) { await post(`/api/meetings/${ctx.slice(8)}/attendance`, { attendance: [{ member_id: m.id, status: 'present' }] }); what = t('present'); }
    else if (ctx.startsWith('post:')) { await post(`/api/posts/${ctx.slice(5)}/attend`, { member_id: m.id }); what = t('attended'); }
  } catch (e) { return; }
  S._scanned.unshift({ m, what, at: new Date() }); toast(`✓ ${nameOf(m)} · ${what}`, 'ok'); if (navigator.vibrate) navigator.vibrate(80);
  document.getElementById('scan-list').innerHTML = S._scanned.map(x => `<div class="item">${avatar(x.m)}<div class="body"><div class="t">${esc(nameOf(x.m))} <span class="small muted num">${esc(x.m.member_no)}</span></div><div class="s">${esc(x.what)} · ${x.at.toLocaleTimeString()}</div></div></div>`).join('');
  const inp = document.getElementById('scan-manual'); if (inp) inp.value = '';
};

// ---------- judging ----------
async function viewJudging() {
  const rows = await get('/api/judging');
  render(page(t('my_judging'), '', '', `<div class="card"><div class="list">${rows.map(p => `<div class="item click" onclick="nav('#/judging/${p.id}')"><div class="body"><div class="t">${esc(bil(p, 'title'))}</div><div class="s">${esc(fmtDT(p.starts_at))}</div></div></div>`).join('') || empty()}</div></div>`));
}
async function viewScoreSheet({ id }) {
  const d = await get(`/api/posts/${id}/judging`); const p = await get(`/api/posts/${id}`);
  render(page(t('score_sheet'), esc(bil(p, 'title')), `<button class="btn" onclick="A.saveScores(${id})">${t('save_scores')}</button>`, `<form id="ss" onsubmit="return false">${d.items.map(it => `<div class="card"><h2>${esc(bil(it, 'name'))} ${it.age_group ? `<span class="pill">${esc(it.age_group)}</span>` : ''}</h2>${tbl([{ h: '#', f: r => r.id }, { h: t('name'), f: r => `<b>${esc(r.participant_name)}</b>${r.team ? ` <span class="small muted">${esc(r.team)}</span>` : ''}` }, { h: t('score'), f: r => `<input class="in num" type="number" step="0.5" min="0" max="100" name="s_${r.id}" value="${r.score ?? ''}" style="width:90px">` }, { h: t('remark'), f: r => `<input class="in" name="r_${r.id}" value="${esc(r.remark)}">` }], d.registrations.filter(r => r.item_id === it.id))}</div>`).join('') || `<div class="card">${empty()}</div>`}</form>`));
}
A.saveScores = async id => { const f = document.getElementById('ss'); const scores = [...f.querySelectorAll('[name^=s_]')].filter(i => i.value !== '').map(i => ({ registration_id: Number(i.name.slice(2)), score: Number(i.value), remark: (f.querySelector(`[name=r_${i.name.slice(2)}]`) || {}).value || '' })); const r = await post(`/api/posts/${id}/scores`, { scores }); toast(`${t('saved')}: ${r.saved}`, 'ok'); };

// ---------- annual report ----------
async function viewAnnual({ query }) {
  const year = query.year || new Date().getFullYear(); const r = await get('/api/reports/annual?year=' + year);
  const tile = (k, v) => `<div class="tile" style="cursor:default"><div class="v">${v}</div><div class="k">${esc(k)}</div></div>`; const types = Object.fromEntries(S.settings.membership_types.map(x => [x.key, S.lang === 'ml' ? x.ml : x.en]));
  render(page(`${t('annual_report')} ${year}`, '', `<select class="in" style="width:auto" onchange="nav('#/reports/annual?year='+this.value)">${r.years.map(y => `<option ${String(y) === String(year) ? 'selected' : ''}>${y}</option>`).join('')}</select><a class="btn" target="_blank" href="/api/reports/annual/print?year=${year}&lang=${S.lang}">${t('open_report')}</a>`,
    `<h2>${t('members')}</h2><div class="tiles">${tile(t('members_active'), r.members.active)}${tile(t('joined_this_year'), r.members.joined)}${tile(t('family_members'), r.members.family)}${r.members.by_type.map(x => tile(types[x.k] || x.k, x.n)).join('')}</div>
    <h2>${t('news')}</h2><div class="card">${r.events.length ? tbl([{ h: t('title'), f: x => `<a href="#/posts/${x.id}">${esc(bil(x, 'title'))}</a>` }, { h: t('kind'), f: x => esc(kindLabel(x.kind)) }, { h: t('when'), f: x => esc(fmtDate(x.starts_at)) }, { h: t('participants'), num: true, f: x => x.participants }], r.events) : empty()}</div>
    <h2>${t('meetings')}</h2><div class="card">${r.meetings.length ? tbl([{ h: t('committee'), f: x => esc(bil(x, 'name')) }, { h: t('meetings'), num: true, f: x => x.meetings }, { h: t('present'), num: true, f: x => x.avg_present.toFixed(1) }], r.meetings) : empty()}${r.resolutions.length ? `<h3 style="margin-top:12px">${t('resolutions')}</h3>${r.resolutions.map(x => `<div style="padding:6px 0;border-bottom:1px solid var(--line)"><b>${esc(x.resolution_no)}</b> ${esc(bil(x, 'title'))} <span class="small muted">${esc(bil(x, 'committee'))} · ${esc(fmtDate(x.scheduled_at))}</span><div class="small">${esc(bil(x, 'decision'))}</div></div>`).join('')}` : ''}</div>
    <h2>${t('library')}</h2><div class="tiles">${tile(t('books'), r.library.books)}${tile(t('added'), r.library.added)}${tile(t('issues_count'), r.library.issues)}${tile(t('active_readers'), r.library.readers)}${tile(t('reading_room'), r.library.reading_room)}${tile(t('fine'), money(r.library.fines))}</div>
    <h2>${t('accounts')}</h2><div class="tiles">${tile(t('receipts'), money(r.accounts.receipts))}${tile(t('vouchers'), money(r.accounts.payments))}${tile(t('surplus'), money(r.accounts.receipts - r.accounts.payments))}${tile(t('outstanding'), money(r.accounts.dues))}${tile(t('bookings'), r.bookings)}${tile(t('assets'), r.assets)}</div>
    <div class="card">${tbl([{ h: t('head'), f: h => `${h.kind === 'receipt' ? '▲' : '▼'} ${esc(headLabel(h.head))}` }, { h: t('total'), num: true, f: h => money(h.total) }], r.accounts.by_head)}</div>`));
}
R('/documents', viewDocuments);
R('/assets', viewAssets);
R('/assets/:id', viewAsset);
R('/bookings', viewBookings);
R('/scan', viewScan);
R('/judging', viewJudging);
R('/judging/:id', viewScoreSheet);
R('/reports/annual', viewAnnual);
