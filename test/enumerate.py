#!/usr/bin/env python3
"""List every editable copy field in the rendered prototype.

Drives the built page through each screen (and the About story chapters,
whose captions only exist while active), collects every text unit with the
same rule the editor uses, numbers them, and writes:

  test/fields.json          machine list used by e2e.py
  docs/editable-fields.md   human checklist, one row per field

Run `python3 build.py` first.
"""

import datetime
import json
import pathlib

from playwright.sync_api import sync_playwright

from fields_lib import GLOBAL_PREFIX, JS_HELPERS, ROOT, SCREENS, activate_bio, goto_screen, wait_ready

COLLECT = "() => {" + JS_HELPERS + " return collect(); }"

SUBSTATE_NOTE = {
    "bio": "About 页个人故事第 {n} 段，滚动到该段后可编辑",
    "faq": "FAQ 第 {n} 条，点击右侧 + 展开后可编辑",
}


def main():
    fields = []
    seen = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        wait_ready(page)

        def take(items, screen, prefix, bio=0):
            for it in items:
                if it.get("story") and not it["substate"]:
                    it["substate"] = f"bio:{bio}"
                it.pop("story", None)
                if it["key"] in seen:
                    if screen != seen[it["key"]]["screen"]:
                        seen[it["key"]]["also"].append(screen)
                    continue
                if it["region"] in ("header", "footer"):
                    pfx, reg = GLOBAL_PREFIX, it["region"]
                else:
                    pfx, reg = prefix, screen
                rec = {"id": None, "prefix": pfx, "region": reg, "screen": screen, **it, "also": []}
                seen[it["key"]] = rec
                fields.append(rec)

        for screen, label, prefix in SCREENS:
            goto_screen(page, label)
            take(page.evaluate(COLLECT), screen, prefix)
            if screen == "about":
                for i in range(1, 4):
                    activate_bio(page, i)
                    take(page.evaluate(COLLECT), screen, prefix, bio=i)
                page.evaluate("window.scrollTo(0, 0)")
        browser.close()

    # number per prefix in the order encountered
    counters = {}
    for f in fields:
        counters[f["prefix"]] = counters.get(f["prefix"], 0) + 1
        f["id"] = f"{f['prefix']}{counters[f['prefix']]:03d}"

    (ROOT / "test" / "fields.json").write_text(json.dumps(fields, ensure_ascii=False, indent=1), encoding="utf-8")

    # human checklist
    title = {"G": "全站共用（页头、页脚）", "H": "首页 Home", "A": "About 页", "C": "Courses 页", "S": "Stories 页", "K": "Contact 页"}
    lines = [
        "# 可编辑文案清单",
        "",
        f"生成时间：{datetime.date.today().isoformat()} · 来源：src/RosieChinese_v2.dc.html · 共 {len(fields)} 条",
        "",
        "每一条对应网页上一段可以直接点击修改的文字。编号规则：G 全站共用，H 首页，A About，C Courses，S Stories，K Contact。",
        "同一段文字在多个位置出现的只列一次，改一处全站同步。首页滚动的学生评价和 Stories 页内容相同，列在 Stories 下。",
        "预约、结账、学生后台、老师后台里的文字是演示数据，不在清单里。",
        "",
    ]
    for pfx in ["G", "H", "A", "C", "S", "K"]:
        group = [f for f in fields if f["prefix"] == pfx]
        if not group:
            continue
        lines += [f"## {title[pfx]}（{len(group)} 条）", "", "| 编号 | 类型 | 原文 | 备注 |", "|---|---|---|---|"]
        for f in group:
            note = ""
            if f["substate"]:
                kind, n = f["substate"].split(":")
                note = SUBSTATE_NOTE[kind].format(n=int(n) + 1)
            if f["key"].startswith("placeholder:"):
                note = "输入框里的提示文字"
            if f["also"]:
                note = (note + "；" if note else "") + "也用在 " + "、".join(sorted(set(f["also"])))
            text = f["text"].replace("|", "\\|")
            if len(text) > 140:
                text = text[:140] + "…"
            lines.append(f"| {f['id']} | {f['tag']} | {text} | {note} |")
        lines.append("")
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "editable-fields.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(fields)} fields → test/fields.json, docs/editable-fields.md")
    for pfx in ["G", "H", "A", "C", "S", "K"]:
        print(f"  {pfx}: {counters.get(pfx, 0)}")


if __name__ == "__main__":
    main()
