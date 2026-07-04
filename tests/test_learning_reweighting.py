import math

from app import app as flask_app
from extensions import db
import models
from learning.reweighting import guncel_agirliklari_al, _sigmoid, _lojistik_regresyon_egit


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


def test_sigmoid_zero_is_half():
    assert math.isclose(_sigmoid(0), 0.5)


def test_sigmoid_large_positive_is_near_one():
    assert _sigmoid(50) > 0.999


def test_sigmoid_large_negative_is_near_zero():
    assert _sigmoid(-50) < 0.001


def test_lojistik_regresyon_egit_learns_dominant_feature():
    # Birinci ozellik etiketle mukemmel iliskili, ikincisi rastgele gurultu
    X = [
        [1.0, 0.9], [1.0, 0.1], [1.0, 0.5], [1.0, 0.3],
        [0.0, 0.9], [0.0, 0.1], [0.0, 0.5], [0.0, 0.7],
    ]
    y = [1, 1, 1, 1, 0, 0, 0, 0]

    agirliklar = _lojistik_regresyon_egit(X, y, ogrenme_orani=0.5, epoch_sayisi=2000)

    assert abs(agirliklar[0]) > abs(agirliklar[1])
    assert agirliklar[0] > 0
