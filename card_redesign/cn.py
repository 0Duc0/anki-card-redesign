"""Chinese (CC-CEDICT note type) field cleaners. Stdlib only, no Anki imports."""

from __future__ import annotations

try:  # inside Anki this module lives in the package `card_redesign`
    from .common import (AUDIO_RE, MARK, NoteResult, count_audio, esc as _esc, short_credit, words, LABEL_WORDS,
                         is_clean, meanings_section as _meanings_html, strip_ws as _strip_ws)
    from .html_tree import Node, parse
    from . import fieldnames, hints as H
except ImportError:  # tests and tools import it directly
    from common import (AUDIO_RE, MARK, NoteResult, count_audio, esc as _esc, short_credit, words, LABEL_WORDS,
                        is_clean, meanings_section as _meanings_html, strip_ws as _strip_ws)
    from html_tree import Node, parse
    import fieldnames
    import hints as H


# --------------------------------------------------------------------------- meanings

def _reading_section(sec: Node) -> tuple[str, list[str]] | None:
    """(pinyin, [li inner html]) for a CC-CEDICT `section.reading`, or None if unknown."""
    head = sec.find("reading-head")
    ul = sec.find(tag="ul")
    if head is None or ul is None:
        return None
    for child in _strip_ws(sec.children):
        if child is not head and child is not ul:
            return None
    pinyin = head.find("pinyin")
    py = pinyin.inner_html() if pinyin is not None else head.inner_html()
    items = []
    for li in _strip_ws(ul.children):
        if li.tag != "li":
            return None
        items.append(li.inner_html().strip())
    return py, items


def _capitalised(node: Node) -> bool:
    py = node.find("pinyin") if node.tag == "section" else None
    t = py.text_content().strip() if py is not None else ""
    return bool(t) and t[0].isupper()


def clean_definitions(html: str) -> str | None:
    if is_clean(html):
        return html
    root = parse(html)
    parts: list[str] = []
    readings = 0
    pinyins: set[str] = set()
    nodes = _strip_ws(root.children)
    if not any(n.tag == "div" and "form-head" in n.classes for n in nodes):
        # proper-noun readings (capitalised pinyin, e.g. "Yě: surname Ye") go after the ordinary ones
        nodes.sort(key=lambda n: _capitalised(n))
    for node in nodes:
        if node.tag == "div" and "form-head" in node.classes:
            span = node.find(tag="span")
            if span is None:
                return None
            parts.append(f'<div class="r-form">traditional: <span lang="zh-Hant">{span.inner_html()}</span></div>')
        elif node.tag == "section" and "reading" in node.classes:
            sec = _reading_section(node)
            if sec is None:
                return None
            readings += 1
            pinyins.add(parse(sec[0]).text_content().strip())
            parts.append(_meanings_html(*sec))
        else:
            return None
    if not readings:
        return None
    return f'<div class="{MARK} cr-defs" data-readings="{readings}" data-pinyins="{len(pinyins)}">' + "".join(parts) + "</div>"


# --------------------------------------------------------------------------- examples

import re
from dataclasses import dataclass, field

SENTENCE_END = set("。！？!?；…」”")
_PUNCT_WS = re.compile(r"[\s　，。！？!?；;：:、,.…「」“”\"'‘’（）()《》—-]+")


@dataclass
class CleanedExamples:
    examples: str
    sources: str
    dropped: list[str] = field(default_factory=list)
    audio_in: int = 0
    audio_out: int = 0
    audio_dropped: int = 0


@dataclass
class _Ex:
    simp: str | None = None   # inner html
    trad: str | None = None
    both: str | None = None   # script unknown / identical
    reading: str = ""
    translation: str = ""
    audio: list[str] = field(default_factory=list)
    key: str = ""             # reading this example illustrates (from v2-sense)
    phrase: bool = False      # a short phrase, not a full sentence: listed after sentences
    notes: list[str] = field(default_factory=list)  # audio labels such as "pronunciation may vary"

    def norms(self) -> set[str]:
        return {_norm(h) for h in (self.simp, self.trad, self.both) if h}


def _norm(html: str) -> str:
    return _PUNCT_WS.sub("", parse(html).text_content())


