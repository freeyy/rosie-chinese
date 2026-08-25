# RosieChinese — static site

A static, self-contained export of the `RosieChinese_v2` design from Claude Design,
published with GitHub Pages so it can be previewed by anyone with the link.

**Live:** https://freeyy.github.io/rosie-chinese/

This is a **visual prototype**: every screen, animation and interaction from the
design preview works (nav, booking flow, dashboards, tabs, FAQ), but nothing is
wired to a backend — no accounts, no payments, no data is stored or sent.

## Layout

| Path | What it is |
| --- | --- |
| `index.html` | The design file itself (template + component logic) |
| `support.js` | Claude Design runtime that renders the template |
| `image-slot.js` | Runtime helper the design file references |
| `vendor/` | React 18.3.1 UMD builds, vendored so the site has no CDN dependency |
| `assets/` | Photography used by the page |
| `favicon.svg` | Tab icon |
| `.nojekyll` | Tells GitHub Pages to serve the files as-is |

## Run it locally

```sh
python3 -m http.server 8000
# open http://localhost:8000
```

A plain file open (`file://`) will not work — the runtime fetches `support.js`
relative to the page, so it needs to be served over HTTP.

## Fonts

Newsreader, Hanken Grotesk and Noto Sans SC are loaded from Google Fonts.
Everything else is served from this repository.
