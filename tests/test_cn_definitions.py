from conftest import fixture
from html_tree import parse
from cn import MARK, clean_definitions


def _defs(name):
    out = clean_definitions(fixture(name)["DefinitionsHTML"])
    assert out is not None
    return parse(out)


def test_gaoxing_main_all_four():
    root = _defs("gaoxing")
    items = [li.text_content() for li in root.find("m-main").find_all(tag="li")]
    assert items == ["happy", "glad", "willing (to do sth)", "in a cheerful mood"]
    assert root.find("m-also") is None
    assert MARK in root.elements()[0].classes


def test_long_entry_splits_3_also_fold():
    src = fixture("long_entry")["DefinitionsHTML"]
    total = src.count("<li>")
    root = _defs("long_entry")
    assert len(root.find("m-main").find_all(tag="li")) == 3
    also = root.find("m-also")
    assert len(also.find_all("g")) == 6
    fold = root.find("m-fold")
    assert len(fold.find_all("g")) == total - 9
    assert fold.find(tag="summary").text_content() == f"more meanings ({total - 9})"


def test_ni_keeps_two_readings_and_forms():
    root = _defs("ni")
    assert root.elements()[0].attrs["data-readings"] == "2"
    forms = [f.find(tag="span").text_content() for f in root.find_all("r-form")]
    assert forms == ["你", "妳"]


def test_le_keeps_each_reading_label():
    root = _defs("le")
    pys = [p.text_content() for p in root.find_all("r-py")]
    assert pys[:2] == ["le", "liǎo"]


def test_idempotent():
    for name in ("gaoxing", "long_entry", "ni", "le"):
        once = clean_definitions(fixture(name)["DefinitionsHTML"])
        assert clean_definitions(once) == once


def test_unknown_returns_none():
    assert clean_definitions("<table><tr><td>x</td></tr></table>") is None


def test_distinct_pinyin_count():
    assert _defs("ni").elements()[0].attrs["data-pinyins"] == "1"   # nǐ, nǐ
    assert int(_defs("le").elements()[0].attrs["data-pinyins"]) >= 2


def test_surname_reading_counts_separately_and_goes_last():
    root = _defs("ye")
    top = root.elements()[0]
    assert top.attrs["data-pinyins"] == "2"            # Yě (surname) and yě are different
    pys = [p.text_content() for p in root.find_all("r-py")]
    assert pys == ["yě", "Yě"]                          # real meanings first, surname reading last
