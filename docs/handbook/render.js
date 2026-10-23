// Renders an HTML file to PDF with Chromium. Default: handbook.html -> ClubPro-Handbook.pdf (A4, header, footer with page numbers, bookmarks).
// node render.js [in.html] [out.pdf] [plain]   -- "plain" renders with no margins / header / footer (used for the barcode overlay).
const path = require('path');
let chromium;
try { ({ chromium } = require('playwright')); } catch (e) { ({ chromium } = require('/opt/node-tools/node_modules/playwright')); }
const HERE = __dirname;
const inFile = process.argv[2] || path.join(HERE, 'handbook.html'), outFile = process.argv[3] || path.join(HERE, 'ClubPro-Handbook.pdf'), plain = process.argv[4] === 'plain';
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('file://' + inFile, { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(plain ? 100 : 800);
  const common = { path: outFile, format: 'A4', printBackground: true, preferCSSPageSize: true };
  if (plain) await page.pdf({ ...common, margin: { top: 0, bottom: 0, left: 0, right: 0 } });
  else await page.pdf({
    ...common, outline: true, tagged: true, displayHeaderFooter: true,
    headerTemplate: `<div style="font-family:Inter,sans-serif;font-size:7.5pt;color:#5A6079;width:100%;padding:0 16mm;display:flex;justify-content:space-between"><span style="font-weight:600;color:#4F46E5">ClubPro</span><span>User Manual &amp; Handbook</span><span>www.bpropms.com</span></div>`,
    footerTemplate: `<div style="font-family:Inter,sans-serif;font-size:7.5pt;color:#5A6079;width:100%;padding:0 16mm;display:flex;justify-content:space-between;align-items:center"><span>Designed &amp; Developed by Dr. Babu B · Bpro Consulting &amp; Technologies</span><span style="font-weight:700;color:#4F46E5">Page <span class="pageNumber"></span> of <span class="totalPages"></span></span><span style="width:34mm"></span></div>`,
    margin: { top: '17mm', bottom: '22mm', left: '16mm', right: '16mm' },
  });
  await browser.close();
  console.log(path.basename(outFile) + ' written');
})().catch(e => { console.error(e); process.exit(1); });
