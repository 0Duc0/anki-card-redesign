import re

from conftest import fixture
from html_tree import parse
from cn import MARK, clean_examples, count_audio

FIXTURES = ["gaoxing", "de", "ni", "le", "ren", "zhenzuo", "classifiers", "long_entry", "orthography"]


def _clean(name):
    f = fixture(name)
    out = clean_examples(f["ExampleSentence"], f["ExampleTranslation"], f["Simplified"], f["Traditional"])
    assert out is not None, name
    return out


def test_gaoxing_phrase_kept_after_sentences():
    out = _clean("gaoxing")
    root = parse(out.examples)
    assert MARK in root.elements()[0].classes
    exs = root.find_all("ex")
    assert len(exs) == 3
    assert "ex-phrase" in exs[2].classes and "高興得了不得" in exs[2].text_content()
    assert out.dropped == []
    assert "Wiktionary / Kaikki" in out.sources
    assert "Wiktionary via Kaikki (CC BY-SA)" in out.sources
    assert "Device voice" not in out.examples


def test_example_layout_trad_main_simp_small():
    root = parse(_clean("gaoxing").examples)
    first = root.find("ex")
    assert first.find("ex-main").inner_html() == '很<b class="hl">高興</b>認識你。'
    sub = first.find("ex-sub")
    assert sub.find("ex-simp").inner_html() == '很<b class="hl">高兴</b>认识你。'
    assert sub.find("ex-t") is None and sub.find("ex-dot") is None   # English gets its own line
    tl = first.find("ex-tl")
    assert tl.tag == "div" and tl.find("ex-t").text_content() == "Pleased to meet you."
    kids = [c for c in first.elements() if c.tag == "div" or c.tag == "details"]
    order = [next(k for k in ("ex-row", "ex-sub", "ex-tl", "ex-pinyin") if k in c.classes) for c in kids if any(k in c.classes for k in ("ex-row", "ex-sub", "ex-tl", "ex-pinyin"))]
    assert order == ["ex-row", "ex-sub", "ex-tl", "ex-pinyin"]
    assert sub.find("ex-r") is None                       # pinyin only pops up on request
    pin = first.find("ex-pinyin")
    assert pin.tag == "details" and pin.find("ex-r").text_content() == "Hěn gāoxìng rènshi nǐ."
    # one audio token per example, next to the main line
    assert len(first.find_all("ex-a")) == 1 and first.find("ex-a").text_content().startswith("[anki:tts")


def test_de_alternate_gives_both_scripts():
    root = parse(_clean("de").examples)
    ex = [e for e in root.find_all("ex") if "鑰匙" in e.text_content()][0]
    assert ex.find("ex-main").text_content().startswith("這是我的鑰匙。")
    assert ex.find("ex-simp").text_content().startswith("这是我的钥匙。")


def test_de_sense_captions_for_multi_reading():
    root = parse(_clean("de").examples)
    caps = {k.text_content().split(" · ")[0] for k in root.find_all("ex-k")}
    assert {"dí", "dì"} <= caps
    assert root.elements()[0].attrs["data-multi"] == "1"


def test_zhenzuo_old_format():
    out = _clean("zhenzuo")
    root = parse(out.examples)
    exs = root.find_all("ex")
    assert len(exs) == 1
    assert exs[0].find("ex-main") is not None and exs[0].find("ex-simp") is None  # script unknown without a lexicon
    assert exs[0].find("ex-t").text_content() == "The situation is improving, so cheer up!"
    assert "tatoeba.org #263782" in out.sources


def test_all_examples_in_one_dropdown():
    one = ('<div class="ex"><div class="ex-zh" lang="zh-CN">我{i}<b class="hl">好</b>。</div>'
           '<div class="ex-py">wǒ hǎo.</div><div class="ex-en">fine {i}</div></div>')
    out = clean_examples("".join(one.format(i=i) for i in range(5)), "", "好", "好")
    top = parse(out.examples).elements()[0]
    assert top.tag == "details" and MARK in top.classes and "open" in top.attrs   # Chinese examples start open
    assert top.find(tag="summary").text_content() == "Examples (5)"
    assert len(top.find_all("ex")) == 5 and top.find("ex-more") is None


def test_audio_preserved():
    for name in FIXTURES:
        f = fixture(name)
        out = _clean(name)
        assert out.audio_in == count_audio(f["ExampleSentence"])
        assert out.audio_out == count_audio(out.examples)
        assert out.audio_out == out.audio_in - out.audio_dropped, name