def _highlight(html: str, word: str) -> str:
    if not word or 'class="hl"' in html or "<" in html:
        return html
    return html.replace(word, f'<b class="hl">{word}</b>', 1)


class _Unknown(Exception):
    pass


def _audio_and_credit(span: Node, sources: list[str], notes: list[str] | None = None) -> list[str]:
    raw = span.inner_html()
    for a in span.find_all(tag="a"):
        sources.append(a.outer_html())
    if notes is not None:
        rest = " ".join(n.text for n in span.children if n.tag is None)
        rest = AUDIO_RE.sub(" ", rest).replace("Device voice", " ")
        rest = " ".join(rest.split()).strip(" ·")
        if rest:
            notes.append(rest)
    return AUDIO_RE.findall(raw)


def _from_ex(node: Node, sources: list[str]) -> _Ex:
    ex = _Ex()
    for c in _strip_ws(node.children):
        cls = c.classes
        if "ex-zh" in cls:
            ex.simp = c.inner_html().strip()
        elif "ex-trad" in cls:
            ex.trad = c.inner_html().strip()
        elif "ex-py" in cls:
            ex.reading = c.inner_html().strip()
        elif "ex-en" in cls:
            ex.translation = c.inner_html().strip()
        elif "example-audio-v2" in cls:
            ex.audio += _audio_and_credit(c, sources, ex.notes)
        else:
            raise _Unknown
    if ex.simp is None:
        raise _Unknown
    if ex.trad is None or _norm(ex.trad) == _norm(ex.simp):
        ex.both, ex.simp, ex.trad = ex.simp, None, None
    return ex


def _from_v2(node: Node, sources: list[str]) -> _Ex:
    ex = _Ex()
    main_lang = ""
    main = alt = None
    for c in _strip_ws(node.children):
        cls = c.classes
        if "v2-sense" in cls:
            ex.key = c.text_content().strip()
        elif "v2-alternate" in cls:
            alt = c.inner_html().strip()
        elif "v2-translation" in cls:
            ex.translation = c.inner_html().strip()
        elif "example-audio-v2" in cls:
            ex.audio += _audio_and_credit(c, sources, ex.notes)
        elif "v2-source" in cls:
            sources.append(c.inner_html().strip())
        elif c.tag == "div" and "lang" in c.attrs and not cls:
            main, main_lang = c.inner_html().strip(), c.attrs["lang"]
        else:
            raise _Unknown
    if main is None:
        raise _Unknown
    if main_lang == "zh-Hans":
        ex.simp, ex.trad = main, alt
    elif main_lang == "zh-Hant":
        ex.trad, ex.simp = main, alt
    else:
        ex.both = main
    if ex.simp and not ex.trad:
        ex.both, ex.simp = ex.simp, None
    if ex.trad and not ex.simp:
        ex.both, ex.trad = ex.trad, None
    return ex


def _is_sentence(ex: _Ex) -> bool:
    txt = parse(ex.both or ex.simp or ex.trad or "").text_content().strip()
    return any(ch in SENTENCE_END for ch in txt) or len(txt) > 8


def _ex_html(ex: _Ex, simplified: str, traditional: str, lexicon=None) -> str:
    trad, simp, main = ex.trad, ex.simp, None
    if ex.both is not None:
        script = lexicon.detect(parse(ex.both).text_content()) if lexicon is not None else "unknown"
        if script == "trad":
            trad = ex.both
            simp = _esc(lexicon.to_simp(parse(ex.both).text_content()))
        elif script == "simp":
            simp = ex.both
            trad = _esc(lexicon.to_trad(parse(ex.both).text_content()))
        else:
            main = ex.both
    if main is None and trad is not None and simp is not None and _norm(trad) == _norm(simp):
        main, trad, simp = trad, None, None
    reading = ex.reading
    if not reading and lexicon is not None:
        reading = _esc(lexicon.pinyin(parse(simp or main or trad).text_content()))
    out = ['<div class="ex ex-phrase">' if ex.phrase else '<div class="ex">']
    if ex.key:
        out.append(f'<div class="ex-k">{_esc(ex.key)}</div>')
    if main is not None:
        line = _highlight(_highlight(main, traditional), simplified)
        out.append(f'<div class="ex-row"><div class="ex-s ex-main" lang="zh">{line}</div>')
    else:
        out.append(f'<div class="ex-row"><div class="ex-s ex-main" lang="zh-Hant">{_highlight(trad, traditional)}</div>')
    if ex.audio:
        out.append(f'<span class="ex-a">{" ".join(ex.audio)}</span>')
    out.append("</div>")
    if main is None:
        out.append(f'<div class="ex-sub"><span class="ex-simp" lang="zh-Hans">{_highlight(simp, simplified)}</span></div>')
    if ex.translation:   # English on its own line
        out.append(f'<div class="ex-tl"><span class="ex-t">{ex.translation}</span></div>')
    if reading:   # pinyin only on request
        out.append(f'<details class="ex-pinyin"><summary>pinyin</summary><span class="ex-r">{reading}</span></details>')
    for n in ex.notes:
        out.append(f'<div class="ex-n">{n}</div>')
    out.append("</div>")
    return "".join(out)


