# Feedback Collection + Auto-Reweighting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let candidates give 👍/👎 feedback on each AI match analysis, store it, and let an admin manually retrain the five scoring weights (teknik/deneyim/egitim/dil/sertifika) from accumulated feedback once enough data exists.

**Architecture:** Two new tables (`Geribildirim` for feedback, `ScoringConfig` for versioned weight snapshots). A new `learning/reweighting.py` module reads the latest weights, and — when triggered — trains a from-scratch pure-Python logistic regression (no scikit-learn/numpy) over stored `alt_puanlar` sub-scores vs. feedback labels, then writes a new `ScoringConfig` row. `scoring/hybrid_scorer.py` gains an optional `agirliklar` parameter so `app.py` can inject the current weights instead of always using the hardcoded default. A minimal admin-only panel (gated by `Kullanici.rol == 'admin'`) shows current weights/sample counts and has a "retrain" button — no scheduled/cron retraining.

**Tech Stack:** Python 3.14, Flask, Flask-SQLAlchemy, pure-Python logistic regression (gradient descent, stdlib `math` only), pytest + `unittest.mock`.

## Global Constraints

- This is Plan 3 of the 3-plan rollout in `docs/superpowers/specs/2026-07-02-modular-scraping-engine-design.md` (section 5). Plans 1 (scraper engine) and 2 (hybrid scoring) are done and merged to `main`.
- **No numpy, no scikit-learn.** Confirmed on this environment: `python -c "import numpy"` segfaults (`Segmentation fault`, MINGW-W64 Windows build is experimental/unstable) — `scikit-learn` imports numpy internally and would crash identically. The user explicitly chose pure-Python logistic regression over fixing the environment or trying scikit-learn anyway. Implement gradient descent by hand using only the stdlib `math` module.
- **Weight vector order is fixed:** `["teknik", "deneyim", "egitim", "dil", "sertifika"]` — this exact order is used everywhere a plain list of 5 floats represents weights (feature vectors for training, the trained coefficient list, iteration order). Getting this order wrong anywhere silently swaps which sub-score each weight applies to.
- **Retrain threshold:** at least 40 total feedback samples AND at least 10 samples in each class (`olumlu`/`olumsuz`). Below threshold, `yeniden_egit()` returns `(None, "Yetersiz veri (X/40)")` where X is the actual total count, and does NOT write a `ScoringConfig` row or run any training.
- **Weight normalization:** after training, take the absolute value of each of the 5 learned coefficients (the bias/intercept term is discarded — it's not a per-sub-score weight) and normalize so they sum to 1.0. If all 5 are exactly zero (degenerate case), fall back to the hardcoded default weights `{"teknik": 0.40, "deneyim": 0.25, "egitim": 0.15, "dil": 0.10, "sertifika": 0.10}` instead of dividing by zero.
- **Versioning:** every successful retrain INSERTS a new `ScoringConfig` row (never updates one in place) — the row's auto-increment `id` doubles as its version number. "Current weights" always means the row with the highest `id`. Old rows are kept as history, never deleted.
- **`scoring/hybrid_scorer.py` backward compatibility:** `ilani_karsilastir_hibrit(cv_verisi, ilan_metni, agirliklar=None)` — the new third parameter is optional and defaults to `None`, meaning "use the hardcoded `AGIRLIKLAR` dict". Every existing call and test from Plan 2 (which calls it with exactly 2 positional args) must keep passing unchanged.
- **Admin gating:** reuse the existing `Kullanici.rol` column (already in `models.py`, defaults to `'aday'`, currently never checked anywhere in the app). Gate the admin route with `if kullanici.rol != 'admin': abort(403)`. There is no self-service UI to grant admin in this plan (out of scope, matches the spec's "kapsam dışı" discipline for anything beyond the minimum) — promoting a user is a manual one-off SQL statement, documented in Task 9, not a new script or UI flow.
- **Session-based role check for nav visibility:** store `session['rol'] = user.rol` at login (alongside the existing `session['user_id']`) so `templates/base.html` can show/hide the admin nav link with `{% if session.rol == 'admin' %}` without an extra DB query on every page render.
- **CSRF:** this repo has `CSRFProtect(app)` enabled globally in `app.py`. AJAX POST requests must send the token as an `X-CSRFToken` header read from the page's rendered `<input name="csrf_token">` (the exact pattern already used by `kaydedilenler.html`'s existing `topluAnalizBaslat()` function — copy it, don't invent a new pattern). Tests rely on `tests/conftest.py`'s existing `flask_app.config["WTF_CSRF_ENABLED"] = False`, so test requests don't need to supply a token.
- **`proje.db` must not be modified by any task in this plan.** All tests use the existing `tests/conftest.py` `client` fixture (`sqlite:///:memory:`, fresh `db.create_all()`/`drop_all()` per test) — never touch the real `proje.db` file. The two new tables get added to the real dev database later, out of band, via Flask-SQLAlchemy's `db.create_all()` (which only creates tables that don't already exist and never touches/drops existing ones) — not something any task here needs to run.
- **Mock at point of use**, matching this repo's established test style (e.g. `@patch("scoring.hybrid_scorer.gemini_client")`).
- Branch: plain feature branch `feature/feedback-reweighting` off `main` (no git worktree — matches the choice made for Plans 1 and 2).

---

### Task 1: `Geribildirim` and `ScoringConfig` models

**Files:**
- Modify: `models.py` (append two new model classes)
- Test: `tests/test_models_geribildirim_scoringconfig.py`

**Interfaces:**
- Produces: `models.Geribildirim` (columns: `id, eslesme_id, kullanici_id, deger, olusturulma_tarihi`, unique constraint on `(eslesme_id, kullanici_id)`) and `models.ScoringConfig` (columns: `id, teknik, deneyim, egitim, dil, sertifika, ornek_sayisi, olusturulma_tarihi`) — every later task in this plan reads/writes these two tables.

- [ ] **Step 1: Create the branch**

```bash
git checkout main
git pull
git checkout -b feature/feedback-reweighting
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_models_geribildirim_scoringconfig.py`:

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_models_geribildirim_scoringconfig.py -v`
Expected: FAIL (`AttributeError: module 'models' has no attribute 'Geribildirim'`)

- [ ] **Step 4: Implement**

Append to `models.py` (after the existing `Eslesme` class):

```python
class Geribildirim(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    eslesme_id = db.Column(db.Integer, db.ForeignKey('eslesme.id'), nullable=False)
    kullanici_id = db.Column(db.Integer, db.ForeignKey('kullanici.id'), nullable=False)
    deger = db.Column(db.String(10), nullable=False)  # 'olumlu' veya 'olumsuz'
    olusturulma_tarihi = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('eslesme_id', 'kullanici_id', name='uq_geribildirim_eslesme_kullanici'),
    )


class ScoringConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teknik = db.Column(db.Float, nullable=False)
    deneyim = db.Column(db.Float, nullable=False)
    egitim = db.Column(db.Float, nullable=False)
    dil = db.Column(db.Float, nullable=False)
    sertifika = db.Column(db.Float, nullable=False)
    ornek_sayisi = db.Column(db.Integer, nullable=False)
    olusturulma_tarihi = db.Column(db.DateTime, default=datetime.utcnow)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_models_geribildirim_scoringconfig.py -v`
Expected: PASS (3/3)

- [ ] **Step 6: Commit**

```bash
git add models.py tests/test_models_geribildirim_scoringconfig.py
git commit -m "feat: add Geribildirim and ScoringConfig models"
```

---

### Task 2: `POST /geribildirim/<eslesme_id>` endpoint

**Files:**
- Modify: `app.py` (new route)
- Test: `tests/test_app_geribildirim.py`

**Interfaces:**
- Consumes: `models.Geribildirim` (Task 1), `models.Eslesme`, `models.CV` (existing).
- Produces: route `geribildirim_ver` at `POST /geribildirim/<int:eslesme_id>`, returning JSON `{"success": true, "deger": "olumlu"|"olumsuz"}` on success. No other task calls this route directly, but Task 3's JS calls it over HTTP.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_app_geribildirim.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_app_geribildirim.py -v`
Expected: FAIL (404, route doesn't exist yet)

- [ ] **Step 3: Implement**

In `app.py`, add this route after the existing `tekil_analiz` route (near line 307, right before `_tek_ilan_analiz_et`):

```python
@app.route('/geribildirim/<int:eslesme_id>', methods=['POST'])
def geribildirim_ver(eslesme_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Oturum gerekli'}), 401

    user_id = session['user_id']
    eslesme = models.Eslesme.query.get_or_404(eslesme_id)
    if eslesme.cv.aday_id != user_id:
        abort(403)

    veri = request.get_json(silent=True) or {}
    deger = veri.get('deger')
    if deger not in ('olumlu', 'olumsuz'):
        return jsonify({'error': 'Gecersiz deger'}), 400

    kayit = models.Geribildirim.query.filter_by(eslesme_id=eslesme_id, kullanici_id=user_id).first()
    if kayit:
        kayit.deger = deger
    else:
        kayit = models.Geribildirim(eslesme_id=eslesme_id, kullanici_id=user_id, deger=deger)
        db.session.add(kayit)
    db.session.commit()

    return jsonify({'success': True, 'deger': deger})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_app_geribildirim.py -v`
Expected: PASS (5/5)

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_app_geribildirim.py
git commit -m "feat: add POST /geribildirim/<eslesme_id> endpoint"
```

---

### Task 3: 👍/👎 feedback widget in kaydedilenler.html

**Files:**
- Modify: `app.py:251-267` (the `kaydedilenler` route)
- Modify: `templates/kaydedilenler.html`
- Test: `tests/test_app_geribildirim.py` (append)

**Interfaces:**
- Consumes: `POST /geribildirim/<eslesme_id>` (Task 2).
- Produces: nothing new for later tasks — this is a UI-facing leaf task.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_app_geribildirim.py`:

```python
def test_kaydedilenler_shows_feedback_widget_with_existing_state(client):
    with flask_app.app_context():
        user = models.Kullanici(email="widget@example.com", parola="hashed")
        db.session.add(user)
        db.session.commit()
        cv = models.CV(orjinal_dosya_adi="x.pdf", aday_id=user.id, cikarilan_veriler={})
        db.session.add(cv)
        ilan = models.IsIlani(
            baslik="Test Ilan", sirket_adi="Acme",
            kaynak_url="https://example.com/widget1", bulan_kullanici_id=user.id,
        )
        db.session.add(ilan)
        db.session.commit()
        eslesme = models.Eslesme(
            cv_id=cv.id, is_ilani_id=ilan.id, skor=80,
            analiz_sonucu={"alt_puanlar": {"teknik": 80, "deneyim": 70, "egitim": 75, "dil": 100, "sertifika": 60}},
        )
        db.session.add(eslesme)
        db.session.commit()
        gb = models.Geribildirim(eslesme_id=eslesme.id, kullanici_id=user.id, deger="olumlu")
        db.session.add(gb)
        db.session.commit()
        user_id, eslesme_id = user.id, eslesme.id

    with client.session_transaction() as sess:
        sess['user_id'] = user_id

    resp = client.get('/kaydedilenler')

    assert resp.status_code == 200
    body = resp.data.decode('utf-8')
    assert f'data-eslesme-id="{eslesme_id}"' in body
    assert 'geribildirim-btn active' in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_app_geribildirim.py::test_kaydedilenler_shows_feedback_widget_with_existing_state -v`
Expected: FAIL (`data-eslesme-id` not found in response body)

- [ ] **Step 3: Implement — app.py route data**

In `app.py`, replace the `kaydedilenler` route (lines 251-267):

```python
@app.route('/kaydedilenler')
def kaydedilenler():
    if 'user_id' not in session: return redirect(url_for('login'))
    user_id = session['user_id']

    # Sadece kullanicinin buldugu ilanlari goster
    ilanlar = models.IsIlani.query.filter_by(bulan_kullanici_id=user_id).order_by(models.IsIlani.id.desc()).limit(100).all()
    cvler = models.CV.query.filter_by(aday_id=user_id).all()

    puanlar = {}
    analizler = {}
    eslesme_idler = {}
    if cvler:
        for e in models.Eslesme.query.filter_by(cv_id=cvler[0].id).all():
            puanlar[e.is_ilani_id] = e.skor
            analizler[e.is_ilani_id] = e.analiz_sonucu
            eslesme_idler[e.is_ilani_id] = e.id

    mevcut_geribildirimler = {}
    if eslesme_idler:
        for gb in models.Geribildirim.query.filter(
            models.Geribildirim.kullanici_id == user_id,
            models.Geribildirim.eslesme_id.in_(eslesme_idler.values()),
        ).all():
            mevcut_geribildirimler[gb.eslesme_id] = gb.deger

    return render_template(
        'kaydedilenler.html', ilanlar=ilanlar, puanlar=puanlar, analizler=analizler,
        cvler=cvler, eslesme_idler=eslesme_idler, mevcut_geribildirimler=mevcut_geribildirimler,
    )
```

- [ ] **Step 4: Implement — template widget**

In `templates/kaydedilenler.html`, inside the `{% if alt %}...{% endif %}` block (lines 100-110), add the feedback widget right after that block's closing `{% endif %}` but still inside the outer `{% if ilan.id in puanlar %}` block (i.e., insert between line 110's `{% endif %}` and line 111's `{% else %}`):

```html
                            {% if alt %}
                            <div class="d-flex flex-wrap gap-1 mt-1" style="font-size: 0.65em;">
                                <span class="badge bg-primary bg-opacity-75" title="Teknik Yetenekler">T:{{ alt.teknik
                                    }}</span>
                                <span class="badge bg-info bg-opacity-75" title="Deneyim">D:{{ alt.deneyim }}</span>
                                <span class="badge bg-purple" style="background-color: #7c3aed;" title="Eğitim">E:{{
                                    alt.egitim }}</span>
                                <span class="badge bg-success bg-opacity-75" title="Dil">L:{{ alt.dil }}</span>
                                <span class="badge bg-warning text-dark" title="Sertifika">S:{{ alt.sertifika }}</span>
                            </div>
                            {% endif %}
                            {% if ilan.id in eslesme_idler %}
                            {% set eslesme_id = eslesme_idler[ilan.id] %}
                            {% set mevcut = mevcut_geribildirimler.get(eslesme_id) %}
                            <div class="d-flex gap-1 mt-1 geribildirim-widget" data-eslesme-id="{{ eslesme_id }}">
                                <button type="button" class="btn btn-sm btn-outline-success geribildirim-btn {% if mevcut == 'olumlu' %}active{% endif %}" data-deger="olumlu" title="Faydalı">👍</button>
                                <button type="button" class="btn btn-sm btn-outline-danger geribildirim-btn {% if mevcut == 'olumsuz' %}active{% endif %}" data-deger="olumsuz" title="Faydasız">👎</button>
                            </div>
                            {% endif %}
```

- [ ] **Step 5: Implement — JS handler**

In `templates/kaydedilenler.html`, inside the existing `<script>` block, add this after the closing brace of the `topluAnalizBaslat` function (right before the final `</script>`):

```javascript
document.querySelectorAll('.geribildirim-widget').forEach(function (widget) {
    const eslesmeId = widget.dataset.eslesmeId;
    widget.querySelectorAll('.geribildirim-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
            const deger = btn.dataset.deger;
            const csrfToken = document.querySelector('input[name="csrf_token"]')?.value || '';

            fetch(`/geribildirim/${eslesmeId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ deger: deger })
            })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        widget.querySelectorAll('.geribildirim-btn').forEach(b => b.classList.remove('active'));
                        btn.classList.add('active');
                    }
                })
                .catch(error => console.error('Geribildirim hatasi:', error));
        });
    });
});
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_app_geribildirim.py -v`
Expected: PASS (6/6)

- [ ] **Step 7: Run the full test suite to check for regressions**

Run: `python -m pytest -v`
Expected: all tests pass

- [ ] **Step 8: Commit**

```bash
git add app.py templates/kaydedilenler.html tests/test_app_geribildirim.py
git commit -m "feat: add feedback widget to kaydedilenler.html"
```

---

### Task 4: `hybrid_scorer` optional weight override

**Files:**
- Modify: `scoring/hybrid_scorer.py`
- Modify: `tests/test_scoring_hybrid_scorer.py` (append)

**Interfaces:**
- Consumes: nothing new.
- Produces: `scoring.hybrid_scorer.ilani_karsilastir_hibrit(cv_verisi, ilan_metni, agirliklar=None)` — Task 8 passes a weights dict from `learning.reweighting.guncel_agirliklari_al()` here.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_scoring_hybrid_scorer.py`:

