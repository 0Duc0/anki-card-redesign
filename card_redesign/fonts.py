"""Learning fonts shipped with the add-on and copied into the collection's media folder.

Fusion Kai T / G / J follow the Taiwan (MOE), mainland (GB) and Japanese character standards in the same
pen-written style; Be Vietnam Pro is made for Vietnamese diacritics. All are SIL OFL 1.1 (see OFL-*.txt).
File names start with "_" so Anki keeps them (Check Media) and syncs them to other devices.
"""

from __future__ import annotations

import os

DIR = os.path.join(os.path.dirname(__file__), "fonts")
FILES = {
    "cn": ["_cr_FusionKaiT.woff2", "_cr_FusionKaiG.woff2"],
    "jp": ["_cr_FusionKaiJ.woff2"],
    "vn": ["_cr_BeVietnamPro-latin-400.woff2", "_cr_BeVietnamPro-latin-600.woff2",
           "_cr_BeVietnamPro-vietnamese-400.woff2", "_cr_BeVietnamPro-vietnamese-600.woff2"],
}


def install(col, lang: str) -> list[str]:
    """Copy this language's font files into the media folder; returns the files actually written."""
    media = col.media.dir()
    written = []
    for name in FILES[lang]:
        with open(os.path.join(DIR, name), "rb") as f:
            data = f.read()
        dest = os.path.join(media, name)
        if os.path.exists(dest):
            with open(dest, "rb") as f:
                if f.read() == data:
                    continue
        with open(dest, "wb") as f:
            f.write(data)
        written.append(name)
    return written
