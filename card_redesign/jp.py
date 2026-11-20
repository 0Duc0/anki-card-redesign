"""Japanese (JMdict note type) field cleaner. Stdlib only, no Anki imports.

Writes MainSenses (main meanings), AllDefinitions (full dictionary entry without examples) and
ExampleJP (every example once, as one closed "Examples" dropdown). Everything else stays untouched.
"""

from __future__ import annotations

import html as _html
import re
from dataclasses import dataclass

try:  # inside Anki this module lives in the package `card_redesign`
    from . import fieldnames, hints as H
    from .common import (AUDIO_RE, MARK, NoteResult, SimpleEx, Unknown, count_audio, is_clean,
                         loses_something, meanings_section, merge_examples, render_examples, strip_ws)
    from .html_tree import Node, parse
except ImportError:  # tests and tools import it directly
    import fieldnames
    import hints as H
    from common import (AUDIO_RE, MARK, NoteResult, SimpleEx, Unknown, count_audio, is_clean,
                        loses_something, meanings_section, merge_examples, render_examples, strip_ws)
    from html_tree import Node, parse

WRITTEN = ("MainSenses", "AllDefinitions", "ExampleJP")
SENTENCE_END = set("。！？!?」")
_NUM = re.compile(r"^\s*\d+\.\s*")
_KANA = re.compile(r"[぀-ゟ]")


def _highlight(html: str, word: str) -> str:
    """Bold the word, or for a conjugated verb/adjective its stem; never touches existing markup."""
    if not word or "<" in html:
        return html
    if word in html:
        return html.replace(word, f'<b class="hl">{word}</b>', 1)
    if len(word) >= 2 and _KANA.match(word[-1]) and word[:-1] in html:
        stem = word[:-1]
        return html.replace(stem, f'<b class="hl">{stem}</b>', 1)
    return html


def _audio(span: Node, sources: list[str], notes: list[str]) -> list[str]:
    for a in span.find_all(tag="a"):
        sources.append(a.outer_html())
    rest = " ".join(n.text for n in span.children if n.tag is None)
    rest = " ".join(AUDIO_RE.sub(" ", rest).replace("Device voice", " ").split()).strip(" ·")
    if rest:
        notes.append(rest)
    return AUDIO_RE.findall(span.inner_html())


def _is_phrase(text_html: str) -> bool:
    t = parse(text_html).text_content().strip()
    return not any(ch in SENTENCE_END for ch in t) and len(t) <= 8


def _example_block(node: Node, key: str, sources: list[str]) -> SimpleEx:
    """div.sense / div.study-meaning-example children: example, example-en, example-audio-v2, example-origin."""
    ex = SimpleEx(text="", key=key, lang="ja")
    for c in strip_ws(node.children):
        cls = c.classes
        if "example" in cls:
            ex.text = c.inner_html().strip()
        elif "example-en" in cls:
            ex.translation = c.inner_html().strip()
        elif "example-audio-v2" in cls:
            ex.audio += _audio(c, sources, ex.notes)
        elif "example-origin" in cls:
            sources.append(c.inner_html().strip())
        else:
            raise Unknown
    return ex


def _v2(node: Node, sources: list[str]) -> SimpleEx:
    ex = SimpleEx(text="", lang="ja")
    for c in strip_ws(node.children):
        cls = c.classes
        if "v2-sense" in cls:
            ex.key = c.text_content().strip()
        elif "v2-translation" in cls:
            ex.translation = c.inner_html().strip()
        elif "example-audio-v2" in cls:
            ex.audio += _audio(c, sources, ex.notes)
        elif "v2-source" in cls:
            sources.append(c.inner_html().strip())
        elif c.tag == "div" and "lang" in c.attrs and not cls:
            ex.text = c.inner_html().strip()
        else:
            raise Unknown
    if not ex.text:
        raise Unknown
    return ex


def _main_senses(html: str, sources: list[str], exs: list[SimpleEx]) -> list[str]:
    titles = []
    for node in strip_ws(parse(html).children):
        if node.tag == "div" and "sense" in node.classes:
            title = node.find("sense-title")
            if title is None:
                raise Unknown
            num = title.find("sense-number")
            t_html = title.inner_html().replace(num.outer_html(), "", 1).strip() if num else title.inner_html().strip()
            titles.append(t_html)
            rest = [c for c in strip_ws(node.children) if c is not title]
            if rest:
                holder = Node("div")
                holder.children = rest
                ex = _example_block(holder, parse(t_html).text_content().strip(), sources)
                if not ex.text:
                    raise Unknown
                exs.append(ex)
        elif node.tag == "section" and "v2-example" in node.classes:
            exs.append(_v2(node, sources))
        else:
            raise Unknown
    if not titles:
        raise Unknown
    return titles


def _line_key(line: Node) -> str:
    t = line.text_content().strip()
    return _NUM.sub("", t)