```python
@patch("scoring.hybrid_scorer.gemini_client")
@patch("scoring.hybrid_scorer.deterministic")
def test_ilani_karsilastir_hibrit_uses_custom_agirliklar_when_given(mock_det, mock_gc):
    mock_gc.gereksinimleri_cikar.return_value = ({
        "gereken_yetenekler": [], "min_deneyim_yili": None, "egitim_gereksinimi": "",
        "dil_gereksinimleri": [], "sertifika_gereksinimleri": [],
    }, None)
    mock_det.teknik_puani_hesapla.return_value = (100, [], [])
    mock_det.deneyim_puani_hesapla.return_value = (0, "")
    mock_det.dil_puani_hesapla.return_value = (0, "")
    mock_det.sertifika_puani_hesapla.return_value = 0
    mock_gc.egitim_ve_anlatim_uret.return_value = ({
        "egitim_puan": 0, "egitim_uyumu": "", "uygunluk_nedeni": "",
        "guclu_yonler": [], "gelistirilmesi_gerekenler": [], "tavsiyeler": [],
    }, None)

    ozel_agirliklar = {"teknik": 1.0, "deneyim": 0.0, "egitim": 0.0, "dil": 0.0, "sertifika": 0.0}

    sonuc, hata = ilani_karsilastir_hibrit(
        {}, "Yeterince uzun bir iş ilanı metni buraya gelir, elli karakterden uzun olmalı.",
        agirliklar=ozel_agirliklar,
    )

    assert hata is None
    assert sonuc["uygunluk_skoru"] == 100


@patch("scoring.hybrid_scorer.gemini_client")
@patch("scoring.hybrid_scorer.deterministic")
def test_ilani_karsilastir_hibrit_defaults_to_module_agirliklar_when_none(mock_det, mock_gc):
    mock_gc.gereksinimleri_cikar.return_value = ({
        "gereken_yetenekler": [], "min_deneyim_yili": None, "egitim_gereksinimi": "",
        "dil_gereksinimleri": [], "sertifika_gereksinimleri": [],
    }, None)
    mock_det.teknik_puani_hesapla.return_value = (80, [], [])
    mock_det.deneyim_puani_hesapla.return_value = (70, "")
    mock_det.dil_puani_hesapla.return_value = (100, "")
    mock_det.sertifika_puani_hesapla.return_value = 60
    mock_gc.egitim_ve_anlatim_uret.return_value = ({
        "egitim_puan": 90, "egitim_uyumu": "", "uygunluk_nedeni": "",
        "guclu_yonler": [], "gelistirilmesi_gerekenler": [], "tavsiyeler": [],
    }, None)

    # agirliklar hic verilmiyor - eski Plan 2 cagri sekli, geriye donuk uyumluluk
    sonuc, hata = ilani_karsilastir_hibrit(
        {}, "Yeterince uzun bir iş ilanı metni buraya gelir, elli karakterden uzun olmalı."
    )

    assert hata is None
    beklenen_skor = round(80 * 0.40 + 70 * 0.25 + 90 * 0.15 + 100 * 0.10 + 60 * 0.10)
    assert sonuc["uygunluk_skoru"] == beklenen_skor
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_scoring_hybrid_scorer.py -v`
Expected: FAIL (`TypeError: ilani_karsilastir_hibrit() got an unexpected keyword argument 'agirliklar'`)

