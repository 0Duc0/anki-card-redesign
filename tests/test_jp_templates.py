import json

import pytest

from conftest import FIX, make_lang_collection
from html_tree import parse
import jp
from jp_templates import build_jp_templates

NAMES = ["taberu", "kimochi", "no_examples", "homograph"]


@pytest.fixture
def col(tmp_path):
    col, nids = make_lang_collection(tmp_path / "jp.anki2", "jp", NAMES, jp.clean_note)
    nt = [m for m in col.models.all() if m["name"].startswith("JP Vocabulary")][0]
    col.models.update_dict(build_jp_templates(nt))
    yield col, nids
    col.close()


def _cards(col, nid):
    return {c.ord: c for c in col.get_note(nid).cards()}


def test_front_and_back_share_headword(col):
    col, nids = col
    c = _cards(col, nids["taberu"])[0]
    q, a = parse(c.question()), parse(c.answer())
    assert q.find("cr-mode").text_content() == a.find("cr-mode").text_content() == "Japanese → meaning"
    assert [h.text_content() for h in q.find_all("cr-hz")] == ["食べる"] == [h.text_content() for h in a.find_all("cr-hz")]
    assert a.find(tag="ruby") is None or a.find("cr-head").find(tag="ruby") is None


def test_reading_row_and_meanings(col):
    col, nids = col
    a = parse(_cards(col, nids["taberu"])[0].answer())
    assert a.find("cr-kana").text_content() == "たべる"
    assert [li.text_content() for li in a.find("cr-meanings").find_all(tag="li")][:1] == ["to eat"]
    assert "to subsist on" in a.find("m-also").text_content()


def test_examples_closed_dropdown_and_more(col):
    col, nids = col
    ans = _cards(col, nids["taberu"])[0].answer()
    det = parse(ans).find("cr-ex")
    assert det.tag == "details" and "open" not in det.attrs
    head, meanings, foot = (ans.index(s) for s in ('class="cr-head"', 'class="cr-meanings"', 'class="cr-foot"'))
    assert head < meanings < ans.index('class="cr-examples"') < foot and meanings < ans.index('class="cr-dict"') < foot


def test_no_examples_no_empty_section(col):
    col, nids = col
    ans = _cards(col, nids["no_examples"])[0].answer()
    assert 'class="cr-examples"' not in ans


def test_production_front_and_back(col):
    col, nids = col
    c = _cards(col, nids["taberu"])[1]
    assert "Meaning → Japanese" in c.question() and "to eat" in c.question()
    from conftest import visible_text
    assert visible_text(c.answer()).splitlines()[0].strip() == "Meaning → Japanese"


def test_wrong_model_raises():
    m = json.loads((FIX.parent / "jp" / "model.json").read_text(encoding="utf-8"))
    m["tmpls"] = m["tmpls"][:1]
    with pytest.raises(ValueError):
        build_jp_templates(m)


@pytest.fixture
def col2(tmp_path):
    col, nids = make_lang_collection(tmp_path / "jp2.anki2", "jp", ["homograph", "context", "read_aloud", "taberu"], jp.clean_note)
    nt = [m for m in col.models.all() if m["name"].startswith("JP Vocabulary")][0]
    col.models.update_dict(build_jp_templates(nt))
    yield col, nids
    col.close()


def test_front_never_shows_the_answers(col2):
    from conftest import visible_text
    col, nids = col2
    front = visible_text(_cards(col, nids["homograph"])[0].question())
    assert "accomplice" not in front and "guru" not in front


def test_context_caption_on_front_hides_reading_and_not_on_back(col2):
    from conftest import visible_text
    col, nids = col2
    c = _cards(col, nids["context"])[0]
    front, back = visible_text(c.question()), visible_text(c.answer())
    # 2026-11-19: no reading-specific captions on the front any more, only "Recall a meaning."
    assert "Recall a meaning." in front and "Meaning for this reading" not in back


def test_no_read_aloud_production_card(col2):
    """User decision 2026-11-19: only meaning → Japanese and kanji → meaning; never a read-aloud card."""
    from conftest import visible_text
    col, nids = col2
    c = _cards(col, nids["read_aloud"])[1]
    front, back = visible_text(c.question()), visible_text(c.answer())
    assert "Meaning → Japanese" in front and "Read this aloud" not in front
    assert "Read aloud" not in back
    assert visible_text(_cards(col, nids["taberu"])[1].answer()).splitlines()[0].strip() == "Meaning → Japanese"


def test_jp_layout_open_forms_dictionary_fold_footer_last(col):
    from conftest import visible_text
    col, nids = col
    ans = _cards(col, nids["taberu"])[0].answer()
    root = parse(ans)
    forms = root.find("cr-forms")
    assert forms is not None and "喰べる" in forms.text_content()
    assert ans.index('class="cr-meanings"') < ans.index('class="cr-forms"') < ans.index('class="cr-foot"')
    assert ans.index('class="cr-meanings"') < ans.index('class="cr-dict"') < ans.index('class="cr-foot"')
    lines = [l for l in visible_text(ans).splitlines() if l.strip()]
    assert lines[-1].startswith("Sources") and any(l.startswith("N5") for l in lines[-3:])
