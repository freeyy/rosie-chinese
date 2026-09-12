#!/usr/bin/env python3
"""Build index.html from the Claude Design export in src/.

The design file is a template plus component logic that the Claude Design
runtime (src/support.js) renders in the browser. This script bundles the
runtime, React, the webfont declarations and the in-place copy editor
(src/editor.js) straight into the page. Nothing is fetched from a third party.

On top of the plain export it:
  * tags every screen's <main> with data-screen="…" so the editor and the
    tests can tell screens apart,
  * drops the "warm temperature" developer tool,
  * appends the copy editor.

Usage: python3 build.py            # full build
       python3 build.py --no-editor  # plain preview, no editor (used by tests)
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).parent
SRC = ROOT / "src"

TITLE = "RosieChinese — Real Chinese, one conversation at a time"
DESCRIPTION = (
    "Private 1:1 Mandarin lessons that get you actually speaking "
    "— not just memorizing characters."
)

SCREENS = [
    ("HOME", "home"),
    ("ABOUT", "about"),
    ("COURSES", "courses"),
    ("TESTIMONIALS", "stories"),
    ("SCHEDULING", "schedule"),
    ("CHECKOUT", "checkout"),
    ("STUDENT DASHBOARD", "dashboard"),
    ("TEACHER PORTAL", "teacher"),
    ("CONTACT", "contact"),
]


def read(name):
    return (SRC / name).read_text(encoding="utf-8")


def inline_script(name):
    body = read(name)
    if "</script" in body.lower():
        raise SystemExit(f"{name} contains a closing script tag; cannot inline it")
    return f"<script>\n{body}\n</script>"


def drop(html, pattern, expected=1, label="", flags=re.I):
    """Remove a pattern, asserting how many times it was supposed to match."""
    out, found = re.subn(pattern, "", html, flags=flags)
    if found != expected:
        raise SystemExit(f"expected {expected} match(es) for {label or pattern}, found {found}")
    return out


def tag_screens(html):
    for label, key in SCREENS:
        pat = r"(<!-- ===== " + re.escape(label) + r" ===== -->\s*<sc-if[^>]*>\s*<main)"
        html, n = re.subn(pat, r'\1 data-screen="%s"' % key, html)
        if n != 1:
            raise SystemExit(f"expected 1 <main> for screen {label}, found {n}")
    pat = r'(<!-- ===== LIGHTBOX ===== -->\s*<div onClick="\{\{ closePopup \}\}")'
    html, n = re.subn(pat, r'\1 data-screen="popup"', html)
    if n != 1:
        raise SystemExit(f"expected 1 lightbox root, found {n}")
    return html


def build(with_editor=True):
    html = read("RosieChinese_v2.dc.html")

    # The runtime is inlined below, and the fonts are served from ./fonts.
    html = drop(html, r'\s*<script src="\./support\.js"></script>', label="support.js tag")
    html = drop(html, r'\s*<link rel="preconnect" href="https://fonts\.googleapis\.com">', label="preconnect")
    html = drop(html, r'\s*<link rel="preconnect" href="https://fonts\.gstatic\.com"[^>]*>', label="preconnect crossorigin")
    html = drop(html, r'\s*<link href="https://fonts\.googleapis\.com/css2[^"]*" rel="stylesheet">', label="google fonts")
    # <image-slot> is never used on this page, so its helper is dead weight.
    html = drop(html, r'\s*<script src="\./image-slot\.js"></script>', label="image-slot.js tag")
    # The warm-temperature simulator is a design-time tool; the teacher never needs it.
    html = drop(
        html,
        r"\s*<!-- ===== WARMTH SIMULATOR \(dev tool\) ===== -->.*?(?=\s*<!-- ===== LIGHTBOX ===== -->)",
        label="warmth simulator block",
        flags=re.S,
    )
    # Inline onmouseover/onmouseout strings make React throw (#231). The hover
    # effects they carried are reproduced in CSS below.
    html, n = re.subn(r'\s+onmouse(?:over|out)="[^"]*"', "", html)
    if n != 12:
        raise SystemExit(f"expected 12 inline mouse handlers, found {n}")
    html = tag_screens(html)

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
  /* hover effects for the social icons (moved out of inline handlers) */
  main a[title="TikTok"], main a[title="小红书"], main a[title="YouTube"] {{ transition: transform 0.15s ease; }}
  main a[title="TikTok"]:hover, main a[title="小红书"]:hover, main a[title="YouTube"]:hover {{ transform: translateY(-3px); }}
  footer a[title="TikTok"]:hover {{ background: #111 !important; }}
  footer a[title="YouTube"]:hover {{ background: #FF0000 !important; }}
  footer a[title="YouTube"]:hover path {{ fill: #fff; }}
  main span[style*="cursor: pointer"][style*="border-radius: 50%"][style*="width: 70px"]:hover {{ transform: scale(1.08); }}
</style>
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
"""
    editor = inline_script("editor.js") + "\n" if with_editor else ""
    html = html.replace("</body>", fallback + editor + "</body>", 1)

    out = ROOT / "index.html"
    out.write_text(html, encoding="utf-8")
    kb = out.stat().st_size / 1024
    print(f"wrote index.html ({kb:.0f} KB){'' if with_editor else ' [no editor]'}")


if __name__ == "__main__":
    build(with_editor="--no-editor" not in sys.argv)
