# ClubPro handbook

`ClubPro-Handbook.pdf` is the user manual and handbook (v1.1, the visual edition): members, office bearers, operator and a
reference part, with 90 screenshots, numbered pointers and tooltips, lens zoom-ins, sticky notes, missions and badges,
a barcode on every page (`CLUBPRO-HB-<version>-P<page>`), a contents page with page numbers, and credits.

To regenerate after the screens change (needs the dev server on 127.0.0.1:8810 with the demo data, Node with Playwright,
and in the Python environment: Pillow, pypdf, pdfplumber, python-barcode):

```bash
node docs/handbook/capture.js                 # screenshots into docs/handbook/img
python docs/handbook/build.py                 # two renders (contents page numbers) + barcode stamping -> ClubPro-Handbook.pdf
```

`build.py` holds the text, the pointer / lens coordinates and the missions; `handbook.css` the design system (palette,
gradients, highlighters, sticky notes, pins, lenses); `render.js` the A4 rendering with header, footer and bookmarks.
Bump `VERSION` in `build.py` for a new edition and add a row to the version table.
