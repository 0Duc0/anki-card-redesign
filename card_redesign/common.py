"""Helpers shared by the Chinese, Japanese and Vietnamese cleaners (stdlib only)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import escape

try:  # inside Anki this module lives in the package `card_redesign`
    from .html_tree import Node, parse
except ImportError:  # tests and tools import it directly
    from html_tree import Node, parse

MARK = "cr-v1"
MAIN_ALL_UP_TO = 4   # <= 4 glosses: all are main meanings
MAIN_COUNT = 3       # otherwise the first 3 are main
ALSO_COUNT = 6       # up to 6 more under "also"; the rest fold
AUDIO_RE = re.compile(r"\[sound:[^\]]+\]|\[anki:tts[^\]]*\].*?\[/anki:tts\]", re.S)
PUNCT_WS = re.compile(r"[\s　，。！？!?；;：:、,.…「」“”\"'‘’（）()《》『』—\-~～/]+")
WORD_RE = re.compile(r"[A-Za-zÀ-ɏḀ-ỿ']+|[぀-ヿ㐀-鿿豈-﫿\U00020000-\U000323af]")
# words the old layouts used as labels; they may disappear
LABEL_WORDS = {"device", "voice", "source", "license", "sources", "written", "traditional", "info", "sentence",
               "details", "example", "examples", "computer", "human", "english", "meanings", "other", "recordings"}


def is_clean(html: str) -> bool:
    h = html.lstrip()
    return h.startswith(f'<div class="{MARK}') or h.startswith(f'<details class="{MARK}')


def strip_ws(nodes: list[Node]) -> list[Node]:
    return [n for n in nodes if n.tag is not None or n.text.strip()]


def count_audio(html: str) -> int:
    return len(AUDIO_RE.findall(html))


def esc(t: str) -> str:
    return escape(t, quote=False)


def norm(html: str) -> str:
    return PUNCT_WS.sub("", parse(html).text_content()).lower()


def words(*htmls: str) -> set[str]:
    texts = [n.text_content() for h in htmls for n in parse(h).iter() if n.tag is None]
    text = " ".join(AUDIO_RE.sub(" ", t) for t in texts).replace("\u2019", "'").replace("\u2018", "'")
    return {w.lower() for w in WORD_RE.findall(text)}


def glosses(items: list[str]) -> str:
    return "; ".join(f'<span class="g">{i}</span>' for i in items)


def meanings_section(label: str, items: list[str], fold_rest: bool = True) -> str:
    """One <section class="r"> with main meanings, an "also" line and (optionally) a fold."""
    if len(items) <= MAIN_ALL_UP_TO:
        main, also, fold = items, [], []
    else:
        main = items[:MAIN_COUNT]
        also = items[MAIN_COUNT:MAIN_COUNT + ALSO_COUNT] if fold_rest else items[MAIN_COUNT:]
        fold = items[MAIN_COUNT + ALSO_COUNT:] if fold_rest else []
    out = [f'<section class="r"><div class="r-py">{label}</div>' if label else '<section class="r">',
           '<ol class="m-main">' + "".join(f"<li>{i}</li>" for i in main) + "</ol>"]
    if also:
        out.append('<p class="m-also"><span class="m-label">also</span> ' + glosses(also) + "</p>")
    if fold:
        out.append(f'<details class="m-fold"><summary>more meanings ({len(fold)})</summary><p>'
                   + glosses(fold) + "</p></details>")
    out.append("</section>")
    return "".join(out)


@dataclass
class NoteResult:
    changes: dict[str, str] = field(default_factory=dict)
    unrecognised: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    audio_in: int = 0
    audio_out: int = 0
    audio_dropped: int = 0


class Unknown(Exception):
    """Raised by parsers when a field has a shape they don't know; the field is then left alone."""


@dataclass
class SimpleEx:
    """One example for languages without a second script (Japanese, Vietnamese)."""
    text: str                       # inner HTML of the sentence, highlight already applied
    translation: str = ""
    audio: list[str] = field(default_factory=list)
    key: str = ""                   # the sense this example illustrates
    phrase: bool = False            # short phrase, listed after full sentences
    notes: list[str] = field(default_factory=list)
    lang: str = ""


def _same_text(a: str, b: str) -> bool:
    def n(t: str) -> str:
        return PUNCT_WS.sub("", parse(t).text_content().replace("\u2019", "'").replace("\u2018", "'")).lower()
    return n(a) == n(b)


