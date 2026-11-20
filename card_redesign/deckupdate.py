"""Find, download and describe deck updates from the anki-language-decks releases on GitHub.

No Qt here: the dialog runs these functions in the background and shows the result.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import dataclass, field

try:  # inside Anki this module lives in the package `card_redesign`
    from . import runner, updater
except ImportError:  # tests import it directly
    import runner
    import updater

RELEASES_API = "https://api.github.com/repos/0Duc0/anki-language-decks/releases/latest"
# pack language → Card Redesign language key and label
LANGS = {"vi": ("vn", "Vietnamese"), "ja": ("jp", "Japanese"), "zh": ("cn", "Chinese")}
_ASSET = re.compile(r"^(vietnamese|japanese|chinese)-update-.*\.json(\.gz)?$")
_ASSET_LANG = {"vietnamese": "vi", "japanese": "ja", "chinese": "zh"}
TIMEOUT = 30


class UpdateError(RuntimeError):
    pass


@dataclass
class Available:
    language: str            # vi / ja / zh
    name: str                # file name
    url: str
    size: int
    release: str             # tag
    path: str = ""           # local file once downloaded
    pack: dict | None = None
    plan: updater.Plan | None = None
    deck_id: int = 0
    deck_name: str = ""
    layout_needed: bool = False
    problem: str = ""
    notes: list = field(default_factory=list)

    @property
    def label(self) -> str:
        return LANGS[self.language][1]

    @property
    def has_work(self) -> bool:
        return self.plan is not None and bool(self.plan.to_change or self.plan.new_notes or self.layout_needed)


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "anki-card-redesign", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.read()
    except Exception as error:   # no network, GitHub down, rate limit …
        raise UpdateError(f"Could not reach GitHub ({error}). Check the internet connection and try again.") from error


def latest(api: str = RELEASES_API) -> list[Available]:
    """The update files of the newest release."""
    data = json.loads(_get(api).decode("utf-8"))
    out = []
    for asset in data.get("assets", []):
        m = _ASSET.match(str(asset.get("name", "")))
        if m:
            out.append(Available(_ASSET_LANG[m.group(1)], asset["name"], asset["browser_download_url"],
                                 int(asset.get("size", 0)), str(data.get("tag_name", ""))))
    if not out:
        raise UpdateError("The newest release has no deck updates.")
    return out


def download(item: Available, folder: str) -> str:
    """Save the update file in folder (kept, so it is downloaded only once)."""
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, item.name)
    if not (os.path.exists(path) and (not item.size or os.path.getsize(path) == item.size)):
        data = _get(item.url)
        tmp = path + ".part"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    item.path = path
    return path


def layout_needed(col, lang_key: str) -> bool:
    """True when this language's card layout is not the current one yet."""
    try:
        model = runner.find_model(col, lang_key)
        new = runner._prepare_templates(col, lang_key, model)
    except Exception:
        return False
    return ([(t["qfmt"], t["afmt"]) for t in new["tmpls"]] != [(t["qfmt"], t["afmt"]) for t in model["tmpls"]]
            or new["css"] != model["css"])


def inspect(col, item: Available) -> Available:
    """Load the downloaded file and compare it with the collection (changes nothing)."""
    try:
        item.pack = updater.load_pack(item.path)
        item.plan = updater.plan(col, item.pack)
    except updater.PackError as error:
        item.problem = str(error)
        return item
    item.deck_id = updater.default_deck(col, item.pack, item.plan.model_id)
    item.deck_name = col.decks.name(item.deck_id)
    item.layout_needed = layout_needed(col, LANGS[item.language][0])
    return item


def check(col, folder: str, api: str = RELEASES_API) -> list[Available]:
    """Newest updates for the languages this collection has."""
    found = []
    for item in latest(api):
        try:
            runner.find_model(col, LANGS[item.language][0])
        except Exception:
            continue                  # no deck of this language: don't download it
        download(item, folder)
        inspect(col, item)
        if item.problem.startswith("None of your note types"):
            continue                  # language not in this collection
        found.append(item)
    return found


def describe(item: Available) -> str:
    if item.problem:
        return item.problem
    p = item.plan
    parts = []
    if item.layout_needed:
        parts.append("new card layout")
    if p.to_change:
        parts.append(f"{len(p.to_change):,} notes improved")
    if p.new_notes:
        parts.append(f"{len(p.new_notes):,} new words → {item.deck_name.split('::')[-1]}")
    return " · ".join(parts) if parts else "up to date"


def run(col, item: Available, undo_dir: str, progress=None) -> dict:
    """Layout (if needed) and content of one language. The caller makes Anki's backup first."""
    out = {"language": item.label}
    lang_key = LANGS[item.language][0]
    if item.layout_needed:
        rep = runner.apply(col, lang_key, undo_dir, progress=progress)
        out["layout"] = {"notes_cleaned": rep.notes_changed, "templates_updated": rep.templates_updated}
    fresh = updater.plan(col, item.pack)
    if fresh.to_change or fresh.new_notes:
        result = updater.apply(col, item.pack, fresh, item.deck_id, undo_dir, progress=progress)
        out.update(changed_notes=result.changed_notes, added_notes=result.added_notes, undo_file=result.undo_file)
    return out
