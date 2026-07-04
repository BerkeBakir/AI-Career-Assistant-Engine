from app import app as flask_app
from extensions import db
import models


def _fixture(client):
    with flask_app.app_context():
        user = models.Kullanici(email="gb@example.com", parola="hashed")
        db.session.add(user)
        db.session.commit()
        cv = models.CV(orjinal_dosya_adi="x.pdf", aday_id=user.id, cikarilan_veriler={})
        db.session.add(cv)
        ilan = models.IsIlani(kaynak_url="https://example.com/gb1", bulan_kullanici_id=user.id)
        db.session.add(ilan)
        db.session.commit()
        eslesme = models.Eslesme(cv_id=cv.id, is_ilani_id=ilan.id, skor=80)
        db.session.add(eslesme)
        db.session.commit()
        user_id, eslesme_id = user.id, eslesme.id

    with client.session_transaction() as sess:
        sess['user_id'] = user_id
    return eslesme_id


def test_geribildirim_ver_creates_new_record(client):
    eslesme_id = _fixture(client)

    resp = client.post(f'/geribildirim/{eslesme_id}', json={'deger': 'olumlu'})

    assert resp.status_code == 200
    assert resp.get_json() == {'success': True, 'deger': 'olumlu'}
    with flask_app.app_context():
        kayit = models.Geribildirim.query.filter_by(eslesme_id=eslesme_id).first()
        assert kayit.deger == 'olumlu'


def test_geribildirim_ver_upserts_existing_record(client):
    eslesme_id = _fixture(client)
    client.post(f'/geribildirim/{eslesme_id}', json={'deger': 'olumlu'})

    resp = client.post(f'/geribildirim/{eslesme_id}', json={'deger': 'olumsuz'})

    assert resp.status_code == 200
    with flask_app.app_context():
        kayitlar = models.Geribildirim.query.filter_by(eslesme_id=eslesme_id).all()
        assert len(kayitlar) == 1
        assert kayitlar[0].deger == 'olumsuz'


def test_geribildirim_ver_rejects_invalid_deger(client):
    eslesme_id = _fixture(client)
    resp = client.post(f'/geribildirim/{eslesme_id}', json={'deger': 'bilinmiyor'})
    assert resp.status_code == 400


def test_geribildirim_ver_blocks_non_owner(client):
    eslesme_id = _fixture(client)
    with flask_app.app_context():
        baskasi = models.Kullanici(email="other@example.com", parola="hashed")
        db.session.add(baskasi)
        db.session.commit()
        baskasi_id = baskasi.id
    with client.session_transaction() as sess:
        sess['user_id'] = baskasi_id

    resp = client.post(f'/geribildirim/{eslesme_id}', json={'deger': 'olumlu'})
    assert resp.status_code == 403


def test_geribildirim_ver_requires_login(client):
    resp = client.post('/geribildirim/1', json={'deger': 'olumlu'})
    assert resp.status_code == 401