def test_human_recording_kept_and_credited():
    src = ('<div class="ex"><div class="ex-zh" lang="zh-CN"><b class="hl">服</b>了你了。</div>'
           '<span class="example-audio-v2"><a href="https://tatoeba.org/en/sentences/show/440087">'
           'Human recording · Tatoeba · GlossaMatik · CC BY-NC 4.0</a> [sound:x.mp3]</span>'
           '<div class="ex-py">Fú le nǐ le.</div><div class="ex-en">You win.</div></div>')
    out = clean_examples(src, "", "服", "服")
    assert "[sound:x.mp3]" in out.examples
    assert "GlossaMatik" not in out.examples and "GlossaMatik" in out.sources


def test_unknown_html_returns_none():
    assert clean_examples("<p>my own note</p>", "", "x", "x") is None


def test_idempotent():
    for name in FIXTURES:
        f = fixture(name)
        out = _clean(name)
        again = clean_examples(out.examples, out.sources, f["Simplified"], f["Traditional"])
        assert (again.examples, again.sources) == (out.examples, out.sources)


def test_empty_stays_empty():
    out = clean_examples("", "", "儌", "儌")
    assert out.examples == "" and out.sources == ""


def test_sentences_come_before_phrases():
    f = fixture("de")
    out = clean_examples(f["ExampleSentence"], f["ExampleTranslation"], f["Simplified"], f["Traditional"])
    kinds = ["ex-phrase" in e.classes for e in parse(out.examples).find_all("ex")]
    assert kinds == sorted(kinds)  # all sentences (False) before phrases (True)


def test_sense_gloss_kept():
    f = fixture("de")
    out = _clean("de")
    caps = [k.text_content() for k in parse(out.examples).find_all("ex-k")]
    assert "dí · indeed in 的确" in caps and "dī · taxi in 的士" in caps


def test_single_reading_sense_kept_but_marked():
    root = parse(_clean("gaoxing").examples)
    top = root.elements()[0]
    assert top.attrs.get("data-multi") == "0"
    assert any("glad; happy" in k.text_content() for k in root.find_all("ex-k"))


def test_key_is_escaped():
    src = ('<section class="v2-example"><div class="v2-sense">a&lt;b · x</div><div lang="zh-Hans">我好。</div>'
           '<div class="v2-translation">fine</div></section>')
    out = clean_examples(src, "", "好", "好")
    assert "a&lt;b" in out.examples


def test_audio_label_kept_as_note():
    src = ('<div class="ex"><div class="ex-zh" lang="zh-CN">你好<b class="hl">吗</b>？</div>'
           '<span class="example-audio-v2">Device voice · pronunciation may vary [anki:tts lang=zh_CN]你好吗？[/anki:tts]</span>'
           '<div class="ex-py">Nǐ hǎo ma?</div><div class="ex-en">How are you?</div></div>')
    out = clean_examples(src, "", "吗", "嗎")
    root = parse(out.examples)
    assert root.find("ex-n").text_content() == "pronunciation may vary"
    assert "Device voice" not in out.examples


def test_merged_mirror_keeps_its_audio_label():
    src = ('<div class="ex"><div class="ex-zh" lang="zh-CN">你好<b class="hl">吗</b>？</div>'
           '<span class="example-audio-v2">Device voice [anki:tts lang=zh_CN]你好吗？[/anki:tts]</span>'
           '<div class="ex-en">How are you?</div></div>'
           '<section class="v2-example"><div class="v2-sense">ma · question particle</div><div lang="zh-Hans">你好吗？</div>'
           '<div class="v2-translation">How are you?</div>'
           '<span class="example-audio-v2">Device voice · pronunciation may vary [anki:tts lang=zh_CN]你好吗？[/anki:tts]</span>'
           '<div class="v2-source">Wiktionary</div></section>')
    out = clean_examples(src, "", "吗", "嗎")
    root = parse(out.examples)
    assert len(root.find_all("ex")) == 1
    assert root.find("ex-n").text_content() == "pronunciation may vary"



def test_missing_script_and_pinyin_filled_from_dictionary():
    from test_zh_lex import _lex
    f = fixture("gaoxing")
    out = clean_examples(f["ExampleSentence"], f["ExampleTranslation"], f["Simplified"], f["Traditional"], lexicon=_lex())
    phrase = [e for e in parse(out.examples).find_all("ex") if "ex-phrase" in e.classes][0]
    assert phrase.find("ex-main").text_content() == "高興得了不得"
    assert phrase.find("ex-simp").text_content() == "高兴得了不得"
    assert phrase.find("ex-r").text_content() == "Gāoxìng dé liǎobudé"
