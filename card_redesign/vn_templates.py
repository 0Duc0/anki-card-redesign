"""New fronts, backs and CSS for the Vietnamese v8 note type (same card types, same fields)."""

from __future__ import annotations

import copy

try:
    from .cn_templates import _read, carry_css
    from . import fieldnames
except ImportError:
    import fieldnames
    from cn_templates import _read, carry_css

NAMES = ["Vietnamese → English", "English → Vietnamese"]
MODES = ["Vietnamese → meaning", "Meaning → Vietnamese"]
KEEP = ("disclosure", "word-class", "senses", "definition", "origin", "sense-example", "translation", "pron",
        "dialect", "side-list", "clue", "gap", ".row", ".label", "sound-item")


def build_vn_templates(model: dict) -> dict:
    tmpls = model.get("tmpls", [])
    if [t["name"] for t in tmpls] != NAMES:
        raise ValueError(f"Unexpected card types: {[t['name'] for t in tmpls]}")
    fmap = fieldnames.resolve(model, "vn")      # the user's field names (renamed 2026-11-19)
    back = fieldnames.map_template(_read("vn_back.html"), fmap)
    new = copy.deepcopy(model)
    for i, t in enumerate(new["tmpls"]):
        t["qfmt"] = fieldnames.map_template(_read(f"vn_front_{i + 1}.html"), fmap)
        t["afmt"] = back.replace("{{MODE}}", f'<p class="cr-mode">{fieldnames.map_template(MODES[i], fmap)}</p>')
    new["css"] = _read("base.css") + "\n" + _read("vn.css") + "\n" + carry_css(model.get("css", ""), KEEP)
    return new
