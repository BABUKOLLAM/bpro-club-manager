"""The club's public website page at /site: who we are, office bearers, what is coming up, news, documents and
photos, in English or Malayalam, with Open Graph tags for sharing."""
import datetime as dt
import html
import json

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from . import comms, db, i18n

router = APIRouter()


def site_data():
    s = db.settings_all()
    today = dt.date.today().isoformat()
    return {
        "settings": {k: s[k] for k in ("club_name_en", "club_name_ml", "club_short", "club_reg_no", "club_address_en", "club_address_ml", "club_place_en", "club_place_ml", "club_phone", "club_email",
                                       "about_en", "about_ml", "map_url", "social_facebook", "social_instagram", "social_youtube", "social_whatsapp", "site_cover", "public_registration", "footer_credit")},
        "office_bearers": db.q("SELECT cm.designation_en, cm.designation_ml, m.name_en, m.name_ml, m.photo, m.show_phone, CASE WHEN m.show_phone=1 THEN m.phone ELSE '' END AS phone FROM committee_members cm JOIN members m ON m.id=cm.member_id "
                               "JOIN committees c ON c.id=cm.committee_id WHERE cm.active=1 AND c.kind='executive' AND m.status='active' ORDER BY cm.sort, cm.id"),
        "upcoming": db.q("SELECT id, kind, title_en, title_ml, starts_at, venue_en, venue_ml, cover, reg_open FROM posts WHERE status='published' AND audience='public' AND deleted=0 AND starts_at>=? ORDER BY starts_at LIMIT 8", (today,)),
        "news": db.q("SELECT id, kind, title_en, title_ml, body_en, body_ml, cover, published_at FROM posts WHERE status='published' AND audience='public' AND deleted=0 AND (starts_at<? OR starts_at='') ORDER BY pinned DESC, published_at DESC LIMIT 8", (today,)),
        "documents": db.q("SELECT id, title_en, title_ml, category, path, year FROM documents WHERE deleted=0 AND audience='public' ORDER BY category, year DESC LIMIT 30"),
        "photos": db.q("SELECT f.path, f.caption, p.title_en, p.title_ml FROM post_files f JOIN posts p ON p.id=f.post_id WHERE p.status='published' AND p.audience='public' AND p.deleted=0 ORDER BY f.id DESC LIMIT 12"),
        "stats": {"members": db.one("SELECT COUNT(*) n FROM members WHERE status='active'")["n"], "books": db.one("SELECT COUNT(*) n FROM copies WHERE status<>'withdrawn'")["n"],
                  "events": db.one("SELECT COUNT(*) n FROM posts WHERE status='published' AND deleted=0 AND kind<>'news'")["n"]},
    }


@router.get("/api/public/site")
def public_site():
    return site_data()


