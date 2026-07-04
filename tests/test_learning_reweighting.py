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


from datetime import datetime

from learning.reweighting import yeniden_egit, MIN_TOPLAM_ORNEK


def _fixture_kullanici_cv(etiket):
    user = models.Kullanici(email=f"rw-{etiket}-{datetime.utcnow().timestamp()}@example.com", parola="hashed")
    db.session.add(user)
    db.session.commit()
    cv = models.CV(orjinal_dosya_adi="x.pdf", aday_id=user.id, cikarilan_veriler={})
    db.session.add(cv)
    db.session.commit()
    return user, cv


def _geribildirim_ekle(user, cv, alt_puanlar, deger, benzersiz_no):
    ilan = models.IsIlani(kaynak_url=f"https://example.com/rw-{benzersiz_no}", bulan_kullanici_id=user.id)
    db.session.add(ilan)
    db.session.commit()
    eslesme = models.Eslesme(cv_id=cv.id, is_ilani_id=ilan.id, skor=80, analiz_sonucu={"alt_puanlar": alt_puanlar})
    db.session.add(eslesme)
    db.session.commit()
    gb = models.Geribildirim(eslesme_id=eslesme.id, kullanici_id=user.id, deger=deger)
    db.session.add(gb)
    db.session.commit()


def test_yeniden_egit_yetersiz_veri_ile_reddeder(client):
    with flask_app.app_context():
        user, cv = _fixture_kullanici_cv("az")
        for i in range(5):
            _geribildirim_ekle(
                user, cv, {"teknik": 80, "deneyim": 70, "egitim": 60, "dil": 90, "sertifika": 50}, "olumlu", f"az{i}",
            )

        sonuc, hata = yeniden_egit()

        assert sonuc is None
        assert f"Yetersiz veri (5/{MIN_TOPLAM_ORNEK})" == hata
        assert models.ScoringConfig.query.count() == 0


def test_yeniden_egit_yeterli_veri_ile_agirlik_uretir(client):
    with flask_app.app_context():
        user, cv = _fixture_kullanici_cv("yeterli")
        for i in range(25):
            _geribildirim_ekle(
                user, cv, {"teknik": 90, "deneyim": 85, "egitim": 80, "dil": 90, "sertifika": 85}, "olumlu", f"pos{i}",
            )
        for i in range(25):
            _geribildirim_ekle(
                user, cv, {"teknik": 10, "deneyim": 15, "egitim": 20, "dil": 10, "sertifika": 15}, "olumsuz", f"neg{i}",
            )

        sonuc, hata = yeniden_egit()

        assert hata is None
        assert sonuc is not None
        assert abs(sum(sonuc.values()) - 1.0) < 1e-6
        assert models.ScoringConfig.query.count() == 1
        assert models.ScoringConfig.query.first().ornek_sayisi == 50
