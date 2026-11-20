from zh_lex import Lexicon


def _lex():
    lx = Lexicon()
    for simp, trad, py in [("高兴", "高興", "gāo xìng"), ("了不得", "了不得", "liǎo bu dé"), ("得", "得", "dé · de · děi"),
                           ("我", "我", "wǒ"), ("的", "的", "de · dí"), ("书", "書", "shū"), ("这", "這", "zhè"),
                           ("是", "是", "shì"), ("钥匙", "鑰匙", "yào shi"), ("也", "也", "Yě · yě")]:
        lx.add(simp, trad, py)
    return lx


def test_detect_script():
    lx = _lex()
    assert lx.detect("高興得了不得") == "trad"
    assert lx.detect("高兴得了不得") == "simp"
    assert lx.detect("我的") == "same"


def test_convert_both_ways():
    lx = _lex()
    assert lx.to_simp("這是我的鑰匙。") == "这是我的钥匙。"
    assert lx.to_trad("这是我的钥匙。") == "這是我的鑰匙。"


def test_pinyin_word_by_word():
    lx = _lex()
    assert lx.pinyin("高兴得了不得") == "Gāoxìng dé liǎobudé"
    assert lx.pinyin("这是我的钥匙。") == "Zhè shì wǒ de yàoshi."
    assert lx.pinyin("我也是") == "Wǒ yě shì"           # lower-case reading preferred over the surname


def test_unknown_characters_kept():
    lx = _lex()
    assert lx.to_simp("我X書") == "我X书"
    assert lx.pinyin("我？") == "Wǒ?"
