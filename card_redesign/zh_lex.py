"""Word-level simplified/traditional conversion and pinyin from the CC-CEDICT notes in the collection.

Greedy longest match against the dictionary. Characters with several readings get the first ordinary
(lower-case) reading of the matched word, so pinyin for polyphonic characters can be wrong in places.
"""

from __future__ import annotations

PUNCT = {"。": ".", "，": ",", "？": "?", "！": "!", "：": ":", "；": ";", "、": ",", "“": '"', "”": '"',
         "「": '"', "」": '"', "（": "(", "）": ")", "…": "…", "—": "—", "《": '"', "》": '"', "　": " "}
MAX_WORD = 8


def _first_reading(pinyin: str) -> str:
    parts = [p.strip() for p in pinyin.split("·") if p.strip()]
    for p in parts:
        if p[:1].islower():
            return p
    return parts[0] if parts else ""


class Lexicon:
    def __init__(self) -> None:
        self.s2t: dict[str, str] = {}
        self.t2s: dict[str, str] = {}
        self.py: dict[str, str] = {}   # word (either script) -> syllables joined, e.g. "gāoxìng"
        self.maxlen = 1

    def add(self, simp: str, trad: str, pinyin: str) -> None:
        simp, trad = simp.strip(), trad.strip()
        if not simp or not trad or len(simp) != len(trad) or len(simp) > MAX_WORD:
            return
        reading = "".join(_first_reading(pinyin).split())
        self.s2t.setdefault(simp, trad)
        self.t2s.setdefault(trad, simp)
        if reading:
            self.py.setdefault(simp, reading)
            self.py.setdefault(trad, reading)
        self.maxlen = max(self.maxlen, len(simp))

    def __len__(self) -> int:
        return len(self.py)

    def _segment(self, text: str, table: dict[str, str]) -> list[tuple[str, bool]]:
        out, i = [], 0
        while i < len(text):
            for n in range(min(self.maxlen, len(text) - i), 0, -1):
                w = text[i:i + n]
                if w in table:
                    out.append((w, True))
                    i += n
                    break
            else:
                out.append((text[i], False))
                i += 1
        return out

    def to_simp(self, text: str) -> str:
        return "".join(self.t2s[w] if known else w for w, known in self._segment(text, self.t2s))

    def to_trad(self, text: str) -> str:
        return "".join(self.s2t[w] if known else w for w, known in self._segment(text, self.s2t))

    def detect(self, text: str) -> str:
        if self.to_simp(text) != text:
            return "trad"
        if self.to_trad(text) != text:
            return "simp"
        return "same"

    def pinyin(self, text: str) -> str:
        words: list[str] = []
        for w, known in self._segment(text, self.py):
            if known:
                words.append(self.py[w])
            elif w in PUNCT:
                if words:
                    words[-1] += PUNCT[w]
                else:
                    words.append(PUNCT[w])
            elif w.strip():
                if words and not ("㐀" <= w <= "鿿") and not words[-1][-1:].isspace():
                    words[-1] += w if not w.isalnum() or not words[-1][-1:].isalnum() else " " + w
                else:
                    words.append(w)
        s = " ".join(words)
        return s[:1].upper() + s[1:]
