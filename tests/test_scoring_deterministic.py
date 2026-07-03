import math

from scoring.deterministic import kosinus_benzerligi, teknik_puani_hesapla


def test_kosinus_benzerligi_identical_vectors_is_one():
    assert math.isclose(kosinus_benzerligi([1.0, 0.0], [1.0, 0.0]), 1.0)


def test_kosinus_benzerligi_orthogonal_vectors_is_zero():
    assert math.isclose(kosinus_benzerligi([1.0, 0.0], [0.0, 1.0]), 0.0)


def test_kosinus_benzerligi_empty_vector_returns_zero():
    assert kosinus_benzerligi([], [1.0, 0.0]) == 0.0
    assert kosinus_benzerligi([1.0, 0.0], []) == 0.0


def test_teknik_puani_tam_eslesme():
    vektorler = {"Python": [1.0, 0.0]}
    puan, eslesen, eksik = teknik_puani_hesapla(["Python"], ["Python"], vektorler.get)
    assert puan == 100
    assert eslesen == ["Python"]
    assert eksik == []


def test_teknik_puani_benzer_teknoloji_yarim_puan():
    vektorler = {"React": [1.0, 0.0], "Vue": [0.75, 0.6614378277661477]}
    puan, eslesen, eksik = teknik_puani_hesapla(["Vue"], ["React"], vektorler.get)
    assert puan == 50
    assert eslesen == ["React"]
    assert eksik == []


def test_teknik_puani_eslesmeyen_yetenek():
    vektorler = {"React": [1.0, 0.0], "Excel": [0.0, 1.0]}
    puan, eslesen, eksik = teknik_puani_hesapla(["Excel"], ["React"], vektorler.get)
    assert puan == 0
    assert eslesen == []
    assert eksik == ["React"]


def test_teknik_puani_bos_gereken_liste_elli_puan():
    puan, eslesen, eksik = teknik_puani_hesapla(["Python"], [], lambda t: [1.0, 0.0])
    assert puan == 50
    assert eslesen == []
    assert eksik == []


def test_teknik_puani_gomme_basarisiz_olursa_eksige_dusuyor():
    puan, eslesen, eksik = teknik_puani_hesapla(["Python"], ["React"], lambda t: None)
    assert puan == 0
    assert eksik == ["React"]
