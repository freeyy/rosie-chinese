#!/usr/bin/env python3
"""Visual regression: the editor build must render every screen exactly like
the plain prototype when edit mode is off.

Compares full-page screenshots of a baseline page (default: index.html at git
HEAD, i.e. what is deployed) against the current build, per screen, with
animations frozen and each build's own floating tools hidden. Writes
test/visual-report.md. Exit code 1 if any screen differs by more than 0.05%.

Usage: python3 visual.py [baseline.html]
"""

import pathlib
import subprocess
import sys

from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

from fields_lib import ROOT, SCREENS, goto_screen

FREEZE = "*{animation:none!important;transition:none!important} #rc-edpanel,.rc-edtoast,[title='Warm temperature simulator']{display:none!important}"
OUT = ROOT / "test" / "visual"


def shoot(page, url, tag):
    page.goto(url)
    page.wait_for_selector("#dc-root main[data-screen], #dc-root main", timeout=15000)
    page.wait_for_timeout(600)
    page.add_style_tag(content=FREEZE)
    page.evaluate("() => { try { localStorage.removeItem('rc-warmth'); localStorage.removeItem('rc-warmtint'); localStorage.removeItem('rc-copy-edits-v1'); } catch (e) {} }")
    paths = {}
    for screen, label, _ in SCREENS + [("schedule", "Booking", ""), ("dashboard", "Student", ""), ("teacher", "Teacher portal", "")]:
        goto_screen(page, label)
        page.wait_for_timeout(300)
        p = OUT / f"{tag}-{screen}.png"
        page.screenshot(path=str(p), full_page=True)
        paths[screen] = p
    return paths


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if len(sys.argv) > 1:
        baseline = pathlib.Path(sys.argv[1]).resolve()
    else:
        baseline = OUT / "baseline-head.html"
        html = subprocess.check_output(["git", "-C", str(ROOT), "show", "HEAD:index.html"])
        (ROOT / "index.baseline.html").write_bytes(html)  # next to fonts/ and assets/ so relative URLs resolve
        baseline = ROOT / "index.baseline.html"
    rows = []
    worst = 0.0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        a = shoot(page, baseline.as_uri(), "base")
        b = shoot(page, (ROOT / "index.html").as_uri(), "new")
        browser.close()
    for screen in a:
        ia, ib = Image.open(a[screen]).convert("RGB"), Image.open(b[screen]).convert("RGB")
        note = ""
        if ia.size != ib.size:
            note = f"尺寸不同 {ia.size} → {ib.size}"
            h = min(ia.size[1], ib.size[1]); w = min(ia.size[0], ib.size[0])
            ia, ib = ia.crop((0, 0, w, h)), ib.crop((0, 0, w, h))
        diff = ImageChops.difference(ia, ib).convert("L").point(lambda v: 255 if v > 24 else 0)
        changed = sum(1 for v in diff.getdata() if v)
        pct = 100.0 * changed / (diff.size[0] * diff.size[1])
        worst = max(worst, pct)
        if changed:
            diff.save(OUT / f"diff-{screen}.png")
        rows.append((screen, ia.size, pct, note))
    if (ROOT / "index.baseline.html").exists():
        (ROOT / "index.baseline.html").unlink()
    lines = ["# 视觉回归报告", "", f"基线：{'git HEAD 的 index.html（即线上版本）' if len(sys.argv) == 1 else baseline}", "",
             "| 页面 | 截图尺寸 | 像素差异 | 备注 |", "|---|---|---|---|"]
    lines += [f"| {s} | {w}×{h} | {pct:.3f}% | {note} |" for s, (w, h), pct, note in rows]
    (ROOT / "test" / "visual-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for s, size, pct, note in rows:
        print(f"{s:10s} {size} diff {pct:.3f}% {note}")
    sys.exit(0 if worst <= 0.05 else 1)


if __name__ == "__main__":
    main()
