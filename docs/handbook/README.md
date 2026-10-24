# ClubPro handbook

`ClubPro-Handbook.pdf` is the user manual and handbook (v1.5): members, office bearers, operator and a
reference part, with 120+ screenshots cropped to their content, numbered pointers and tooltips, lens zoom-ins, sticky notes, missions and badges,
a barcode on every page (`CLUBPRO-HB-<version>-P<page>`), a part-coloured frame ribbon in the outer margin of every content
page, a running header, a page-number pill, PDF bookmarks, a full-bleed cover, six full-bleed part openers that list their chapters, a contents page with page numbers, credits and a release history.

To regenerate after the screens change (needs the dev server on 127.0.0.1:8810 with the demo data, Node with Playwright,
and in the Python environment: Pillow, pypdf, pdfplumber, python-barcode):

```bash
python docs/handbook/seed_demo.py            # fills the dev demo club with members, finance, loans, bookings, polls, units and tickets, so screenshots are never empty
node docs/handbook/capture.js                 # screenshots into docs/handbook/img
node docs/handbook/capture-v13.js             # society accounts, Library Council and association-mode screens (switches the demo club to association mode and back)
python docs/handbook/build.py                 # body (two renders for contents page numbers) + cover/back + frame and barcode overlay -> ClubPro-Handbook.pdf
```

`build.py` holds the text, the pointer / lens coordinates and the missions; `handbook.css` the design system (palette,
gradients, highlighters, sticky notes, pins, lenses); `render.js` the A4 rendering of the body; the header, footer, page pill, ribbon, barcode and bookmarks are stamped by `build.py` from an overlay page, and the cover, back cover and part openers are rendered full-bleed and merged in; `brand/` the Bpro
wordmark in white (cover, back, colophon) and navy (footer). Bump `VERSION` in `build.py` for a new edition and add a row to
`HISTORY`.
