from conftest import vn_fixture
from html_tree import parse
from common import MARK, count_audio
import vn

VN_FIXTURES = ["an", "nha", "no_english_meanings", "only_example", "senses_no_example_field"]


def _res(name):
    f = vn_fixture(name)
    return f, vn.clean_note(f)


def _field(f, res, name):
    return res.changes.get(name, f[name])


def test_an_meanings_main_also():
    f, res = _res("an")
    assert not res.unrecognised
    d = parse(_field(f, res, "DetailsHTML"))
    defs = d.find("cr-defs")
    assert MARK in defs.classes
    main = [li.text_content() for li in defs.find("m-main").find_all(tag="li")]
    assert main[:2] == ["to eat", "to dine; to feast, to attend a feast, to celebrate, to commemorate"]
    assert defs.find("m-also") is not None


def test_other_disclosures_kept_verbatim():
    f, res = _res("an")
    new = _field(f, res, "DetailsHTML")
    old = parse(f["DetailsHTML"])
    ipa = [d for d in old.elements() if d.find(tag="summary").text_content() == "Regional IPA"][0]
    assert ipa.outer_html() in new
    assert parse(new).find("cr-dict").find(tag="summary").text_content() == "Full dictionary entry"
    assert "English meanings" not in new


def test_an_examples_include_sense_phrases():
    f, res = _res("an")
    ex = parse(_field(f, res, "ExampleVietnamese"))
    top = ex.elements()[0]
    assert top.tag == "details" and "open" not in top.attrs
    pairs = {e.find("ex-main").text_content(): e.find("ex-t").text_content() for e in ex.find_all("ex") if e.find("ex-t")}
    assert pairs["ăn thịt"] == "to eat meat; to be carnivorous"
    assert pairs["ăn uống đầy bụng"] == "to eat and drink one's fill"
    first = ex.find_all("ex")[0]
    assert "ex-phrase" not in first.classes                     # full sentences come first
    assert '<b class="hl">ăn</b>' in ex.find("ex-main").inner_html().lower() or "hl" in ex.find("ex-main").inner_html()


def test_example_audio_carried_from_examplesource():
    f, res = _res("an")
    ex = _field(f, res, "ExampleVietnamese")
    assert "[sound:vi_tts_example_9a5b4a4f317f5046942cf7c3.mp3]" in ex
    assert set(res.changes) <= {"DetailsHTML", "ExampleVietnamese"}


def test_no_english_meanings_keeps_only_the_dictionary():
    # the back always shows the English field as the headline, so it is not copied into DetailsHTML
    f, res = _res("no_english_meanings")
    d = parse(_field(f, res, "DetailsHTML"))
    assert d.find("cr-defs").find(tag="li") is None
    assert "Previous dictionary details" in d.find("cr-dict").text_content()


def test_idempotent():
    for name in VN_FIXTURES:
        f, res = _res(name)
        assert not res.unrecognised, name
        assert vn.clean_note(dict(f, **res.changes)).changes == {}, name


def test_unknown_left_alone():
    f = dict(vn_fixture("an"), DetailsHTML="<table><tr><td>mine</td></tr></table>")
    res = vn.clean_note(f)
    assert res.unrecognised and not res.changes
