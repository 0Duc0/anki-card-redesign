"""Deck updates (content packs): only untouched fields change, personal fields never, undo works."""
import gzip
import json

import pytest

import updater


@pytest.fixture
def col(tmp_path):
    from anki.collection import Collection
    col = Collection(str(tmp_path / "c.anki2"))
    m = col.models.new("Kaikki/Underthesea/FVDP (VN - EN) ")
    for name in ("Headword (VN)", "Gloss", "Examples", "EntryID", "PersonalNotes"):
        col.models.add_field(m, col.models.new_field(name))
    t = col.models.new_template("Vietnamese → English")
    t["qfmt"], t["afmt"] = "{{Headword (VN)}}", "{{Gloss}}"
    col.models.add_template(m, t)
    col.models.add(m)
    m = col.models.by_name(m["name"])
    for word, gloss in (("thương", "long-handled spear"), ("vốn", "originally"), ("có", "to have")):
        n = col.new_note(m)
        n["Headword (VN)"], n["Gloss"], n["EntryID"] = word, gloss, "id-" + word
        n.guid = "g-" + word
        col.add_note(n, 1)
    yield col
    col.close()


def make_pack(tmp_path, updates, new_notes=()):
    pack = {"format": updater.FORMAT, "version": 1, "language": "vn", "title": "test",
            "notetype_prefixes": ["Kaikki/Underthesea/FVDP (VN"], "key_fields": ["Headword (VN)", "EntryID"],
            "protected_fields": ["PersonalNotes"], "new_note_deck": "", "updates": updates,
            "new_notes": list(new_notes)}
    path = tmp_path / "p.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(pack, f)
    return str(path)


def upd(guid, key, **fields):
    return {"guid": guid, "key": key, "fields": {k: [updater.sha1(old), new] for k, (old, new) in fields.items()}}


def note(col, word):
    return col.get_note(col.find_notes(f'"Headword (VN):{word}"')[0])


def test_changes_only_untouched_fields_and_never_personal(col, tmp_path):
    n = note(col, "vốn")
    n["Gloss"] = "my own gloss"           # the user edited this one
    col.update_notes([n])
    path = make_pack(tmp_path, [
        upd("g-thương", ["thương", "id-thương"], Gloss=("long-handled spear", "to love; to feel sorry for")),
        upd("g-vốn", ["vốn", "id-vốn"], Gloss=("originally", "capital; originally")),
        upd("g-có", ["có", "id-có"], PersonalNotes=("", "should never be written")),
    ])
    pack = updater.load_pack(path)
    p = updater.plan(col, pack)
    assert p.fields_to_change == {"Gloss": 1}
    assert p.kept_your_edit == {"Gloss": 1}
    r = updater.apply(col, pack, p, 1, str(tmp_path / "undo"))
    assert r.changed_fields == 1
    assert note(col, "thương")["Gloss"] == "to love; to feel sorry for"
    assert note(col, "vốn")["Gloss"] == "my own gloss"
    assert note(col, "có")["PersonalNotes"] == ""


def test_falls_back_to_headword_and_entry_id(col, tmp_path):
    path = make_pack(tmp_path, [upd("other-guid", ["thương", "id-thương"], Gloss=("long-handled spear", "to love"))])
    p = updater.plan(col, updater.load_pack(path))
    assert p.matched_by_key == 1 and p.fields_to_change == {"Gloss": 1}


def test_new_notes_once_and_undo(col, tmp_path):
    new = [{"guid": "new-xay-ra", "fields": {"Headword (VN)": "xảy ra", "Gloss": "to happen"}, "tags": ["deck-update"]}]
    path = make_pack(tmp_path, [upd("g-có", ["có", "id-có"], Gloss=("to have", "to have; there is/are"))], new)
    pack = updater.load_pack(path)
    r = updater.apply(col, pack, updater.plan(col, pack), 1, str(tmp_path / "undo"))
    assert r.added_notes == 1 and r.added_cards == 1
    again = updater.plan(col, pack)                # second run: nothing left to do
    assert not again.to_change and not again.new_notes and again.already_done == 1 and again.new_already_there == 1
    n = note(col, "có")
    n["Gloss"] = "edited after the update"
    col.update_notes([n])
    back = updater.restore(col, r.undo_file)
    assert back.removed_notes == 1 and back.kept_newer_edit == 1
    assert note(col, "có")["Gloss"] == "edited after the update"
    assert not col.find_notes('"Headword (VN):xảy ra"')


def test_undo_keeps_studied_new_words(col, tmp_path):
    new = [{"guid": "new-w", "fields": {"Headword (VN)": "miễn là", "Gloss": "as long as"}, "tags": []}]
    pack = updater.load_pack(make_pack(tmp_path, [], new))
    r = updater.apply(col, pack, updater.plan(col, pack), 1, str(tmp_path / "undo"))
    cid = col.find_cards('"Headword (VN):miễn là"')[0]
    col.db.execute("update cards set reps = 3 where id = ?", cid)
    back = updater.restore(col, r.undo_file)
    assert back.kept_studied_notes == 1 and back.removed_notes == 0


def test_rejects_other_files(tmp_path):
    p = tmp_path / "x.json"
    p.write_text('{"format": "something else"}')
    with pytest.raises(updater.PackError):
        updater.load_pack(str(p))
