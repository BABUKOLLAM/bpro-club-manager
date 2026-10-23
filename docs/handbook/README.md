# ClubPro handbook

`ClubPro-Handbook.pdf` is the user manual: members, office bearers, operator and a reference part, with screenshots.

To regenerate after the screens change (needs the dev server on 127.0.0.1:8810 with the demo data, Node with Playwright, Python with Pillow):

```bash
node docs/handbook/capture.js       # screenshots into docs/handbook/img
python docs/handbook/build.py       # handbook.html + ClubPro-Handbook.pdf (render.js, Chromium)
```

`build.py` holds the text; `handbook.css` the print styles; `render.js` the A4 rendering with headers, page numbers and bookmarks.