def _sources_html(items: list[str]) -> str:
    seen, uniq = set(), []
    for s in items:
        s = s.strip()
        if s and s not in seen:
            seen.add(s)
            uniq.append(s)
    if not uniq:
        return ""
    return f'<div class="{MARK} cr-src"><ul>' + "".join(f"<li>{s}</li>" for s in uniq) + "</ul></div>"


def _old_translation(translation_html: str) -> tuple[str, list[str]] | None:
    """Old format: (<div.example-translation>, <details.example-source>) -> (translation, sources)."""
    root = parse(translation_html)
    tr = root.find("example-translation")
    if tr is None:
        return None
    srcs = []
    det = root.find("example-source")
    if det is not None:
        srcs = [d.inner_html().strip() for d in det.elements() if d.tag != "summary"]
    return tr.inner_html().strip(), srcs


def clean_examples(examples_html: str, translation_html: str,
                   simplified: str, traditional: str, lexicon=None) -> CleanedExamples | None:
    audio_in = count_audio(examples_html)
    if is_clean(examples_html) or (not examples_html.strip() and is_clean(translation_html)):
        return CleanedExamples(examples_html, translation_html, [], audio_in, audio_in, 0)
    if not examples_html.strip() and not translation_html.strip():
        return CleanedExamples("", "", [], 0, 0, 0)

    sources: list[str] = []
    old = _old_translation(translation_html) if "<" in translation_html else None
    if is_clean(translation_html):
        sources += [li.inner_html() for li in parse(translation_html).find_all(tag="li")]
    elif old is None and translation_html.strip():
        sources.append(translation_html.strip())

    root = parse(examples_html)
    exs: list[_Ex] = []
    dropped: list[str] = []
    audio_dropped = 0
    try:
        top = _strip_ws(root.children)
        if old is not None:
            # old format: a plain sentence + audio span; translation lives in the other field
            ex = _Ex(translation=old[0])
            sentence = []
            for c in top:
                if c.tag == "span" and "example-audio-v2" in c.classes:
                    ex.audio += _audio_and_credit(c, sources)
                elif c.tag is None or c.tag == "b":
                    sentence.append(c.outer_html())
                else:
                    raise _Unknown
            ex.both = "".join(sentence).strip()
            if not ex.both:
                raise _Unknown
            sources += old[1]
            exs.append(ex)
        else:
            for c in top:
                if c.tag == "div" and "ex" in c.classes:
                    exs.append(_from_ex(c, sources))
                elif c.tag == "section" and "v2-example" in c.classes:
                    ex = _from_v2(c, sources)
                    twin = next((e for e in exs if e.norms() & ex.norms()), None)
                    if twin is not None:
                        twin.key = twin.key or ex.key
                        twin.notes += [n for n in ex.notes if n not in twin.notes]
                        if not any(a.startswith("[sound:") for a in twin.audio) and \
                                any(a.startswith("[sound:") for a in ex.audio):
                            audio_dropped += len(twin.audio)
                            twin.audio = ex.audio
                        else:
                            audio_dropped += len(ex.audio)
                        continue
                    ex.phrase = not _is_sentence(ex)
                    exs.append(ex)
                else:
                    raise _Unknown
    except _Unknown:
        return None

    exs.sort(key=lambda e: e.phrase)  # stable: sentences first, then phrases
    readings = {e.key.split(" · ", 1)[0].strip() for e in exs if e.key}
    multi = "1" if len(readings) > 1 else "0"   # captions only shown when examples cover several readings
    blocks = [_ex_html(e, simplified, traditional, lexicon) for e in exs]
    html = ""
    if blocks:
        html = (f'<details class="{MARK} cr-ex" data-multi="{multi}" open><summary>Examples ({len(blocks)})</summary>'
                + "".join(blocks) + "</details>")
    return CleanedExamples(html, _sources_html(sources), dropped, audio_in, count_audio(html), audio_dropped)


