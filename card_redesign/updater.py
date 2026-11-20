"""Deck updates: apply a content pack (new meanings, example sentences, new words) to the notes.

A pack lists, per note, the fields to change together with a fingerprint (SHA-1) of the value
the change was made from. A field is only written while it still has that value, so whatever
you edited yourself stays as it is and is listed in the report. Personal fields are never
written. Review history, due dates, decks and tags of existing cards are never touched.

Every apply writes an undo file (user_files/update-undo-*.json): "Undo last update" puts the old
values back (only where the field still has the pack's value) and removes the words the update
added, unless you have already studied them.

Stdlib + anki only (no aqt), so it can be tested without the GUI.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import time
from dataclasses import asdict, dataclass, field

try:  # inside Anki this module lives in the package `card_redesign`
    from . import fieldnames
except ImportError:  # tests and tools import it directly
    import fieldnames

FORMAT = "anki-language-decks.content-pack"
SUPPORTED_VERSIONS = (1,)
PROTECTED = {"PersonalNotes", "Mnemonic", "Notizen", "UserMnemonic", "Eigene_Merkhilfe"}
BATCH = 500
LANG_OF_PREFIX = (("CC-CEDICT", "cn"), ("JMdict", "jp"), ("JP Vocabulary", "jp"), ("Kaikki/Underthesea", "vn"),
                  ("Vietnamese Optimized", "vn"))
_TAG = re.compile(r"<[^>]+>")


class PackError(ValueError):
    """The file is not a usable pack (or not for this collection); nothing was changed."""


def sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _plain(html: str) -> str:
    return " ".join(_TAG.sub(" ", html or "").split())


def load_pack(path: str) -> dict:
    opener = gzip.open if path.endswith(".gz") else open
    try:
        with opener(path, "rt", encoding="utf-8") as f:
            pack = json.load(f)
    except (OSError, ValueError) as e:
        raise PackError(f"Could not read the update file: {e}") from e
    if not isinstance(pack, dict) or pack.get("format") != FORMAT:
        raise PackError("This file is not a deck update (content pack).")
    if pack.get("version") not in SUPPORTED_VERSIONS:
        raise PackError(f"This deck update needs a newer Card Redesign (pack version {pack.get('version')}).")
    for key in ("notetype_prefixes", "updates", "new_notes"):
        if not isinstance(pack.get(key), list):
            raise PackError(f"The update file is incomplete ({key} missing).")
    return pack


def find_model(col, prefixes: list[str]) -> dict:
    found = [m for m in col.models.all() if any(m["name"].startswith(p) for p in prefixes)]
    if not found:
        raise PackError("None of your note types matches this update (" + ", ".join(prefixes) + ").")
    if len(found) > 1:
        # several copies (e.g. "… +" after an import): take the one with most notes
        found.sort(key=lambda m: -col.models.use_count(m))
    return found[0]


def _field_map(model: dict) -> dict[str, str]:
    """Name used in the pack -> name in this note type (handles the 2026-11-19 field renames both ways)."""
    names = {f["name"] for f in model["flds"]}
    out = {n: n for n in names}
    lang = next((code for prefix, code in LANG_OF_PREFIX if model["name"].startswith(prefix)), None)
    if lang:
        for canon, live in fieldnames.LIVE[lang].items():
            if live in names and canon not in out:
                out[canon] = live
            if canon in names and live not in out:
                out[live] = canon
    return out


@dataclass
class Plan:
    title: str = ""
    language: str = ""
    model_id: int = 0
    model_name: str = ""
    notes_in_pack: int = 0
    matched: int = 0
    matched_by_key: int = 0
    not_found: int = 0
    to_change: dict = field(default_factory=dict)        # nid -> {field: new}
    fields_to_change: dict = field(default_factory=dict)  # field -> count
    kept_your_edit: dict = field(default_factory=dict)    # field -> count (value differs from the pack's "before")
    already_done: int = 0
    unknown_fields: list = field(default_factory=list)
    new_notes: list = field(default_factory=list)         # pack entries still to add
    new_already_there: int = 0
    samples: list = field(default_factory=list)
    hashes: dict = field(default_factory=dict)            # nid -> {field: (old sha1, new sha1, guid)}

    def summary(self) -> dict:
        d = asdict(self)
        for k in ("to_change", "new_notes", "hashes"):
            d.pop(k)
        d["notes_to_change"] = len(self.to_change)
        d["new_notes"] = len(self.new_notes)
        return d


def plan(col, pack: dict, sample: int = 12) -> Plan:
    model = find_model(col, pack["notetype_prefixes"])
    fmap = _field_map(model)
    names = [f["name"] for f in model["flds"]]
    protected = PROTECTED | set(pack.get("protected_fields") or [])
    p = Plan(title=pack.get("title", ""), language=pack.get("language", ""), model_id=model["id"],
             model_name=model["name"], notes_in_pack=len(pack["updates"]))
    rows = col.db.all("select id, guid, flds from notes where mid = ?", model["id"])
    by_guid = {guid: (nid, flds) for nid, guid, flds in rows}
    key_fields = [fmap.get(k) for k in pack.get("key_fields") or []]
    by_key: dict[tuple, tuple] = {}
    if key_fields and all(k in names for k in key_fields):
        idx = [names.index(k) for k in key_fields]
        for nid, guid, flds in rows:
            vals = flds.split("\x1f")
            by_key.setdefault(tuple(_plain(vals[i]) for i in idx), (nid, flds))
    unknown = set()
    for upd in pack["updates"]:
        hit = by_guid.get(upd.get("guid"))
        if hit is None and by_key and upd.get("key"):
            hit = by_key.get(tuple(_plain(k) for k in upd["key"]))
            if hit is not None:
                p.matched_by_key += 1
        if hit is None:
            p.not_found += 1
            continue
        p.matched += 1
        nid, flds = hit
        vals = dict(zip(names, flds.split("\x1f")))
        for fname, (old_hash, new) in upd["fields"].items():
            real = fmap.get(fname)
            if real is None or real not in vals:
                unknown.add(fname)
                continue
            if real in protected or fname in protected:
                continue
            current = vals[real]
            if current == new:
                p.already_done += 1
            elif sha1(current) == old_hash:
                p.to_change.setdefault(nid, {})[real] = new
                p.hashes.setdefault(nid, {})[real] = (old_hash, sha1(new), upd.get("guid"))
                p.fields_to_change[real] = p.fields_to_change.get(real, 0) + 1
                if len(p.samples) < sample:
                    p.samples.append({"note": _plain(flds.split("\x1f")[0])[:40], "field": real,
                                      "before": _plain(current)[:200], "after": _plain(new)[:200]})
            else:
                p.kept_your_edit[real] = p.kept_your_edit.get(real, 0) + 1
    all_guids = {guid for _nid, guid, _f in rows} | set(col.db.list("select guid from notes"))
    for entry in pack["new_notes"]:
        if entry.get("guid") in all_guids:
            p.new_already_there += 1
        else:
            p.new_notes.append(entry)
    p.unknown_fields = sorted(unknown)
    return p


def default_deck(col, pack: dict, model_id: int) -> int:
    """The deck named in the pack if it exists, else the deck holding most cards of the note type."""
    wanted = pack.get("new_note_deck") or ""
    if wanted:
        d = col.decks.by_name(wanted)
        if d:
            return int(d["id"])
    did = col.db.scalar("select c.did from cards c join notes n on n.id = c.nid where n.mid = ? "
                        "group by c.did order by count() desc limit 1", model_id)
    return int(did or 1)


@dataclass
class Result:
    changed_notes: int = 0
    changed_fields: int = 0
    added_notes: int = 0
    added_cards: int = 0
    undo_file: str = ""
    seconds: float = 0.0


def apply(col, pack: dict, p: Plan, deck_id: int, undo_dir: str, progress=None) -> Result:
    """Write the plan. Re-checks every field right before writing (nothing changed since the dry run)."""
    t0 = time.time()
    res = Result()
    model = col.models.get(p.model_id)
    if model is None:
        raise PackError("The note type disappeared since the check. Nothing was changed.")
    if col.decks.get(deck_id, default=False) is None or col.decks.is_filtered(deck_id):
        raise PackError("Choose a normal (not filtered) deck for the new words.")
    undo = {"pack": p.title, "language": p.language, "model_id": p.model_id, "applied": time.strftime("%Y-%m-%d %H:%M:%S"),
            "changed": {}, "added": []}
    os.makedirs(undo_dir, exist_ok=True)
    path = os.path.join(undo_dir, f"update-undo-{p.language}-{time.strftime('%Y%m%d-%H%M%S')}.json")
    nids = list(p.to_change)
    for i in range(0, len(nids), BATCH):
        notes = []
        for nid in nids[i:i + BATCH]:
            note = col.get_note(nid)
            entry = {}
            for fname, new in p.to_change[nid].items():
                old_hash, new_hash, _guid = p.hashes[nid][fname]
                if sha1(note[fname]) != old_hash:   # changed after the dry run: leave it
                    continue
                entry[fname] = [note[fname], new_hash]
                note[fname] = new
            if entry:
                undo["changed"][note.guid] = entry
                notes.append(note)
                res.changed_fields += len(entry)
        if notes:
            col.update_notes(notes)
            res.changed_notes += len(notes)
        if progress:
            progress(min(i + BATCH, len(nids)), len(nids) + len(p.new_notes))
        _write_json(path, undo)                     # written as we go: a crash still leaves a usable undo file
    names = {f["name"] for f in model["flds"]}
    fmap = _field_map(model)
    cards_before = col.card_count()
    existing = set(col.db.list("select guid from notes"))
    for j, entry in enumerate(p.new_notes):
        if entry["guid"] in existing:
            continue
        note = col.new_note(model)
        note.guid = entry["guid"]
        for fname, value in entry["fields"].items():
            real = fmap.get(fname)
            if real in names and real not in PROTECTED:
                note[real] = value
        note.tags = list(entry.get("tags") or [])
        col.add_note(note, deck_id)
        undo["added"].append(entry["guid"])
        res.added_notes += 1
        if progress and j % 200 == 0:
            progress(len(nids) + j, len(nids) + len(p.new_notes))
            _write_json(path, undo)
    res.added_cards = col.card_count() - cards_before
    _write_json(path, undo)
    res.undo_file = path
    res.seconds = round(time.time() - t0, 1)
    return res


def _write_json(path: str, data: dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


@dataclass
class RestoreResult:
    restored_fields: int = 0
    kept_newer_edit: int = 0
    removed_notes: int = 0
    kept_studied_notes: int = 0


def restore(col, undo_file: str) -> RestoreResult:
    with open(undo_file, encoding="utf-8") as f:
        undo = json.load(f)
    out = RestoreResult()
    guids = list(undo.get("changed", {}))
    for i in range(0, len(guids), BATCH):
        chunk = guids[i:i + BATCH]
        marks = ",".join("?" for _ in chunk)
        notes = []
        for nid in col.db.list(f"select id from notes where guid in ({marks})", *chunk):
            note = col.get_note(nid)
            changed = False
            for fname, (old, new_hash) in undo["changed"][note.guid].items():
                if fname in note.keys() and sha1(note[fname]) == new_hash:
                    note[fname] = old
                    changed = True
                    out.restored_fields += 1
                else:
                    out.kept_newer_edit += 1
            if changed:
                notes.append(note)
        if notes:
            col.update_notes(notes)
    added = undo.get("added", [])
    remove = []
    for i in range(0, len(added), BATCH):
        chunk = added[i:i + BATCH]
        marks = ",".join("?" for _ in chunk)
        for nid, studied in col.db.all(
                f"select n.id, max(c.reps) from notes n left join cards c on c.nid = n.id "
                f"where n.guid in ({marks}) group by n.id", *chunk):
            if studied:
                out.kept_studied_notes += 1
            else:
                remove.append(nid)
    for i in range(0, len(remove), BATCH):
        col.remove_notes(remove[i:i + BATCH])
    out.removed_notes = len(remove)
    return out