@router.get("/site", response_class=HTMLResponse)
def site(lang: str = ""):
    d = site_data(); s = d["settings"]; e = html.escape
    lang = lang if lang in ("en", "ml") else db.setting("default_lang")
    other = "en" if lang == "ml" else "ml"
    L = {"en": ("About us", "Office bearers", "Upcoming", "News", "Documents", "Photos", "Members", "Books", "Events & programmes", "Apply for membership", "Member sign-in", "Contact", "Register"),
         "ml": ("ഞങ്ങളെക്കുറിച്ച്", "ഭാരവാഹികൾ", "വരാനിരിക്കുന്നവ", "വാർത്തകൾ", "രേഖകൾ", "ഫോട്ടോകൾ", "അംഗങ്ങൾ", "പുസ്തകങ്ങൾ", "പരിപാടികൾ", "അംഗത്വത്തിന് അപേക്ഷിക്കുക", "അംഗങ്ങളുടെ പ്രവേശനം", "ബന്ധപ്പെടുക", "രജിസ്റ്റർ ചെയ്യുക")}[lang]
    name = s["club_name_ml" if lang == "ml" else "club_name_en"] or s["club_name_en"]
    place = s["club_place_ml" if lang == "ml" else "club_place_en"] or s["club_place_en"]
    about = s["about_ml" if lang == "ml" else "about_en"] or s["about_en"] or s["about_ml"]
    addr = s["club_address_ml" if lang == "ml" else "club_address_en"] or s["club_address_en"]
    base = comms.club_ctx()["link"]
    cover = f"<img class='cover' src='/uploads/{e(s['site_cover'])}'>" if s["site_cover"] else ""
    og_img = f"<meta property='og:image' content='{base}/uploads/{e(s['site_cover'])}'>" if s["site_cover"] else ""
    when = lambda p: __import__("app.news", fromlist=["_when"])._when(p, lang)
    kind = lambda k: i18n.label(i18n.KIND_LABELS, k, lang)
    ob = "".join(f"<div class='ob'>{('<img src=/uploads/' + e(x['photo']) + '>') if x['photo'] else '<div class=av></div>'}<b>{e(i18n.pick(x, 'name', lang))}</b><span>{e(i18n.pick(x, 'designation', lang))}</span>{('<a href=tel:' + e(x['phone']) + '>' + e(x['phone']) + '</a>') if x['phone'] else ''}</div>" for x in d["office_bearers"])
    up = "".join(f"<a class='card' href='/p/{p['id']}?lang={lang}'>{('<img src=/uploads/' + e(p['cover']) + '>') if p['cover'] else ''}<div class=b><div class=t>{e(i18n.pick(p, 'title', lang))}</div><div class=s>{e(kind(p['kind']))} · {e(when(p))}{(' · ' + e(i18n.pick(p, 'venue', lang))) if i18n.pick(p, 'venue', lang) else ''}</div>{('<span class=pill>' + L[12] + '</span>') if p['reg_open'] else ''}</div></a>" for p in d["upcoming"])
    news = "".join(f"<a class='card' href='/p/{p['id']}?lang={lang}'>{('<img src=/uploads/' + e(p['cover']) + '>') if p['cover'] else ''}<div class=b><div class=t>{e(i18n.pick(p, 'title', lang))}</div><div class=s>{e(i18n.pick(p, 'body', lang)[:140])}</div></div></a>" for p in d["news"])
    docs = "".join(f"<li><a href='/uploads/{e(x['path'])}' target=_blank>{e(i18n.pick(x, 'title', lang))}</a> <span class=s>{e(x['year'])}</span></li>" for x in d["documents"])
    photos = "".join(f"<a href='/uploads/{e(x['path'])}' target=_blank><img src='/uploads/{e(x['path'])}' alt='{e(x['caption'] or i18n.pick(x, 'title', lang))}'></a>" for x in d["photos"])
    social = "".join(f"<a class=btn href='{e(u)}' target=_blank rel=noopener>{n}</a>" for n, u in (("Facebook", s["social_facebook"]), ("Instagram", s["social_instagram"]), ("YouTube", s["social_youtube"]), ("WhatsApp", s["social_whatsapp"])) if u)
    st = d["stats"]
    return f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(name)}</title><meta name="description" content="{e((about or name)[:160])}"><meta property="og:title" content="{e(name)}"><meta property="og:description" content="{e((about or place or name)[:200])}">{og_img}
