from app import app as flask_app
from extensions import db
import models


def _admin_kullanici(client):
    with flask_app.app_context():
        admin = models.Kullanici(email="admin@example.com", parola="hashed", rol="admin")
        db.session.add(admin)
        db.session.commit()
        admin_id = admin.id
    with client.session_transaction() as sess:
        sess['user_id'] = admin_id
    return admin_id


def _aday_kullanici(client):
    with flask_app.app_context():
        aday = models.Kullanici(email="aday@example.com", parola="hashed")
        db.session.add(aday)
        db.session.commit()
        aday_id = aday.id
    with client.session_transaction() as sess:
        sess['user_id'] = aday_id
    return aday_id


def test_admin_agirliklar_blocks_non_admin(client):
    _aday_kullanici(client)
    resp = client.get('/admin/agirliklar')
    assert resp.status_code == 403


def test_admin_agirliklar_requires_login(client):
    resp = client.get('/admin/agirliklar')
    assert resp.status_code == 302


def test_admin_agirliklar_shows_default_weights_when_no_config(client):
    _admin_kullanici(client)
    resp = client.get('/admin/agirliklar')
    assert resp.status_code == 200
    assert b'40' in resp.data  # esik degeri (MIN_TOPLAM_ORNEK) sayfada gorunmeli


def test_admin_agirliklar_post_reports_insufficient_data(client):
    _admin_kullanici(client)
    resp = client.post('/admin/agirliklar', follow_redirects=True)
    assert resp.status_code == 200
    assert 'Yetersiz veri'.encode('utf-8') in resp.data
    with flask_app.app_context():
        assert models.ScoringConfig.query.count() == 0
