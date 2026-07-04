from unittest.mock import patch

from app import app as flask_app
from extensions import db
import models


@patch("app.scoring.hybrid_scorer.ilani_karsilastir_hibrit")
def test_tekil_analiz_stores_score_from_hybrid_scorer(mock_hibrit, client):
    mock_hibrit.return_value = ({
        "uygunluk_skoru": 77,
        "alt_puanlar": {"teknik": 80, "deneyim": 70, "egitim": 75, "dil": 100, "sertifika": 60},
    }, None)

    with flask_app.app_context():
        user = models.Kullanici(email="analiz@example.com", parola="hashed")
        db.session.add(user)
        db.session.commit()
        cv = models.CV(
            orjinal_dosya_adi="test.pdf", aday_id=user.id,
            cikarilan_veriler={"yetenekler": ["Python"]},
        )
        db.session.add(cv)
        ilan = models.IsIlani(
            baslik="Python Developer", sirket_adi="Acme",
            kaynak_url="https://example.com/job/2", kaynak_site="Test",
            bulan_kullanici_id=user.id,
            gereksinimler_json={"full_text": "Python geliştirici aranıyor, 3 yıl deneyim."},
        )
        db.session.add(ilan)
        db.session.commit()
        user_id, cv_id, ilan_id = user.id, cv.id, ilan.id

    with client.session_transaction() as sess:
        sess["user_id"] = user_id

    resp = client.post(f"/analiz-et/{ilan_id}/{cv_id}", follow_redirects=True)

    assert resp.status_code == 200
    with flask_app.app_context():
        eslesme = models.Eslesme.query.filter_by(cv_id=cv_id, is_ilani_id=ilan_id).first()
        assert eslesme.skor == 77
        assert eslesme.analiz_sonucu["alt_puanlar"]["teknik"] == 80
    mock_hibrit.assert_called_once()


@patch("app.scoring.hybrid_scorer.ilani_karsilastir_hibrit")
@patch("app.learning.reweighting.guncel_agirliklari_al")
def test_tekil_analiz_passes_current_weights_to_hybrid_scorer(mock_agirliklar, mock_hibrit, client):
    mock_agirliklar.return_value = {"teknik": 0.5, "deneyim": 0.2, "egitim": 0.1, "dil": 0.1, "sertifika": 0.1}
    mock_hibrit.return_value = ({
        "uygunluk_skoru": 55,
        "alt_puanlar": {"teknik": 80, "deneyim": 70, "egitim": 75, "dil": 100, "sertifika": 60},
    }, None)

    with flask_app.app_context():
        user = models.Kullanici(email="weights@example.com", parola="hashed")
        db.session.add(user)
        db.session.commit()
        cv = models.CV(
            orjinal_dosya_adi="test.pdf", aday_id=user.id,
            cikarilan_veriler={"yetenekler": ["Python"]},
        )
        db.session.add(cv)
        ilan = models.IsIlani(
            baslik="Python Developer", sirket_adi="Acme",
            kaynak_url="https://example.com/job/weights", kaynak_site="Test",
            bulan_kullanici_id=user.id,
            gereksinimler_json={"full_text": "Python geliştirici aranıyor, 3 yıl deneyim."},
        )
        db.session.add(ilan)
        db.session.commit()
        user_id, cv_id, ilan_id = user.id, cv.id, ilan.id

    with client.session_transaction() as sess:
        sess["user_id"] = user_id

    client.post(f"/analiz-et/{ilan_id}/{cv_id}", follow_redirects=True)

    mock_hibrit.assert_called_once_with(
        cv.cikarilan_veriler, "Python geliştirici aranıyor, 3 yıl deneyim.",
        agirliklar={"teknik": 0.5, "deneyim": 0.2, "egitim": 0.1, "dil": 0.1, "sertifika": 0.1},
    )
