from unittest.mock import patch

from scoring.hybrid_scorer import ilani_karsilastir_hibrit, AGIRLIKLAR


def test_agirliklar_toplami_bir():
    assert abs(sum(AGIRLIKLAR.values()) - 1.0) < 1e-9


@patch("scoring.hybrid_scorer.gemini_client")
@patch("scoring.hybrid_scorer.deterministic")
def test_ilani_karsilastir_hibrit_agirlikli_ortalama_hesaplar(mock_det, mock_gc):
    mock_gc.gereksinimleri_cikar.return_value = ({
        "gereken_yetenekler": ["Python"],
        "min_deneyim_yili": 3,
        "egitim_gereksinimi": "Bilgisayar Mühendisliği",
        "dil_gereksinimleri": [],
        "sertifika_gereksinimleri": [],
    }, None)
    mock_det.teknik_puani_hesapla.return_value = (80, ["Python"], [])
    mock_det.deneyim_puani_hesapla.return_value = (70, "3 yıl deneyim")
    mock_det.dil_puani_hesapla.return_value = (100, "Dil gereksinimi yok")
    mock_det.sertifika_puani_hesapla.return_value = 60
    mock_gc.egitim_ve_anlatim_uret.return_value = ({
        "egitim_puan": 90,
        "egitim_uyumu": "Tam uyum",
        "uygunluk_nedeni": "Güçlü aday",
        "guclu_yonler": ["Python"],
        "gelistirilmesi_gerekenler": [],
        "tavsiyeler": [],
    }, None)

    cv_verisi = {
        "yetenekler": ["Python"], "is_deneyimleri": [], "yabanci_diller": [],
        "sertifikalar": [], "projeler": [], "egitim_bilgileri": [],
    }

    sonuc, hata = ilani_karsilastir_hibrit(
        cv_verisi, "Yeterince uzun bir iş ilanı metni buraya gelir, elli karakterden uzun olmalı."
    )

    assert hata is None
    beklenen_skor = round(80 * 0.40 + 70 * 0.25 + 90 * 0.15 + 100 * 0.10 + 60 * 0.10)
    assert sonuc["uygunluk_skoru"] == beklenen_skor
    assert sonuc["alt_puanlar"] == {"teknik": 80, "deneyim": 70, "egitim": 90, "dil": 100, "sertifika": 60}
    assert sonuc["eslesen_yetenekler"] == ["Python"]
    assert sonuc["guclu_yonler"] == ["Python"]


@patch("scoring.hybrid_scorer.gemini_client")
def test_ilani_karsilastir_hibrit_gereksinim_hatasi_propagates(mock_gc):
    mock_gc.gereksinimleri_cikar.return_value = (None, "API hatası")
    sonuc, hata = ilani_karsilastir_hibrit(
        {}, "Yeterince uzun bir iş ilanı metni buraya gelir, elli karakterden uzun."
    )
    assert sonuc is None
    assert hata == "API hatası"


@patch("scoring.hybrid_scorer.gemini_client")
@patch("scoring.hybrid_scorer.deterministic")
def test_ilani_karsilastir_hibrit_anlatim_hatasi_propagates(mock_det, mock_gc):
    mock_gc.gereksinimleri_cikar.return_value = ({
        "gereken_yetenekler": [], "min_deneyim_yili": None, "egitim_gereksinimi": "",
        "dil_gereksinimleri": [], "sertifika_gereksinimleri": [],
    }, None)
    mock_det.teknik_puani_hesapla.return_value = (50, [], [])
    mock_det.deneyim_puani_hesapla.return_value = (50, "")
    mock_det.dil_puani_hesapla.return_value = (100, "")
    mock_det.sertifika_puani_hesapla.return_value = 40
    mock_gc.egitim_ve_anlatim_uret.return_value = (None, "Anlatim hatasi")

    sonuc, hata = ilani_karsilastir_hibrit(
        {}, "Yeterince uzun bir iş ilanı metni buraya gelir, elli karakterden uzun."
    )
    assert sonuc is None
    assert hata == "Anlatim hatasi"
