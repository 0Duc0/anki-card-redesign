"""Card Redesign (by Claude) – Tools > Card redesign…

Cleans the contents of the Chinese CC-CEDICT notes into one simple structure and
installs a new card layout (same fields, same card types, so no full sync).
Review history, due dates and your own notes are never touched.
"""

try:
    from aqt import mw
except ImportError:  # imported outside Anki (tests)
    mw = None

if mw is not None:
    from . import ui  # noqa: F401  (adds the Tools menu entry)