# --------------------------------------------------------------------------- whole note

PROTECTED = ("Notizen", "UserMnemonic")  # never written


# --- Meaning → Chinese prompt (card 3): English + one closed "Hints" button ---------------------------

def _defs_parts(defs_html: str) -> tuple[list[str], list[str]]:
    """(main meanings, other meanings) from a cleaned DefinitionsHTML."""
    root = parse(defs_html or "")
    main = [li.text_content().strip() for ol in root.find_all("m-main") for li in ol.find_all(tag="li")]
    also = [g.text_content().strip() for p in root.find_all("m-also") for g in p.find_all("g")]
    return [m for m in main if m], [a for a in also if a]


def _prompt_body(prompt: str) -> str:
    body = prompt[: prompt.index(H.END)] if H.END in prompt else prompt
    return H.HINTS_RE.sub("", body)


def prompt_text(fields: dict[str, str]) -> str:
    """The English the front shows (what the "Not:" index compares)."""
    body = _prompt_body(fields.get("MeaningPromptHTML", ""))
    if "read-aloud" in body or not body.strip():
        defs = fields.get("DefinitionsHTML", "")
        main, _ = _defs_parts(clean_definitions(defs) if defs.strip() and not is_clean(defs) else defs)
        return "; ".join(main)
    return H.plain(body)


def _clue(html: str) -> str:
    """RecognitionHintHTML ("1 character" + optional semantic clue) as one line."""
    parts = [n.text_content().strip() if n.tag else n.text.strip() for n in parse(html or "").children]
    return " · ".join(p for p in parts if p)


def word_key(fields: dict[str, str]) -> str:
    return f'{fields.get("Simplified", "").strip()}|{fields.get("Traditional", "").strip()}'


def _show(key: str) -> str:
    s, _, t = key.partition("|")
    return s if not t or t == s else f"{s} / {t}"


def meaning_prompt(fields: dict[str, str], index=None) -> str | None:
    """The new MeaningPromptHTML, or None to leave it. Never shows the Chinese word or its pinyin."""
    old = fields.get("MeaningPromptHTML", "")
    body = _prompt_body(old)
    text = prompt_text(fields)
    if not text:
        return None
    if "read-aloud" in body or not body.strip():
        body = f'<div class="{MARK} {H.PP_MARK}"><div class="{H.PP_MARK}-en">{_esc(text)}</div></div>'
    _, also = _defs_parts(fields.get("DefinitionsHTML", ""))
    items = []
    if also:
        items.append("Also: " + _esc("; ".join(also[:4])))
    clue = _clue(fields.get("RecognitionHintHTML", ""))
    if clue:
        items.append(_esc(clue))
    others = index.others(word_key(fields), text) if index is not None else []
    new = body + H.hints_block(items, H.not_hint(others, _show) if others else "") + H.END
    return None if new == old else new


def meaning_index(col, model: dict):
    names = fieldnames.canonical_names(model, "cn")
    idx = H.MeaningIndex()
    for (flds,) in col.db.all("select flds from notes where mid = ?", model["id"]):
        f = dict(zip(names, flds.split("\x1f")))
        idx.add(word_key(f), prompt_text(f))
    return idx


