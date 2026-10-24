// Handbook v1.3 screenshots: society accounts, the Library Council pack and association mode. Runs after capture.js on the same demo server.
// The demo club is switched to association mode for the second half and switched back at the end.
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const fs = require('fs');
const BASE = 'http://127.0.0.1:8810', OUT = '/home/user/bpro-club-manager/docs/handbook/img';
const problems = [];
// Same approach as capture.js: a narrow 940 px layout, no sidebar, cropped to the content or to the open dialog.
const NOSIDE = '.side{display:none!important}.shell{grid-template-columns:1fr!important}';
const shot = async (pg, name, o = {}) => {
  const { viewport, max, ...rest } = o; const opts = { path: `${OUT}/${name}.jpg`, type: 'jpeg', quality: 86 };
  if (pg.__desktop && !viewport) {
    const sel = await pg.evaluate(() => document.querySelector('#sheet.open .panel') ? '#sheet.open .panel' : (document.getElementById('main') ? '#main' : ''));
    if (sel) {
      const loc = pg.locator(sel).first(); const box = await loc.boundingBox(); const maxH = max || 1250;
      if (sel === '#main' && box && box.height > maxH) { const sc = await pg.evaluate(() => [scrollX, scrollY]); return pg.screenshot({ ...opts, fullPage: true, clip: { x: box.x + sc[0], y: box.y + sc[1], width: box.width, height: maxH } }); }
      return loc.screenshot(opts);
    }
  }
  return pg.screenshot({ ...opts, ...rest });
};
async function withSide(pg, fn) { await pg.setViewportSize({ width: 1280, height: 860 }); await pg.evaluate(css => { const s = [...document.querySelectorAll('style')].find(x => x.textContent === css); if (s) { s.dataset.off = '1'; s.media = 'not all'; } }, NOSIDE); await wait(pg, 500); await fn(); await pg.evaluate(() => { const s = document.querySelector('style[data-off]'); if (s) { s.media = ''; delete s.dataset.off; } }); await pg.setViewportSize({ width: 940, height: 700 }); await wait(pg, 300); }
const wait = (p, ms = 800) => p.waitForTimeout(ms);
const H = { 'X-Club': '1' };
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 940, height: 700 }, deviceScaleFactor: 2 }); const page = await ctx.newPage();
  page.on('pageerror', e => problems.push('a pageerror ' + e.message + ' @ ' + page.url()));
  const api = async (method, url, data) => (await ctx.request.fetch(BASE + url, { method, headers: { ...H, 'Content-Type': 'application/json' }, data })).json();
  await page.goto(BASE + '/'); await page.waitForSelector('#login-f'); await page.evaluate(() => localStorage.setItem('club_lang', 'en')); await page.reload(); await page.waitForSelector('#login-f');
  await page.fill('[name=login]', 'admin@club.test'); await page.fill('[name=password]', 'admin-password-1'); await page.click('#login-b'); await page.waitForSelector('.shell'); page.__desktop = true; await page.addStyleTag({ content: NOSIDE });
  await api('POST', '/api/settings', { org_kind: 'club', features: {}, council_reg_no: 'KSLC/KTM/0421', council_grade: 'C', council_district: 'Kottayam', council_taluk: 'Meenachil', library_hours: '9 am - 8 pm' });
  const go = async (r, name, o) => { await page.goto(BASE + '/' + r); await wait(page, 1000); await shot(page, name, o); };
  // a grant with one voucher charged, so the sheet has content
  const grants = await api('GET', '/api/council/grants'); const g = grants[0];
  if (g) { const gd = await api('GET', `/api/council/grants/${g.id}`); if (!gd.vouchers.length && gd.candidates.length) await api('POST', `/api/council/grants/${g.id}/link`, { add: [gd.candidates[0].id] }); }
  // ---------- society accounts ----------
  await go('#/finance/statements', 'd-statements', { fullPage: true });
  await page.click('text=Opening balances').catch(() => problems.push('openings button')); await wait(page, 600); await shot(page, 'd-openings'); await page.click('.sheet .x').catch(() => {});
  await go('#/finance/books?book=cash', 'd-cashbook');
  await go('#/finance', 'd-finance-contra'); await page.click('text=Cash ⇄ bank').catch(() => {}); await wait(page, 500); await shot(page, 'd-contra'); await page.click('.sheet .x').catch(() => {});
  await page.goto(BASE + '/#/settings'); await wait(page, 1000); await page.locator('.card:has([name=fy_start_month])').first().screenshot({ path: `${OUT}/d-settings-accounts.jpg`, type: 'jpeg', quality: 86 });
  // ---------- Library Council ----------
  await go('#/library/council', 'd-council', { fullPage: true });
  await page.click('button:has-text("Vouchers charged")').catch(() => problems.push('grant button')); await wait(page, 600); await shot(page, 'd-grant'); await page.click('.sheet .x').catch(() => {});
  // printables
  for (const [n, u, h] of [['d-print-statements', '/api/accounts/statements/print?lang=en', 1700], ['d-print-council', '/api/council/statement/print?lang=ml', 2300], ['d-print-uc', `/api/council/grants/${g ? g.id : 1}/uc/print?lang=en`, 1100], ['d-print-cashbook', '/api/accounts/book/print?book=bank&lang=en', 900]]) {
    const p2 = await ctx.newPage(); await p2.addInitScript(() => { window.print = () => {}; }); await p2.goto(BASE + u); await wait(p2, 900); await p2.setViewportSize({ width: 860, height: 1200 }); await wait(p2, 300); await p2.screenshot({ path: `${OUT}/${n}.jpg`, type: 'jpeg', quality: 86, clip: { x: 0, y: 0, width: 860, height: Math.round(h * 0.78) } }); await p2.close();
  }
  // ---------- association mode ----------
  await api('POST', '/api/settings', { org_kind: 'association', features: { library: false, units: true, maintenance: true, helpdesk: true }, wards: ['A', 'B'], maint_basis: 'sqft', maint_rate: '2.5', maint_late_fee: '100' });
  await page.evaluate(() => App.me());
  await page.goto(BASE + '/#/settings'); await wait(page, 1000); await page.locator('.card:has([name=org_kind])').first().screenshot({ path: `${OUT}/d-assoc-settings.jpg`, type: 'jpeg', quality: 86 });
  await page.goto(BASE + '/#/'); await wait(page, 900); await withSide(page, () => shot(page, 'd-assoc-home', { viewport: true }));
  await go('#/units', 'd-units');
  const units = await api('GET', '/api/units'); const a101 = units.find(u => u.label === 'A-101') || units[0];
  await go('#/units/' + a101.id, 'd-unit', { fullPage: true });
  await page.click('text=Assign resident').catch(() => {}); await wait(page, 500); await shot(page, 'd-assign-resident'); await page.click('.sheet .x').catch(() => {});
  await page.click('text=Add units in bulk').catch(() => {}); await wait(page, 300); await page.goto(BASE + '/#/units'); await wait(page, 800); await page.click('text=Add units in bulk'); await wait(page, 500);
  await page.fill('#sheet [name=lines]', 'A, 301, 3, 2BHK, 950\nA, 302, 3, 3BHK, 1200\nB, 201, 2, Villa, 1800'); await shot(page, 'd-units-bulk'); await page.click('.sheet .x');
  await go('#/maintenance', 'd-maintenance');
  await page.click('text=Generate bills').catch(() => {}); await wait(page, 400); await shot(page, 'd-generate-bills'); await page.click('.sheet .x').catch(() => {});
  await go('#/maintenance?tab=defaulters', 'd-maint-due');
  await go('#/helpdesk', 'd-helpdesk');
  const tk = await api('GET', '/api/tickets'); const t0 = tk.rows[0];
  if (t0) await go('#/helpdesk/' + t0.id, 'd-ticket');
  await page.click('text=Assigned to').catch(() => {}); await wait(page, 500); await shot(page, 'd-ticket-assign'); await page.click('.sheet .x').catch(() => {});
  await go('#/members', 'd-residents');
  await ctx.close();
  // ---------- resident on a phone ----------
  const mm = await browser.newContext({ viewport: { width: 340, height: 740 }, deviceScaleFactor: 2 }); const p = await mm.newPage();
  p.on('pageerror', e => problems.push('mm pageerror ' + e.message + ' @ ' + p.url()));
  await p.goto(BASE + '/'); await p.waitForSelector('#login-f'); await p.evaluate(() => localStorage.setItem('club_lang', 'ml')); await p.reload(); await p.waitForSelector('#login-f'); await wait(p); await shot(p, 'm-assoc-landing');
  await p.goto(BASE + '/#/apply'); await p.waitForSelector('#ap-f'); await p.fill('[name=name_en]', 'Mary Thomas'); await p.click('text=അടുത്തത്').catch(async () => p.click('text=Next')); await wait(p, 400);
  await p.evaluate(() => window.scrollTo(0, 260)); await shot(p, 'm-assoc-apply');
  await p.fill('[name=login]', '9847012345').catch(() => {});
  await p.goto(BASE + '/#/login'); await p.waitForSelector('[name=login]'); await p.fill('[name=login]', '9847012345'); await p.fill('[name=password]', 'member-pass-1'); await p.click('#login-b'); await p.waitForSelector('.shell');
  const mgo = async (r, name, o) => { await p.goto(BASE + '/' + r); await wait(p, 900); await shot(p, name, o); };
  await mgo('#/', 'm-assoc-home'); await mgo('#/payments', 'm-assoc-payments', { fullPage: true });
  await mgo('#/helpdesk', 'm-assoc-helpdesk'); await p.click('.page-head .btn').catch(() => {}); await wait(p, 500); await shot(p, 'm-assoc-ticket-form'); await p.click('.sheet .x').catch(() => {});
  const mt = await p.evaluate(async () => (await (await fetch('/api/tickets', { headers: { 'X-Club': '1' } })).json()).rows[0]); if (mt) await mgo('#/helpdesk/' + mt.id, 'm-assoc-ticket');
  await mm.close();
  // back to club mode
  const c2 = await browser.newContext(); const r2 = c2.request;
  await r2.post(BASE + '/api/auth/login', { headers: H, data: { login: 'admin@club.test', password: 'admin-password-1' } });
  await r2.post(BASE + '/api/settings', { headers: H, data: { org_kind: 'club', features: {} } }); await c2.close();
  await browser.close();
  console.log(problems.length ? 'PROBLEMS\n' + problems.join('\n') : 'capture v13 ok'); console.log(fs.readdirSync(OUT).length, 'files');
})().catch(e => { console.error('FATAL', e.message.split('\n')[0]); process.exit(1); });