- [ ] **Step 3: Implement**

In `scoring/hybrid_scorer.py`, change the function signature and the score-summing line:

```python
def ilani_karsilastir_hibrit(cv_verisi, ilan_metni, agirliklar=None):
    aktif_agirliklar = agirliklar if agirliklar is not None else AGIRLIKLAR

    if not ilan_metni or len(ilan_metni) < 50:
        ilan_metni = "İlan içeriğine tam erişilemedi. Başlık ve şirket bilgisine göre genel değerlendirme yap."

    gereksinimler, hata = gemini_client.gereksinimleri_cikar(ilan_metni)
    if hata:
        return None, hata

    teknik_puan, eslesen_yetenekler, eksik_yetenekler = deterministic.teknik_puani_hesapla(
        cv_verisi.get('yetenekler', []),
        gereksinimler.get('gereken_yetenekler', []),
        gemini_client._gemini_gomlemesi_al,
    )

    deneyim_puan, deneyim_uyumu = deterministic.deneyim_puani_hesapla(
        cv_verisi.get('is_deneyimleri', []),
        gereksinimler.get('min_deneyim_yili'),
    )

    dil_puan, dil_uyumu = deterministic.dil_puani_hesapla(
        cv_verisi.get('yabanci_diller', []),
        gereksinimler.get('dil_gereksinimleri', []),
    )

    sertifika_puan = deterministic.sertifika_puani_hesapla(
        cv_verisi.get('sertifikalar', []),
        cv_verisi.get('projeler', []),
        gereksinimler.get('sertifika_gereksinimleri', []),
    )

    alt_puanlar_kismi = {
        "teknik": teknik_puan,
        "deneyim": deneyim_puan,
        "dil": dil_puan,
        "sertifika": sertifika_puan,
    }

    egitim_sonuc, hata = gemini_client.egitim_ve_anlatim_uret(
        cv_verisi, gereksinimler, alt_puanlar_kismi, eslesen_yetenekler, eksik_yetenekler,
        deneyim_uyumu, dil_uyumu,
    )
    if hata:
        return None, hata

    egitim_puan = egitim_sonuc.get('egitim_puan', 50)

    alt_puanlar = {
        "teknik": teknik_puan,
        "deneyim": deneyim_puan,
        "egitim": egitim_puan,
        "dil": dil_puan,
        "sertifika": sertifika_puan,
    }

    toplam_puan = sum(alt_puanlar[k] * aktif_agirliklar[k] for k in AGIRLIKLAR)

    sonuc = {
        "teknik_puan": teknik_puan,
        "deneyim_puan": deneyim_puan,
        "egitim_puan": egitim_puan,
        "dil_puan": dil_puan,
        "sertifika_puan": sertifika_puan,
        "uygunluk_nedeni": egitim_sonuc.get('uygunluk_nedeni', ''),
        "eslesen_yetenekler": eslesen_yetenekler,
        "eksik_yetenekler": eksik_yetenekler,
        "deneyim_uyumu": deneyim_uyumu,
        "egitim_uyumu": egitim_sonuc.get('egitim_uyumu', ''),
        "dil_uyumu": dil_uyumu,
        "guclu_yonler": egitim_sonuc.get('guclu_yonler', []),
        "gelistirilmesi_gerekenler": egitim_sonuc.get('gelistirilmesi_gerekenler', []),
        "tavsiyeler": egitim_sonuc.get('tavsiyeler', []),
        "uygunluk_skoru": round(toplam_puan),
        "alt_puanlar": alt_puanlar,
    }

    return sonuc, None
```

