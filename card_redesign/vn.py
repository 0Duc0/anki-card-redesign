"""Vietnamese (v8 note type) field cleaner. Stdlib only, no Anki imports.

Writes DetailsHTML (main meanings + every other dictionary section, unchanged, in one
"Full dictionary entry" fold) and ExampleVietnamese (every example once, as one closed
"Examples" dropdown). ExampleEnglish and ExampleSource stay untouched and are no longer shown.
"""

from __future__ import annotations

import re

try:  # inside Anki this module lives in the package `card_redesign`
    from .common import (AUDIO_RE, MARK, NoteResult, SimpleEx, Unknown, count_audio, is_clean,
                         loses_something, meanings_section, merge_examples, render_examples, strip_ws)
    from .html_tree import Node, parse
except ImportError:  # tests and tools import it directly
    from common import (AUDIO_RE, MARK, NoteResult, SimpleEx, Unknown, count_audio, is_clean,
                        loses_something, meanings_section, merge_examples, render_examples, strip_ws)
    from html_tree import Node, parse

WRITTEN = ("DetailsHTML", "ExampleVietnamese")
ENGLISH_MEANINGS = "English meanings"
KEY_CHARS = 70


def _highlight(html: str, word: str) -> str:
    if not word or "<" in html:
        return html
    m = re.search(r"(?<![\w])" + re.escape(word) + r"(?![\w])", html, re.I)
    if not m:
        return html
    return html[:m.start()] + f'<b class="hl">{m.group(0)}</b>' + html[m.end():]


def _is_phrase(text_html: str) -> bool:
    t = parse(text_html).text_content().strip()
    return not re.search(r"[.!?…]", t) and len(t.split()) <= 5


def _definition_key(defn: Node) -> str:
    t = " ".join(n.text_content() for n in defn.children if not (n.tag and "usage" in n.classes)).strip()
    return t if len(t) <= KEY_CHARS else t[:KEY_CHARS - 1].rstrip() + "…"


def _english_meanings(det: Node, exs: list[SimpleEx], origins: list[str]) -> list[tuple[str, list[str]]]:
    """[(word class, [definition inner html])] from the "English meanings" disclosure; examples go to exs."""
    groups: list[tuple[str, list[str]]] = []
    label = ""
    for node in strip_ws(det.children):
        if node.tag == "summary":
            continue
        if node.tag == "h3" and "word-class" in node.classes:
            label = node.inner_html().strip()
        elif node.tag == "ol" and "senses" in node.classes:
            items = []
            for li in strip_ws(node.children):
                if li.tag != "li":
                    raise Unknown
                defn = None
                for c in strip_ws(li.children):
                    if c.tag == "div" and "definition" in c.classes:
                        defn = c
                    elif c.tag == "span" and "origin" in c.classes:
                        origins.append(c.inner_html().strip())
                    elif c.tag == "div" and "sense-example" in c.classes:
                        vi, tr = c.find(tag="span"), c.find("translation")
                        if vi is None or "lang" not in vi.attrs:
                            raise Unknown
                        exs.append(SimpleEx(text=vi.inner_html().strip(),
                                            translation=tr.inner_html().strip() if tr is not None else "",
                                            key=_definition_key(defn) if defn is not None else "", lang="vi"))
                    else:
                        raise Unknown
                if defn is None:
                    raise Unknown
                items.append(defn.inner_html().strip())
            groups.append((label, items))
        else:
            raise Unknown
    return groups


def _example_field(fields: dict[str, str], sources: list[str]) -> SimpleEx | None:
    text = fields.get("ExampleVietnamese", "").strip()
    if not text:
        return None
    ex = SimpleEx(text=text, translation=fields.get("ExampleEnglish", "").strip(), lang="vi")
    src = parse(fields.get("ExampleSource", ""))
    ex.audio = AUDIO_RE.findall(fields.get("ExampleSource", ""))
    for a in src.find_all(tag="a"):
        sources.append(a.outer_html())
    rest = " ".join(n.text for n in src.children if n.tag is None)
    rest = " ".join(AUDIO_RE.sub(" ", rest).replace("Computer voice", " ").split()).strip(" ·")
    if rest:
        sources.append(rest)
    return ex


def clean_note(fields: dict[str, str], ctx=None) -> NoteResult:
    res = NoteResult()
    old = {k: fields.get(k, "") for k in WRITTEN}
    # the example's audio lives in ExampleSource and is carried into the examples block
    carried = [fields.get("ExampleEnglish", "")]
    if old["ExampleVietnamese"].strip():
        carried.append(fields.get("ExampleSource", ""))
    res.audio_in = res.audio_out = sum(count_audio(v) for v in [*old.values(), *carried[1:]])
    if is_clean(old["DetailsHTML"]):
        return res
    word = fields.get("Vietnamese", "").strip()
    sources: list[str] = []
    origins: list[str] = []
    exs: list[SimpleEx] = []
    first = _example_field(fields, sources)
    if first is not None:
        exs.append(first)
    groups: list[tuple[str, list[str]]] = []
    others: list[str] = []
    try:
        for node in strip_ws(parse(old["DetailsHTML"]).children):
            summary = node.find(tag="summary") if node.tag == "details" else None
            if summary is None:
                raise Unknown
            if summary.text_content().strip() == ENGLISH_MEANINGS:
                groups += _english_meanings(node, exs, origins)
            else:
                others.append(node.outer_html())
    except Unknown:
        res.unrecognised.append("DetailsHTML")
        return res
    labels = {g[0] for g in groups}
    defs = ""
    if groups:
        defs = (f'<div class="{MARK} cr-defs" data-readings="{len(groups)}" data-pinyins="{len(labels)}">'
                + "".join(meanings_section(lbl, items, fold_rest=False) for lbl, items in groups) + "</div>")
    origin_line = list(dict.fromkeys(origins))
    dict_part = ""
    if others or origin_line:
        dict_part = ('<details class="cr-dict"><summary>Full dictionary entry</summary>' + "".join(others)
                     + (f'<p class="cr-dict-src">Meanings from: {" · ".join(origin_line)}</p>' if origin_line else "")
                     + "</details>")
    for ex in exs:
        ex.text = _highlight(ex.text, word)
        ex.phrase = _is_phrase(ex.text)
    merged, dropped = merge_examples(exs)
    new = {"DetailsHTML": (defs + dict_part) if defs else dict_part,
           "ExampleVietnamese": render_examples(merged, sources)}
    if new["DetailsHTML"] and not new["DetailsHTML"].startswith(f'<div class="{MARK}'):
        new["DetailsHTML"] = f'<div class="{MARK} cr-defs" data-readings="0" data-pinyins="0"></div>' + new["DetailsHTML"]
    if loses_something([*old.values(), *carried], [*new.values(), fields.get("ExampleEnglish", "")], dropped):
        res.unrecognised.append("ExampleVietnamese")
        return res
    res.changes = {k: v for k, v in new.items() if v != old[k]}
    res.audio_out = sum(count_audio(v) for v in new.values())
    res.audio_dropped = dropped
    return res
