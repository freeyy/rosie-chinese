#!/usr/bin/env python3
"""End-to-end check: every field in test/fields.json can actually be edited.

For each screen: switch on edit mode, click every field, append a marker,
press Enter, and confirm the change shows on the page and lands in the record.
Then leave the screen and come back (the prototype remounts its DOM) and
confirm every edit is still visible. Finally reload the page to confirm the
edits survive in localStorage, and check the export.

Writes test/e2e-report.md. Exit code 1 on any failure.
"""

import datetime
import json
import sys
import time

from playwright.sync_api import sync_playwright

from fields_lib import INDEX_URL, JS_HELPERS, ROOT, SCREENS, activate_bio, goto_screen, open_faq, wait_ready

MARK = " ✎"
FIELDS = json.loads((ROOT / "test" / "fields.json").read_text(encoding="utf-8"))
LABEL = dict((k, l) for k, l, _ in SCREENS)

FIND = "(key) => {" + JS_HELPERS + """
  const el = findByKey(key); if (!el) return null;
  el.scrollIntoView({block: 'center', inline: 'center'}); return true; }"""
MEASURE = "(key) => {" + JS_HELPERS + """
  const el = findByKey(key); if (!el) return null;
  const visible = e => { for (; e && e !== document.body; e = e.parentElement) { if (e.hasAttribute('data-reveal')) continue; if (getComputedStyle(e).opacity === '0') return false; } return true; };
  const center = () => { const r = el.getBoundingClientRect(); return {x: r.left + r.width / 2, y: r.top + r.height / 2}; };
  const paragraphLike = e => e.children.length > 0 && [...e.children].every(c => c.tagName === 'BR' || /^inline/.test(getComputedStyle(c).display));
  const clear = c => { const top = document.elementsFromPoint(c.x, c.y).filter(e => !e.closest('[data-ed-ui]') && visible(e)).find(e => directText(e) || e.matches('input,textarea') || paragraphLike(e)); return !!top && (el.contains(top) || top.contains(el)); };
  let c = center();
  for (const dy of [0, -220, 440, -660]) { if (dy) window.scrollBy(0, dy); c = center(); if (clear(c)) break; }
  return {x: c.x, y: c.y, covered: !clear(c), tag: el.tagName}; }"""
CARET_END = """() => { const a = document.activeElement; if (!a) return;
  if (a.matches('input,textarea')) { const n = a.value.length; a.setSelectionRange(n, n); return; }
  const r = document.createRange(); r.selectNodeContents(a); r.collapse(false); const s = getSelection(); s.removeAllRanges(); s.addRange(r); }"""
FOCUSED_IN = "(key) => {" + JS_HELPERS + " const el = findByKey(key); const a = document.activeElement; if (!el || !a) return 'no element'; if (el.matches('input,textarea')) return a === el ? 'ok' : 'focus elsewhere: ' + a.tagName; const host = el.querySelector('.rc-edwrap') || el; return (a === host && host.isContentEditable) ? 'ok' : 'focus elsewhere: ' + a.tagName + ' editable=' + a.isContentEditable; }"
TEXT_OF = "(key) => {" + JS_HELPERS + """
  const t = key.startsWith('placeholder:') ? key.slice(12) : null;
  for (const el of document.querySelectorAll('body *')) {
    if (el.closest(ENUM_SKIP) || displayNone(el)) continue;
    if (t !== null) { if (el.matches('input,textarea') && el.placeholder.startsWith(t)) return norm(el.placeholder); continue; }
    if (!isUnit(el)) continue;
    if (norm(el.innerHTML).startsWith(key.replace(/<[^>]+>$/, '')) && textOf(el).endsWith('✎')) return textOf(el);
  }
  return null; }"""
SHOWS_AFTER = "(after) => {" + JS_HELPERS + """
  if (after.startsWith('placeholder:')) return [...document.querySelectorAll('input,textarea')].some(i => norm(i.placeholder) === after.slice(12) && !displayNone(i));
  for (const el of document.querySelectorAll('body *')) { if (el.closest(ENUM_SKIP) || displayNone(el) || !isUnit(el)) continue; if (norm(el.innerHTML) === after) return true; }
  return false; }"""
TEST_CSS = "[data-reveal],.rc-lift,.rc-chap,.rc-photo{transition:none!important}"