def merge_examples(exs: list[SimpleEx]) -> tuple[list[SimpleEx], int]:
    """Merge duplicates (same normalised text); a human [sound:] recording wins over TTS.
    Returns (kept examples with sentences before phrases, number of audio tokens dropped)."""
    kept: list[SimpleEx] = []
    dropped = 0
    for ex in exs:
        twin = next((k for k in kept if norm(k.text) == norm(ex.text)), None)
        if twin is None:
            kept.append(ex)
            continue
        if ex.translation and _same_text(ex.translation, twin.translation) is False:
            twin.translation = f"{twin.translation} · {ex.translation}" if twin.translation else ex.translation
        twin.key = twin.key or ex.key
        twin.notes += [n for n in ex.notes if n not in twin.notes]
        if "<" not in twin.text and "<" in ex.text:   # keep the version that carries a highlight
            twin.text = ex.text
        has_human = any(a.startswith("[sound:") for a in twin.audio)
        if not has_human and any(a.startswith("[sound:") for a in ex.audio):
            dropped += len(twin.audio)
            twin.audio = ex.audio
        elif not twin.audio:
            twin.audio = ex.audio
        else:
            dropped += len(ex.audio)
    kept.sort(key=lambda e: e.phrase)
    return kept, dropped


def render_examples(exs: list[SimpleEx], sources: list[str]) -> str:
    if not exs:
        return ""
    keys = {e.key for e in exs if e.key}
    out = [f'<details class="{MARK} cr-ex" data-multi="{"1" if len(keys) > 1 else "0"}">'
           f"<summary>Examples ({len(exs)})</summary>"]
    for ex in exs:
        out.append('<div class="ex ex-phrase">' if ex.phrase else '<div class="ex">')
        if ex.key:
            out.append(f'<div class="ex-k">{esc(ex.key)}</div>')
        lang = f' lang="{ex.lang}"' if ex.lang else ""
        out.append(f'<div class="ex-row"><div class="ex-s ex-main"{lang}>{ex.text}</div>')
        if ex.audio:
            out.append(f'<span class="ex-a">{" ".join(ex.audio)}</span>')
        out.append("</div>")
        if ex.translation:
            out.append(f'<div class="ex-sub"><span class="ex-t">{ex.translation}</span></div>')
        for n in ex.notes:
            out.append(f'<div class="ex-n">{n}</div>')
        out.append("</div>")
    out.append("</details>")
    uniq = list(dict.fromkeys(s.strip() for s in sources if s.strip()))
    if uniq:  # after the dropdown: the layout shows it small at the bottom of the card
        out.append('<p class="ex-src">Example sources: ' + " · ".join(uniq) + "</p>")
    return "".join(out)


def loses_something(old: list[str], new: list[str], audio_dropped: int) -> bool:
    """True if a word or an audio token of the old fields is missing from the new ones.
    TTS copies may disappear when duplicates were merged (audio_dropped > 0)."""
    old_tokens, new_tokens = set(AUDIO_RE.findall("".join(old))), set(AUDIO_RE.findall("".join(new)))
    missing_tokens = old_tokens - new_tokens
    if any(t.startswith("[sound:") for t in missing_tokens):
        return True
    if missing_tokens and not audio_dropped:
        return True
    if count_audio("".join(new)) + audio_dropped != count_audio("".join(old)):
        return True
    return bool(words(*old) - words(*new) - LABEL_WORDS)


_LICENCE = re.compile(r"CC[ -]?(?:BY(?:-[A-Z]+)*|0)\s*\d+\.\d+|Public domain|CC0", re.I)


def short_credit(html: str) -> str:
    """"Archive · Speaker: Name · <a>CC BY 2.0 France</a>" -> "Name · CC BY 2.0" (rest kept, hidden)."""
    root = parse(html)
    if root.find("cr-credit") is not None:
        return html
    link = root.find(tag="a")
    pieces = [p.strip() for p in "".join(n.text_content() if n.tag is None else "" for n in root.children).split("·")]
    pieces = [p for p in pieces if p]
    name = next((p.split(":", 1)[1].strip() for p in pieces if p.lower().startswith("speaker:")), pieces[0] if pieces else "")
    rest = [p for p in pieces if p != name]
    out = f'<span class="cr-credit">{name}' if name else '<span class="cr-credit">'
    hidden = list(rest)
    if link is not None:
        full = link.text_content().strip()
        m = _LICENCE.search(full)
        shown = m.group(0) if m else full
        out += (" · " if name else "") + f'<a href="{esc(link.attrs.get("href", ""))}">{esc(shown)}</a>'
        if shown != full:
            hidden.append(full)
    if hidden:
        out += '<span class="cr-hide"> · ' + esc(" · ".join(hidden)) + "</span>"
    return out + "</span>"
