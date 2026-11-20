from html_tree import parse
from common import MARK, SimpleEx, render_examples, words


def test_render_examples_shape():
    exs = [SimpleEx(text='私は<b class="hl">食べる</b>。', translation="I eat.", audio=["[sound:a.mp3]"], key="to eat", lang="ja"),
           SimpleEx(text="食べ物", translation="food", phrase=True, key="food", lang="ja")]
    html = render_examples(exs, ["Tatoeba", "Tatoeba", "Editorial example"])
    top = parse(html).elements()[0]
    assert top.tag == "details" and MARK in top.classes and top.attrs["data-multi"] == "1"
    assert top.find(tag="summary").text_content() == "Examples (2)"
    first, second = top.find_all("ex")
    assert first.find("ex-main").attrs["lang"] == "ja" and first.find("ex-a").text_content() == "[sound:a.mp3]"
    assert first.find("ex-t").text_content() == "I eat." and "ex-phrase" in second.classes
    assert top.find("ex-src") is None                         # sources sit after the dropdown, shown at the bottom
    src = parse(html).elements()[1]
    assert "ex-src" in src.classes and src.text_content() == "Example sources: Tatoeba · Editorial example"


def test_render_nothing_for_no_examples():
    assert render_examples([], ["x"]) == ""


def test_words_cover_kana_and_vietnamese():
    assert {"食", "べ", "る", "ăn", "uống"} <= words("食べる ăn uống")


def test_merge_keeps_both_different_translations():
    from common import merge_examples
    kept, _ = merge_examples([SimpleEx(text="Chào!", translation="Bye!"), SimpleEx(text="chào", translation="Hello!")])
    assert len(kept) == 1 and kept[0].translation == "Bye! · Hello!"


def test_merge_treats_apostrophe_variants_as_same():
    from common import merge_examples
    kept, _ = merge_examples([SimpleEx(text="Nếu…", translation="If I’m free"), SimpleEx(text="Nếu…", translation="If I'm free")])
    assert kept[0].translation == "If I’m free"
    assert words("I’m") == words("I'm")
