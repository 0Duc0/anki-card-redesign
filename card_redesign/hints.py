"""Shared "Hints" button for the Meaning → target-language cards (Japanese and Chinese).

The prompt keeps its text; one closed <details> "Hints" holds the other meanings, clues and a "Not: …"
line listing other words with the same English prompt. The end marker makes re-runs stable.
"""

from __future__ import annotations

import html as _html
import re
from collections import defaultdict

PP_MARK = "cr-prod"
END = f"<!--{PP_MARK}-end-->"
_TAGS = re.compile(r"<[^>]+>")
HINTS_RE = re.compile(rf'<details class="{PP_MARK}-hints">(.*?)</details>', re.S)
HINT_ITEM_RE = re.compile(rf'<div class="{PP_MARK}-hint">(.*?)</div>', re.S)


def plain(html: str) -> str:
    return " ".join(_html.unescape(_TAGS.sub(" ", html or "")).split())


def meaning_key(meaning: str) -> str:
    return plain(meaning).lower()


class MeaningIndex:
    """English prompt -> the words that have it. `group` (e.g. the reading) marks spellings of one word."""

    def __init__(self):
        self._by: dict[str, list[tuple[str, str]]] = defaultdict(list)

    def add(self, key: str, meaning: str, group: str = "") -> None:
        m = meaning_key(meaning)
        if m:
            self._by[m].append((plain(key), plain(group)))

    def others(self, key: str, meaning: str, group: str = "") -> list[str]:
        key, group = plain(key), plain(group)
        out: list[str] = []
        for k, g in self._by.get(meaning_key(meaning), ()):
            if k != key and (not group or g != group) and k not in out:
                out.append(k)
        return out


def not_hint(others: list[str], show=lambda k: k) -> str:
    shown = " · ".join(_html.escape(show(w)) for w in others[:3])
    more = f" +{len(others) - 3} more" if len(others) > 3 else ""
    return f'<div class="{PP_MARK}-hint {PP_MARK}-not">Not: {shown}{more}</div>'


def hints_block(items: list[str], not_line: str = "") -> str:
    items = [i for i in items if plain(i)]
    if not items and not not_line:
        return ""
    body = "".join(f'<div class="{PP_MARK}-hint">{i}</div>' for i in items) + not_line
    return f'<details class="{PP_MARK}-hints"><summary>Hints</summary>{body}</details>'


def previous_items(body: str) -> list[str]:
    """Hint lines (not the "Not:" line) from a prompt we built before."""
    prev = HINTS_RE.search(body)
    return HINT_ITEM_RE.findall(prev.group(1)) if prev else []
