from conftest import jp_fixture
from html_tree import parse
from common import MARK, count_audio
import jp

JP_FIXTURES = ["taberu", "kimochi", "no_examples", "homograph", "v2_in_alldefs", "example_origin", "three_senses", "style_alldefs"]


def _res(name):
    f = jp_fixture(name)
    return f, jp.clean_note(f)


def _field(f, res, name):
    return res.changes.get(name, f[name])


def test_taberu_meanings_and_examples():
    f, res = _res("taberu")
    assert not res.unrecognised
    defs = parse(_field(f, res, "MainSenses"))
    assert MARK in defs.elements()[0].classes
    assert [li.text_content() for li in defs.find_all(tag="li")] == ["to eat", "to live on (e.g. a salary); to live off"]
    ex = parse(_field(f, res, "ExampleJP"))
    top = ex.elements()[0]
    assert top.tag == "details" and top.attrs["data-multi"] == "1"
    texts = [e.find("ex-main").text_content() for e in ex.find_all("ex")]
    assert texts == ["もっと果物を食べるべきです。", "僕は脚本家で食べていく決心をした。"]
    assert ex.find("ex-t").text_content() == "You should eat more fruit."
    assert '<b class="hl">食べる</b>' in ex.find("ex-main").inner_html()
    assert '<b class="hl">食べ</b>ていく' in ex.find_all("ex-main")[1].inner_html()   # conjugated: stem highlighted


def test_alldefinitions_keep_senses_without_examples():
    f, res = _res("taberu")
    d = parse(_field(f, res, "AllDefinitions"))
    assert MARK in d.elements()[0].classes and "cr-dict" in d.elements()[0].classes
    assert "to live on (e.g. a salary), to live off, to subsist on" in d.text_content()
    assert "果物" not in d.text_content() and d.find("example") is None


def test_kimochi_v2_examples_keep_strong_and_source():
    f, res = _res("kimochi")
    ex = parse(_field(f, res, "ExampleJP"))
    mains = [e.find("ex-main") for e in ex.find_all("ex")]
    assert any("<strong>気持ち</strong>" in m.inner_html() for m in mains)
    assert "Editorial example" in ex.find("ex-src").text_content()


def test_v2_in_alldefinitions_moves_to_examples():
    f, res = _res("v2_in_alldefs")
    ex = _field(f, res, "ExampleJP")
    assert "このスープはあっさりした味で飲みやすい。" in parse(ex).text_content()
    assert "v2-example" not in _field(f, res, "AllDefinitions")


def test_example_origin_becomes_source():
    f, res = _res("example_origin")
    assert "Curated example for this deck" in parse(_field(f, res, "ExampleJP")).find("ex-src").text_content()


def test_no_examples_leaves_examplejp_empty():
    f, res = _res("no_examples")
    assert "ExampleJP" not in res.changes and not res.unrecognised


def test_audio_balanced_everywhere():
    for name in JP_FIXTURES:
        f, res = _res(name)
        written = ("MainSenses", "AllDefinitions", "ExampleJP")
        before = sum(count_audio(f[k]) for k in written)
        after = sum(count_audio(res.changes.get(k, f[k])) for k in written)
        assert after == before - res.audio_dropped, name
        assert not res.unrecognised, name


def test_idempotent():
    for name in JP_FIXTURES:
        f, res = _res(name)
        g = dict(f, **res.changes)
        assert jp.clean_note(g).changes == {}, name


def test_unknown_left_alone():
    f = dict(jp_fixture("taberu"), MainSenses="<table><tr><td>mine</td></tr></table>")
    res = jp.clean_note(f)
    assert "MainSenses" in res.unrecognised and "MainSenses" not in res.changes


def test_never_writes_protected():
    for name in JP_FIXTURES:
        f, res = _res(name)
        assert set(res.changes) <= {"MainSenses", "AllDefinitions", "ExampleJP", "ProductionPrompt"}