<link rel="icon" href="/static/icons/icon.svg" type="image/svg+xml"><link href="https://fonts.googleapis.com/css2?family=Manjari:wght@400;700&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>:root{{--g:#0F4C45;--a:#C9542A;--bg:#F7F4EC;--ink:#1D2A28;--mut:#5B6B68;--line:#E3DED2}}*{{box-sizing:border-box}}body{{margin:0;font-family:Inter,Manjari,sans-serif;background:var(--bg);color:var(--ink);line-height:1.5}}
html[lang=ml] body{{font-family:Manjari,Inter,sans-serif}}a{{color:var(--g);text-decoration:none}}header{{background:var(--g);color:#fff;padding:14px 18px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}}
header .brand{{flex:1;font-weight:700;font-size:1.15rem;min-width:200px}}header .brand small{{display:block;font-weight:400;opacity:.8;font-size:.8rem}}.btn{{display:inline-block;padding:8px 14px;border-radius:10px;background:rgba(255,255,255,.15);color:#fff;font-weight:600}}
.btn.a{{background:var(--a)}}main{{max-width:1040px;margin:0 auto;padding:18px 16px 50px}}.cover{{width:100%;max-height:380px;object-fit:cover;border-radius:16px;margin-bottom:16px}}
h1{{font-size:1.7rem;margin:.3em 0}}h2{{font-size:1.2rem;margin:26px 0 10px;color:var(--g);border-bottom:2px solid var(--g);padding-bottom:4px}}.s{{color:var(--mut);font-size:.85rem}}
.stats{{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0}}.stats div{{background:#fff;border:1px solid var(--line);border-radius:12px;padding:10px 16px}}.stats b{{display:block;font-size:1.4rem;font-family:Inter}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}}.card{{background:#fff;border:1px solid var(--line);border-radius:14px;overflow:hidden;display:block;color:inherit}}.card img{{width:100%;aspect-ratio:16/9;object-fit:cover}}
.card .b{{padding:12px 14px}}.card .t{{font-weight:600}}.pill{{display:inline-block;background:#FBE9E1;color:var(--a);border-radius:999px;padding:1px 9px;font-size:.75rem;font-weight:600;margin-top:6px}}
.obs{{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}}.ob{{background:#fff;border:1px solid var(--line);border-radius:12px;padding:12px;text-align:center}}.ob img,.ob .av{{width:72px;height:72px;border-radius:50%;object-fit:cover;background:#eef2ef;margin:0 auto 6px;display:block}}
.ob b{{display:block}}.ob span{{display:block;color:var(--mut);font-size:.85rem}}.ph{{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:8px}}.ph img{{width:100%;aspect-ratio:4/3;object-fit:cover;border-radius:10px}}
pre{{white-space:pre-wrap;font:inherit}}ul{{padding-left:18px}}footer{{text-align:center;color:var(--mut);font-size:.8rem;padding:20px}}.contact a{{display:inline-block;margin-right:12px}}.social a{{margin:0 8px 8px 0;background:var(--g)}}</style></head>
<body><header><div class="brand">{e(name)}<small>{e(place)}</small></div><a class="btn" href="/site?lang={other}">{'English' if lang == 'ml' else 'മലയാളം'}</a><a class="btn" href="/#/login">{L[10]}</a>{('<a class="btn a" href="/#/apply">' + L[9] + '</a>') if s['public_registration'] == '1' else ''}</header>
<main>{cover}<h1>{e(name)}</h1>{('<div class=s>' + e(s['club_reg_no']) + '</div>') if s['club_reg_no'] else ''}
<div class="stats"><div><b>{st['members']}</b>{L[6]}</div><div><b>{st['books']}</b>{L[7]}</div><div><b>{st['events']}</b>{L[8]}</div></div>
{('<h2>' + L[0] + '</h2><pre>' + e(about) + '</pre>') if about else ''}
{('<h2>' + L[1] + '</h2><div class=obs>' + ob + '</div>') if ob else ''}
{('<h2>' + L[2] + '</h2><div class=grid>' + up + '</div>') if up else ''}
{('<h2>' + L[3] + '</h2><div class=grid>' + news + '</div>') if news else ''}
{('<h2>' + L[5] + '</h2><div class=ph>' + photos + '</div>') if photos else ''}
{('<h2>' + L[4] + '</h2><ul>' + docs + '</ul>') if docs else ''}
<h2>{L[11]}</h2><div class="contact">{('<pre>' + e(addr) + '</pre>') if addr else ''}{('<a href="tel:' + e(s['club_phone']) + '">📞 ' + e(s['club_phone']) + '</a>') if s['club_phone'] else ''}{('<a href="mailto:' + e(s['club_email']) + '">✉ ' + e(s['club_email']) + '</a>') if s['club_email'] else ''}{('<a href="' + e(s['map_url']) + '" target=_blank rel=noopener>📍 Map</a>') if s['map_url'] else ''}</div>
{('<div class=social style="margin-top:10px">' + social + '</div>') if social else ''}
</main><footer>{e(s['footer_credit'])}</footer></body></html>"""
