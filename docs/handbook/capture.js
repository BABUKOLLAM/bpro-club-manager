// Screenshots for the handbook. Desktop 1280x800 @2x as admin (English), phone 390x844 @2x as a member (Malayalam / English).
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const fs = require('fs');
const BASE = 'http://127.0.0.1:8810', OUT = '/home/user/bpro-club-manager/docs/handbook/img';
const PORTRAIT = '/tmp/claude-0/-home-user-bpro-classy-estimator/5b078c38-27de-5fbe-b675-f02a36881208/scratchpad/portrait.jpg';
const LOGO = '/tmp/claude-0/-home-user-bpro-classy-estimator/5b078c38-27de-5fbe-b675-f02a36881208/scratchpad/logo.png';
const problems = [];
// Desktop pages are captured at a narrow 940 px layout with the sidebar hidden, cropped to the content (or to the open dialog),
// so the text is large enough to read when the picture is scaled to the page width. {viewport:true} keeps a plain viewport shot.
const shot = async (pg, name, o = {}) => {
  const { viewport, max, ...rest0 } = o; const rest = { ...rest0, max }; const opts = { path: `${OUT}/${name}.jpg`, type: 'jpeg', quality: 86 };
  if (pg.__desktop && !viewport) {
    const sel = await pg.evaluate(() => document.querySelector('#sheet.open .panel') ? '#sheet.open .panel' : (document.getElementById('main') ? '#main' : ''));
    if (sel) {
      const loc = pg.locator(sel).first(); const box = await loc.boundingBox(); const maxH = rest.max || 1250;   // long lists: the first screenful is enough
      if (sel === '#main' && box && box.height > maxH) { const sc = await pg.evaluate(() => [scrollX, scrollY]); return pg.screenshot({ ...opts, fullPage: true, clip: { x: box.x + sc[0], y: box.y + sc[1], width: box.width, height: maxH } }); }
      return loc.screenshot(opts);
    }
  }
  const { max: _m, ...clean } = rest; return pg.screenshot({ ...opts, ...clean });
};
const NOSIDE = '.side{display:none!important}.shell{grid-template-columns:1fr!important}';
async function hideSide(pg) { pg.__desktop = true; await pg.addStyleTag({ content: NOSIDE, }).then(h => { pg.__side = h; }); }
async function withSide(pg, fn) { await pg.setViewportSize({ width: 1280, height: 860 }); await pg.evaluate(css => { const s = [...document.querySelectorAll('style')].find(x => x.textContent === css); if (s) { s.dataset.off = '1'; s.media = 'not all'; } }, NOSIDE); await wait(pg, 500); await fn(); await pg.evaluate(css => { const s = document.querySelector('style[data-off]'); if (s) { s.media = ''; delete s.dataset.off; } }, NOSIDE); await pg.setViewportSize({ width: 940, height: 700 }); await wait(pg, 300); }
const wait = (p, ms = 700) => p.waitForTimeout(ms);
(async () => {
  const browser = await chromium.launch({ args: ['--host-resolver-rules=MAP *.clubs.local 127.0.0.1'] });
  // ---------- phone: public landing, wizard, signup ----------
  const m = await browser.newContext({ viewport: { width: 340, height: 740 }, deviceScaleFactor: 2 }); const mp = await m.newPage();
  mp.on('pageerror', e => problems.push('m pageerror ' + e.message));
  await mp.goto(BASE + '/'); await mp.waitForSelector('#login-f'); await mp.evaluate(() => localStorage.setItem('club_lang', 'ml')); await mp.reload(); await mp.waitForSelector('#login-f'); await wait(mp); await shot(mp, 'm-landing-ml');
  await mp.evaluate(() => localStorage.setItem('club_lang', 'en')); await mp.reload(); await mp.waitForSelector('#login-f'); await wait(mp); await shot(mp, 'm-landing-en');
  await mp.click('a[onclick*="A.forgot"]'); await wait(mp, 400); await shot(mp, 'm-forgot'); await mp.click('.sheet .x');
  await mp.goto(BASE + '/#/apply'); await mp.waitForSelector('#ap-f'); await wait(mp);
  await mp.fill('[name=name_en]', 'Anitha Krishnan'); await mp.fill('[name=name_ml]', 'അനിത കൃഷ്ണൻ'); await mp.selectOption('[name=gender]', 'female'); await mp.fill('[name=dob]', '1988-03-12'); await mp.selectOption('[name=blood_group]', 'B+'); await shot(mp, 'm-apply-1');
  await mp.click('text=Next'); await wait(mp, 300); await mp.fill('[name=phone]', '98' + String(Date.now()).slice(-8)); await mp.fill('[name=house_en]', 'Puthenpura'); await mp.fill('[name=pincode]', '686001'); await shot(mp, 'm-apply-2');
  await mp.click('text=Next'); await wait(mp, 300); await mp.click('.chip >> nth=1'); await mp.waitForSelector('#sf'); await mp.fill('#sf [name=name_en]', 'Vishnu K'); await mp.fill('#sf [name=dob]', '2012-09-01'); await mp.click('#sf-save'); await wait(mp, 300); await shot(mp, 'm-apply-3');
  await mp.click('text=Next'); await wait(mp, 300); await mp.setInputFiles('input[type=file] >> nth=1', PORTRAIT); await mp.waitForSelector('img.pv'); await shot(mp, 'm-apply-4');
  await mp.click('text=Next'); await wait(mp, 300); await mp.fill('[name=password]', 'anitha-pass-1'); await mp.fill('[name=password2]', 'anitha-pass-1'); await mp.check('[name=consent_true]'); await mp.check('[name=consent_msgs]'); await shot(mp, 'm-apply-5');
  await mp.click('text=Next'); await wait(mp, 300); await shot(mp, 'm-apply-6', { fullPage: true });
  await mp.click('#ap-submit'); try { await mp.waitForSelector('.steps', { timeout: 8000 }); } catch (e) { problems.push('apply submit'); } await shot(mp, 'm-apply-done');
  await mp.goto(BASE + '/signup?lang=en'); await wait(mp); await shot(mp, 'm-signup');
  await m.close();

  // ---------- admin desktop ----------
  const ctx = await browser.newContext({ viewport: { width: 940, height: 700 }, deviceScaleFactor: 2 }); const page = await ctx.newPage();
  page.on('pageerror', e => problems.push('a pageerror ' + e.message + ' @ ' + page.url()));
  await page.goto(BASE + '/'); await page.waitForSelector('#login-f'); await page.evaluate(() => localStorage.setItem('club_lang', 'en')); await page.reload(); await page.waitForSelector('#login-f'); await wait(page); await shot(page, 'd-landing');
  await page.fill('[name=login]', 'admin@club.test'); await page.fill('[name=password]', 'admin-password-1'); await page.click('#login-b'); await page.waitForSelector('.shell'); await hideSide(page);
  // Ramesh gets a photo
  const up = await ctx.request.post(BASE + '/api/upload/members', { headers: { 'X-Club': '1' }, multipart: { file: { name: 'p.jpg', mimeType: 'image/jpeg', buffer: fs.readFileSync(PORTRAIT) } } });
  const photo = (await up.json()).path; await ctx.request.put(BASE + '/api/members/1', { headers: { 'X-Club': '1' }, data: { photo, joined_on: '2019-06-01' } });
  const go = async (r, name, o) => { await page.goto(BASE + '/' + r); await wait(page, 900); await shot(page, name, o); };
  await page.goto(BASE + '/#/'); await wait(page, 900); await withSide(page, () => shot(page, 'd-dashboard', { viewport: true }));
  await go('#/applications', 'd-applications'); await page.click('.tbl tr.click').catch(() => {}); await wait(page); await shot(page, 'd-application-detail');
  await go('#/members', 'd-members');
  await go('#/members/1', 'd-member', { fullPage: true });
  await page.click('text=Edit'); await wait(page); await shot(page, 'd-member-edit'); await page.click('.sheet .x');
  await go('#/members/1/family', 'd-member-family');
  await go('#/members', 'd-members-2'); await page.click('text=Import register'); await wait(page); await shot(page, 'd-import'); await page.click('.sheet .x');
  await go('#/directory', 'd-directory');
  await go('#/posts', 'd-posts'); await page.click('text=+'); await wait(page); await shot(page, 'd-post-form', { fullPage: true }); await page.click('.sheet .x');
  await go('#/posts/1', 'd-competition', { fullPage: true });
  await page.click('text=Add fixture').catch(() => {}); await wait(page); await shot(page, 'd-fixture-form'); await page.click('.sheet .x').catch(() => {});
  await go('#/posts/2', 'd-event', { fullPage: true });
  await go('#/committees', 'd-committees');
  const cid = await page.evaluate(async () => (await (await fetch('/api/committees', { headers: { 'X-Club': '1' } })).json()).find(c => c.name_en.startsWith('Executive')).id);
  await go('#/committees/' + cid, 'd-committee', { fullPage: true });
  await go('#/meetings', 'd-meetings'); await page.click('text=New meeting').catch(() => {}); await wait(page); await shot(page, 'd-meeting-form'); await page.click('.sheet .x').catch(() => {});
  await go('#/meetings/1', 'd-meeting', { fullPage: true });
  await go('#/actions', 'd-actions'); await go('#/plans', 'd-plans');
  await go('#/library', 'd-library');
  const bid = await page.evaluate(async () => (await (await fetch('/api/library/books', { headers: { 'X-Club': '1' } })).json())[0].id);
  await go('#/library/books/' + bid, 'd-book', { fullPage: true });
  await go('#/library/circulation', 'd-circulation'); await page.click('.page-head .btn'); await wait(page); await shot(page, 'd-issue-form'); await page.click('.sheet .x');
  await go('#/library/reading-room', 'd-reading-room'); await go('#/library/periodicals', 'd-periodicals');
  await go('#/finance', 'd-finance'); await page.click('.page-head .btn'); await wait(page); await shot(page, 'd-tx-form'); await page.click('.sheet .x');
  await go('#/finance/dues', 'd-dues'); await go('#/finance/claims', 'd-claims'); await go('#/finance/online', 'd-online');
  await go('#/bookings', 'd-bookings'); await page.click('text=Add facility').catch(() => {}); await wait(page); await shot(page, 'd-facility-form'); await page.click('.sheet .x').catch(() => {});
  await go('#/assets', 'd-assets'); await go('#/documents', 'd-documents'); await page.click('text=Add document').catch(() => {}); await wait(page); await shot(page, 'd-document-form'); await page.click('.sheet .x').catch(() => {});
  await go('#/broadcast', 'd-broadcast', { fullPage: true }); await page.click('text=Blood donor request').catch(() => {}); await wait(page); await shot(page, 'd-blood'); await page.click('.sheet .x').catch(() => {});
  await go('#/outbox', 'd-outbox');
  await go('#/polls', 'd-polls'); await page.click('text=New poll').catch(() => {}); await wait(page); await page.click('text=Add option').catch(() => {}); await wait(page, 200); await shot(page, 'd-poll-form'); await page.click('.sheet .x').catch(() => {});
  await go('#/reports', 'd-reports', { fullPage: true }); await go('#/reports/annual', 'd-annual', { fullPage: true });
  await go('#/scan', 'd-scan');
  await go('#/users', 'd-users');
  await go('#/settings', 'd-settings'); 
  const card = async (sel, name) => { await wait(page, 300); await page.locator(sel).first().screenshot({ path: `${OUT}/${name}.jpg`, type: 'jpeg', quality: 86 }); };
  await card('.card:has(#brand-prev)', 'd-settings-brand');
  await page.evaluate(() => { document.querySelector('details').open = true; }); await card('.card:has(details)', 'd-settings-channels');
  await card('.card:has([name=member_no_prefix])', 'd-settings-numbering');
  await go('#/audit', 'd-audit');
  // public pages (desktop)
  await page.goto(BASE + '/site?lang=en'); await wait(page); await shot(page, 'd-site', { fullPage: true });
  await page.goto(BASE + '/help?lang=en'); await wait(page); await shot(page, 'd-help');
  await page.goto(BASE + '/p/2?lang=en'); await wait(page); await shot(page, 'd-public-post', { fullPage: true });
  await page.goto(BASE + '/pricing?lang=en'); await wait(page); await shot(page, 'd-pricing', { fullPage: true });
  await page.goto(BASE + '/api/members/1/card?lang=en'); await wait(page, 1500); await shot(page, 'd-card-print', { clip: { x: 0, y: 0, width: 940, height: 400 } });
  // platform console
  await page.goto(BASE + '/_platform'); await page.fill('#key', 'master-key-dev'); await page.click('text=Open'); await wait(page, 1200); await shot(page, 'd-platform', { fullPage: true });
  await ctx.close();

  // ---------- the paying club's plan screen ----------
  const pc = await browser.newContext({ viewport: { width: 940, height: 700 }, deviceScaleFactor: 2 }); const pp = await pc.newPage();
  await pp.goto('http://pala-arts-sports-club.clubs.local:8810/'); await pp.waitForSelector('#login-f'); await pp.evaluate(() => localStorage.setItem('club_lang', 'en')); await pp.reload(); await pp.waitForSelector('#login-f');
  await pp.fill('[name=login]', 'jose@pala.test'); await pp.fill('[name=password]', 'pala-pass-1'); await pp.click('#login-b'); await pp.waitForSelector('.shell'); await hideSide(pp);
  await pp.goto('http://pala-arts-sports-club.clubs.local:8810/#/plan'); await wait(pp, 900); await shot(pp, 'd-plan');
  await pp.click('text=Pay by UPI').catch(() => {}); await wait(pp); await shot(pp, 'd-plan-upi'); await pc.close();

  // ---------- member on a phone (Malayalam) ----------
  const mm = await browser.newContext({ viewport: { width: 340, height: 740 }, deviceScaleFactor: 2 }); const p = await mm.newPage();
  p.on('pageerror', e => problems.push('mm pageerror ' + e.message + ' @ ' + p.url()));
  await p.goto(BASE + '/'); await p.waitForSelector('#login-f'); await p.evaluate(() => localStorage.setItem('club_lang', 'ml')); await p.reload(); await p.waitForSelector('#login-f');
  await p.fill('[name=login]', '9847012345'); await p.fill('[name=password]', 'member-pass-1'); await p.click('#login-b'); await p.waitForSelector('.shell');
  const mgo = async (r, name, o) => { await p.goto(BASE + '/' + r); await wait(p, 900); await shot(p, name, o); };
  await mgo('#/', 'm-home'); await p.click('.top button'); await wait(p, 400); await shot(p, 'm-menu'); await p.evaluate(() => document.querySelector('.side').classList.remove('open'));
  await mgo('#/me', 'm-me', { fullPage: true }); await mgo('#/me/family', 'm-family'); await mgo('#/me/preferences', 'm-preferences', { fullPage: true });
  await mgo('#/notifications', 'm-notifications'); await mgo('#/posts', 'm-posts'); await mgo('#/posts/2', 'm-event', { fullPage: true });
  await mgo('#/library', 'm-library'); await mgo('#/library/mine', 'm-my-books'); await mgo('#/payments', 'm-payments', { fullPage: true });
  await p.click('text=UPI').catch(() => {}); await wait(p); await shot(p, 'm-pay-upi'); await p.click('.sheet .x').catch(() => {});
  await mgo('#/documents', 'm-documents'); await mgo('#/bookings', 'm-bookings'); await mgo('#/polls', 'm-polls'); await mgo('#/meetings', 'm-meetings'); await mgo('#/directory', 'm-directory');
  // e-card PNG as the member would save it
  const png = await p.evaluate(async () => { const d = await get('/api/members/1/card.json'); const b = await ecardPng(d, 'ml'); return await new Promise(r => { const fr = new FileReader(); fr.onload = () => r(fr.result); fr.readAsDataURL(b); }); });
  fs.writeFileSync(`${OUT}/ecard.png`, Buffer.from(png.split(',')[1], 'base64'));
  await mm.close(); await browser.close();
  console.log(problems.length ? 'PROBLEMS\n' + problems.join('\n') : 'capture ok'); console.log(fs.readdirSync(OUT).length, 'files');
})().catch(e => { console.error('FATAL', e.message.split('\n')[0], (e.stack.match(/capture.js:\d+/) || [''])[0]); process.exit(1); });
