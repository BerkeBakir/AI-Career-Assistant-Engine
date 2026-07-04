import pytest
from sqlalchemy.exc import IntegrityError

from app import app as flask_app
from extensions import db
import models


def _kullanici_cv_eslesme():
    user = models.Kullanici(email="fb@example.com", parola="hashed")
    db.session.add(user)
    db.session.commit()
    cv = models.CV(orjinal_dosya_adi="x.pdf", aday_id=user.id, cikarilan_veriler={})
    db.session.add(cv)
    ilan = models.IsIlani(kaynak_url="https://example.com/model-test-1", bulan_kullanici_id=user.id)
    db.session.add(ilan)
    db.session.commit()
    eslesme = models.Eslesme(cv_id=cv.id, is_ilani_id=ilan.id, skor=80)
    db.session.add(eslesme)
    db.session.commit()
    return user, eslesme


def test_geribildirim_unique_constraint_blocks_duplicate(client):
    with flask_app.app_context():
        user, eslesme = _kullanici_cv_eslesme()

        gb1 = models.Geribildirim(eslesme_id=eslesme.id, kullanici_id=user.id, deger="olumlu")
        db.session.add(gb1)
        db.session.commit()

        gb2 = models.Geribildirim(eslesme_id=eslesme.id, kullanici_id=user.id, deger="olumsuz")
        db.session.add(gb2)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_geribildirim_stores_deger_and_timestamp(client):
    with flask_app.app_context():
        user, eslesme = _kullanici_cv_eslesme()

        gb = models.Geribildirim(eslesme_id=eslesme.id, kullanici_id=user.id, deger="olumlu")
        db.session.add(gb)
        db.session.commit()

        yeniden = models.Geribildirim.query.first()
        assert yeniden.deger == "olumlu"
        assert yeniden.olusturulma_tarihi is not None


def test_scoring_config_stores_weights_and_sample_count(client):
    with flask_app.app_context():
        cfg = models.ScoringConfig(
            teknik=0.5, deneyim=0.2, egitim=0.1, dil=0.1, sertifika=0.1, ornek_sayisi=42,
        )
        db.session.add(cfg)
        db.session.commit()

        yeniden = models.ScoringConfig.query.first()
        assert yeniden.teknik == 0.5
        assert yeniden.ornek_sayisi == 42
        assert yeniden.olusturulma_tarihi is not None
