# RosieChinese — static site

A self-contained export of the `RosieChinese_v2` design from Claude Design,
published with GitHub Pages so it can be previewed by anyone with the link.

**Live:** https://freeyy.github.io/rosie-chinese/

This is a **visual prototype**: every screen, animation and interaction from the
design preview works (nav, booking flow, dashboards, tabs, FAQ), but nothing is
wired to a backend — no accounts, no payments, no data is stored or sent.

## How it renders

The design file is not plain HTML. It is a template plus a component-logic class
that the Claude Design runtime turns into a page in the browser. Rather than
rewrite the design by hand, this site ships that runtime, so what you see is the
same code that produced the preview.

Everything the page needs is bundled into `index.html` itself — the runtime,
React, and the `@font-face` declarations. Loading the site makes three requests:
the HTML and the two photographs. Nothing is fetched from a CDN or from Google
Fonts, so no third-party outage or blocked domain can leave the page half-built.

`index.html` is generated. Edit `src/`, not the root file.

## Layout

| Path | What it is |
| --- | --- |
| `build.py` | Generates `index.html` from `src/` |
| `src/RosieChinese_v2.dc.html` | The design export, exactly as Claude Design produced it |
| `src/support.js` | Claude Design runtime |
| `src/react*.min.js` | React 18.3.1 UMD builds |
| `src/fonts.css` | `@font-face` rules pointing at `fonts/` |
| `index.html` | Generated — the whole site in one file |
| `assets/` | Photography |
| `fonts/` | Newsreader, Hanken Grotesk and the Noto Sans SC subsets this page uses |
| `favicon.svg` | Tab icon |
| `.nojekyll` | Tells GitHub Pages to serve the files as-is |

## Rebuild after a design change

Re-export `RosieChinese_v2.dc.html` from Claude Design over `src/`, then:

```sh
python3 build.py
```

`build.py` fails loudly if the design file no longer contains something it
expects to rewrite, so a silently half-applied build is not possible.

## Run it locally

```sh
python3 -m http.server 8000
# open http://localhost:8000
```

Opening the file directly (`file://`) works too, but serving it is closer to
production.

## Known limitation

At phone widths the Contact screen still scrolls sideways by about 32px. The
contact-card column is a grid item with the default `min-width: auto`, so it
refuses to shrink below its own min-content width of ~390px. It is the same
pattern the hero had before it was changed to `minmax(0, ...)`, and it is best
fixed in the design rather than patched here. Every other screen is clean.