def main():
    results = []  # (id, ok, note)
    t0 = time.time()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        wait_ready(page)
        page.add_style_tag(content=TEST_CSS)
        page.evaluate("rcEditor.clearAll(); rcEditor.setOpen(false)")

        expected_after = {}
        for screen, label, _ in SCREENS:
            goto_screen(page, label)
            page.evaluate("rcEditor.setMode(true)")
            group = [f for f in FIELDS if f["screen"] == screen]
            open_faq_i = 0
            cur_bio = 0
            for f in group:
                fid, key = f["id"], f["key"]
                try:
                    if f["substate"].startswith("bio:"):
                        i = int(f["substate"][4:])
                        if i != cur_bio:
                            activate_bio(page, i)
                            cur_bio = i
                    elif f["substate"].startswith("faq:"):
                        i = int(f["substate"][4:])
                        if i != open_faq_i:
                            open_faq(page, i)
                            open_faq_i = i
                    if not page.evaluate(FIND, key):
                        results.append((fid, False, "页面上找不到该元素"))
                        continue
                    page.wait_for_timeout(150)  # let reveal-on-scroll settle before measuring
                    box = page.evaluate(MEASURE, key)
                    if box["covered"]:
                        results.append((fid, False, "元素被其他内容遮挡，点不到"))
                        continue
                    page.wait_for_timeout(60)
                    page.mouse.click(box["x"], box["y"])
                    page.wait_for_timeout(40)
                    st = page.evaluate(FOCUSED_IN, key)
                    if st != "ok":
                        results.append((fid, False, f"点击后未进入编辑状态（{st}）"))
                        page.keyboard.press("Escape")
                        continue
                    page.evaluate(CARET_END)
                    page.keyboard.type(MARK)
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(40)
                    edits = page.evaluate("rcEditor.getEdits()")
                    e = edits.get(key)
                    if not e:
                        results.append((fid, False, "修改没有进入记录"))
                        continue
                    if not e["afterText"].endswith("✎"):
                        results.append((fid, False, f"记录的新文字不对：{e['afterText'][:60]}"))
                        continue
                    if e["beforeText"] != f["text"]:
                        results.append((fid, False, f"记录的原文不对：{e['beforeText'][:60]}"))
                        continue
                    shown = page.evaluate(SHOWS_AFTER, e["after"])
                    if not shown:
                        results.append((fid, False, "页面上没有显示改后的文字"))
                        continue
                    expected_after[fid] = e["after"]
                    results.append((fid, True, ""))
                except Exception as ex:  # noqa: BLE001
                    results.append((fid, False, f"异常：{str(ex)[:80]}"))
                    try:
                        page.keyboard.press("Escape")
                    except Exception:  # noqa: BLE001
                        pass

            # persistence through a remount: leave and come back
            other = "About" if label != "About" else "Home"
            goto_screen(page, other)
            goto_screen(page, label)
            cur_bio = 0
            open_faq_i = 0
            for f in group:
                fid = f["id"]
                if fid not in expected_after:
                    continue
                if f["substate"].startswith("bio:"):
                    i = int(f["substate"][4:])
                    if i != cur_bio:
                        activate_bio(page, i)
                        cur_bio = i
                elif f["substate"].startswith("faq:"):
                    i = int(f["substate"][4:])
                    if i != open_faq_i:
                        open_faq(page, i)
                        open_faq_i = i
                page.wait_for_timeout(120)  # edits are re-applied on the next animation frame
                if not page.evaluate(SHOWS_AFTER, expected_after[fid]):
                    results = [(a, False, "换页回来后修改丢失") if a == fid else (a, b, c) for a, b, c in results]
            page.evaluate("window.scrollTo(0,0)")

        # the home marquee mirrors Stories: an edited quote must show there too
        goto_screen(page, "Home")
        quote = next((f for f in FIELDS if f["screen"] == "stories" and f["tag"] == "span" and len(f["text"]) > 60), None)
        marquee_ok = None
        if quote and quote["id"] in expected_after:
            marquee_ok = page.evaluate("(after) => {" + JS_HELPERS + " return [...document.querySelectorAll('.rc-marquee-track p span')].some(s => norm(s.innerHTML) === after); }", expected_after[quote["id"]])

        # reload: edits must come back from localStorage
        n_before = len(expected_after)
        page.reload()
        page.wait_for_selector("#dc-root main[data-screen]", timeout=15000)
        page.wait_for_timeout(500)
        n_after = len(page.evaluate("rcEditor.getEdits()"))
        reload_ok = n_after == n_before
        h1_ok = page.evaluate("() => /✎/.test(document.querySelector('main[data-screen=home] h1').textContent)")
        md = page.evaluate("rcEditor.exportMarkdown()")
        export_ok = md.count("\n| ") >= n_before and "```json" in md
        page.evaluate("rcEditor.clearAll()")
        cleared_ok = page.evaluate("() => !/✎/.test(document.body.innerText)") and len(page.evaluate("rcEditor.getEdits()")) == 0
        browser.close()

    passed = sum(1 for _, ok, _ in results if ok)
    failed = [(i, n) for i, ok, n in results if not ok]
    extra = [
        ("首页滚动评价条同步显示 Stories 页的修改", marquee_ok),
        (f"刷新后修改从 localStorage 恢复（{n_before} 条）", reload_ok),
        ("刷新后首页标题仍显示修改", h1_ok),
        ("导出的 Markdown 含全部记录和 JSON 块", export_ok),
        ("清空后页面恢复原文", cleared_ok),
        ("页面无 JavaScript 报错", not errors),
    ]
    lines = [
        "# 端到端测试报告",
        "",
        f"时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} · 耗时 {time.time() - t0:.0f} 秒 · 字段 {len(results)} 条：通过 {passed}，失败 {len(failed)}",
        "",
        "## 整体检查",
        "",
        "| 检查 | 结果 |",
        "|---|---|",
    ]
    lines += [f"| {name} | {'通过' if ok else '失败'} |" for name, ok in extra]
    if errors:
        lines += ["", "JavaScript 报错：", ""] + [f"- {e[:200]}" for e in errors[:10]]
    lines += ["", "## 逐条结果", "", "| 编号 | 结果 | 说明 |", "|---|---|---|"]
    lines += [f"| {i} | {'通过' if ok else '失败'} | {n} |" for i, ok, n in results]
    (ROOT / "test" / "e2e-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{passed}/{len(results)} fields passed; extra checks: {[(n, ok) for n, ok in extra]}")
    for i, n in failed:
        print(f"  FAIL {i}: {n}")
    sys.exit(0 if not failed and all(ok for _, ok in extra) else 1)


if __name__ == "__main__":
    main()
