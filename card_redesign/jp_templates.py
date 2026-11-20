"""New fronts, backs and CSS for the JMdict note type (same card types, same fields)."""

from __future__ import annotations

import copy

try:
    from .cn_templates import HERE, _read, carry_css, writing_notes_html
    from . import fieldnames
except ImportError:
    import fieldnames
    from cn_templates import HERE, _read, carry_css, writing_notes_html  # noqa: F401

NAMES = ["JP → EN", "EN → JP"]
MODES = ["Japanese → meaning", "Meaning → Japanese"]
STROKE_START, STROKE_END = "{{#StrokeOrder}}", "{{/StrokeOrder}}"
KEEP = ("kvg", "disambig", "recognition-alternatives", "deck-recognition", "production-form-hint",
        "qa-answer-cue", "reference-label", "audio-source", "stroke-links")


def stroke_block(afmt: str) -> str:
    """The KanjiVG panel, verbatim, from {{#StrokeOrder}} to {{/StrokeOrder}}."""
    if STROKE_START not in afmt:
        raise ValueError("Kanji stroke-order section not found in the current back template")
    start = afmt.index(STROKE_START)
    end = afmt.index(STROKE_END, start) + len(STROKE_END)
    block = afmt[start:end]
    if "kvg-panel" not in block:
        raise ValueError("The kanji stroke-order section doesn't look as expected")
    return block


def build_jp_templates(model: dict) -> dict:
    tmpls = model.get("tmpls", [])
    if [t["name"] for t in tmpls] != NAMES:
        raise ValueError(f"Unexpected card types: {[t['name'] for t in tmpls]}")
    strokes = stroke_block(tmpls[0]["afmt"])
    fmap = fieldnames.resolve(model, "jp")      # the user's field names (renamed 2026-11-19)
    back = fieldnames.map_template(_read("jp_back.html"), fmap)
    new = copy.deepcopy(model)
    for i, t in enumerate(new["tmpls"]):
        t["qfmt"] = fieldnames.map_template(_read(f"jp_front_{i + 1}.html"), fmap)
        mode = f'<p class="cr-mode">{MODES[i]}</p>'
        t["afmt"] = back.replace("{{MODE}}", mode).replace("{{WRITING}}", writing_notes_html("jp")).replace("{{STROKES}}", strokes)
    new["css"] = _read("base.css") + "\n" + _read("jp.css") + "\n" + carry_css(model.get("css", ""), KEEP)
    return new
