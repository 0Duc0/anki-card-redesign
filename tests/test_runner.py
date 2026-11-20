import json

import pytest

from conftest import make_collection, model_dict
import runner


@pytest.fixture
def col(tmp_path):
    col, nids = make_collection(tmp_path / "t.anki2", clean=False)
    # give cards some scheduling to prove it is untouched
    for i, cid in enumerate(col.find_cards("")):
        col.db.execute("update cards set type=2, queue=2, ivl=?, due=?, reps=?, factor=2500 where id=?", 3 + i, 100 + i, 5, cid)
    yield col, nids, tmp_path
    col.close()


def _sched(col):
    return col.db.all("select id, due, ivl, factor, reps, lapses, queue, type, did from cards order by id")


def _note_mods(col):
    return col.db.all("select id, mod, flds from notes order by id")


def test_dry_run_changes_nothing(col):
    col, nids, tmp = col
    before, cmod = _note_mods(col), col.mod
    rep = runner.dry_run(col, "cn")
    assert rep.notes_changed > 0 and rep.notes_total == len(nids)
    assert _note_mods(col) == before and col.mod == cmod
    assert not rep.templates_updated


def test_apply_keeps_schema_and_scheduling(col):
    col, nids, tmp = col
    scm, sched, ncards = col.db.scalar("select scm from col"), _sched(col), col.card_count()
    rep = runner.apply(col, "cn", str(tmp))
    assert rep.notes_changed > 0 and rep.templates_updated
    assert col.db.scalar("select scm from col") == scm
    assert _sched(col) == sched and col.card_count() == ncards


def test_apply_never_touches_personal(col):
    col, nids, tmp = col
    n = col.get_note(nids["gaoxing"])
    n["Notizen"], n["UserMnemonic"] = "<b>mine</b> 高", "tall + happy"
    col.update_note(n)
    runner.apply(col, "cn", str(tmp))
    n = col.get_note(nids["gaoxing"])
    assert (n["Notizen"], n["UserMnemonic"]) == ("<b>mine</b> 高", "tall + happy")
    assert n["DefinitionsHTML"].startswith('<div class="cr-v1')


def test_apply_twice_second_is_noop(col):
    col, nids, tmp = col
    runner.apply(col, "cn", str(tmp))
    rep = runner.apply(col, "cn", str(tmp))
    assert rep.notes_changed == 0 and not rep.templates_updated


def test_restore_templates(col):
    col, nids, tmp = col
    nt = col.models.by_name(model_dict()["name"])
    old = [(t["qfmt"], t["afmt"]) for t in nt["tmpls"]], nt["css"]
    rep = runner.apply(col, "cn", str(tmp))
    runner.restore_templates(col, rep.template_backup)
    nt = col.models.by_name(model_dict()["name"])
    assert ([(t["qfmt"], t["afmt"]) for t in nt["tmpls"]], nt["css"]) == old


def test_unrecognised_field_left_alone_and_reported(col):
    col, nids, tmp = col
    n = col.get_note(nids["ren"])
    n["ExampleSentence"] = "<p>my own example 人</p>"
    col.update_note(n)
    rep = runner.apply(col, "cn", str(tmp))
    assert col.get_note(nids["ren"])["ExampleSentence"] == "<p>my own example 人</p>"
    assert nids["ren"] in rep.unrecognised["ExampleSentence"]


def test_report_is_json(col):
    col, nids, tmp = col
    json.dumps(runner.dry_run(col, "cn").to_dict())


from cn import clean_note


def test_clean_note_flags_lost_text():
    fields = {"Simplified": "好", "Traditional": "好", "DefinitionsHTML": "",
              "ExampleSentence": '<div class="ex"><div class="ex-zh" lang="zh-CN">我<b class="hl">好</b>。</div>'
                                 '<div class="ex-en">first translation</div><div class="ex-en">second one</div></div>',
              "ExampleTranslation": ""}
    res = clean_note(fields)
    assert "ExampleSentence" in res.unrecognised and "ExampleSentence" not in res.changes


def test_clean_note_flags_audio_imbalance():
    fields = {"Simplified": "好", "Traditional": "好", "DefinitionsHTML": "",
              "ExampleSentence": '<section class="v2-example"><div lang="zh-Hans">我好。</div>'
                                 '<div class="v2-translation">fine</div><div class="v2-source">[sound:x.mp3] src</div></section>',
              "ExampleTranslation": ""}
    res = clean_note(fields)
    assert "ExampleSentence" in res.unrecognised


