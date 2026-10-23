/* The electronic membership card: an on-screen version (HTML/CSS) and a PNG rendering (canvas) for saving or sharing. */
'use strict';
const CARD_W = 428, CARD_H = 270;   // 85.6 x 54 mm at ~5 px/mm
function cardLabels(lang) { return lang === 'ml' ? ['അംഗത്വ നമ്പർ', 'രക്തം', 'ചേർന്നത്', 'സാധുത'] : ['Member No', 'Blood', 'Joined', 'Valid']; }
function cardText(d, lang) {
  const ml = lang === 'ml';
  return { name: ml ? (d.name_ml || d.name_en) : d.name_en, other: ml ? d.name_en : d.name_ml, club: ml ? (d.club_ml || d.club_en) : d.club_en, place: ml ? (d.place_ml || d.place_en) : d.place_en,
    type: ml ? d.type_ml : d.type_en, valid: ml ? d.valid_ml : d.valid, labels: cardLabels(lang) };
}
function ecardHtml(d, lang) {
  const x = cardText(d, lang); const L = x.labels;
  const photo = d.photo ? `<img class="photo" src="/uploads/${esc(d.photo)}" alt="">` : `<div class="photo ini">${esc((d.name_en || '?')[0].toUpperCase())}</div>`;
  return `<div class="ecard-wrap"><div class="ecard ${lang === 'ml' ? 'ml' : ''}"><div class="band"><div class="club">${esc(x.club)}</div><div class="place">${esc(x.place)}</div><div class="short">${esc(d.club_short)}</div><div class="stripe"></div></div>
  ${photo}<div class="body"><div class="n">${esc(x.name)}</div><div class="n2">${esc(x.other)}</div><span class="type">${esc(x.type)}</span>
  <div class="rows"><div><small>${L[0]}</small><b class="no">${esc(d.member_no)}</b></div><div><small>${L[1]}</small><b>${esc(d.blood_group || '-')}</b></div><div><small>${L[2]}</small><b>${esc(fmtDate(d.joined_on) || '-')}</b></div><div><small>${L[3]}</small><b>${esc(x.valid)}</b></div></div></div>
  <img class="qr" src="${d.qr}" alt="QR"><div class="foot">${esc(d.club_phone)}${d.reg_no ? ' · ' + esc(d.reg_no) : ''}</div></div></div>`;
}
function fitCards() { document.querySelectorAll('.ecard-wrap').forEach(w => { const sc = Math.min(1, (w.clientWidth) / CARD_W); w.style.height = (CARD_H * sc) + 'px'; w.firstElementChild.style.transform = `scale(${sc})`; }); }
window.addEventListener('resize', fitCards);
function loadImg(src) { return new Promise((res, rej) => { const im = new Image(); im.onload = () => res(im); im.onerror = rej; im.src = src; }); }
function rr(ctx, x, y, w, h, r) { ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); }
function fitText(ctx, text, max) { let t = text || ''; while (t && ctx.measureText(t).width > max) t = t.slice(0, -2); return t === text ? t : t + '…'; }
async function ecardPng(d, lang) {
  const S = 4, W = CARD_W * S, H = CARD_H * S; const c = document.createElement('canvas'); c.width = W; c.height = H; const ctx = c.getContext('2d');
  const x = cardText(d, lang); const mlFont = 'Manjari, "Noto Sans Malayalam", sans-serif', latin = 'Inter, sans-serif'; const F = lang === 'ml' ? mlFont : latin;
  try { await Promise.all([document.fonts.load(`700 ${12 * S}px Manjari`), document.fonts.load(`700 ${12 * S}px Inter`), document.fonts.load(`400 ${12 * S}px Inter`)]); } catch (e) {}
  rr(ctx, 0, 0, W, H, 14 * S); ctx.clip(); ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, W, H);
  const g = ctx.createLinearGradient(0, 0, W, 85 * S); g.addColorStop(0, '#0F4C45'); g.addColorStop(.7, '#196B61'); g.addColorStop(1, '#2A8C7F'); ctx.fillStyle = g; ctx.fillRect(0, 0, W, 85 * S);
  ctx.fillStyle = '#C9542A'; ctx.fillRect(0, 85 * S - 6 * S, W, 6 * S);
  ctx.fillStyle = '#fff'; ctx.font = `700 ${12.5 * S}px ${F}`; ctx.fillText(fitText(ctx, x.club, 300 * S), 20 * S, 32 * S);
  ctx.font = `400 ${9 * S}px ${F}`; ctx.globalAlpha = .85; ctx.fillText(fitText(ctx, x.place, 300 * S), 20 * S, 50 * S); ctx.globalAlpha = 1;
  ctx.font = `700 ${10 * S}px ${latin}`; const sw = ctx.measureText(d.club_short).width + 16 * S; ctx.fillStyle = 'rgba(255,255,255,.18)'; rr(ctx, W - 20 * S - sw, 16 * S, sw, 22 * S, 5 * S); ctx.fill(); ctx.fillStyle = '#fff'; ctx.fillText(d.club_short, W - 20 * S - sw + 8 * S, 32 * S);
  // photo
  const px = 20 * S, py = 65 * S, pw = 110 * S, ph = 130 * S;
  ctx.save(); ctx.shadowColor = 'rgba(0,0,0,.25)'; ctx.shadowBlur = 12 * S; ctx.shadowOffsetY = 4 * S; ctx.fillStyle = '#fff'; rr(ctx, px - 4 * S, py - 4 * S, pw + 8 * S, ph + 8 * S, 12 * S); ctx.fill(); ctx.restore();
  ctx.save(); rr(ctx, px, py, pw, ph, 9 * S); ctx.clip(); ctx.fillStyle = '#EEF2EF'; ctx.fillRect(px, py, pw, ph);
  if (d.photo) { try { const im = await loadImg('/uploads/' + d.photo); const r = Math.max(pw / im.width, ph / im.height); const iw = im.width * r, ih = im.height * r; ctx.drawImage(im, px + (pw - iw) / 2, py + (ph - ih) / 2, iw, ih); } catch (e) {} }
  else { ctx.fillStyle = '#0F4C45'; ctx.font = `700 ${56 * S}px ${latin}`; ctx.textAlign = 'center'; ctx.fillText((d.name_en || '?')[0].toUpperCase(), px + pw / 2, py + ph / 2 + 20 * S); ctx.textAlign = 'left'; }
  ctx.restore();
  // body
  const bx = 145 * S; ctx.fillStyle = '#1D2A28'; ctx.font = `700 ${15 * S}px ${F}`; ctx.fillText(fitText(ctx, x.name, 250 * S), bx, 110 * S);
  ctx.fillStyle = '#5B6B68'; ctx.font = `400 ${9.5 * S}px ${lang === 'ml' ? latin : mlFont}`; ctx.fillText(fitText(ctx, x.other, 250 * S), bx, 126 * S);
  ctx.font = `700 ${8.5 * S}px ${F}`; const tw = ctx.measureText(x.type).width + 14 * S; ctx.fillStyle = '#FBE9E1'; rr(ctx, bx, 133 * S, tw, 16 * S, 8 * S); ctx.fill(); ctx.fillStyle = '#C9542A'; ctx.fillText(x.type, bx + 7 * S, 145 * S);
  const rows = [[x.labels[0], d.member_no, true], [x.labels[1], d.blood_group || '-'], [x.labels[2], fmtDate(d.joined_on) || '-'], [x.labels[3], x.valid]];
  rows.forEach(([k, v, big], i) => { const cx = bx + (i % 2) * 125 * S, cy = 170 * S + Math.floor(i / 2) * 34 * S; ctx.fillStyle = '#8a948f'; ctx.font = `600 ${6.5 * S}px ${F}`; ctx.fillText(String(k).toUpperCase(), cx, cy); ctx.fillStyle = big ? '#0F4C45' : '#1D2A28'; ctx.font = `700 ${(big ? 11.5 : 10) * S}px ${big ? latin : F}`; ctx.fillText(fitText(ctx, String(v), 118 * S), cx, cy + 14 * S); });
  try { const qr = await loadImg(d.qr); ctx.drawImage(qr, W - 20 * S - 72 * S, H - 20 * S - 72 * S, 72 * S, 72 * S); } catch (e) {}
  ctx.fillStyle = '#8a948f'; ctx.font = `400 ${6.5 * S}px ${latin}`; ctx.fillText([d.club_phone, d.reg_no].filter(Boolean).join(' · '), 20 * S, H - 12 * S);
  return new Promise(res => c.toBlob(res, 'image/png'));
}
A.saveCard = async (mid) => { try { const d = await get(`/api/members/${mid}/card.json`); const blob = await ecardPng(d, S.lang); const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `${(d.member_no || 'card').replace(/[^\w-]+/g, '_')}.png`; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 5000); } catch (e) { toast(t('error'), 'bad'); } };
A.shareCard = async (mid) => { try { const d = await get(`/api/members/${mid}/card.json`); const blob = await ecardPng(d, S.lang); const file = new File([blob], `${(d.member_no || 'card').replace(/[^\w-]+/g, '_')}.png`, { type: 'image/png' }); if (navigator.canShare && navigator.canShare({ files: [file] })) await navigator.share({ files: [file], title: d.club_short }); else A.saveCard(mid); } catch (e) { if (e && e.name !== 'AbortError') toast(t('error'), 'bad'); } };
function ecardBlock(mid, d) { return `<div class="card"><h2>${t('ecard')}</h2>${ecardHtml(d, S.lang)}<p class="small muted">${t('card_hint')}</p><div class="actions"><button class="btn" onclick="A.saveCard(${mid})">⤓ ${t('save_card')}</button><button class="btn ghost" onclick="A.shareCard(${mid})">${t('share_card')}</button><a class="btn ghost" target="_blank" href="/api/members/${mid}/card?lang=${S.lang}">${t('print')}</a></div></div>`; }