def _all_definitions(html: str, sources: list[str], exs: list[SimpleEx]) -> str:
    lines: list[str] = []

    def walk(nodes: list[Node]):
        key = ""
        for node in strip_ws(nodes):
            if node.tag == "div" and "study-merged-senses" in node.classes:
                walk(node.children)
            elif node.tag == "div" and not node.classes and "style" in node.attrs:
                lines.append(node.outer_html())
                key = _line_key(node)
            elif node.tag == "div" and "study-meaning-example" in node.classes:
                ex = _example_block(node, key, sources)
                if not ex.text:
                    raise Unknown
                exs.append(ex)
            elif node.tag == "section" and "v2-example" in node.classes:
                exs.append(_v2(node, sources))
            else:
                raise Unknown
    walk(parse(html).children)
    return f'<div class="{MARK} cr-dict">' + "".join(lines) + "</div>" if lines else ""


# --- Meaning → Japanese prompt (card 2) ------------------------------------------------------------
# User 2026-11-19: front = English meaning (+ word type); one closed "Hints" button with the word's
# other meanings, nothing else.

PP_MARK, _END, _plain = H.PP_MARK, H.END, H.plain
_POS = [("expression", "expression"), ("adjectival nouns", "na-adjective"), ("pre-noun adjectival", "pre-noun adjective"),
        ("adjective", "adjective"), ("verb", "verb"), ("adverb", "adverb"), ("interjection", "interjection"),
        ("pronoun", "pronoun"), ("counter", "counter"), ("conjunction", "conjunction"), ("particle", "particle"),
        ("prefix", "prefix"), ("suffix", "suffix"), ("numeric", "number"), ("noun", "noun")]
_DISAMBIG = re.compile(r'<div class="disambig-hint">(.*?)</div>', re.S)
_LABEL = re.compile(r'<span class="disambig-label">.*?</span>\s*', re.S)
_DROP = [re.compile(p, re.S) for p in (
    r'<details class="production-form-hint">.*?</details>',          # Codex form hint
    rf'<div class="{PP_MARK}-not">.*?</div>',                        # earlier version: "Not:" line
    rf'<details class="{PP_MARK}-tip">.*</details>',                 # earlier version: kanji tip
    rf'<details class="{PP_MARK}-hints">.*?</details>')]             # our own button (rebuilt)


class MeaningIndex(H.MeaningIndex):
    """English main meaning -> Japanese words; words with the same reading are one word."""

    def add(self, word: str, reading: str, meaning: str) -> None:  # type: ignore[override]
        super().add(word, meaning, reading)

    def others(self, word: str, reading: str, meaning: str) -> list[str]:  # type: ignore[override]
        return super().others(word, meaning, reading)


def meaning_index(col, model: dict) -> MeaningIndex:
    names = fieldnames.canonical_names(model, "jp")
    i_w, i_r, i_m = names.index("Word"), names.index("Reading"), names.index("MainMeaning")
    idx = MeaningIndex()
    for (flds,) in col.db.all("select flds from notes where mid = ?", model["id"]):
        v = flds.split("\x1f")
        idx.add(v[i_w], v[i_r], v[i_m])
    return idx


def _short_pos(pos: str) -> str:
    first = _plain(pos).split(";")[0].lower()
    return next((short for key, short in _POS if key in first), "")


def production_prompt(fields: dict[str, str], index=None) -> str | None:
    """The new ProductionPrompt, or None to leave the field as it is."""
    old = fields.get("ProductionPrompt", "")
    body = old[: old.index(_END)] if _END in old else old
    if "read-aloud" in body or not body.strip() or f'class="{MARK} {PP_MARK}"' in body:
        meaning = fields.get("MainMeaning", "")
        pos = _short_pos(fields.get("PartOfSpeech", ""))
        base = (f'<div class="{MARK} {PP_MARK}"><div class="{PP_MARK}-en">{_html.escape(_plain(meaning))}'
                + (f' <span class="{PP_MARK}-pos">({pos})</span>' if pos else "") + "</div></div>")
        others = [_plain(m) for m in re.split(r"[;\n]|<br\s*/?>", fields.get("OtherMeanings", "")) if _plain(m)]
        hints = ["Also: " + _html.escape("; ".join(others[:4]))] if others else []
    else:   # a curated (Codex) prompt: text kept, its sense hint moves behind the button
        hints = H.previous_items(body)
        base = body
        for rx in _DROP:
            base = rx.sub("", base)
        hints += [_LABEL.sub("", h).strip() for h in _DISAMBIG.findall(base)]
        base = _DISAMBIG.sub("", base)

    others = index.others(fields.get("Word", ""), fields.get("Reading", ""), fields.get("MainMeaning", "")) if index else []
    if base == body and not hints and not others and _END not in old:
        return None   # curated prompt with nothing to move, remove or add: left as it is
    new = base + H.hints_block(hints, H.not_hint(others) if others else "") + _END
    return None if new == old else new