def test_template_problem_stops_before_any_note_changes(col):
    col, nids, tmp = col
    nt = col.models.by_name(model_dict()["name"])
    for t in nt["tmpls"]:
        t["afmt"] = t["afmt"].replace('<details class="stroke-tools"', '<details id="x" class="stroke-tools"')
    col.models.update_dict(nt)
    before = _note_mods(col)
    with pytest.raises(ValueError):
        runner.apply(col, "cn", str(tmp))
    assert _note_mods(col) == before
    rep = runner.dry_run(col, "cn")
    assert rep.template_error and "stroke" in rep.template_error.lower()


def test_card_generation_change_is_refused(col, monkeypatch):
    col, nids, tmp = col
    import cn_templates
    real = cn_templates.build_cn_templates

    def unguarded(model):  # card 2 front without its {{#ScriptDiff}} guard → would create cards
        new = real(model)
        new["tmpls"][1]["qfmt"] = "{{Traditional}}"
        return new
    monkeypatch.setattr(runner.LANGS["cn"], "build_templates", unguarded)
    before, ncards = _note_mods(col), col.card_count()
    with pytest.raises(ValueError, match="card"):
        runner.apply(col, "cn", str(tmp))
    assert _note_mods(col) == before and col.card_count() == ncards


def test_live_v57_model_applies(tmp_path):
    from conftest import FIX, make_collection
    m = json.loads((FIX / "model_v57.json").read_text(encoding="utf-8"))
    col, nids = make_collection(tmp_path / "v57.anki2", model=m, clean=False)
    try:
        n = col.card_count()
        rep = runner.apply(col, "cn", str(tmp_path))
        assert rep.templates_updated and col.card_count() == n
        ans = col.get_note(nids["gaoxing"]).cards()[0].answer()
        assert ans.count("<script") <= 3 and "ccStrokeChars" in ans
    finally:
        col.close()


def test_apply_fills_missing_script_from_collection_dictionary(col):
    col, nids, tmp = col
    runner.apply(col, "cn", str(tmp))
    from html_tree import parse
    ex = parse(col.get_note(nids["gaoxing"])["ExampleSentence"])
    phrase = [e for e in ex.find_all("ex") if "ex-phrase" in e.classes][0]
    assert phrase.find("ex-simp").text_content() == "高兴得了不得"


@pytest.mark.parametrize("lang,names", [("jp", ["taberu", "kimochi", "no_examples", "homograph", "v2_in_alldefs"]),
                                        ("vn", ["an", "nha", "no_english_meanings", "only_example", "senses_no_example_field"])])
def test_other_language_apply_end_to_end(tmp_path, lang, names):
    from conftest import make_lang_collection
    col, nids = make_lang_collection(tmp_path / f"{lang}.anki2", lang, names)
    try:
        scm, sched, n = col.db.scalar("select scm from col"), _sched(col), col.card_count()
        dry = runner.dry_run(col, lang)
        assert dry.template_error is None and dry.card_check.startswith("ok") and not dry.unrecognised_count
        rep = runner.apply(col, lang, str(tmp_path))
        assert rep.notes_changed == len(names) and rep.templates_updated
        assert col.db.scalar("select scm from col") == scm and _sched(col) == sched and col.card_count() == n
        again = runner.apply(col, lang, str(tmp_path))
        assert again.notes_changed == 0 and not again.templates_updated
    finally:
        col.close()


def test_missing_cards_stop_the_run_before_any_write(col):
    col, nids, tmp = col
    cid = [c.id for c in col.get_note(nids["gaoxing"]).cards() if c.ord == 2][0]
    col.remove_cards_and_orphaned_notes([cid]) if hasattr(col, "remove_cards_and_orphaned_notes") else col.db.execute("delete from cards where id=?", cid)
    before, n = _note_mods(col), col.card_count()
    rep = runner.dry_run(col, "cn")
    assert rep.missing_cards == 1
    with pytest.raises(ValueError, match="missing"):
        runner.apply(col, "cn", str(tmp))
    assert _note_mods(col) == before and col.card_count() == n
