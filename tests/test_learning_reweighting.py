from app import app as flask_app
from extensions import db
import models
from learning.reweighting import guncel_agirliklari_al


def test_guncel_agirliklari_al_returns_none_when_no_config(client):
    with flask_app.app_context():
        assert guncel_agirliklari_al() is None


def test_guncel_agirliklari_al_returns_latest_config(client):
    with flask_app.app_context():
        eski = models.ScoringConfig(teknik=0.5, deneyim=0.2, egitim=0.1, dil=0.1, sertifika=0.1, ornek_sayisi=40)
        db.session.add(eski)
        db.session.commit()
        yeni = models.ScoringConfig(teknik=0.3, deneyim=0.3, egitim=0.2, dil=0.1, sertifika=0.1, ornek_sayisi=60)
        db.session.add(yeni)
        db.session.commit()

        sonuc = guncel_agirliklari_al()
        assert sonuc == {"teknik": 0.3, "deneyim": 0.3, "egitim": 0.2, "dil": 0.1, "sertifika": 0.1}