def clean_note(fields: dict[str, str], lexicon=None) -> NoteResult:
    res = NoteResult()
    d = fields.get("DefinitionsHTML", "")
    if d.strip():
        new = clean_definitions(d)
        if new is None:
            res.unrecognised.append("DefinitionsHTML")
        elif new != d:
            res.changes["DefinitionsHTML"] = new
    ex, tr = fields.get("ExampleSentence", ""), fields.get("ExampleTranslation", "")
    out = clean_examples(ex, tr, fields.get("Simplified", ""), fields.get("Traditional", ""), lexicon)
    res.audio_in = count_audio(ex)
    if out is None:
        res.unrecognised.append("ExampleSentence")
        res.audio_out = res.audio_in
    else:
        res.dropped, res.audio_out, res.audio_dropped = out.dropped, out.audio_out, out.audio_dropped
        if out.examples != ex:
            res.changes["ExampleSentence"] = out.examples
        if out.sources != tr:
            res.changes["ExampleTranslation"] = out.sources
    for f, fn in (("HumanAudioSourceHTML", short_credit), ("AlternativeHumanAudioHTML", clean_alt_audio)):
        old = fields.get(f, "")
        if old.strip():
            new = fn(old)
            if new is None or not (words(old) - LABEL_WORDS <= words(new)) or count_audio(old) != count_audio(new):
                res.unrecognised.append(f)
            elif new != old:
                res.changes[f] = new
    if out is not None and "ExampleSentence" not in res.unrecognised and _loses_something(ex, tr, out, res):
        res.unrecognised.append("ExampleSentence")
        res.changes.pop("ExampleSentence", None)
        res.changes.pop("ExampleTranslation", None)
        res.audio_out, res.audio_dropped = res.audio_in, 0
    if fields.get("ScriptDiff", "") == "form":   # separate Taiwan-form cards were dropped again (user decision)
        res.changes["ScriptDiff"] = ""
    if "MeaningPromptHTML" in fields:   # uses the cleaned definitions of this same run
        prompt = meaning_prompt({**fields, **res.changes}, getattr(lexicon, "meanings", None))
        if prompt is not None:
            res.changes["MeaningPromptHTML"] = prompt
    for p in PROTECTED:
        res.changes.pop(p, None)
    return res


def clean_alt_audio(html: str) -> str | None:
    """Other human recordings -> one compact row: ▶ Name · CC BY … per recording (archive names kept, hidden)."""
    if not html.strip() or 'class="cr-alt' in html:
        return html
    root = parse(html)
    rows = root.find_all("audio-alternative")
    if not rows:
        return None
    out = ['<span class="cr-alts-row">']
    for r in rows:
        label, button = r.find("audio-alternative-label"), r.find("audio-alternative-button")
        if label is None or button is None:
            return None
        pieces = label.inner_html()
        # "Name · Archive · <a>Licence</a>" -> credit with the name first
        out.append(f'<span class="cr-alt">{button.inner_html().strip()}{short_credit(pieces)}</span> ')
    summary = root.find(tag="summary")
    if summary is not None:
        out.append(f'<span class="cr-hide">{summary.inner_html()}</span>')
    return "".join(out) + "</span>"


_WORD_RE = re.compile(r"[A-Za-z\u00C0-\u024F\u1E00-\u1EFF']+|[\u3400-\u9fff\uf900-\ufaff\U00020000-\U000323af]")


def _words(*htmls: str) -> set[str]:
    texts = [n.text_content() for h in htmls for n in parse(h).iter() if n.tag is None]
    text = " ".join(AUDIO_RE.sub(" ", t) for t in texts)
    return {w.lower() for w in _WORD_RE.findall(text)}


def _loses_something(old_ex: str, old_tr: str, out: "CleanedExamples", res: NoteResult) -> bool:
    """True if any word or audio token of the old example fields would be missing afterwards."""
    if out.audio_out != res.audio_in - out.audio_dropped:
        return True
    old_tokens = set(AUDIO_RE.findall(old_ex + old_tr))
    new_tokens = set(AUDIO_RE.findall(out.examples + out.sources))
    if not old_tokens <= new_tokens | _merged_tokens(old_ex, out):
        return True
    missing = _words(old_ex, old_tr) - _words(out.examples, out.sources) - LABEL_WORDS
    return bool(missing)


def _merged_tokens(old_ex: str, out: "CleanedExamples") -> set[str]:
    # TTS copies of merged duplicate sentences are allowed to disappear (their sentence is still there)
    return {t for t in AUDIO_RE.findall(old_ex) if t.startswith("[anki:tts")} if out.audio_dropped else set()
