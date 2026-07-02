from unittest.mock import patch

from app import app as flask_app
from extensions import db
import models


def _login_with_cv(client):
    with flask_app.app_context():
        user = models.Kullanici(email="test@example.com", parola="hashed")
        db.session.add(user)
        db.session.commit()
        cv = models.CV(orjinal_dosya_adi="test.pdf", aday_id=user.id, cikarilan_veriler={"yetenekler": ["Python"]})
        db.session.add(cv)
        db.session.commit()
        user_id, cv_id = user.id, cv.id

    with client.session_transaction() as sess:
        sess["user_id"] = user_id
    return cv_id


@patch("app.job_search_service.search_jobs")
def test_is_ara_creates_ilan_from_job_search_service(mock_search_jobs, client):
    mock_search_jobs.return_value = [
        {"baslik": "Python Developer", "link": "https://example.com/job/1", "sirket": "Acme", "kaynak": "Test", "aciklama": "Istanbul"},
    ]
    cv_id = _login_with_cv(client)

    resp = client.post("/is-ara", data={"secilen_cv_id": cv_id}, follow_redirects=True)

    assert resp.status_code == 200
    with flask_app.app_context():
        assert models.IsIlani.query.filter_by(kaynak_url="https://example.com/job/1").count() == 1
    mock_search_jobs.assert_called_once_with(["Python"])


@patch("app.job_search_service.search_jobs")
def test_is_ara_shows_warning_when_no_results(mock_search_jobs, client):
    mock_search_jobs.return_value = []
    cv_id = _login_with_cv(client)

    resp = client.post("/is-ara", data={"secilen_cv_id": cv_id}, follow_redirects=True)

    assert resp.status_code == 200
    assert "bulunamad".encode("utf-8") in resp.data
