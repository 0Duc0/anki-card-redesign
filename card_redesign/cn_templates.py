"""New fronts, backs and CSS for the CC-CEDICT note type (same card types, same fields)."""

from __future__ import annotations

import copy
import os
import re

try:
    from . import fieldnames
except ImportError:
    import fieldnames

HERE = os.path.join(os.path.dirname(__file__), "templates")
NAMES = ["1 Simplified → Meaning", "2 Traditional → Meaning", "3 Meaning → Hanzi"]
SCRIPTS = ["show-simp", "show-trad", "show-simp"]
# which script sits on top of the back: the one the front asked about (production: traditional first)
ORDERS = [("simp", "trad"), ("trad", "simp"), ("trad", "simp")]
MODES = [
    '{{#ScriptDiff}}<span class="l-sd">Simplified</span><span class="l-form">Mainland form</span>{{/ScriptDiff}}'
    "{{^ScriptDiff}}Chinese{{/ScriptDiff}} → meaning",
    '<span class="l-sd">Traditional</span><span class="l-form">Taiwan form</span> → meaning',
    "Meaning → Chinese",
]
ROW = {
    "simp": '<div class="cr-w"><small><span class="l-sd">simplified</span><span class="l-form">mainland form</span></small>'
            '<span class="cr-hz" lang="zh-Hans">{{Simplified}}</span></div>',
    "trad": '<div class="cr-w"><small><span class="l-sd">traditional</span><span class="l-form">Taiwan form</span></small>'
            '<span class="cr-hz" lang="zh-Hant">{{Traditional}}</span></div>',
}
# same characters in both scripts: the back shows both standards, Taiwan (front form) first (user 2026-11-19)
SAME = ('{{^ScriptDiff}}<div class="cr-words cr-stack cr-same">'
        '<div class="cr-w"><small>Taiwan</small><span class="cr-hz" lang="zh-Hant">{{Simplified}}</span></div>'
        '<div class="cr-w"><small>Mainland</small><span class="cr-hz" lang="zh-Hans">{{Simplified}}</span></div>'
        '<p class="cr-same-note">same characters in both scripts</p></div>{{/ScriptDiff}}')


def words_html(order: tuple[str, str]) -> str:
    rows = "\n      ".join(ROW[k] for k in order)
    return (f'    {{{{#ScriptDiff}}}}<div class="cr-words cr-stack">\n      {rows}\n    </div>{{{{/ScriptDiff}}}}\n'
            f"    {SAME}\n")
STROKE_START = '<details class="stroke-tools"'
# old CSS rules still needed by field content and the stroke-order tool
KEEP_CSS = ("stroke", "mini-badge", "hidden-source", "info-box", "warning-box", "variant-", "merged-forms",
            "inline-pinyin", "script-variants", "read-aloud", "practice-word", "semantic-clue",
            "audio-alternative", "tool-link", "badge", "muted", "pinyin-num")


def _read(name: str) -> str:
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read()


def stroke_block(afmt: str) -> str:
    """The Hanzi Writer section, verbatim: from <details class="stroke-tools" through its </script>."""
    if STROKE_START not in afmt:
        raise ValueError("Stroke-order section not found in the current back template")
    start = afmt.index(STROKE_START)
    end = afmt.index("</script>", start) + len("</script>")
    block = afmt[start:end]
    if block.count("<script") != 1 or not ("ccStrokeChars" in block and "hanzi-writer" in block):
        raise ValueError("The stroke-order section doesn't have the expected Hanzi Writer script")
    return block


def _rules(css: str):
    """Top-level CSS rules as (selector, full text); @media blocks come back whole."""
    i, n = 0, len(css)
    while i < n:
        j = css.find("{", i)
        if j < 0:
            return
        sel = css[i:j]
        depth, k = 1, j + 1
        while k < n and depth:
            depth += {"{": 1, "}": -1}.get(css[k], 0)
            k += 1
        yield re.sub(r"/\*.*?\*/", "", sel, flags=re.S).strip(), css[i:k].strip()
        i = k


KEPT_MARK = "/* kept from the previous layout: stroke order, spellings, badges */"


def carry_css(old_css: str, keep: tuple[str, ...] = KEEP_CSS) -> str:
    if KEPT_MARK in old_css:  # already redesigned: keep the block we carried last time
        return old_css[old_css.index(KEPT_MARK):]
    kept = [text for sel, text in _rules(old_css)
            if not sel.startswith(".card") and any(key in (text if sel.startswith("@") else sel) for key in keep)]
    return KEPT_MARK + "\n" + "\n".join(kept)


def writing_notes_html(lang: str) -> str:
    """Closed "Writing note" box: documented differences (print vs handwriting, Taiwan vs mainland) and,
    for Chinese, stroke counts where Taiwan and mainland differ."""
    import json
    notes = [n for n in json.loads(_read("writing_notes.json")) if n["lang"] == lang]
    strokes = json.loads(_read("stroke_counts.json")) if lang == "cn" else {}
    return (_read("writing_notes.html").replace("%NOTES%", json.dumps(notes, ensure_ascii=False))
            .replace("%STROKES%", json.dumps(strokes, ensure_ascii=False, separators=(",", ":")))
            .replace("%LANG%", lang))


def build_cn_templates(model: dict) -> dict:
    tmpls = model.get("tmpls", [])
    if [t["name"] for t in tmpls] != NAMES:
        raise ValueError(f"Unexpected card types: {[t['name'] for t in tmpls]}")
    strokes = stroke_block(tmpls[0]["afmt"])
    fmap = fieldnames.resolve(model, "cn")      # the user's field names (renamed 2026-11-19)
    m = lambda text: fieldnames.map_template(text, fmap)  # noqa: E731
    back = m(_read("cn_back.html")).replace("%BIG5%", _read("big5_common.txt").strip())
    new = copy.deepcopy(model)
    for i, t in enumerate(new["tmpls"]):
        t["qfmt"] = m(_read(f"cn_front_{i + 1}.html"))
        t["afmt"] = (back.replace("{{SCRIPT}}", SCRIPTS[i])
                     .replace("{{MODE}}", f'<p class="cr-mode">{m(MODES[i])}</p>').replace("{{WORDS}}", m(words_html(ORDERS[i])))
                     .replace("{{FORMDIFF}}", writing_notes_html("cn")).replace("{{STROKES}}", strokes))
        t["bqfmt"] = ""
        t["bafmt"] = ""
    new["css"] = _read("base.css") + "\n" + _read("cn.css") + "\n" + carry_css(model.get("css", ""))
    return new