(Only the `def` line gained `agirliklar=None`, one new `aktif_agirliklar = ...` line was added, and the `toplam_puan` line now reads from `aktif_agirliklar` instead of `AGIRLIKLAR` — everything else is unchanged from Plan 2.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_scoring_hybrid_scorer.py -v`
Expected: PASS (6/6 — 4 from Plan 2 plus 2 new)

- [ ] **Step 5: Commit**

```bash
git add scoring/hybrid_scorer.py tests/test_scoring_hybrid_scorer.py
git commit -m "feat: allow ilani_karsilastir_hibrit to accept custom weights"
```

---

### Task 5: Read the current active weights

**Files:**
- Create: `learning/__init__.py` (empty)
- Create: `learning/reweighting.py`
- Test: `tests/test_learning_reweighting.py`

**Interfaces:**
- Consumes: `models.ScoringConfig` (Task 1).
- Produces: `learning.reweighting.guncel_agirliklari_al() -> dict | None` (returns `{"teknik": ..., "deneyim": ..., "egitim": ..., "dil": ..., "sertifika": ...}` from the highest-`id` `ScoringConfig` row, or `None` if the table is empty), `learning.reweighting.OZELLIK_SIRASI = ["teknik", "deneyim", "egitim", "dil", "sertifika"]`, `learning.reweighting.VARSAYILAN_AGIRLIKLAR` (the same 5 hardcoded defaults as `scoring.hybrid_scorer.AGIRLIKLAR`). Task 7 and Task 9 use `guncel_agirliklari_al`; Task 6/7 use `OZELLIK_SIRASI`.

- [ ] **Step 1: Create the package skeleton**

You are already on branch `feature/feedback-reweighting` (created in Task 1) — do not create a new branch.

```bash
mkdir -p learning
touch learning/__init__.py
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_learning_reweighting.py`:

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_learning_reweighting.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'learning.reweighting'`)

