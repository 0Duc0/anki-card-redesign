"""Automatic deck updates: where new words go, finding updates in a release, one-button run."""
import gzip
import json

import pytest

import deckupdate
import updater
from test_updater import col, upd  # noqa: F401  (fixture + helper)


def _pack(tmp_path, name, updates, new_notes=(), deck=""):
    pack = {"format": updater.FORMAT, "version": 1, "language": "vi", "title": "test",
            "notetype_prefixes": ["Kaikki/Underthesea/FVDP (VN"], "key_fields": ["Headword (VN)", "EntryID"],
            "protected_fields": ["PersonalNotes"], "new_note_deck": deck, "updates": updates,
            "new_notes": list(new_notes)}
    path = tmp_path / name
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(pack, f)
    return path


def test_new_words_find_the_users_deck_even_if_renamed(col):
    m = col.models.by_name("Kaikki/Underthesea/FVDP (VN - EN) ")
    study = col.decks.id("Language::Tiếng Việt::a. Frieren")
    ref = col.decks.id("Language::Tiếng Việt::Vietnamese Optimized Dictionary::99 Dictionary Reference")
    col.decks.id("Other::99 Dictionary Reference")
    col.db.execute("update cards set did=?", study)          # the user's notes live in a study deck
    pack = {"new_note_deck": "Language::Vietnamese::Vietnamese Optimized Dictionary::99 Dictionary Reference"}
    assert updater.default_deck(col, pack, m["id"]) == ref    # same ending, not the study deck
    assert updater.default_deck(col, {"new_note_deck": ""}, m["id"]) == study
    exact = col.decks.id("Language::Vietnamese::Vietnamese Optimized Dictionary::99 Dictionary Reference")
    assert updater.default_deck(col, pack, m["id"]) == exact


def test_check_finds_downloads_and_runs(col, tmp_path, monkeypatch):
    pack = _pack(tmp_path, "vietnamese-update-2026-11-20.json.gz",
                 [upd("g-thương", ["thương", "id-thương"], Gloss=("long-handled spear", "to love"))])
    other = _pack(tmp_path, "japanese-update-2026-11-20.json.gz", [])
    release = {"tag_name": "2026-11-20", "assets": [
        {"name": pack.name, "browser_download_url": pack.as_uri(), "size": pack.stat().st_size},
        {"name": other.name, "browser_download_url": other.as_uri(), "size": other.stat().st_size},
        {"name": "notes.txt", "browser_download_url": "file:///nope", "size": 1}]}
    api = tmp_path / "release.json"
    api.write_text(json.dumps(release))
    known = {"vn"}
    monkeypatch.setattr(deckupdate.runner, "find_model",
                        lambda col, lang: {} if lang in known else (_ for _ in ()).throw(ValueError("none")))
    monkeypatch.setattr(deckupdate, "layout_needed", lambda col, lang: False)
    items = deckupdate.check(col, str(tmp_path / "dl"), api=api.as_uri())
    assert [i.language for i in items] == ["vi"]                  # no Japanese deck → not downloaded
    assert not (tmp_path / "dl" / other.name).exists()
    item = items[0]
    assert item.has_work and "1 notes improved" in deckupdate.describe(item)
    out = deckupdate.run(col, item, str(tmp_path / "undo"))
    assert out["changed_notes"] == 1
    again = deckupdate.check(col, str(tmp_path / "dl"), api=api.as_uri())
    assert not again[0].has_work and deckupdate.describe(again[0]) == "up to date"


def test_no_network_is_a_clear_message(tmp_path):
    with pytest.raises(deckupdate.UpdateError, match="Could not reach GitHub"):
        deckupdate.latest((tmp_path / "missing.json").as_uri())