def clean_note(fields: dict[str, str], ctx=None) -> NoteResult:
    """Meanings/examples cleanup (once) plus the Meaning → Japanese prompt (kept up to date on every run)."""
    res = _clean_meanings(fields)
    prompt = production_prompt(fields, ctx) if "ProductionPrompt" in fields else None
    if prompt is not None:   # independent of the meanings: derived only from Word/Reading/MainMeaning
        res.changes = {**res.changes, "ProductionPrompt": prompt}
    return res


def _clean_meanings(fields: dict[str, str]) -> NoteResult:
    res = NoteResult()
    old = {k: fields.get(k, "") for k in WRITTEN}
    res.audio_in = res.audio_out = sum(count_audio(v) for v in old.values())
    if is_clean(old["MainSenses"]):
        return res
    word = fields.get("Word", "").strip()
    sources: list[str] = []
    exs: list[SimpleEx] = []
    try:
        titles = _main_senses(old["MainSenses"], sources, exs)
        alldefs = _all_definitions(old["AllDefinitions"], sources, exs) if old["AllDefinitions"].strip() else ""
    except Unknown:
        res.unrecognised.append("AllDefinitions" if _known(old["MainSenses"]) else "MainSenses")
        return res
    if old["ExampleJP"].strip():
        exs.append(SimpleEx(text=old["ExampleJP"].strip(), translation=fields.get("ExampleEN", "").strip(), lang="ja"))
    for ex in exs:
        ex.text = _highlight(ex.text, word)
        ex.phrase = _is_phrase(ex.text)
    merged, dropped = merge_examples(exs)
    new = {
        "MainSenses": f'<div class="{MARK} cr-defs" data-readings="1" data-pinyins="1">'
                      + meanings_section("", titles) + "</div>",
        "AllDefinitions": alldefs,
        "ExampleJP": render_examples(merged, sources),
    }
    if loses_something([*old.values(), fields.get("ExampleEN", "")],
                       [*new.values(), fields.get("ExampleEN", "")], dropped):
        res.unrecognised.append("ExampleJP")
        return res
    res.changes = {k: v for k, v in new.items() if v != old[k]}
    res.audio_out = sum(count_audio(v) for v in new.values())
    res.audio_dropped = dropped
    return res


def _known(html: str) -> bool:
    try:
        _main_senses(html, [], [])
        return True
    except Unknown:
        return False


# --- one note per written form (user 2026-11-19) -------------------------------------------------------------
@dataclass
class Merge:
    word: str
    primary: int
    others: list


_RARE = ("usage::rare", "usage::archaic", "usage::obsolete")


def _rank(col, nid: int, f: dict[str, str], tags: str) -> tuple:
    """Higher is better: studied > in a personal deck > not rare/archaic > common > JLPT level > has examples."""
    t = tags.lower()
    studied = bool(col.db.scalar("select count() from cards where nid = ? and (type != 0 or reps > 0)", nid))
    decks = [col.decks.name(d) for d in col.db.list("select distinct did from cards where nid = ?", nid)]
    personal = any("Vocabulary::N" not in d for d in decks) and not all(d == "Default" for d in decks)
    jlpt = {"N5": 5, "N4": 4, "N3": 3, "N2": 2, "N1": 1}.get(f.get("JLPTLevel", "").strip(), 0)
    return (studied, personal, not any(r in t for r in _RARE), "frequency::common" in t, jlpt,
            bool(_plain(f.get("ExampleJP", "")).strip()), -nid)


def plan_merges(col, model: dict) -> list[Merge]:
    names = fieldnames.canonical_names(model, "jp")
    groups: dict[str, list] = {}
    for nid, flds, tags in col.db.all("select id, flds, tags from notes where mid = ?", model["id"]):
        f = dict(zip(names, flds.split("\x1f")))
        w = _plain(f.get("Word", "")).strip()
        if w:
            groups.setdefault(w, []).append((nid, f, tags))
    plan = []
    for w, notes in groups.items():
        if len(notes) < 2:
            continue
        ranked = sorted(notes, key=lambda x: _rank(col, x[0], x[1], x[2]), reverse=True)
        plan.append(Merge(w, ranked[0][0], [n[0] for n in ranked[1:]]))
    return plan


def homographs_html(entries: list[dict[str, str]]) -> str:
    """Other readings of the same written form: reading — main meaning (word class)."""
    items = []
    for f in entries:
        pos = _plain(f.get("WordType", "")).strip()
        items.append(f'<li><span class="h-r" lang="ja">{_html.escape(_plain(f.get("Reading", "")))}</span> '
                     f'<span class="h-g">{_html.escape(_plain(f.get("MainMeaning", "")))}</span>'
                     + (f' <span class="h-p">({_html.escape(pos.lower())})</span>' if pos else "") + "</li>")
    return f'<div class="{MARK} cr-homog"><ul>{"".join(items)}</ul></div>'
