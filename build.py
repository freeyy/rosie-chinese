#!/usr/bin/env python3
"""Build index.html from the Claude Design export in src/.

The design file is a template plus component logic that the Claude Design
runtime (src/support.js) renders in the browser. This script bundles the
runtime, React and the webfont declarations straight into the page, so the
published site needs exactly three network requests to become usable: the
HTML itself and the two photographs. Nothing is fetched from a third party.

Usage: python3 build.py
"""

import pathlib
import re

ROOT = pathlib.Path(__file__).parent
SRC = ROOT / "src"

TITLE = "RosieChinese — Real Chinese, one conversation at a time"
DESCRIPTION = (
    "Private 1:1 Mandarin lessons that get you actually speaking "
    "— not just memorizing characters."
)


def read(name):
    return (SRC / name).read_text(encoding="utf-8")


def inline_script(name):
    body = read(name)
    if "</script" in body.lower():
        raise SystemExit(f"{name} contains a closing script tag; cannot inline it")
    return f"<script>\n{body}\n</script>"


def drop(html, pattern, expected=1, label=""):
    """Remove a pattern, asserting how many times it was supposed to match."""
    out, found = re.subn(pattern, "", html, flags=re.I)
    if found != expected:
        raise SystemExit(f"expected {expected} match(es) for {label or pattern}, found {found}")
    return out


def build():
    html = read("RosieChinese_v2.dc.html")

    # The runtime is inlined below, and the fonts are served from ./fonts.
    html = drop(html, r'\s*<script src="\./support\.js"></script>', label="support.js tag")
    html = drop(html, r'\s*<link rel="preconnect" href="https://fonts\.googleapis\.com">', label="preconnect")
    html = drop(html, r'\s*<link rel="preconnect" href="https://fonts\.gstatic\.com"[^>]*>', label="preconnect crossorigin")
    html = drop(html, r'\s*<link href="https://fonts\.googleapis\.com/css2[^"]*" rel="stylesheet">', label="google fonts")
    # <image-slot> is never used on this page, so its helper is dead weight.
    html = drop(html, r'\s*<script src="\./image-slot\.js"></script>', label="image-slot.js tag")

    head = f"""<title>{TITLE}</title>
<meta name="description" content="{DESCRIPTION}">
<meta name="theme-color" content="#F4EEE5">
<meta property="og:title" content="{TITLE}">
<meta property="og:description" content="{DESCRIPTION}">
<meta property="og:type" content="website">
<link rel="icon" href="./favicon.svg" type="image/svg+xml">
<link rel="preload" as="image" href="./assets/rosie-soft.png">
<!-- The raw template must never be painted, even if the runtime below fails. -->
<style>x-dc{{display:none!important}}</style>
<style>
{read("fonts.css")}
</style>
<script>
  // Marks the page as self-bundled. The runtime then skips re-fetching and
  // re-parsing its own HTML — which would otherwise find the "<x-dc>" strings
  // inside the inlined runtime source below and mistake them for the template.
  window.__resources = {{}};
</script>
{inline_script("react.production.min.js")}
{inline_script("react-dom.production.min.js")}
{inline_script("support.js")}"""

    html = html.replace(
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n' + head,
        1,
    )

    # If the runtime never mounts, say so instead of showing a blank page.
    fallback = """
<noscript><div class="rc-fallback-note">This page is an interactive prototype and needs JavaScript to render.</div></noscript>
<div id="rc-fallback" hidden class="rc-fallback-note">
  <p>The page didn't finish loading. A refresh usually fixes it.</p>
</div>
<style>
  .rc-fallback-note { position: fixed; inset: 0; display: grid; place-items: center; padding: 32px;
    font-family: system-ui, sans-serif; font-size: 16px; line-height: 1.6; color: #5C5349;
    background: #F4EEE5; text-align: center; z-index: 999; }
  #rc-fallback[hidden] { display: none; }
</style>
<script>
  setTimeout(function () {
    var root = document.getElementById('dc-root');
    if (!root || !root.firstElementChild) document.getElementById('rc-fallback').hidden = false;
  }, 8000);
</script>
</body>"""
    html = html.replace("</body>", fallback, 1)

    (ROOT / "index.html").write_text(html, encoding="utf-8")
    kb = (ROOT / "index.html").stat().st_size / 1024
    print(f"wrote index.html ({kb:.0f} KB)")


if __name__ == "__main__":
    build()
