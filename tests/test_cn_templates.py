import pytest

from conftest import make_collection, model_dict
from html_tree import parse
from cn_templates import build_cn_templates


@pytest.fixture
def col(tmp_path):
    col, nids = make_collection(tmp_path / "t.anki2")
    nt = col.models.by_name(model_dict()["name"])
    col.models.update_dict(build_cn_templates(nt))
    yield col, nids
    col.close()


def _cards(col, nid):
    return {c.ord: c for c in col.get_note(nid).cards()}


def test_head_both_scripts(col):
    col, nids = col
    ans = _cards(col, nids["gaoxing"])[0].answer()
    assert 'class="l-sd">simplified' in ans and 'class="l-sd">traditional' in ans
    hz = parse(ans).find_all("cr-hz")
    assert [h.text_content() for h in hz] == ["高兴", "高興"]


def test_head_same_script(col):
    col, nids = col
    ans = _cards(col, nids["ren"])[0].answer()
    assert "same characters in both scripts" in ans               # both forms shown, marked as identical
    assert "<small>Taiwan</small>" in ans and "<small>Mainland</small>" in ans
    assert 1 not in _cards(col, nids["ren"])  # no traditional card


def test_write_both_on_card3_front(col):
    col, nids = col
    assert "Write both: simplified + traditional" in _cards(col, nids["gaoxing"])[2].question()
    assert "Write both" not in _cards(col, nids["ren"])[2].question()


def test_card_scripts(col):
    col, nids = col
    cards = _cards(col, nids["gaoxing"])
    assert "show-simp" in cards[0].answer() and "show-trad" in cards[1].answer() and "show-simp" in cards[2].answer()


def test_no_empty_sections(col):
    col, nids = col
    ans = _cards(col, nids["no_examples"])[0].answer()
    assert "cr-v1 cr-ex" not in ans and "class=\"cr-examples\"" not in ans and "Examples</h2>" not in ans
    assert "Notizen</h2>" not in ans and "Other spellings" not in ans


def test_no_layout_script(col):
    col, nids = col
    for c in _cards(col, nids["gaoxing"]).values():
        assert c.answer().count("<script") <= 3                  # stroke tools + writing notes
        assert "ccStrokeTools" in c.answer()


def test_order_on_back(col):
    col, nids = col
    ans = _cards(col, nids["gaoxing"])[0].answer()
    pos = [ans.index(s) for s in ('class="cr-head"', 'class="cr-meanings"', 'class="cr-examples"', 'class="cr-more"')]
    assert pos == sorted(pos)
    assert ans.index("Wei Gao") > ans.index('class="cr-more"')  # attribution only inside More


def test_wrong_model_raises():
    m = model_dict()
    m["tmpls"] = m["tmpls"][:2]
    with pytest.raises(ValueError):
        build_cn_templates(m)


def test_build_is_stable_on_new_layout():
    once = build_cn_templates(model_dict())
    twice = build_cn_templates(once)
    assert twice["css"] == once["css"]
    assert [t["afmt"] for t in twice["tmpls"]] == [t["afmt"] for t in once["tmpls"]]


def test_head_scripts_stacked_with_label_first(col):
    col, nids = col
    ans = _cards(col, nids["gaoxing"])[0].answer()
    words = parse(ans).find("cr-words")
    assert "cr-stack" in words.classes
    for w in words.find_all("cr-w"):
        tags = [e.tag for e in w.elements()]
        assert tags == ["small", "span"]  # label, then the characters


def test_same_script_word_shows_both_forms(col):
    """User decision 2026-11-19: the answer always shows the Taiwan and the mainland form."""
    col, nids = col
    words = parse(_cards(col, nids["ren"])[0].answer()).find("cr-words")
    assert "cr-stack" in words.classes and "cr-same" in words.classes


def _hz(html):
    return [h.text_content() for h in parse(html).find_all("cr-hz")]


def test_asked_script_on_top_per_card(col):
    col, nids = col
    cards = _cards(col, nids["gaoxing"])
    assert _hz(cards[0].answer()) == ["高兴", "高興"]   # simplified → meaning
    assert _hz(cards[1].answer()) == ["高興", "高兴"]   # traditional → meaning
    assert _hz(cards[2].answer()) == ["高興", "高兴"]   # production: traditional first


def test_front_and_back_share_top_line_and_size(col):
    col, nids = col
    for c in list(_cards(col, nids["gaoxing"]).values())[:2]:
        q, a = parse(c.question()), parse(c.answer())
        assert q.find("cr-mode").text_content() == a.find("cr-mode").text_content()
        assert _hz(c.question()) == _hz(c.answer())[:1]  # same element class, same character


def test_stroke_block_must_be_the_hanzi_writer_block():
    from cn_templates import stroke_block
    bad = '<details class="stroke-tools"><summary>S</summary></details><script>other()</script><script>hanzi()</script>'
    with pytest.raises(ValueError):
        stroke_block(bad)


def test_examples_are_one_open_dropdown(col):
    col, nids = col
    ans = _cards(col, nids["gaoxing"])[0].answer()
    assert "Examples</h2>" not in ans
    det = parse(ans).find("cr-ex")
    assert det.tag == "details" and "open" in det.attrs


def test_layout_open_spellings_alt_audio_in_head_footer_last(tmp_path):
    from conftest import make_collection, visible_text
    col, nids = make_collection(tmp_path / "f.anki2")
    try:
        import runner
        runner.apply(col, "cn", str(tmp_path))
        ortho = [n for n in nids if n == "orthography"][0]
        ans = col.get_note(nids[ortho]).cards()[0].answer()
        root = parse(ans)
        sp = root.find("cr-spell")
        assert sp is not None and not [a for a in [sp.parent] if a.tag == "details"]
        assert "cr-spell" not in ans[ans.index('class="cr-more"'):]          # not inside More
        txt = visible_text(ans)
        assert txt.rstrip().splitlines()[-1].startswith("Sources")               # footer is the last thing
        g = col.get_note(nids["gaoxing"]).cards()[0].answer()
        head = parse(g).find("cr-head")
        assert head.find("cr-alts") is not None or "AlternativeHumanAudioHTML" not in g
    finally:
        col.close()
