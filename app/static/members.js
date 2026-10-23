/* Office: applications, members register, member detail, directory, broadcast, outbox. */
'use strict';
async function viewApplications() {
  const rows = await get('/api/members/applications');
  render(page(t('applications'), '', '', rows.length ? rows.map(a => `<div class="card"><div class="row">${avatar(a)}<div class="grow"><h2 style="margin:0">${esc(nameOf(a))}${a.name_ml && S.lang === 'en' ? ` <span class="muted">${esc(a.name_ml)}</span>` : ''}</h2><div class="muted small">${esc(t('applied_on'))} ${esc(fmtTs(a.applied_at))} · ${esc(t(a.membership_type))} · ${t('ward')} ${esc(a.ward || '-')}</div></div>
    <a class="btn wa sm" target="_blank" href="${esc(a.wa_link)}">${t('wa_chat')}</a><a class="btn ghost sm" href="tel:${esc(a.phone)}">${t('call')}</a></div>
    <dl class="kv" style="margin-top:10px"><dt>${t('phone')}</dt><dd>${esc(a.phone)} ${a.whatsapp && a.whatsapp !== a.phone ? `(WA ${esc(a.whatsapp)})` : ''}</dd><dt>${t('email')}</dt><dd>${esc(a.email || '-')}</dd><dt>${t('dob')}</dt><dd>${esc(fmtDate(a.dob) || '-')} ${a.gender ? '· ' + esc(t(a.gender)) : ''}</dd><dt>${t('blood_group')}</dt><dd>${esc(a.blood_group || '-')}</dd>
    <dt>${t('address')}</dt><dd>${esc([bil(a, 'house'), bil(a, 'address'), a.pincode].filter(Boolean).join(', ') || '-')}</dd><dt>${t('occupation')}</dt><dd>${esc(a.occupation || '-')} ${a.education ? '· ' + esc(a.education) : ''}</dd><dt>${t('id_proof')}</dt><dd>${esc(a.id_proof || '-')}</dd><dt>${t('interests')}</dt><dd>${esc(a.interests || '-')}</dd></dl>
    ${a.family.length ? `<h3 style="margin-top:10px">${t('family_members')}</h3>${a.family.map(f => `<div class="small">${esc(nameOf(f))} · ${esc(t(f.relation || 'other'))}${f.dob ? ' · ' + esc(fmtDate(f.dob)) : ''}${f.blood_group ? ' · ' + esc(f.blood_group) : ''}</div>`).join('')}` : ''}
    <div class="actions"><button class="btn" onclick="A.decide(${a.id},'approve')">✓ ${t('approve')}</button><button class="btn ghost" onclick="A.decide(${a.id},'reject')">${t('reject')}</button><button class="btn ghost" onclick="nav('#/members/${a.id}')">${t('details')}</button></div></div>`).join('') : `<div class="card">${empty()}</div>`));
}
A.decide = (id, decision) => {
  const types = S.info.membership_types.map(x => [x.key, S.lang === 'ml' ? x.ml : x.en]);
  formSheet(t(decision), decision === 'approve' ? `${F.text('member_no', t('member_no_auto'))}${F.select('membership_type', t('membership_type'), '', types)}${F.date('joined_on', t('joined_on'), today())}${F.area('note', t('decision_note'))}` : F.area('note', t('decision_note'), '', { req: true }),
    async b => { const r = await post(`/api/members/${id}/decide`, { ...b, decision }); closeSheet(); S.membersCache = null; toast(decision === 'approve' ? `${t('approved_msg')} ${r.member_no}` : t('saved'), 'ok'); viewApplications(); }, { saveLabel: t(decision) });
};