- [ ] **Step 4: Implement**

Create `learning/reweighting.py`:

```python
import models

OZELLIK_SIRASI = ["teknik", "deneyim", "egitim", "dil", "sertifika"]

VARSAYILAN_AGIRLIKLAR = {
    "teknik": 0.40,
    "deneyim": 0.25,
    "egitim": 0.15,
    "dil": 0.10,
    "sertifika": 0.10,
}


def guncel_agirliklari_al():
    kayit = models.ScoringConfig.query.order_by(models.ScoringConfig.id.desc()).first()
    if not kayit:
        return None
    return {ozellik: getattr(kayit, ozellik) for ozellik in OZELLIK_SIRASI}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_learning_reweighting.py -v`
Expected: PASS (2/2)

- [ ] **Step 6: Commit**

```bash
git add learning/__init__.py learning/reweighting.py tests/test_learning_reweighting.py
git commit -m "feat: add learning package, read current scoring weights"
```

---

### Task 6: Pure-Python logistic regression trainer

**Files:**
- Modify: `learning/reweighting.py` (append)
- Modify: `tests/test_learning_reweighting.py` (append)

**Interfaces:**
- Consumes: nothing from other modules — pure math over plain lists.
- Produces: `learning.reweighting._sigmoid(z: float) -> float` and `learning.reweighting._lojistik_regresyon_egit(X: list[list[float]], y: list[int], ogrenme_orani: float = 0.1, epoch_sayisi: int = 1000) -> list[float]` (returns one learned coefficient per feature column, same length/order as each row of `X` — Task 7 calls this with `X` columns ordered per `OZELLIK_SIRASI`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_learning_reweighting.py`:

```python
import math

from learning.reweighting import _sigmoid, _lojistik_regresyon_egit


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_learning_reweighting.py -v`
Expected: FAIL (`ImportError: cannot import name '_sigmoid'`)

- [ ] **Step 3: Implement**

Append to `learning/reweighting.py` (add `import math` at the top of the file first):

```python
def _sigmoid(z):
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    ez = math.exp(z)
    return ez / (1.0 + ez)


def _lojistik_regresyon_egit(X, y, ogrenme_orani=0.1, epoch_sayisi=1000):
    m = len(X)
    n = len(X[0])
    agirliklar = [0.0] * n
    bias = 0.0

    for _ in range(epoch_sayisi):
        tahminler = []
        for i in range(m):
            z = bias + sum(agirliklar[j] * X[i][j] for j in range(n))
            tahminler.append(_sigmoid(z))

        bias_gradyan = sum(tahminler[i] - y[i] for i in range(m)) / m
        bias -= ogrenme_orani * bias_gradyan

        for j in range(n):
            agirlik_gradyan = sum((tahminler[i] - y[i]) * X[i][j] for i in range(m)) / m
            agirliklar[j] -= ogrenme_orani * agirlik_gradyan

    return agirliklar
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_learning_reweighting.py -v`
Expected: PASS (6/6)

- [ ] **Step 5: Commit**

```bash
git add learning/reweighting.py tests/test_learning_reweighting.py
git commit -m "feat: add pure-Python logistic regression trainer"
```

---

### Task 7: Retrain orchestration (`yeniden_egit`)

**Files:**
- Modify: `learning/reweighting.py` (append)
- Modify: `tests/test_learning_reweighting.py` (append)

**Interfaces:**
- Consumes: `models.Geribildirim`, `models.Eslesme` (Task 1), `_lojistik_regresyon_egit` (Task 6), `OZELLIK_SIRASI`, `VARSAYILAN_AGIRLIKLAR` (Task 5).
- Produces: `learning.reweighting.yeniden_egit() -> tuple[dict | None, str | None]` and constants `learning.reweighting.MIN_TOPLAM_ORNEK = 40`, `learning.reweighting.MIN_SINIF_ORNEK = 10` — Task 9's admin route calls `yeniden_egit()` directly and reads the two threshold constants for its UI copy.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_learning_reweighting.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_learning_reweighting.py -v`
Expected: FAIL (`ImportError: cannot import name 'yeniden_egit'`)

- [ ] **Step 3: Implement**

Append to `learning/reweighting.py` (add `from extensions import db` to the top of the file, alongside the existing `import models`):

```python
MIN_TOPLAM_ORNEK = 40
MIN_SINIF_ORNEK = 10


def yeniden_egit():
    geribildirimler = models.Geribildirim.query.all()

    X = []
    y = []
    for gb in geribildirimler:
        eslesme = models.Eslesme.query.get(gb.eslesme_id)
        if not eslesme or not eslesme.analiz_sonucu:
            continue
        alt_puanlar = eslesme.analiz_sonucu.get('alt_puanlar')
        if not alt_puanlar:
            continue
        try:
            ozellikler = [alt_puanlar[ozellik] / 100.0 for ozellik in OZELLIK_SIRASI]
        except (KeyError, TypeError):
            continue
        X.append(ozellikler)
        y.append(1 if gb.deger == 'olumlu' else 0)

    toplam = len(y)
    olumlu_sayisi = sum(y)
    olumsuz_sayisi = toplam - olumlu_sayisi

    if toplam < MIN_TOPLAM_ORNEK or olumlu_sayisi < MIN_SINIF_ORNEK or olumsuz_sayisi < MIN_SINIF_ORNEK:
        return None, f"Yetersiz veri ({toplam}/{MIN_TOPLAM_ORNEK})"

    agirliklar_ham = _lojistik_regresyon_egit(X, y)
    mutlak_degerler = [abs(w) for w in agirliklar_ham]
    toplam_mutlak = sum(mutlak_degerler)

    if toplam_mutlak == 0:
        normalize_edilmis = [VARSAYILAN_AGIRLIKLAR[ozellik] for ozellik in OZELLIK_SIRASI]
    else:
        normalize_edilmis = [w / toplam_mutlak for w in mutlak_degerler]

    yeni_agirliklar = dict(zip(OZELLIK_SIRASI, normalize_edilmis))

    kayit = models.ScoringConfig(
        teknik=yeni_agirliklar['teknik'],
        deneyim=yeni_agirliklar['deneyim'],
        egitim=yeni_agirliklar['egitim'],
        dil=yeni_agirliklar['dil'],
        sertifika=yeni_agirliklar['sertifika'],
        ornek_sayisi=toplam,
    )
    db.session.add(kayit)
    db.session.commit()

    return yeni_agirliklar, None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_learning_reweighting.py -v`
Expected: PASS (8/8)

- [ ] **Step 5: Commit**

```bash
git add learning/reweighting.py tests/test_learning_reweighting.py
git commit -m "feat: add feedback-driven weight retraining"
```

---

### Task 8: Wire current weights into app.py's scoring call sites

**Files:**
- Modify: `app.py` (imports + both `ilani_karsilastir_hibrit` call sites)
- Test: `tests/test_app_analiz.py` (append)

**Interfaces:**
- Consumes: `learning.reweighting.guncel_agirliklari_al()` (Task 5), `scoring.hybrid_scorer.ilani_karsilastir_hibrit(..., agirliklar=...)` (Task 4).
- Produces: nothing new for later tasks — this is the production cutover for weight injection.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_app_analiz.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_app_analiz.py::test_tekil_analiz_passes_current_weights_to_hybrid_scorer -v`
Expected: FAIL (`AttributeError: module 'app' has no attribute 'learning'`, since `app.py` doesn't call `guncel_agirliklari_al` yet)

- [ ] **Step 3: Implement — app.py imports**

In `app.py`, after the existing `import scoring.hybrid_scorer` line, add:

```python
import learning.reweighting
```

- [ ] **Step 4: Implement — app.py call sites**

In `app.py`'s `tekil_analiz` route, replace:

```python
        sonuc, err = scoring.hybrid_scorer.ilani_karsilastir_hibrit(cv.cikarilan_veriler, metin)
```

with:

```python
        agirliklar = learning.reweighting.guncel_agirliklari_al()
        sonuc, err = scoring.hybrid_scorer.ilani_karsilastir_hibrit(cv.cikarilan_veriler, metin, agirliklar=agirliklar)
```

In `app.py`'s `_tek_ilan_analiz_et` helper, replace:

```python
            sonuc, err = scoring.hybrid_scorer.ilani_karsilastir_hibrit(cv_verisi, metin)
```

with:

```python
            agirliklar = learning.reweighting.guncel_agirliklari_al()
            sonuc, err = scoring.hybrid_scorer.ilani_karsilastir_hibrit(cv_verisi, metin, agirliklar=agirliklar)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_app_analiz.py -v`
Expected: PASS (all tests in file, including the new one)

- [ ] **Step 6: Run the full test suite to check for regressions**

Run: `python -m pytest -v`
Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add app.py tests/test_app_analiz.py
git commit -m "feat: inject current scoring weights into both analiz call sites"
```

---

### Task 9: Admin panel for weight retraining

**Files:**
- Modify: `app.py` (new route, `login()` route)
- Create: `templates/admin_agirliklar.html`
- Modify: `templates/base.html` (nav link)
- Test: `tests/test_app_admin_agirliklar.py`

**Interfaces:**
- Consumes: `learning.reweighting.guncel_agirliklari_al`, `learning.reweighting.yeniden_egit`, `learning.reweighting.VARSAYILAN_AGIRLIKLAR`, `learning.reweighting.MIN_TOPLAM_ORNEK` (Tasks 5, 7).
- Produces: route `admin_agirliklar` at `GET/POST /admin/agirliklar` — nothing else in this plan depends on it.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_app_admin_agirliklar.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_app_admin_agirliklar.py -v`
Expected: FAIL (404, route doesn't exist yet)

- [ ] **Step 3: Implement — session role at login**

In `app.py`'s `login()` route, replace:

```python
        if user and check_password_hash(user.parola, parola):
            session.permanent = True
            session['user_id'] = user.id
            logger.info(f"Kullanici girisi: {email}")
            return redirect(url_for('panel'))
```

with:

```python
        if user and check_password_hash(user.parola, parola):
            session.permanent = True
            session['user_id'] = user.id
            session['rol'] = user.rol
            logger.info(f"Kullanici girisi: {email}")
            return redirect(url_for('panel'))
```

- [ ] **Step 4: Implement — admin route**

In `app.py`, add this route after `_tek_ilan_analiz_et` and before `/toplu-analiz` (or anywhere else at module level after the imports):

```python
@app.route('/admin/agirliklar', methods=['GET', 'POST'])
def admin_agirliklar():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    kullanici = models.Kullanici.query.get(session['user_id'])
    if not kullanici or kullanici.rol != 'admin':
        abort(403)

    if request.method == 'POST':
        yeni_agirliklar, hata = learning.reweighting.yeniden_egit()
        if hata:
            flash(hata, 'warning')
        else:
            flash(f"Ağırlıklar güncellendi: {yeni_agirliklar}", 'success')
        return redirect(url_for('admin_agirliklar'))

    mevcut_agirliklar = learning.reweighting.guncel_agirliklari_al() or learning.reweighting.VARSAYILAN_AGIRLIKLAR
    toplam_geribildirim = models.Geribildirim.query.count()
    olumlu_sayisi = models.Geribildirim.query.filter_by(deger='olumlu').count()
    olumsuz_sayisi = models.Geribildirim.query.filter_by(deger='olumsuz').count()

    return render_template(
        'admin_agirliklar.html',
        agirliklar=mevcut_agirliklar,
        toplam=toplam_geribildirim,
        olumlu=olumlu_sayisi,
        olumsuz=olumsuz_sayisi,
        esik=learning.reweighting.MIN_TOPLAM_ORNEK,
    )
```

- [ ] **Step 5: Implement — admin template**

Create `templates/admin_agirliklar.html`:

```html
{% extends 'base.html' %}

{% block content %}
<div class="container mt-4">
    <h2 class="mb-4">⚙️ Skorlama Ağırlıkları</h2>

    <div class="card shadow-sm border-0 p-4 mb-4">
        <h5 class="mb-3">Mevcut Ağırlıklar</h5>
        <table class="table table-sm">
            <tr><td>Teknik</td><td>{{ "%.2f"|format(agirliklar.teknik) }}</td></tr>
            <tr><td>Deneyim</td><td>{{ "%.2f"|format(agirliklar.deneyim) }}</td></tr>
            <tr><td>Eğitim</td><td>{{ "%.2f"|format(agirliklar.egitim) }}</td></tr>
            <tr><td>Dil</td><td>{{ "%.2f"|format(agirliklar.dil) }}</td></tr>
            <tr><td>Sertifika</td><td>{{ "%.2f"|format(agirliklar.sertifika) }}</td></tr>
        </table>
    </div>

    <div class="card shadow-sm border-0 p-4">
        <h5 class="mb-3">Geri Bildirim Durumu</h5>
        <p>Toplam: <strong>{{ toplam }}</strong> / Gereken: <strong>{{ esik }}</strong></p>
        <p>👍 Olumlu: <strong>{{ olumlu }}</strong> &nbsp; 👎 Olumsuz: <strong>{{ olumsuz }}</strong></p>

        <form method="POST">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
            <button type="submit" class="btn btn-primary">Ağırlıkları Yeniden Eğit</button>
        </form>
    </div>
</div>
{% endblock %}
```

- [ ] **Step 6: Implement — admin nav link**

In `templates/base.html`, inside the `{% if session.user_id %}` block, add a new `<li>` right after the "Havuz" nav-item (line 119) and before the logout button item:

```html
                        <li class="nav-item"><a class="nav-link" href="{{ url_for('kaydedilenler') }}"><i class="fas fa-bookmark me-1"></i> Havuz</a></li>
                        {% if session.rol == 'admin' %}
                        <li class="nav-item"><a class="nav-link" href="{{ url_for('admin_agirliklar') }}"><i class="fas fa-sliders-h me-1"></i> Ağırlıklar</a></li>
                        {% endif %}
                        <li class="nav-item ms-2">
                            <a class="btn btn-outline-light btn-sm px-3 rounded-pill" href="{{ url_for('logout') }}">Çıkış Yap</a>
                        </li>
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python -m pytest tests/test_app_admin_agirliklar.py -v`
Expected: PASS (4/4)

- [ ] **Step 8: Run the full test suite**

Run: `python -m pytest -v`
Expected: all tests pass

- [ ] **Step 9: Commit**

```bash
git add app.py templates/admin_agirliklar.html templates/base.html tests/test_app_admin_agirliklar.py
git commit -m "feat: add admin panel for weight retraining"
```

---

## Notes for the final review

- After Task 9, run `python -m pytest -v` once more for the complete suite, then follow `superpowers:subagent-driven-development`'s final whole-branch review step (dispatch on the most capable available model) before `superpowers:finishing-a-development-branch`.
- Check `git status` for a dirty `proje.db` before generating any review diff/package; restore with `git checkout -- proje.db` if needed.
- To actually use this feature against the real dev database, the two new tables (`geribildirim`, `scoring_config`) need to exist in `proje.db` — run `db.create_all()` once in an app context (it only creates missing tables, never touches `kullanici`/`cv`/`is_ilani`/`eslesme`). Not part of any task here; a one-off operational step for whoever deploys this.
- To promote a user to admin so they can see the `/admin/agirliklar` panel, run a one-off SQL statement against `proje.db`, e.g.: `UPDATE kullanici SET rol='admin' WHERE email='...';`. There is no self-service UI for this by design (matches the spec's scope discipline).
