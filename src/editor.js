/* In-place copy editor for the RosieChinese prototype.
 *
 * Adds a small panel; in edit mode any run of text on the page can be clicked
 * and rewritten. Edits are keyed by the ORIGINAL markup of the edited element,
 * kept in localStorage, re-applied after every re-render of the prototype
 * (screen switches remount the DOM), and exported as a Markdown + JSON record
 * that maps straight back to src/RosieChinese_v2.dc.html.
 *
 * Nothing here changes layout: highlights use CSS outlines only, and the only
 * animation touched is the testimonial marquee, paused while editing so cards
 * hold still.
 */
(function () {
  'use strict';
  if (window.rcEditor) return;

  /* ---------- the "editable unit" rule (mirrored in test/fields_lib.py) ---------- */
  const INLINE = new Set(['SPAN', 'EM', 'STRONG', 'B', 'I', 'A', 'SMALL', 'SUP', 'SUB', 'LABEL']);
  const norm = s => s.replace(/\s+/g, ' ').trim();
  const directText = el => { let s = ''; for (const n of el.childNodes) if (n.nodeType === 3) s += n.nodeValue; return norm(s); };
  const isIcon = s => /^[^\p{L}\p{N}]{1,3}$/u.test(s);
  const ownsText = el => { const t = directText(el); return !!t && !isIcon(t); };
  const EXCLUDE = '.rc-proto,[data-ed-ui],main[data-screen="schedule"],main[data-screen="checkout"],main[data-screen="dashboard"],main[data-screen="teacher"],script,style,svg,noscript,#rc-fallback';
  const skip = el => !!el.closest(EXCLUDE);
  const unitOf = el => { let cur = el; while (cur.parentElement && INLINE.has(cur.tagName) && ownsText(cur.parentElement) && !skip(cur.parentElement)) cur = cur.parentElement; return cur; };
  const isUnit = el => ownsText(el) && unitOf(el) === el && !skip(el);
  const isField = el => el.matches('input[placeholder],textarea[placeholder]') && !skip(el);
  const textOf = el => norm((el.innerText || el.textContent).replace(/\n+/g, ' / '));
  const region = el => {
    const m = el.closest('main[data-screen],[data-screen="popup"]');
    if (m) return m.dataset.screen;
    if (el.closest('header')) return 'header';
    if (el.closest('footer')) return 'footer';
    return 'other';
  };
  const tplOf = el => { const t = el.closest('[data-dc-tpl]'); return t ? t.getAttribute('data-dc-tpl') : ''; };
  const SCREEN_NAMES = { home: '首页', about: 'About', courses: 'Courses', stories: 'Stories', contact: 'Contact', header: '页头', footer: '页脚', popup: '弹窗', other: '其他' };

  /* ---------- state ---------- */
  const STORAGE = 'rc-copy-edits-v1';
  const state = { on: false, edits: {}, editing: null, open: false, confirmClear: false };
  let applying = false;

  function load() {
    try { const raw = localStorage.getItem(STORAGE); if (raw) state.edits = JSON.parse(raw) || {}; } catch (e) { state.edits = {}; }
  }
  function save() {
    try { localStorage.setItem(STORAGE, JSON.stringify(state.edits)); } catch (e) { /* private mode etc. */ }
  }

  /* ---------- applying edits to the live DOM ---------- */
  // Which edit produced this element's current content, if any.
  function keyFor(cur) {
    if (state.edits[cur]) return cur;
    for (const k in state.edits) if (state.edits[k].after === cur) return k;
    return cur;
  }
  function setContent(el, html) {
    // Single text node: rewrite it in place, so the runtime keeps owning the node.
    if (el.childNodes.length === 1 && el.firstChild.nodeType === 3 && !/[<>&]/.test(html.replace(/&amp;|&lt;|&gt;|&quot;|&#39;|&nbsp;/g, ''))) {
      const tmp = document.createElement('span'); tmp.innerHTML = html;
      el.firstChild.nodeValue = tmp.textContent;
    } else {
      el.innerHTML = html;
    }
  }
  function applyAll(root) {
    root = root || document.body;
    const edits = state.edits;
    const keys = Object.keys(edits);
    applying = true;
    try {
      const afters = new Set(keys.map(k => edits[k].after));
      for (const el of root.querySelectorAll('*')) {
        if (el === state.editing || el.closest('[data-ed-ui]')) continue;
        if (el.matches('input,textarea')) {
          if (!el.placeholder || skip(el)) continue;
          const cur = 'placeholder:' + norm(el.placeholder);
          const e = edits[cur];
          if (e) { el.placeholder = e.afterText; el.classList.add('rc-edited'); }
          else if (!afters.has(cur) && !keyFor(cur).startsWith('placeholder:')) el.classList.remove('rc-edited');
          else el.classList.toggle('rc-edited', keyFor(cur) !== cur);
          continue;
        }
        if (!keys.length) { if (el.classList.contains('rc-edited')) el.classList.remove('rc-edited'); continue; }
        if (!isUnit(el)) continue;
        const cur = norm(el.innerHTML);
        const e = edits[cur];
        if (e && e.after !== cur) { setContent(el, e.after); el.classList.add('rc-edited'); }
        else el.classList.toggle('rc-edited', afters.has(cur));
      }
    } finally { applying = false; }
  }
  let raf = 0;
  const mo = new MutationObserver(muts => {
    if (applying) return;
    if (!muts.some(m => !(m.target instanceof Element) || !m.target.closest('[data-ed-ui]'))) return;
    if (!raf) raf = requestAnimationFrame(() => { raf = 0; applyAll(); });
  });

  /* ---------- editing ---------- */
  // Is this element actually showing? Stacked layers fade with opacity; a faded layer must not take clicks.
  function visible(el) {
    for (let e = el; e && e !== document.body; e = e.parentElement) {
      if (e.hasAttribute('data-reveal')) continue;            // reveal-on-scroll, still legitimately clickable
      if (getComputedStyle(e).opacity === '0') return false;
    }
    return true;
  }
  const paragraphLike = e => e.children.length > 0 && [...e.children].every(c => c.tagName === 'BR' || /^inline/.test(getComputedStyle(c).display));
  function unitAt(x, y, target) {
    if (!(target instanceof Element)) return null;
    if (target.closest('[data-ed-ui],.rc-proto')) return null;
    // Walk the hit-test stack top-down: the first thing that owns text wins; an icon (＋, ×, ▶) passes through.
    const stack = document.elementsFromPoint(x, y);
    for (const e of stack) {
      if (e.closest('[data-ed-ui]')) continue;
      if (e.closest('.rc-proto')) return null;
      if (!visible(e)) continue;
      if (isField(e)) return skip(e) ? null : e;
      const dt = directText(e);
      if (dt) { if (isIcon(dt)) return null; const u = unitOf(e); return isUnit(u) ? u : null; }
      // A paragraph whose text sits in inline children: the pointer may be in the gap between two lines.
      if (paragraphLike(e)) {
        const r = document.caretRangeFromPoint ? document.caretRangeFromPoint(x, y) : null;
        const n = r && r.startContainer;
        const d = n ? (n.nodeType === 3 ? n.parentElement : (n instanceof Element ? n : null)) : null;
        if (d && d !== e && e.contains(d) && ownsText(d)) { const u = unitOf(d); return isUnit(u) ? u : null; }
      }
    }
    // Nothing textual under the pointer: allow clicks on the padding of a button or link to edit its label.
    const ctl = target.closest('button,a');
    const r = ctl && document.caretRangeFromPoint ? document.caretRangeFromPoint(x, y) : null;
    if (r && r.startContainer) {
      const n = r.startContainer;
      const el = n.nodeType === 3 ? n.parentElement : (n instanceof Element ? n : null);
      if (el && ctl.contains(el) && ownsText(el)) { const u = unitOf(el); return isUnit(u) ? u : null; }
    }
    return null;
  }

  function startEdit(unit, x, y) {
    if (state.editing) commit(false);
    // fold the panel so it never sits on top of the text being edited
    if (state.open) { state.open = false; renderPanel(); }
    state.editing = unit;
    if (isField(unit)) {
      unit._edBefore = norm(unit.placeholder);
      unit._edKey = keyFor('placeholder:' + unit._edBefore);
      unit.value = unit.placeholder;
      unit.classList.add('rc-editing');
      unit.focus(); unit.select();
      return;
    }
    unit._edBefore = norm(unit.innerHTML);
    unit._edBeforeText = textOf(unit);
    unit._edKey = keyFor(unit._edBefore);
    let host = unit;
    if (unit.tagName === 'BUTTON' || unit.tagName === 'A') {
      // Buttons and links do not take a caret themselves: edit inside a temporary wrapper.
      host = document.createElement('span');
      host.className = 'rc-edwrap';
      while (unit.firstChild) host.appendChild(unit.firstChild);
      unit.appendChild(host);
      unit._edHost = host;
    }
    host.setAttribute('contenteditable', 'plaintext-only');
    if (!host.isContentEditable) host.setAttribute('contenteditable', 'true');
    unit.classList.add('rc-editing');
    host.focus();
    const r = document.caretRangeFromPoint ? document.caretRangeFromPoint(x, y) : null;
    const sel = window.getSelection();
    if (r && host.contains(r.startContainer)) { sel.removeAllRanges(); sel.addRange(r); }
    else { const rng = document.createRange(); rng.selectNodeContents(host); rng.collapse(false); sel.removeAllRanges(); sel.addRange(rng); }
    refreshHover(null);
  }

  function commit(cancel) {
    const unit = state.editing;
    if (!unit) return;
    state.editing = null;
    unit.classList.remove('rc-editing');
    const key = unit._edKey;
    if (isField(unit)) {
      const v = norm(unit.value);
      unit.value = '';
      const origText = key.slice(12);
      if (cancel) { unit.placeholder = unit._edBefore; return; }
      if (v === origText || !v) { delete state.edits[key]; unit.placeholder = origText; }
      else state.edits[key] = { key, kind: 'placeholder', screen: region(unit), tag: unit.tagName.toLowerCase(), tpl: tplOf(unit), before: key, beforeText: origText, after: 'placeholder:' + v, afterText: v, at: Date.now() };
      finish();
      return;
    }
    const host = unit._edHost || unit;
    host.removeAttribute('contenteditable');
    if (unit._edHost) { while (host.firstChild) unit.appendChild(host.firstChild); host.remove(); unit._edHost = null; }
    if (cancel) { setContent(unit, unit._edBefore); finish(); return; }
    const afterHtml = norm(unit.innerHTML);
    // the original wording: from the existing record if this element was already edited, else as it read before this edit
    const beforeText = state.edits[key] ? state.edits[key].beforeText : unit._edBeforeText;
    if (afterHtml === key || !textOf(unit)) {
      delete state.edits[key];
      if (afterHtml !== key) setContent(unit, key);
    } else {
      state.edits[key] = { key, kind: 'text', screen: region(unit), tag: unit.tagName.toLowerCase(), tpl: tplOf(unit), before: key, beforeText, after: afterHtml, afterText: textOf(unit), at: Date.now() };
    }
    finish();
  }
  function finish() { save(); applyAll(); renderPanel(); }

  function undo(key) {
    const e = state.edits[key];
    if (!e) return;
    delete state.edits[key];
    save();
    // put the original back wherever the edited content is showing
    for (const el of document.querySelectorAll('*')) {
      if (el.closest('[data-ed-ui]')) continue;
      if (e.kind === 'placeholder') { if (el.matches('input,textarea') && norm(el.placeholder) === e.afterText) { el.placeholder = e.beforeText; el.classList.remove('rc-edited'); } continue; }
      if (isUnit(el) && norm(el.innerHTML) === e.after) { setContent(el, e.before); el.classList.remove('rc-edited'); }
    }
    applyAll(); renderPanel();
  }
  function clearAll() { for (const k of Object.keys(state.edits)) undo(k); state.confirmClear = false; renderPanel(); }

  /* ---------- export ---------- */
  function exportMarkdown() {
    const list = Object.values(state.edits).sort((a, b) => a.at - b.at);
    const d = new Date();
    const pad = n => String(n).padStart(2, '0');
    const stamp = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
    const esc = s => s.replace(/\|/g, '\\|');
    const lines = [`# 文案修改记录 · ${stamp}`, '', `共 ${list.length} 处`, '', '| 页面 | 原文 | 改后 |', '|---|---|---|'];
    for (const e of list) lines.push(`| ${SCREEN_NAMES[e.screen] || e.screen} | ${esc(e.beforeText)} | ${esc(e.afterText)} |`);
    lines.push('', '```json', JSON.stringify(list.map(e => ({ screen: e.screen, tpl: e.tpl, tag: e.tag, before: e.before, after: e.after })), null, 1), '```', '');
    return lines.join('\n');
  }
  function download() {
    const blob = new Blob([JSON.stringify(Object.values(state.edits), null, 1)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'rosiechinese-copy-edits.json';
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }
  async function copy() {
    const md = exportMarkdown();
    try { await navigator.clipboard.writeText(md); flash('已复制，直接粘贴发给我们就行'); }
    catch (e) { const ta = panel.querySelector('textarea'); ta.hidden = false; ta.value = md; ta.select(); flash('请手动全选复制下面的内容'); }
  }

  /* ---------- mode ---------- */
  function setMode(on) {
    state.on = !!on;
    document.body.classList.toggle('rc-ed-on', state.on);
    if (!state.on) { commit(false); refreshHover(null); }
    renderPanel();
  }
  let hovered = null;
  function refreshHover(el) {
    if (hovered && hovered !== el) hovered.classList.remove('rc-edhover');
    hovered = el;
    if (el && el !== state.editing && !(state.editing && state.editing.contains(el))) el.classList.add('rc-edhover');
  }

  document.addEventListener('click', ev => {
    if (!state.on) return;
    const t = ev.target;
    if (!(t instanceof Element) || t.closest('[data-ed-ui]')) return;
    // Space/Enter inside a button being edited makes the browser synthesize a click
    // (detail 0, at 0,0). Swallow it: it must neither navigate nor start another edit.
    if (state.editing && ev.detail === 0) { ev.preventDefault(); ev.stopPropagation(); return; }
    if (state.editing && (state.editing.contains(t) || t === state.editing)) return;
    const unit = unitAt(ev.clientX, ev.clientY, t);
    if (!unit) { if (state.editing) commit(false); return; }
    ev.preventDefault(); ev.stopPropagation();
    startEdit(unit, ev.clientX, ev.clientY);
  }, true);
  document.addEventListener('mousedown', ev => {
    // keep the runtime from reacting to the press that starts an edit
    if (!state.on) return;
    const t = ev.target;
    if (!(t instanceof Element) || t.closest('[data-ed-ui]')) return;
    if (state.editing && state.editing.contains(t)) return;
    if (unitAt(ev.clientX, ev.clientY, t)) ev.stopPropagation();
  }, true);
  let hoverRaf = 0;
  document.addEventListener('mousemove', ev => {
    if (!state.on || hoverRaf) return;
    hoverRaf = requestAnimationFrame(() => { hoverRaf = 0; refreshHover(unitAt(ev.clientX, ev.clientY, ev.target)); });
  }, true);
  document.addEventListener('keydown', ev => {
    if (!state.editing) return;
    if (ev.key === 'Enter' && !ev.shiftKey) { ev.preventDefault(); ev.stopPropagation(); commit(false); }
    else if (ev.key === 'Escape') { ev.preventDefault(); ev.stopPropagation(); commit(true); }
    else ev.stopPropagation();
  }, true);
  document.addEventListener('keyup', ev => {
    if (!state.editing) return;
    // a Space released inside a button would "press" the button
    if (ev.key === ' ' && state.editing.closest('button,a')) ev.preventDefault();
    ev.stopPropagation();
  }, true);
  document.addEventListener('keypress', ev => { if (state.editing) ev.stopPropagation(); }, true);
  document.addEventListener('focusout', ev => {
    const u = state.editing;
    if (!u) return;
    const host = u._edHost || u;
    if (ev.target !== host && ev.target !== u) return;
    // let a click on another unit start its own edit first
    setTimeout(() => { if (state.editing === u && document.activeElement !== host) commit(false); }, 0);
  }, true);

  /* ---------- panel ---------- */
  const css = `
  /* A terracotta ring with a white halo stays visible on cream, on the dark boxes and on terracotta buttons alike. */
  body.rc-ed-on .rc-edhover:not(:has(> .rc-edwrap)) { outline: 2px dashed #C2674F; outline-offset: 3px; box-shadow: 0 0 0 5px rgba(255,255,255,.85); border-radius: 4px; cursor: text; }
  .rc-editing:not(:has(> .rc-edwrap)), .rc-edwrap { outline: 2px solid #C2674F !important; outline-offset: 3px; box-shadow: 0 0 0 5px rgba(255,255,255,.9) !important; border-radius: 4px; cursor: text; caret-color: auto; }
  .rc-edwrap { display: inline; }
  .rc-edwrap:focus, [contenteditable]:focus { outline: 2px solid #C2674F; }
  body.rc-ed-on .rc-edited { text-decoration: underline dotted currentColor; text-underline-offset: 3px; text-decoration-thickness: 1.5px; }
  body.rc-ed-on .rc-marquee-track { animation: none !important; }
  body.rc-ed-on .rc-marquee { overflow-x: auto !important; }
  body.rc-ed-on .rc-photo[style*="opacity:0;"], body.rc-ed-on .rc-photo[style*="opacity: 0;"] { pointer-events: none; }
  body.rc-ed-on [data-ed-ui] .rc-edhover { outline: none; }
  #rc-edpanel { position: fixed; right: 18px; bottom: 18px; z-index: 200; width: 316px; max-width: calc(100vw - 36px); font-family: 'Hanken Grotesk', -apple-system, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', system-ui, sans-serif; font-size: 13px; color: #F4EEE5; background: rgba(38,32,27,.94); backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px); border: 1px solid rgba(255,255,255,.12); border-radius: 18px; box-shadow: 0 24px 50px -22px rgba(0,0,0,.6); overflow: hidden; }
  #rc-edpanel * { box-sizing: border-box; }
  #rc-edpanel .hd { display: flex; align-items: center; gap: 10px; padding: 13px 14px 12px; border-bottom: 1px solid rgba(255,255,255,.1); }
  #rc-edpanel .hd b { font-size: 14px; font-weight: 700; letter-spacing: .01em; }
  #rc-edpanel .hd .n { color: #E59B82; font-weight: 700; }
  #rc-edpanel .sw { margin-left: auto; display: flex; align-items: center; gap: 8px; cursor: pointer; user-select: none; }
  #rc-edpanel .sw i { width: 38px; height: 22px; border-radius: 100px; background: #6B6258; position: relative; transition: background .2s; }
  #rc-edpanel .sw i::after { content: ''; position: absolute; top: 3px; left: 3px; width: 16px; height: 16px; border-radius: 50%; background: #fff; transition: transform .2s; }
  #rc-edpanel .sw.on i { background: #C2674F; }
  #rc-edpanel .sw.on i::after { transform: translateX(16px); }
  #rc-edpanel .fold { background: none; border: none; color: #B7AC9C; cursor: pointer; font-size: 16px; padding: 0 2px; line-height: 1; }
  #rc-edpanel .hint { padding: 10px 14px; color: #CCC0AD; line-height: 1.5; border-bottom: 1px solid rgba(255,255,255,.08); }
  #rc-edpanel .hint kbd { font: inherit; color: #F4EEE5; background: rgba(255,255,255,.1); padding: 0 5px; border-radius: 4px; }
  #rc-edpanel .list { max-height: 36vh; overflow: auto; }
  #rc-edpanel .row { display: grid; grid-template-columns: 1fr auto; gap: 8px; padding: 9px 14px; border-bottom: 1px solid rgba(255,255,255,.06); }
  #rc-edpanel .row .tag { font-size: 10.5px; color: #9A8A75; text-transform: uppercase; letter-spacing: .06em; margin-bottom: 3px; }
  #rc-edpanel .row .b { color: #9A8A75; text-decoration: line-through; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
  #rc-edpanel .row .a { color: #F4EEE5; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; margin-top: 2px; }
  #rc-edpanel .row button { align-self: center; background: none; border: 1px solid rgba(255,255,255,.18); color: #CCC0AD; border-radius: 100px; padding: 4px 9px; cursor: pointer; font: inherit; font-size: 11.5px; }
  #rc-edpanel .row button:hover { border-color: #E59B82; color: #E59B82; }
  #rc-edpanel .empty { padding: 16px 14px; color: #9A8A75; line-height: 1.5; }
  #rc-edpanel .ft { display: flex; gap: 8px; padding: 12px 14px; border-top: 1px solid rgba(255,255,255,.1); flex-wrap: wrap; }
  #rc-edpanel .ft button { font: inherit; font-weight: 700; border: none; border-radius: 100px; padding: 9px 13px; cursor: pointer; }
  #rc-edpanel .ft .pri { background: #C2674F; color: #FBF4EE; flex: 1; }
  #rc-edpanel .ft .sec { background: rgba(255,255,255,.08); color: #F4EEE5; }
  #rc-edpanel .ft .danger { background: none; color: #9A8A75; }
  #rc-edpanel .ft .danger.arm { background: #B5634A; color: #fff; }
  #rc-edpanel .status { padding: 0 14px 11px; color: #9A8A75; font-size: 11.5px; }
  #rc-edpanel textarea { display: block; width: calc(100% - 28px); margin: 0 14px 12px; height: 140px; font: 12px/1.4 ui-monospace, Menlo, monospace; color: #2E2823; border-radius: 10px; border: none; padding: 8px; }
  #rc-edpanel textarea[hidden] { display: none; }
  #rc-edpanel.min { width: auto; }
  #rc-edpanel.min .hd { border-bottom: none; padding: 11px 14px; }
  #rc-edpanel.min .hint, #rc-edpanel.min .list, #rc-edpanel.min .ft, #rc-edpanel.min .status, #rc-edpanel.min textarea { display: none; }
  .rc-edtoast { position: fixed; left: 50%; bottom: 84px; transform: translateX(-50%); z-index: 210; background: #2E2823; color: #F4EEE5; padding: 10px 16px; border-radius: 100px; font: 13px 'Hanken Grotesk', system-ui, sans-serif; box-shadow: 0 12px 30px -10px rgba(0,0,0,.4); opacity: 0; transition: opacity .25s; pointer-events: none; }
  .rc-edtoast.show { opacity: 1; }
  @media (max-width: 700px) { #rc-edpanel { right: 10px; bottom: 74px; width: calc(100vw - 20px); } }
  `;
  const style = document.createElement('style'); style.setAttribute('data-ed-ui', ''); style.textContent = css; document.head.appendChild(style);

  const panel = document.createElement('div');
  panel.id = 'rc-edpanel'; panel.setAttribute('data-ed-ui', '');
  const toast = document.createElement('div'); toast.className = 'rc-edtoast'; toast.setAttribute('data-ed-ui', '');
  let toastT = 0;
  function flash(msg) { toast.textContent = msg; toast.classList.add('show'); clearTimeout(toastT); toastT = setTimeout(() => toast.classList.remove('show'), 2200); }

  function renderPanel() {
    const list = Object.values(state.edits).sort((a, b) => b.at - a.at);
    const n = list.length;
    panel.classList.toggle('min', !state.open);
    const rows = list.map(e => `<div class="row"><div><div class="tag">${SCREEN_NAMES[e.screen] || e.screen}</div><div class="b">${escapeHtml(e.beforeText)}</div><div class="a">${escapeHtml(e.afterText)}</div></div><button data-undo="${escapeAttr(e.key)}">撤销</button></div>`).join('');
    panel.innerHTML = `
      <div class="hd"><b>文案修改</b><span class="n">${n ? n + ' 处' : ''}</span>
        <span class="sw ${state.on ? 'on' : ''}" data-sw role="switch" aria-checked="${state.on}"><span>${state.on ? '编辑中' : '浏览'}</span><i></i></span>
        <button class="fold" data-fold title="${state.open ? '收起' : '展开'}">${state.open ? '▾' : '▴'}</button></div>
      <div class="hint">${state.on
        ? '点页面上任何一段文字直接改，<kbd>Enter</kbd> 保存，<kbd>Esc</kbd> 取消。换页请用底部的导航条。'
        : '打开右上角开关进入编辑模式。浏览模式下网页照常使用。'}</div>
      <div class="list">${n ? rows : '<div class="empty">还没有修改。改过的文字会在这里列出，也会在页面上加点状下划线。</div>'}</div>
      <div class="ft"><button class="pri" data-copy ${n ? '' : 'disabled'}>复制修改记录</button><button class="sec" data-dl ${n ? '' : 'disabled'}>下载</button><button class="danger ${state.confirmClear ? 'arm' : ''}" data-clear ${n ? '' : 'disabled'}>${state.confirmClear ? '确定清空？' : '清空'}</button></div>
      <textarea hidden readonly></textarea>
      <div class="status">修改自动保存在这台设备的浏览器里。改完点「复制修改记录」发给我们即可。</div>`;
  }
  const escapeHtml = s => s.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const escapeAttr = s => escapeHtml(s).replace(/'/g, '&#39;');
  panel.addEventListener('click', ev => {
    const t = ev.target.closest('[data-sw],[data-fold],[data-copy],[data-dl],[data-clear],[data-undo]');
    if (!t) return;
    if (t.hasAttribute('data-sw')) setMode(!state.on);
    else if (t.hasAttribute('data-fold')) { state.open = !state.open; renderPanel(); }
    else if (t.hasAttribute('data-copy')) copy();
    else if (t.hasAttribute('data-dl')) download();
    else if (t.hasAttribute('data-clear')) { if (state.confirmClear) clearAll(); else { state.confirmClear = true; renderPanel(); setTimeout(() => { state.confirmClear = false; renderPanel(); }, 3000); } }
    else if (t.hasAttribute('data-undo')) undo(t.getAttribute('data-undo'));
  });

  /* ---------- boot ---------- */
  load();
  document.body.appendChild(panel);
  document.body.appendChild(toast);
  renderPanel();
  mo.observe(document.body, { childList: true, characterData: true, subtree: true });
  applyAll();

  window.rcEditor = {
    setMode, isOn: () => state.on,
    setOpen: open => { state.open = !!open; renderPanel(); },
    getEdits: () => JSON.parse(JSON.stringify(state.edits)),
    undo, clearAll, exportMarkdown, applyAll,
    unitAt, isUnit, norm,
    editing: () => state.editing,
  };
})();
