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
  else await page.pdf({ ...common, tagged: true, displayHeaderFooter: false, margin: { top: '22mm', bottom: '25mm', left: '17mm', right: '17mm' } });   // header, footer and page numbers are stamped by build.py
  await browser.close();
  console.log(path.basename(outFile) + ' written');
})().catch(e => { console.error(e); process.exit(1); });
