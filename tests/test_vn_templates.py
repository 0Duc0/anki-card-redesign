import json

import pytest

from conftest import FIX, make_lang_collection
from html_tree import parse
import vn
from vn_templates import build_vn_templates

NAMES = ["an", "nha", "no_english_meanings", "senses_no_example_field"]


@pytest.fixture
def col(tmp_path):
    col, nids = make_lang_collection(tmp_path / "vn.anki2", "vn", NAMES, vn.clean_note)
    nt = [m for m in col.models.all() if m["name"].startswith("Vietnamese")][0]
    col.models.update_dict(build_vn_templates(nt))
    yield col, nids
    col.close()


def _cards(col, nid):
    return {c.ord: c for c in col.get_note(nid).cards()}


def test_front_and_back_share_headword(col):
    col, nids = col
    c = _cards(col, nids["an"])[0]
    q, a = parse(c.question()), parse(c.answer())
    assert q.find("cr-mode").text_content() == a.find("cr-mode").text_content() == "Vietnamese → meaning"
    assert [h.text_content() for h in q.find_all("cr-hz")] == ["ăn"] == [h.text_content() for h in a.find_all("cr-hz")]


def test_order_meanings_examples_more(col):
    col, nids = col
    ans = _cards(col, nids["an"])[0].answer()
    pos = [ans.index(s) for s in ('class="cr-head"', 'class="cr-meanings"', 'class="cr-examples"', 'class="cr-foot"')]
    assert pos == sorted(pos)
    det = parse(ans).find("cr-ex")
    assert det.tag == "details" and "open" not in det.attrs
    assert parse(ans).find("cr-dict") is not None


def test_production_modes(col):
    col, nids = col
    c = _cards(col, nids["an"])[1]
    assert "Meaning → Vietnamese" in c.question() and "cr-prod-hints" in c.question()
    assert parse(c.answer()).find("cr-mode").text_content() == "Meaning → Vietnamese"


def test_wrong_model_raises():
    m = json.loads((FIX.parent / "vn" / "model.json").read_text(encoding="utf-8"))
    m["tmpls"] = m["tmpls"][:1]
    with pytest.raises(ValueError):
        build_vn_templates(m)


def test_english_is_always_the_headline(col):
    from conftest import visible_text
    col, nids = col
    for name in ("an", "no_english_meanings"):
        note = col.get_note(nids[name])
        back = visible_text(note.cards()[0].answer())
        lines = [l.strip() for l in back.splitlines() if l.strip()]
        i = lines.index(parse(note["English"]).text_content().strip())
        assert i < lines.index("EXAMPLES (" + back.split("EXAMPLES (")[1].split(")")[0] + ")") if "EXAMPLES (" in back else True
        assert back.count(parse(note["English"]).text_content().strip()) >= 1
    gl = parse(col.get_note(nids["an"]).cards()[0].answer()).find("cr-gloss")
    assert gl is not None and gl.text_content() == "to eat"


def test_vn_meanings_fully_open_alt_audio_in_head_footer_last(col):
    from conftest import visible_text
    col, nids = col
    ans = _cards(col, nids["an"])[0].answer()
    root = parse(ans)
    assert root.find("m-fold") is None                                 # no "more meanings" fold
    assert root.find("cr-head").find("cr-alts") is not None or "HumanAudioAlternativesHTML" not in ans
    lines = [l for l in visible_text(ans).splitlines() if l.strip()]
    assert lines[-1].startswith("Sources")
