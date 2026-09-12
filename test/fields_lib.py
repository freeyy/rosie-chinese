"""Shared helpers for the field enumerator and the end-to-end test."""

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
INDEX_URL = (ROOT / "index.html").as_uri()

# (screen key, label on the prototype nav bar, checklist prefix)
SCREENS = [
    ("home", "Home", "H"),
    ("about", "About", "A"),
    ("courses", "Courses", "C"),
    ("stories", "Stories", "S"),
    ("contact", "Contact", "K"),
]
GLOBAL_PREFIX = "G"  # header + footer, shared by every screen

# The candidate rule shared by the enumerator, the editor and the test:
# an "editable unit" is the outermost element that owns a run of text,
# climbing out of inline formatting (span/em/strong…) into the block that
# holds it, so a whole heading edits as one piece.
JS_HELPERS = r"""
  const INLINE = new Set(['SPAN','EM','STRONG','B','I','A','SMALL','SUP','SUB','LABEL']);
  const norm = s => s.replace(/\s+/g, ' ').trim();
  const directText = el => { let s = ''; for (const n of el.childNodes) if (n.nodeType === 3) s += n.nodeValue; return norm(s); };
  const isIcon = s => /^[^\p{L}\p{N}]{1,3}$/u.test(s);
  const ownsText = el => { const t = directText(el); return !!t && !isIcon(t); };
  const EXCLUDE = '.rc-proto,[data-ed-ui],main[data-screen="schedule"],main[data-screen="checkout"],main[data-screen="dashboard"],main[data-screen="teacher"],script,style,svg,noscript,#rc-fallback';
  const skip = el => !!el.closest(EXCLUDE);
  const displayNone = el => { for (let e = el; e && e !== document.body; e = e.parentElement) if (getComputedStyle(e).display === 'none') return true; return false; };
  const unitOf = el => { let cur = el; while (cur.parentElement && INLINE.has(cur.tagName) && ownsText(cur.parentElement) && !skip(cur.parentElement)) cur = cur.parentElement; return cur; };
  const isUnit = el => ownsText(el) && unitOf(el) === el && !skip(el);
  const textOf = el => norm((el.innerText || el.textContent).replace(/\n+/g, ' / '));
  const region = el => {
    const m = el.closest('main[data-screen],[data-screen="popup"]');
    if (m) return m.dataset.screen;
    if (el.closest('header')) return 'header';
    if (el.closest('footer')) return 'footer';
    return 'other';
  };
  const substateOf = unit => {
    const chap = unit.closest('.rc-chap');
    if (chap) return 'bio:' + [...document.querySelectorAll('.rc-chap')].indexOf(chap);
    const layer = unit.closest('.rc-photo');
    if (layer) return 'bio:' + [...layer.parentElement.querySelectorAll(':scope > .rc-photo')].indexOf(layer);
    const body = unit.closest('main[data-screen="courses"] div[style*="grid-template-rows"]');
    if (body) { const card = body.parentElement; return 'faq:' + [...card.parentElement.children].indexOf(card); }
    return '';
  };
  // The home-page marquee repeats the Stories cards verbatim; the checklist lists them once, under Stories.
  const ENUM_SKIP = '.rc-marquee';
  const collect = () => {
    const seen = new Set(); const out = [];
    for (const el of document.querySelectorAll('body *')) {
      if (el.closest(ENUM_SKIP) || !isUnit(el) || displayNone(el)) continue;
      const key = norm(el.innerHTML);
      if (seen.has(key)) continue;
      seen.add(key);
      const tplEl = el.closest('[data-dc-tpl]');
      out.push({ region: region(el), tag: el.tagName.toLowerCase(), key, text: textOf(el), substate: substateOf(el), story: !!el.closest('[data-story]'), tpl: tplEl ? tplEl.getAttribute('data-dc-tpl') : '' });
    }
    for (const inp of document.querySelectorAll('input[placeholder],textarea[placeholder]')) {
      if (skip(inp) || displayNone(inp)) continue;
      const key = 'placeholder:' + norm(inp.placeholder);
      if (seen.has(key)) continue;
      seen.add(key);
      out.push({ region: region(inp), tag: inp.tagName.toLowerCase(), key, text: norm(inp.placeholder), substate: '', tpl: inp.getAttribute('data-dc-tpl') || '' });
    }
    return out;
  };
  // Locate the first rendered element for a checklist key (used by the e2e test).
  const findByKey = key => {
    if (key.startsWith('placeholder:')) {
      const t = key.slice(12);
      return [...document.querySelectorAll('input[placeholder],textarea[placeholder]')].find(i => norm(i.placeholder) === t && !skip(i) && !displayNone(i)) || null;
    }
    for (const el of document.querySelectorAll('body *')) {
      if (el.closest(ENUM_SKIP) || displayNone(el) || !isUnit(el)) continue;
      if (norm(el.innerHTML) === key) return el;
    }
    return null;
  };
"""


def goto_screen(page, label):
    """Click the prototype nav button with this label and wait for the screen."""
    page.locator(".rc-proto button", has_text=label).first.click()
    page.wait_for_timeout(350)


def activate_bio(page, i):
    """Scroll the About story so chapter i is the active one."""
    page.evaluate(
        "(i) => { const t = document.querySelector('[data-bio=\"' + i + '\"]'); "
        "const r = t.getBoundingClientRect(); window.scrollBy(0, r.top + r.height / 2 - innerHeight / 2); }",
        i,
    )
    page.wait_for_function(
        "(i) => { const c = document.querySelectorAll('.rc-chap')[i]; return c && parseFloat(getComputedStyle(c).opacity) > 0.95; }",
        arg=i,
        timeout=4000,
    )


def open_faq(page, i):
    """Expand FAQ card i with a real click on its chevron (an icon, so it passes through in edit mode)."""
    c = page.evaluate(
        "(i) => { const btn = document.querySelectorAll('main[data-screen=\"courses\"] section button')[i]; "
        "btn.scrollIntoView({block: 'center'}); const r = btn.lastElementChild.getBoundingClientRect(); "
        "return {x: r.left + r.width / 2, y: r.top + r.height / 2}; }",
        i,
    )
    page.mouse.click(c["x"], c["y"])
    page.wait_for_timeout(650)


def wait_ready(page):
    page.goto(INDEX_URL)
    page.wait_for_selector("#dc-root main[data-screen]", timeout=15000)
    page.wait_for_timeout(400)