async function viewMembers({ query }) {
  const q = new URLSearchParams(Object.fromEntries(Object.entries(query).filter(([k, v]) => v))).toString();
  const rows = await get('/api/members?' + (q || 'status=active'));
  const info = S.info; const types = info.membership_types.map(x => [x.key, S.lang === 'ml' ? x.ml : x.en]);
  const filt = `<form class="search" id="mf" onsubmit="return false;"><input class="in" name="q" placeholder="${t('search')}" value="${esc(query.q || '')}"><select class="in" name="status" style="max-width:160px"><option value="">${t('all')}</option>${['active', 'applied', 'inactive', 'suspended', 'resigned', 'deceased', 'rejected'].map(s => `<option ${query.status === s || (!query.status && !q && s === 'active') ? 'selected' : ''} value="${s}">${t(s)}</option>`).join('')}</select>
    <select class="in" name="mtype" style="max-width:180px"><option value="">${t('membership_type')}</option>${types.map(([v, l]) => `<option value="${v}" ${query.mtype === v ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select>
    ${info.wards.length ? `<select class="in" name="ward" style="max-width:120px"><option value="">${t('ward')}</option>${info.wards.map(w => `<option ${query.ward === w ? 'selected' : ''}>${esc(w)}</option>`).join('')}</select>` : ''}
    <select class="in" name="blood" style="max-width:120px"><option value="">${t('blood_group')}</option>${info.blood_groups.map(b => `<option ${query.blood === b ? 'selected' : ''}>${b}</option>`).join('')}</select><button class="btn" onclick="A.filterMembers()">${t('filter')}</button></form>`;
  render(page(t('members'), `${rows.length} ${t('count').toLowerCase()}`, `${can('members.manage') ? `<button class="btn" onclick="memberForm(null,true)">+ ${t('office_entry')}</button><button class="btn ghost" onclick="A.importSheet()">${t('import_members')}</button>` : ''}<button class="btn ghost" onclick="A.printCards()">${t('print_cards')}</button><a class="btn ghost" href="/api/members/export/csv">${t('export_csv')}</a><a class="btn ghost" href="/api/members/export/family.csv">${t('family')} CSV</a>`,
    filt + `<div class="card">${tbl([{ h: t('member_no'), f: r => `<span class="num">${esc(r.member_no || '-')}</span>` }, { h: t('name'), f: r => `<div class="row" style="gap:8px">${avatar(r)}<div><b>${esc(nameOf(r))}</b><div class="small muted">${esc(bil(r, 'house'))}${r.ward ? ' · ' + t('ward') + ' ' + esc(r.ward) : ''}</div></div></div>` },
      { h: t('phone'), f: r => `<span class="num">${esc(r.phone)}</span>${r.wa_link ? ` <a class="pill ok" target="_blank" href="${esc(r.wa_link)}" onclick="event.stopPropagation()">WA</a>` : ''}` }, { h: t('membership_type'), f: r => esc(t(r.membership_type)) }, { h: t('blood_group'), f: r => esc(r.blood_group) }, { h: t('family_count'), num: true, f: r => r.family_count },
      { h: t('dues'), num: true, f: r => r.dues ? `<span class="pill warn">${money(r.dues)}</span>` : '' }, { h: t('status'), f: r => statusPill(r.status) }], rows, r => `class="click" onclick="nav('#/members/${r.id}')"`)}</div>`));
}
A.importSheet = () => {
  sheet(`<p class="small muted">${t('import_intro')}</p><div class="actions" style="margin-top:0"><a class="btn ghost" href="/api/members/import/template.xlsx">${t('download_template')}</a><label class="btn">${t('choose_file')}<input type="file" accept=".xlsx" hidden onchange="A.importPreview(this.files[0])"></label></div><div id="imp-out"></div>`, t('import_members'));
};
async function importPost(file, commit) { const fd = new FormData(); fd.append('file', file); return api('POST', `/api/members/import?commit=${commit}`, fd); }
A.importPreview = async file => {
  if (!file) return; S._importFile = file; const out = document.getElementById('imp-out'); out.innerHTML = `<div class="empty">${t('loading')}</div>`;
  const r = await importPost(file, 0);
  const rowsHtml = (rows) => rows.length ? `<div class="tbl-wrap"><table class="tbl"><tr><th>${t('row')}</th><th>${t('member_no')}</th><th>${t('name')}</th><th>${t('errors')}</th></tr>${rows.map(x => `<tr><td>${x.row}</td><td>${esc(x.member_no || '')}</td><td>${esc(x.name_en)}</td><td>${x.errors.length ? `<span class="pill bad">${esc(x.errors.join('; '))}</span>` : '<span class="pill ok">✓</span>'}</td></tr>`).join('')}</table></div>` : '';
  out.innerHTML = `<div class="row" style="margin:10px 0"><span class="pill ok">${t('valid_rows')}: ${r.valid}</span><span class="pill ${r.invalid ? 'bad' : ''}">${t('invalid_rows')}: ${r.invalid}</span><span class="pill">${t('family')}: ${r.family_valid}</span></div>${rowsHtml(r.members)}${r.family.length ? `<h3 style="margin-top:10px">${t('family')}</h3>${rowsHtml(r.family)}` : ''}
    <div class="actions">${r.valid ? `<button class="btn accent" onclick="A.importCommit()">${t('import_now', { n: r.valid })}</button>` : ''}</div>`;
};
A.importCommit = async () => { const r = await importPost(S._importFile, 1); closeSheet(); S.membersCache = null; toast(`${t('imported')}: ${r.created} + ${r.family_created} ${t('family').toLowerCase()}`, 'ok'); nav('#/members'); };
A.printCards = () => { const info = S.info; formSheet(t('print_cards'), `<p class="full small muted">${t('cards_hint')}</p>${F.select('mtype', t('membership_type'), '', info.membership_types.map(x => [x.key, S.lang === 'ml' ? x.ml : x.en]), { blank: t('all') })}${info.wards.length ? F.select('ward', t('ward'), '', info.wards.map(w => [w, w]), { blank: t('all') }) : F.text('ward', t('ward'))}${F.select('lang', t('language'), S.lang, [['ml', 'മലയാളം'], ['en', 'English']], { blank: false })}`,
  async b => { window.open('/api/members/print/cards?' + new URLSearchParams(Object.fromEntries(Object.entries(b).filter(([k, v]) => v))), '_blank'); closeSheet(); }, { saveLabel: t('print') }); };
A.filterMembers = () => { const b = readForm(document.getElementById('mf')); nav('#/members?' + new URLSearchParams(Object.fromEntries(Object.entries(b).filter(([k, v]) => v))).toString()); };

async function viewMember({ id, tab }) {
  const m = await get(`/api/members/${id}`); S.viewMember = m; const manage = can('members.manage');
  const cur = `#/members/${id}` + (tab ? '/' + tab : '');
  const T = tabs([[`#/members/${id}`, t('details')], [`#/members/${id}/family`, `${t('family')} (${m.family.length})`], [`#/members/${id}/payments`, t('payments')], [`#/members/${id}/books`, t('books')], [`#/members/${id}/activity`, t('timeline')]], cur);
  let body;
  if (!tab) body = `<div class="card"><dl class="kv"><dt>${t('member_no')}</dt><dd><b class="num">${esc(m.member_no || '-')}</b></dd><dt>${t('status')}</dt><dd>${statusPill(m.status)} ${m.decision_note ? `<span class="small muted">${esc(m.decision_note)}</span>` : ''}</dd><dt>${t('membership_type')}</dt><dd>${esc(t(m.membership_type))}</dd><dt>${t('joined_on')}</dt><dd>${esc(fmtDate(m.joined_on) || '-')}</dd>
    <dt>${t('phone')}</dt><dd class="num">${esc(m.phone)} ${m.wa_link ? `<a class="pill ok" target="_blank" href="${esc(m.wa_link)}">WA</a>` : ''}</dd><dt>${t('whatsapp')}</dt><dd class="num">${esc(m.whatsapp || '-')}</dd><dt>${t('email')}</dt><dd>${esc(m.email || '-')}</dd><dt>${t('gender')} / ${t('dob')}</dt><dd>${esc(m.gender ? t(m.gender) : '-')} · ${esc(fmtDate(m.dob) || '-')}</dd><dt>${t('blood_group')}</dt><dd>${esc(m.blood_group || '-')}</dd>
    <dt>${t('house')}</dt><dd>${esc(bil(m, 'house') || '-')}</dd><dt>${t('address')}</dt><dd>${esc(bil(m, 'address') || '-')} ${m.pincode ? '· ' + esc(m.pincode) : ''}</dd><dt>${t('ward')}</dt><dd>${esc(m.ward || '-')}</dd><dt>${t('occupation')}</dt><dd>${esc(m.occupation || '-')}</dd><dt>${t('education')}</dt><dd>${esc(m.education || '-')}</dd>
    <dt>${t('interests')}</dt><dd>${esc(m.interests || '-')}</dd><dt>${t('id_proof')}</dt><dd>${esc(m.id_proof || '-')}</dd><dt>${t('preferences')}</dt><dd>${['notify_whatsapp', 'notify_sms', 'notify_email'].filter(k => m[k]).map(k => t(k)).join(', ') || t('none')} · ${m.lang === 'ml' ? 'മലയാളം' : 'English'}</dd>
    ${manage ? `<dt>${t('notes')}</dt><dd>${esc(m.notes || '-')}</dd><dt>${t('sign_in')}</dt><dd>${m.user ? `${esc(m.user.login)} · ${m.user.active ? t('active') : t('inactive')} · ${t('last_login')}: ${esc(fmtTs(m.user.last_login) || '-')}` : '-'}</dd>` : ''}</dl>
    ${m.committees.length ? `<h3 style="margin-top:14px">${t('committees')}</h3>${m.committees.map(c => `<div><a href="#/committees/${c.committee_id}">${esc(bil(c, 'committee'))}</a> · ${esc(bil(c, 'designation') || t(c.role))}</div>`).join('')}` : ''}</div>`;
  else if (tab === 'family') body = familyHtml(m, false);
  else if (tab === 'payments') body = `<div class="card"><h2>${t('dues')}</h2>${m.subscriptions.length ? tbl([{ h: t('for_year'), f: s => s.year ? s.year : t('admission_fee') }, { h: t('amount'), num: true, f: s => money(s.amount) }, { h: t('paid'), num: true, f: s => money(s.paid) }, { h: t('status'), f: s => statusPill(s.status) }], m.subscriptions) : empty()}
    ${can('finance.manage') ? `<div class="actions"><button class="btn" onclick="A.txForm('receipt',{member_id:${m.id}})">+ ${t('new_receipt')}</button></div>` : ''}</div><div class="card"><h2>${t('receipts')}</h2>${m.receipts.length ? tbl([{ h: '#', f: r => esc(r.no) }, { h: t('date'), f: r => esc(fmtDate(r.tx_date)) }, { h: t('head'), f: r => esc(headLabel(r.head)) }, { h: t('amount'), num: true, f: r => money(r.amount) }, { h: t('mode_pay'), f: r => esc(t(r.mode)) }], m.receipts) : empty()}</div>`;
  else if (tab === 'books') body = `<div class="card">${m.issues.length ? tbl([{ h: t('book'), f: i => `<b>${esc(bil(i, 'title'))}</b> <span class="small muted num">${esc(i.accession_no)}</span>` }, { h: t('issued_on'), f: i => esc(fmtDate(i.issued_on)) }, { h: t('due_on'), f: i => esc(fmtDate(i.due_on)) }, { h: t('returned_on'), f: i => i.returned_on ? esc(fmtDate(i.returned_on)) : statusPill(i.due_on < today() ? 'overdue' : 'issued') }, { h: t('fine'), num: true, f: i => i.fine ? money(i.fine) : '' }], m.issues) : empty()}</div>`;
  else if (tab === 'activity') body = `<div class="card">${m.registrations.length ? `<h2>${t('my_registrations')}</h2>${tbl([{ h: t('event'), f: r => `<a href="#/posts/${r.post_id}">${esc(bil(r, 'title'))}</a>` }, { h: t('participants'), f: r => esc(r.participant_name) }, { h: t('when'), f: r => esc(fmtDT(r.starts_at)) }, { h: t('status'), f: r => statusPill(r.status) }], m.registrations)}` : ''}
    <h2 style="margin-top:14px">${t('timeline')}</h2><div class="list">${m.log.map(l => `<div class="item"><div class="body"><div class="t">${esc(l.kind)} <span class="small muted">${esc(l.text)}</span></div><div class="s">${esc(fmtTs(l.ts))} ${l.by_name ? '· ' + esc(l.by_name) : ''}</div></div></div>`).join('') || empty()}</div></div>`;
  const acts = manage ? `<button class="btn" onclick="memberForm(S.viewMember,true)">${t('edit')}</button><button class="btn ghost" onclick="A.memberStatus(${m.id})">${t('change_status')}</button><button class="btn ghost" onclick="A.memberPw(${m.id})">${t('reset_password')}</button>` : '';
  render(page(nameOf(m), `${esc(m.member_no || t('applied'))} ${m.name_ml && S.lang === 'en' ? '· ' + esc(m.name_ml) : ''}`, `${acts}${m.status === 'active' ? `<a class="btn ghost" target="_blank" href="/api/members/${m.id}/card?lang=${S.lang}">${t('card')}</a>` : ''}${m.wa_link ? `<a class="btn wa" target="_blank" href="${esc(m.wa_link)}">${t('wa_chat')}</a>` : ''}`, T + body));
}
A.memberStatus = id => formSheet(t('change_status'), `${F.select('status', t('status'), 'active', ['active', 'inactive', 'suspended', 'resigned', 'deceased'], { blank: false, full: true })}${F.area('note', t('notes'))}`, async b => { await post(`/api/members/${id}/status`, b); closeSheet(); S.membersCache = null; App.route(); });
A.memberPw = id => formSheet(t('reset_password'), F.text('password', t('new_password'), '', { type: 'text', req: true, full: true, attrs: 'minlength="8"' }), async b => { await post(`/api/members/${id}/reset-password`, b); closeSheet(); toast(t('saved'), 'ok'); });

async function viewDirectory({ query }) {
  const rows = await get('/api/members/directory?' + new URLSearchParams(Object.fromEntries(Object.entries(query).filter(([k, v]) => v))));
  render(page(t('directory'), '', '', `<form class="search" onsubmit="return false" id="df"><input class="in" name="q" placeholder="${t('search')}" value="${esc(query.q || '')}"><select class="in" name="blood" style="max-width:140px"><option value="">${t('blood_group')}</option>${S.info.blood_groups.map(b => `<option ${query.blood === b ? 'selected' : ''}>${b}</option>`).join('')}</select><button class="btn" onclick="(()=>{const b=readForm(document.getElementById('df'));nav('#/directory?'+new URLSearchParams(Object.fromEntries(Object.entries(b).filter(([k,v])=>v))))})()">${t('search')}</button></form>
  <div class="card"><div class="list">${rows.map(m => `<div class="item">${avatar(m)}<div class="body"><div class="t">${esc(nameOf(m))} <span class="small muted num">${esc(m.member_no)}</span></div><div class="s">${esc([bil(m, 'house'), m.ward ? t('ward') + ' ' + m.ward : '', m.occupation].filter(Boolean).join(' · '))}${m.blood_group ? ` · <b>${esc(m.blood_group)}</b>` : ''}</div></div>${m.phone ? `<a class="btn ghost sm" href="tel:${esc(m.phone)}">${t('call')}</a>` : ''}${m.wa_link ? `<a class="btn wa sm" target="_blank" href="${esc(m.wa_link)}">WA</a>` : ''}</div>`).join('') || empty()}</div></div>`));
}

async function viewBroadcast() {
  const [coms, posts, hist] = await Promise.all([get('/api/committees'), get('/api/posts?upcoming=1'), get('/api/broadcasts')]); await membersForPick();
  const ch = S.settings.channels; const chk = (k, l) => `<label class="chk"><input type="checkbox" name="ch_${k}" ${k === 'app' || k === 'whatsapp' ? 'checked' : ''}> ${l} ${ch[k] ? '' : `<span class="pill warn">${t('demo')}</span>`}</label>`;
  render(page(t('broadcast'), t('comms_help'), '', `<div class="card"><form class="form" id="bf" onsubmit="return false">
    ${F.select('kind', t('audience'), 'all', [['all', t('audience_all')], ['ward', t('audience_ward')], ['type', t('audience_type')], ['committee', t('audience_committee')], ['post', t('audience_post')], ['blood', t('audience_blood')], ['dues', t('audience_dues')], ['members', t('audience_members')]], { blank: false, attrs: 'onchange="A.bcKind(this.value)"' })}
    <div id="bc-val">${F.text('value', '—', '', { attrs: 'disabled' })}</div>
    <div class="full"><span class="small muted">${t('channels')}</span><div class="chks">${chk('app', t('in_app'))}${chk('whatsapp', 'WhatsApp')}${chk('sms', 'SMS')}${chk('email', t('email'))}</div></div>
    ${F.text('subject', t('subject'), '', { full: true })}${F.area('body_en', t('message_en'), '', { full: false })}${F.area('body_ml', t('message_ml'), '', { full: false })}${F.dt('send_at', t('send_at'))}
    <div class="full actions"><button class="btn ghost" onclick="A.bcPreview()">${t('recipients')}: <span id="bc-n">?</span></button><button class="btn accent" onclick="A.bcSend()">${t('send')}</button><button class="btn ghost" onclick="A.bloodRequest()">🩸 ${t('blood_request')}</button></div></form></div>
    <div class="card"><h2>${t('previous_broadcasts')}</h2>${hist.length ? tbl([{ h: t('date'), f: r => esc(fmtTs(r.created)) }, { h: t('subject'), f: r => `<b>${esc(r.subject)}</b><div class="small muted">${esc((r.body_ml || r.body_en).slice(0, 90))}</div>` }, { h: t('channels'), f: r => esc(r.channels) }, { h: t('recipients'), num: true, f: r => r.recipients }, { h: t('status'), f: r => `${r.send_at ? `<span class="pill brand">${t('scheduled_label')} ${esc(fmtTs(r.send_at))}</span> ` : ''}${Object.entries(r.delivery).map(([k, v]) => `${statusPill(k)} ${v}`).join(' ')}${r.send_at && r.delivery.pending ? ` <button class="btn ghost sm" onclick="A.bcCancel(${r.id})">${t('cancel_scheduled')}</button>` : ''}` }], hist) : empty()}</div>`));
  S._bc = { coms, posts };
}
A.bcKind = k => {
  const el = document.getElementById('bc-val'); const info = S.info; const { coms, posts } = S._bc;
  const opts = { ward: info.wards.map(w => [w, w]), type: info.membership_types.map(x => [x.key, S.lang === 'ml' ? x.ml : x.en]), committee: coms.map(c => [c.id, bil(c, 'name')]), post: posts.map(p => [p.id, bil(p, 'title')]), blood: info.blood_groups.map(b => [b, b]) }[k];
  if (k === 'members') el.innerHTML = F.wrap('value', t('select_member'), `<textarea class="in" name="value" placeholder="${t('type_to_search')}" list="members-dl"></textarea><div class="help">${esc(t('select_member'))}: <input class="in" list="members-dl" id="bc-pick" onchange="A.bcAddMember(this)"></div>`);
  else if (opts) el.innerHTML = F.select('value', t('audience'), '', opts, { blank: false });
  else if (k === 'ward' && !info.wards.length) el.innerHTML = F.text('value', t('ward'));
  else el.innerHTML = F.text('value', '—', '', { attrs: 'disabled' });
};
A.bcAddMember = inp => { const id = memberIdFromLabel(inp.value); if (id) { const ta = document.querySelector('#bc-val textarea'); ta.value = (ta.value ? ta.value + ',' : '') + id; inp.value = ''; } };
function bcBody() { const b = readForm(document.getElementById('bf')); const aud = { kind: b.kind, value: b.kind === 'members' ? String(b.value || '').split(',').filter(Boolean) : b.value }; const channels = ['app', 'whatsapp', 'sms', 'email'].filter(c => b['ch_' + c]); return { audience: aud, channels, subject: b.subject, body_en: b.body_en, body_ml: b.body_ml, send_at: b.send_at || null }; }
A.bcCancel = async id => { if (await confirmDlg(t('confirm'))) { await post(`/api/broadcasts/${id}/cancel`); viewBroadcast(); } };
A.bloodRequest = () => formSheet(t('blood_request'), `${F.select('blood', t('blood_group'), '', S.info.blood_groups.map(b => [b, b]), { req: true, blank: false })}${F.text('patient', t('patient'), '', { req: true })}${F.text('hospital', t('hospital'), '', { req: true })}${F.text('contact', t('contact'), '', { req: true, type: 'tel' })}${F.text('detail', t('detail'))}`,
  async b => {
    const f = document.getElementById('bf'); f.querySelector('[name=kind]').value = 'blood'; A.bcKind('blood'); f.querySelector('[name=value]').value = b.blood;
    f.querySelector('[name=subject]').value = `${b.blood} blood needed · ${b.blood} രക്തം ആവശ്യമുണ്ട്`;
    f.querySelector('[name=body_en]').value = `URGENT: ${b.blood} blood is needed for ${b.patient} at ${b.hospital}. ${b.detail || ''} Please contact ${b.contact}.`.replace(/\s+/g, ' ');
    f.querySelector('[name=body_ml]').value = `അടിയന്തരം: ${b.hospital}-ൽ ${b.patient}-ന് ${b.blood} രക്തം ആവശ്യമുണ്ട്. ${b.detail || ''} ദയവായി ${b.contact}-ൽ ബന്ധപ്പെടുക.`.replace(/\s+/g, ' ');
    ['app', 'whatsapp', 'sms'].forEach(c => { const el = f.querySelector(`[name=ch_${c}]`); if (el) el.checked = true; });
    closeSheet(); A.bcPreview();
  }, { saveLabel: t('preview') });
A.bcPreview = async () => { const r = await post('/api/broadcast/preview', bcBody()); document.getElementById('bc-n').textContent = r.recipients; };
A.bcSend = async () => { const b = bcBody(); const n = (await post('/api/broadcast/preview', b)).recipients; if (!(await confirmDlg(`${t('send')} → ${n} ${t('recipients').toLowerCase()}?`))) return; const r = await post('/api/broadcast', b); toast(`${t('sent')}: ${r.queued}`, 'ok'); viewBroadcast(); };

async function viewOutbox({ query }) {
  const d = await get('/api/outbox?' + new URLSearchParams(query));
  const cnt = d.counts; const chs = d.channels;
  render(page(t('outbox'), `<span class="pill ${chs.whatsapp ? 'ok' : 'warn'}">WhatsApp: ${chs.whatsapp ? t('configured') : t('not_configured')}</span> <span class="pill ${chs.sms ? 'ok' : 'warn'}">SMS: ${chs.sms ? t('configured') : t('not_configured')}</span> <span class="pill ${chs.email ? 'ok' : 'warn'}">${t('email')}: ${chs.email ? t('configured') : t('not_configured')}</span>`,
    `<button class="btn ghost" onclick="A.obProcess()">${t('process_now')}</button>${cnt.failed ? `<button class="btn" onclick="A.obRetry()">${t('retry')} (${cnt.failed})</button>` : ''}`,
    tabs([['#/outbox', `${t('all')}`], ['#/outbox?status=pending', `${t('pending')} ${cnt.pending || 0}`], ['#/outbox?status=sent', `${t('sent')} ${cnt.sent || 0}`], ['#/outbox?status=failed', `${t('failed')} ${cnt.failed || 0}`], ['#/outbox?status=demo', `${t('demo')} ${cnt.demo || 0}`]], location.hash) +
    `<div class="card">${tbl([{ h: t('date'), f: r => `<span class="nowrap">${esc(fmtTs(r.created))}</span>` }, { h: t('channels'), f: r => esc(r.channel) }, { h: t('to'), f: r => `${esc(nameOf(r) || '')}<div class="small muted num">${esc(r.to_addr)}</div>` }, { h: t('body'), f: r => `<div class="small">${esc(r.subject)}</div><div class="small muted">${esc(r.body.slice(0, 140))}</div>` }, { h: t('status'), f: r => `${statusPill(r.status)}${r.error ? `<div class="small muted">${esc(r.error)}</div>` : ''}` }], d.rows)}</div>`));
}
A.obProcess = async () => { const r = await post('/api/outbox/process'); toast(`${r.processed}`, 'ok'); App.route(); };
A.obRetry = async () => { await post('/api/outbox/retry', {}); App.route(); };

R('/applications', viewApplications);
R('/members', viewMembers);
R('/members/:id', viewMember);
R('/members/:id/:tab', viewMember);
R('/directory', viewDirectory);
R('/broadcast', viewBroadcast);
R('/outbox', viewOutbox);
