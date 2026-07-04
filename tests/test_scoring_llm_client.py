from unittest.mock import patch, MagicMock

import requests

from scoring import llm_client


def _mock_response(status=200, body=None):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = body or {}
    return resp


@patch("scoring.llm_client.requests.post")
def test_gomlemesi_al_returns_vector_on_success(mock_post):
    mock_post.return_value = _mock_response(200, {"data": [{"embedding": [0.1, 0.2, 0.3]}]})
    sonuc = llm_client._llm_gomlemesi_al("Python")
    assert sonuc == [0.1, 0.2, 0.3]


@patch("scoring.llm_client.requests.post")
def test_gomlemesi_al_returns_none_on_non_200(mock_post):
    mock_post.return_value = _mock_response(500, {})
    assert llm_client._llm_gomlemesi_al("Python") is None


@patch("scoring.llm_client.requests.post")
def test_gomlemesi_al_returns_none_on_request_exception(mock_post):
    mock_post.side_effect = requests.exceptions.ConnectionError("boom")
    assert llm_client._llm_gomlemesi_al("Python") is None


def test_gomlemesi_al_returns_none_for_empty_text():
    assert llm_client._llm_gomlemesi_al("") is None
    assert llm_client._llm_gomlemesi_al("   ") is None


@patch("scoring.llm_client._llm_istegi_gonder")
def test_gereksinimleri_cikar_returns_parsed_requirements(mock_istek):
    mock_istek.return_value = ({
        "gereken_yetenekler": ["Python", "Flask"],
        "min_deneyim_yili": 3,
        "egitim_gereksinimi": "Bilgisayar Mühendisliği",
        "dil_gereksinimleri": [{"dil": "İngilizce", "min_seviye": "İleri"}],
        "sertifika_gereksinimleri": [],
    }, None)

    sonuc, hata = llm_client.gereksinimleri_cikar(
        "Python Flask geliştirici aranıyor, min 3 yıl deneyim gereklidir."
    )

    assert hata is None
    assert sonuc["gereken_yetenekler"] == ["Python", "Flask"]
    mock_istek.assert_called_once()


def test_gereksinimleri_cikar_returns_empty_defaults_for_short_text():
    sonuc, hata = llm_client.gereksinimleri_cikar("kısa")
    assert hata is None
    assert sonuc["gereken_yetenekler"] == []
    assert sonuc["min_deneyim_yili"] is None


@patch("scoring.llm_client._llm_istegi_gonder")
def test_gereksinimleri_cikar_propagates_error(mock_istek):
    mock_istek.return_value = (None, "API hatası")
    sonuc, hata = llm_client.gereksinimleri_cikar(
        "Python Flask geliştirici aranıyor, min 3 yıl deneyim, uzun metin burada devam ediyor."
    )
    assert sonuc is None
    assert hata == "API hatası"


@patch("scoring.llm_client._llm_istegi_gonder")
def test_egitim_ve_anlatim_uret_returns_full_narrative(mock_istek):
    mock_istek.return_value = ({
        "egitim_puan": 85,
        "egitim_uyumu": "İlgili bölüm mezunu",
        "uygunluk_nedeni": "Aday teknik olarak güçlü",
        "guclu_yonler": ["Python bilgisi"],
        "gelistirilmesi_gerekenler": ["Bulut deneyimi"],
        "tavsiyeler": ["AWS sertifikası al"],
    }, None)

    cv_verisi = {"egitim_bilgileri": [{"bolum_adi": "Bilgisayar Mühendisliği"}]}
    gereksinimler = {"egitim_gereksinimi": "Bilgisayar Mühendisliği"}
    alt_puanlar = {"teknik": 80, "deneyim": 70, "dil": 100, "sertifika": 60}

    sonuc, hata = llm_client.egitim_ve_anlatim_uret(
        cv_verisi, gereksinimler, alt_puanlar, ["Python"], ["AWS"], "3 yıl", "İngilizce: 100"
    )

    assert hata is None
    assert sonuc["egitim_puan"] == 85
    assert sonuc["guclu_yonler"] == ["Python bilgisi"]
    mock_istek.assert_called_once()
