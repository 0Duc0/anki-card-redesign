from html_tree import parse
from common import short_credit, words, count_audio
from cn import clean_alt_audio

SRC = 'Shtooka Chinese words (HSK 1) · Speaker: Wei Gao · <a href="https://creativecommons.org/licenses/by/2.0/fr/">CC BY 2.0 France</a>'
ALT = ('<details class="audio-alternatives"><summary>Other human recordings (2)</summary>'
       '<div class="audio-alternative"><div class="audio-alternative-label">Yue Tan · Shtooka / University of Caen Mandarin words · '
       '<a href="https://creativecommons.org/licenses/by-sa/3.0/us/">CC BY-SA 3.0 US</a></div>'
       '<div class="audio-alternative-button">[sound:a.flac]</div></div>'
       '<div class="audio-alternative"><div class="audio-alternative-label">Congcong · Shtooka Mandarin vocabulary · '
       '<a href="https://creativecommons.org/licenses/by/3.0/us/">CC BY 3.0 US</a></div>'
       '<div class="audio-alternative-button">[sound:b.flac]</div></div></details>')


def _visible(html):
    root = parse(html)
    for n in root.find_all("cr-hide"):
        n.children = []
    return root.text_content()


def test_short_audio_credit_keeps_everything_but_shows_name_and_licence():
    out = short_credit(SRC)
    assert _visible(out) == "Wei Gao · CC BY 2.0"
    assert parse(out).find(tag="a").attrs["href"] == "https://creativecommons.org/licenses/by/2.0/fr/"
    assert words(SRC) <= words(out)            # nothing lost, the rest is only hidden


def test_alternative_recordings_become_buttons_with_short_credits():
    out = clean_alt_audio(ALT)
    assert count_audio(out) == 2
    assert _visible(out).replace("[sound:a.flac]", "").replace("[sound:b.flac]", "").split() == \
        "Yue Tan · CC BY-SA 3.0 Congcong · CC BY 3.0".split()
    assert words(ALT) - {"other", "human", "recordings"} <= words(out)


def test_short_credit_is_idempotent():
    assert short_credit(short_credit(SRC)) == short_credit(SRC)
    assert clean_alt_audio(clean_alt_audio(ALT)) == clean_alt_audio(ALT)
