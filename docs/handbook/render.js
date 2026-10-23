// Renders docs/handbook/handbook.html to ClubPro-Handbook.pdf with Chromium (A4, headers, page numbers, bookmarks).
const path = require('path');
let chromium;
try { ({ chromium } = require('playwright')); } catch (e) { ({ chromium } = require('/opt/node-tools/node_modules/playwright')); }
const HERE = __dirname;
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('file://' + path.join(HERE, 'handbook.html'), { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(800);
  await page.pdf({
    path: path.join(HERE, 'ClubPro-Handbook.pdf'), format: 'A4', printBackground: true, preferCSSPageSize: true, outline: true, tagged: true,
    displayHeaderFooter: true,
    headerTemplate: `<div style="font-family:Inter,sans-serif;font-size:7.5pt;color:#5B6B68;width:100%;padding:0 16mm;display:flex;justify-content:space-between"><span>ClubPro · User Manual &amp; Handbook</span><span class="title"></span></div>`,
    footerTemplate: `<div style="font-family:Inter,sans-serif;font-size:7.5pt;color:#5B6B68;width:100%;padding:0 16mm;display:flex;justify-content:space-between"><span>Powered by Team Bpro</span><span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span></div>`,
    margin: { top: '18mm', bottom: '20mm', left: '16mm', right: '16mm' },
  });
  await browser.close();
  console.log('ClubPro-Handbook.pdf written');
})().catch(e => { console.error(e); process.exit(1); });
