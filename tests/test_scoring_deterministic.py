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


from datetime import datetime, timedelta

from scoring.deterministic import deneyim_puani_hesapla, _tarihi_parse_et


def test_tarihi_parse_et_turkce_ay_ismi():
    assert _tarihi_parse_et("Ocak 2020") == datetime(2020, 1, 1)


def test_tarihi_parse_et_halen_bugunu_dondurur():
    sonuc = _tarihi_parse_et("Halen")
    assert (datetime.now() - sonuc).total_seconds() < 5


def test_tarihi_parse_et_sadece_yil():
    assert _tarihi_parse_et("2019") == datetime(2019, 1, 1)


def test_tarihi_parse_et_sayisal_ay_yil():
    assert _tarihi_parse_et("03/2021") == datetime(2021, 3, 1)


def test_tarihi_parse_et_parse_edilemeyen_metin_none_doner():
    assert _tarihi_parse_et("bilinmiyor") is None


def test_deneyim_puani_min_deneyim_belirtilmemisse_elli_doner():
    puan, uyum = deneyim_puani_hesapla([], None)
    assert puan == 50


def test_deneyim_puani_tam_uyum():
    is_deneyimleri = [{"baslangic_tarihi": "Ocak 2020", "bitis_tarihi": "Ocak 2023"}]
    puan, uyum = deneyim_puani_hesapla(is_deneyimleri, 3)
    assert puan == 100


def test_deneyim_puani_eksik_deneyim():
    is_deneyimleri = [{"baslangic_tarihi": "Ocak 2022", "bitis_tarihi": "Ocak 2023"}]
    puan, uyum = deneyim_puani_hesapla(is_deneyimleri, 5)
    assert puan == 20


def test_deneyim_puani_halen_devam_eden_is():
    uc_yil_once = (datetime.now() - timedelta(days=3 * 365)).strftime("%m/%Y")
    is_deneyimleri = [{"baslangic_tarihi": uc_yil_once, "bitis_tarihi": "Halen"}]
    puan, uyum = deneyim_puani_hesapla(is_deneyimleri, 3)
    assert puan >= 95


def test_deneyim_puani_parse_edilemeyen_kayit_atlanir():
    is_deneyimleri = [{"baslangic_tarihi": "bilinmiyor", "bitis_tarihi": "bilinmiyor"}]
    puan, uyum = deneyim_puani_hesapla(is_deneyimleri, 3)
    assert puan == 0
