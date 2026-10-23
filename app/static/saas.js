/* Subscription plan: what the club pays the operator, status, pay online / by UPI, history. Also the plan banner. */
function planBanner() {
  const p = S.info && S.info.plan; if (!p || p.exempt) return '';
  const admin = can('settings.manage'); const link = admin ? `<a href="#/plan" class="btn sm">${t('plan_open')}</a>` : '';
  if (p.read_only) return `<div class="notice bad plan-bar">${t('plan_readonly', { product: p.product })} ${link}</div>`;
  if (p.status === 'overdue' && admin) return `<div class="notice plan-bar">${t('plan_overdue', { product: p.product })} ${link}</div>`;
  if (p.status === 'trial' && admin && p.days_left !== null && p.days_left <= 7) return `<div class="notice plan-bar">${t('plan_trial_ending', { days: p.days_left })} ${link}</div>`;
  if (p.status === 'active' && admin && p.days_left !== null && p.days_left <= 7) return `<div class="notice plan-bar">${t('plan_ending', { days: p.days_left })} ${link}</div>`;
  return '';
}

async function viewPlan() {
  const d = await get('/api/saas/plan');
  const st = { trial: 'warn', active: 'ok', overdue: 'warn', suspended: 'bad' }[d.status] || '';
  const pr = d.pricing;
  const rule = d.members <= pr.flat_upto ? t('plan_rule_flat', { n: pr.flat_upto, price: money(pr.flat_price) }) : t('plan_rule_per', { n: pr.flat_upto + 1, price: money(pr.per_member) });
  const hist = d.payments.length ? `<table class="tbl"><tr><th>${t('date')}</th><th>${t('amount')}</th><th>${t('members')}</th><th>${t('reference')}</th></tr>${d.payments.slice().reverse().map(p => `<tr><td>${esc(fmtTs(p.at))}</td><td class="num">${money(p.amount)}</td><td class="num">${p.members}</td><td class="small">${esc(p.ref || '')} · ${esc(p.via || '')}</td></tr>`).join('')}</table>` : `<p class="muted small">${t('plan_no_payments')}</p>`;
  const claims = d.claims.length ? `<div class="notice info">${t('plan_claim_pending', { ref: d.claims.map(c => c.ref).join(', ') })}</div>` : '';
  const pay = d.exempt ? '' : `<div class="card"><h2>${t('plan_pay_title')}</h2><p>${t('plan_price_line', { members: d.members, price: money(d.price) })}<br><span class="small muted">${rule}</span></p>${claims}
    <div class="actions">${d.gateway ? `<button class="btn accent" onclick="A.payPlan()">${t('pay_online')} · ${money(d.price)}</button>` : ''}${d.upi_id ? `<button class="btn ${d.gateway ? 'ghost' : 'accent'}" onclick="A.payPlanUpi()">${t('pay_upi')}</button>` : ''}${!d.gateway && !d.upi_id ? `<span class="muted small">${t('plan_contact_operator')}</span>` : ''}</div>
    ${d.product.support ? `<p class="small muted">${t('support')}: ${esc(d.product.support)}</p>` : ''}</div>`;
  S._plan = d;
  render(page(t('subscription_plan'), esc(d.product.name), '', `<div class="stack">
    <div class="card"><div class="row"><span class="pill ${st}">${t(d.status === 'overdue' ? 'plan_overdue_s' : 'plan_' + d.status)}</span>${d.exempt ? `<span class="muted small">${t('plan_exempt')}</span>` : ''}</div>
      ${d.exempt ? '' : `<div class="kv tiles-kv" style="margin-top:10px"><div><small>${t(d.paid_until ? 'plan_paid_until' : 'plan_trial_until')}</small><b>${esc(fmtTs(d.ends))}</b></div><div><small>${t('plan_days_left')}</small><b>${d.days_left}</b></div><div><small>${t('active_members')}</small><b>${d.members}</b></div><div><small>${t('plan_next_year')}</small><b>${money(d.price)}</b></div></div>
      <p class="small muted" style="margin-top:8px">${t('plan_grace_note', { days: pr.grace_days })}</p>`}</div>
    ${pay}
    <div class="card"><h2>${t('plan_history')}</h2>${hist}</div></div>`));
}
A.payPlan = async () => {
  const d = S._plan; toast(t('paying'));
  try { await loadScript('https://checkout.razorpay.com/v1/checkout.js'); } catch (e) { return toast(t('error'), 'bad'); }
  let o; try { o = await post('/api/saas/pay/order', {}); } catch (e) { return; }
  const rz = new Razorpay({ key: o.key_id, amount: Math.round(o.amount * 100), currency: o.currency, name: d.product.name, description: o.description, order_id: o.order_id, prefill: o.prefill, theme: { color: (S.info.brand || {}).primary || '#0F4C45' },
    handler: async resp => { try { await post('/api/saas/pay/verify', resp); toast(t('plan_paid'), 'ok'); await App.me(); App.route(); } catch (e) {} },
    modal: { ondismiss: () => toast(t('payment_failed'), 'bad') } });
  rz.on('payment.failed', () => toast(t('payment_failed'), 'bad'));
  rz.open();
};
A.payPlanUpi = () => {
  const d = S._plan; const upi = `upi://pay?pa=${encodeURIComponent(d.upi_id)}&pn=${encodeURIComponent(d.upi_name || d.product.name)}&am=${d.price}&cu=INR&tn=${encodeURIComponent(d.product.name + ' ' + (S.info.club_short || ''))}`;
  formSheet(t('pay_upi'), `<div class="full"><p>${t('plan_upi_intro', { price: money(d.price) })}</p><p class="num"><b>${esc(d.upi_id)}</b>${d.upi_name ? ' · ' + esc(d.upi_name) : ''}</p><p><a class="btn" href="${upi}">${t('open_upi_app')}</a></p></div>${F.text('ref', t('plan_upi_ref'), '', { req: true, full: true, help: t('plan_upi_ref_help') })}`,
    async b => { await post('/api/saas/pay/claim', b); closeSheet(); toast(t('plan_claim_sent'), 'ok'); App.route(); }, { saveLabel: t('plan_claim_btn') });
};
R('/plan', viewPlan);
