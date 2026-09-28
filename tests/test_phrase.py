from miratek.phrase import PhraseBuilder


def build(*tokens):
    p = PhraseBuilder()
    for t in tokens:
        if t == "|":
            p.close()
        else:
            p.add(t)
    return p.texts


def test_words_and_spelling():
    assert build("hola", "letra_a", "letra_n", "letra_a", "|", "gracias") == ["Hola", "ANA", "Gracias"]
    assert build("letra_enie", "letra_o") == ["ÑO"]


def test_numbers_compose():
    assert build("num_20", "num_3") == ["23"]
    assert build("num_10", "num_6") == ["16"]
    assert build("num_1", "num_0", "num_0") == ["100"]
    assert build("num_100") == ["100"]
    assert build("num_7", "|", "num_5") == ["7", "5"]
    assert build("num_20", "num_30") == ["20", "30"]
    assert build("num_15", "num_2") == ["15", "2"]


def test_delete_last():
    p = PhraseBuilder()
    for t in ("hola", "letra_s", "letra_i"):
        p.add(t)
    p.delete_last()
    assert p.texts == ["Hola", "S"]
    p.close()
    p.delete_last()
    assert p.texts == ["Hola"]
