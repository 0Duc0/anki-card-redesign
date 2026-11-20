from conftest import fixture
from html_tree import parse, serialize

G = fixture("gaoxing")


def test_roundtrip_exact():
    for field in ("ExampleSentence", "DefinitionsHTML", "AlternativeHumanAudioHTML", "LookupHTML"):
        s = G[field]
        assert serialize(parse(s).children) == s


def test_find_by_class():
    root = parse(G["ExampleSentence"])
    assert len(root.find_all("ex")) == 2
    assert root.find("v2-sense").text_content() == "gāo xìng · glad; happy; pleased; delighted"


def test_sound_token_is_text():
    assert parse("<b>x</b>[sound:a.mp3]").children[1].text == "[sound:a.mp3]"


def test_void_and_entities_roundtrip():
    s = 'a<br>b &amp; &#20320; <img src="x.png"> <span class="k">c</span>'
    assert serialize(parse(s).children) == s
