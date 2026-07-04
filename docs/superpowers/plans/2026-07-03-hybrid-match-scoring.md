# Hybrid Deterministic+LLM Match Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `functions.py:ilani_karsilastir()`'s fully-LLM CV↔job scoring with a hybrid pipeline: one LLM call extracts structured job requirements, four sub-scores (teknik, deneyim, dil, sertifika — ~85% of the weight) are computed deterministically in Python, and only `egitim_puan` plus the narrative text fields stay LLM-judged.

**Architecture:** New `scoring/` package with three modules — `gemini_client.py` (all Gemini API calls: embeddings, requirement extraction, education+narrative judgment), `deterministic.py` (pure-Python sub-score math: cosine similarity, date-math experience calculation, language-level lookup, certificate counting), and `hybrid_scorer.py` (orchestrator that combines both into the same result contract the old `ilani_karsilastir` produced). `app.py` is rewired to call the new orchestrator directly at both existing call sites, and the old `functions.py:ilani_karsilastir()` is deleted. `functions.py:url_den_ilan_cek()` is separately upgraded from raw `BeautifulSoup.get_text()` to `trafilatura` for cleaner extracted job text.

**Tech Stack:** Python 3.14, Flask, `requests` (existing), Gemini `text-embedding-004` embedding endpoint, `trafilatura` (new dependency), pytest + `unittest.mock.patch`.

## Global Constraints

- This is Plan 2 of the 3-plan rollout in `docs/superpowers/specs/2026-07-02-modular-scraping-engine-design.md` (section 4). Plan 3 (feedback/reweighting) is explicitly out of scope for this plan.
- **No numpy.** Verified directly on this environment: `python -c "import numpy"` segfaults (`Segmentation fault`, MINGW-W64 build warning) on this Windows/Python 3.14 setup. Cosine similarity must be pure Python (`math.sqrt`).
- **Result contract is fixed.** `ilani_karsilastir_hibrit(cv_verisi, ilan_metni)` must return `(sonuc, hata)` where `sonuc` contains exactly these keys, matching the old `ilani_karsilastir`: `teknik_puan, deneyim_puan, egitim_puan, dil_puan, sertifika_puan, uygunluk_nedeni, eslesen_yetenekler, eksik_yetenekler, deneyim_uyumu, egitim_uyumu, dil_uyumu, guclu_yonler, gelistirilmesi_gerekenler, tavsiyeler, uygunluk_skoru, alt_puanlar`. `alt_puanlar` must be `{teknik, deneyim, egitim, dil, sertifika}` — `app.py:297,336` reads `sonuc.get('uygunluk_skoru', 0)` and stores the whole dict; `templates/kaydedilenler.html:79,102-108` reads `analiz.get('alt_puanlar', {})` and its five sub-keys.
- **Weights (verbatim from the original hardcoded values, sum to 1.0):** teknik 0.40, deneyim 0.25, egitim 0.15, dil 0.10, sertifika 0.10.
- **Reuse, don't duplicate.** `scoring/gemini_client.py` must import and reuse `functions.API_KEY` and `functions._gemini_istegi_gonder` for all `generateContent`-style calls (retry-across-models JSON helper) — do not re-implement that retry loop.
- **Naming convention:** this package extends `functions.py`'s scoring domain, not the `scrapers/` package's domain — use Turkish function/variable names matching `functions.py` (`ilani_karsilastir_hibrit`, `teknik_puani_hesapla`, etc.), not English names.
- **Mock at point-of-use**, matching the existing test suite's pattern (e.g. `@patch("scrapers.remoteok.requests.get")`): patch `scoring.gemini_client.requests.post`, `scoring.gemini_client._gemini_istegi_gonder`, `scoring.hybrid_scorer.gemini_client`, `scoring.hybrid_scorer.deterministic`, `app.scoring.hybrid_scorer.ilani_karsilastir_hibrit`, `functions.trafilatura.fetch_url` / `functions.trafilatura.extract` as appropriate per task.
- **Builtin `ConnectionError` vs `requests.exceptions.ConnectionError`:** any test simulating a network failure via `side_effect` MUST use `requests.exceptions.ConnectionError`, not the builtin `ConnectionError` — the builtin is not a subclass of `requests.RequestException`, which is what production code catches. (This exact bug bit two tasks in Plan 1.)
- `proje.db` must not be modified — restore with `git checkout -- proje.db` if `git status` shows it dirty after running tests.
- Branch: plain feature branch `feature/hybrid-match-scoring` off `main` (no git worktree — matches the choice made for Plan 1).
- New dependency: add `trafilatura>=1.6.0` to `requirements.txt` under a new `# Metin Cikarma` (or similar) heading, and `pip install` it before running any test that imports it.

---

### Task 1: Branch, package skeleton, and Gemini embedding call

**Files:**
- Create: `scoring/__init__.py` (empty)
- Create: `scoring/gemini_client.py`
- Test: `tests/test_scoring_gemini_client.py`

**Interfaces:**
- Consumes: `functions.API_KEY` (module-level constant), nothing else yet.
- Produces: `scoring.gemini_client._gemini_gomlemesi_al(metin: str) -> list[float] | None` — later tasks (Task 2's `teknik_puani_hesapla`, via Task 7's orchestrator) pass this function in as the `gomme_al` callable.

- [ ] **Step 1: Create the branch**

```bash
git checkout main
git pull
git checkout -b feature/hybrid-match-scoring
```

- [ ] **Step 2: Create the package skeleton**

```bash
mkdir -p scoring
touch scoring/__init__.py
```

- [ ] **Step 3: Write the failing tests**

Create `tests/test_scoring_gemini_client.py`:

```python
from unittest.mock import patch, MagicMock

import requests

from scoring import gemini_client


def _mock_response(status=200, body=None):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = body or {}
    return resp


@patch("scoring.gemini_client.requests.post")
def test_gomlemesi_al_returns_vector_on_success(mock_post):
    mock_post.return_value = _mock_response(200, {"embedding": {"values": [0.1, 0.2, 0.3]}})
    sonuc = gemini_client._gemini_gomlemesi_al("Python")
    assert sonuc == [0.1, 0.2, 0.3]


@patch("scoring.gemini_client.requests.post")
def test_gomlemesi_al_returns_none_on_non_200(mock_post):
    mock_post.return_value = _mock_response(500, {})
    assert gemini_client._gemini_gomlemesi_al("Python") is None


@patch("scoring.gemini_client.requests.post")
def test_gomlemesi_al_returns_none_on_request_exception(mock_post):
    mock_post.side_effect = requests.exceptions.ConnectionError("boom")
    assert gemini_client._gemini_gomlemesi_al("Python") is None


def test_gomlemesi_al_returns_none_for_empty_text():
    assert gemini_client._gemini_gomlemesi_al("") is None
    assert gemini_client._gemini_gomlemesi_al("   ") is None
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `python -m pytest tests/test_scoring_gemini_client.py -v`
Expected: FAIL (`ModuleNotFoundError` or `AttributeError` — `scoring.gemini_client` / `_gemini_gomlemesi_al` don't exist yet)

- [ ] **Step 5: Implement**

Create `scoring/gemini_client.py`:

```python
import json
import logging

import requests

from functions import API_KEY, _gemini_istegi_gonder

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-004"


def _gemini_gomlemesi_al(metin):
    if not metin or not metin.strip():
        return None
    try:
        api_url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{EMBEDDING_MODEL}:embedContent?key={API_KEY}"
        )
        payload = {
            "model": f"models/{EMBEDDING_MODEL}",
            "content": {"parts": [{"text": metin}]},
        }
        response = requests.post(
            api_url,
            headers={'Content-Type': 'application/json'},
            data=json.dumps(payload),
            timeout=10,
        )
        if response.status_code != 200:
            logger.warning(f"Embedding istegi basarisiz: {response.status_code}")
            return None
        return response.json().get('embedding', {}).get('values')
    except requests.RequestException as e:
        logger.warning(f"Embedding istegi hata: {e}")
        return None
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_scoring_gemini_client.py -v`
Expected: PASS (4/4)

- [ ] **Step 7: Commit**

```bash
git add scoring/__init__.py scoring/gemini_client.py tests/test_scoring_gemini_client.py
git commit -m "feat: add scoring package with Gemini embedding call"
```

---

### Task 2: Deterministic technical-skill score (embedding similarity)

**Files:**
- Create: `scoring/deterministic.py`
- Test: `tests/test_scoring_deterministic.py`

**Interfaces:**
- Consumes: nothing from other scoring modules — `teknik_puani_hesapla` takes an injected `gomme_al` callable (matching `scoring.gemini_client._gemini_gomlemesi_al`'s signature: `str -> list[float] | None`), so this file has zero import dependency on `gemini_client`.
- Produces: `scoring.deterministic.kosinus_benzerligi(vec_a: list[float], vec_b: list[float]) -> float` and `scoring.deterministic.teknik_puani_hesapla(aday_yetenekleri: list[str], gereken_yetenekler: list[str], gomme_al: Callable[[str], list[float] | None]) -> tuple[int, list[str], list[str]]` (puan, eslesen_yetenekler, eksik_yetenekler) — Task 7 wires this to `gemini_client._gemini_gomlemesi_al`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_scoring_deterministic.py`:

```python
import math

from scoring.deterministic import kosinus_benzerligi, teknik_puani_hesapla


def test_kosinus_benzerligi_identical_vectors_is_one():
    assert math.isclose(kosinus_benzerligi([1.0, 0.0], [1.0, 0.0]), 1.0)


def test_kosinus_benzerligi_orthogonal_vectors_is_zero():
    assert math.isclose(kosinus_benzerligi([1.0, 0.0], [0.0, 1.0]), 0.0)


def test_kosinus_benzerligi_empty_vector_returns_zero():
    assert kosinus_benzerligi([], [1.0, 0.0]) == 0.0
    assert kosinus_benzerligi([1.0, 0.0], []) == 0.0


def test_teknik_puani_tam_eslesme():
    vektorler = {"Python": [1.0, 0.0]}
    puan, eslesen, eksik = teknik_puani_hesapla(["Python"], ["Python"], vektorler.get)
    assert puan == 100
    assert eslesen == ["Python"]
    assert eksik == []


def test_teknik_puani_benzer_teknoloji_yarim_puan():
    vektorler = {"React": [1.0, 0.0], "Vue": [0.75, 0.6614378277661477]}
    puan, eslesen, eksik = teknik_puani_hesapla(["Vue"], ["React"], vektorler.get)
    assert puan == 50
    assert eslesen == ["React"]
    assert eksik == []


def test_teknik_puani_eslesmeyen_yetenek():
    vektorler = {"React": [1.0, 0.0], "Excel": [0.0, 1.0]}
    puan, eslesen, eksik = teknik_puani_hesapla(["Excel"], ["React"], vektorler.get)
    assert puan == 0
    assert eslesen == []
    assert eksik == ["React"]


def test_teknik_puani_bos_gereken_liste_elli_puan():
    puan, eslesen, eksik = teknik_puani_hesapla(["Python"], [], lambda t: [1.0, 0.0])
    assert puan == 50
    assert eslesen == []
    assert eksik == []


def test_teknik_puani_gomme_basarisiz_olursa_eksige_dusuyor():
    puan, eslesen, eksik = teknik_puani_hesapla(["Python"], ["React"], lambda t: None)
    assert puan == 0
    assert eksik == ["React"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_scoring_deterministic.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'scoring.deterministic'`)

- [ ] **Step 3: Implement**

Create `scoring/deterministic.py`:

```python
import math

TEKNIK_TAM_ESLESME_ESIGI = 0.85
TEKNIK_BENZER_ESIGI = 0.65


def kosinus_benzerligi(vec_a, vec_b):
    if not vec_a or not vec_b:
        return 0.0
    nokta_carpimi = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return nokta_carpimi / (norm_a * norm_b)


def teknik_puani_hesapla(aday_yetenekleri, gereken_yetenekler, gomme_al):
    if not gereken_yetenekler:
        return 50, [], []

    aday_gommeleri = {yetenek: gomme_al(yetenek) for yetenek in aday_yetenekleri}

    eslesen = []
    eksik = []
    toplam_kredi = 0.0

    for gereken in gereken_yetenekler:
        gereken_gomme = gomme_al(gereken)
        en_iyi_benzerlik = 0.0
        if gereken_gomme:
            for aday_gomme in aday_gommeleri.values():
                if not aday_gomme:
                    continue
                benzerlik = kosinus_benzerligi(gereken_gomme, aday_gomme)
                if benzerlik > en_iyi_benzerlik:
                    en_iyi_benzerlik = benzerlik

        if en_iyi_benzerlik >= TEKNIK_TAM_ESLESME_ESIGI:
            toplam_kredi += 1.0
            eslesen.append(gereken)
        elif en_iyi_benzerlik >= TEKNIK_BENZER_ESIGI:
            toplam_kredi += 0.5
            eslesen.append(gereken)
        else:
            eksik.append(gereken)

    puan = round(min(100, (toplam_kredi / len(gereken_yetenekler)) * 100))
    return puan, eslesen, eksik
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_scoring_deterministic.py -v`
Expected: PASS (8/8)

- [ ] **Step 5: Commit**

```bash
git add scoring/deterministic.py tests/test_scoring_deterministic.py
git commit -m "feat: add cosine-similarity technical skill scoring"
```

---

### Task 3: Deterministic experience score (Turkish date parsing)

**Files:**
- Modify: `scoring/deterministic.py` (append)
- Modify: `tests/test_scoring_deterministic.py` (append)

**Interfaces:**
- Consumes: nothing new.
- Produces: `scoring.deterministic._tarihi_parse_et(tarih_metni: str) -> datetime | None` and `scoring.deterministic.deneyim_puani_hesapla(is_deneyimleri: list[dict], min_deneyim_yili: float | None) -> tuple[int, str]` (puan, deneyim_uyumu). Each `is_deneyimleri` item is a dict with string keys `baslangic_tarihi`, `bitis_tarihi` (matches `functions.py:93-99`'s CV extraction schema).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_scoring_deterministic.py`:

```python
from datetime import datetime, timedelta

from scoring.deterministic import deneyim_puani_hesapla, _tarihi_parse_et


def test_tarihi_parse_et_turkce_ay_ismi():
    assert _tarihi_parse_et("Ocak 2020") == datetime(2020, 1, 1)


def test_tarihi_parse_et_halen_bugunu_dondurur():
    sonuc = _tarihi_parse_et("Halen")
    assert (datetime.now() - sonuc).total_seconds() < 5


def test_tarihi_parse_et_sadece_yil():
    assert _tarihi_parse_et("2019") == datetime(2019, 1, 1)


def test_tarihi_parse_et_sayisal_ay_yil():
    assert _tarihi_parse_et("03/2021") == datetime(2021, 3, 1)


def test_tarihi_parse_et_parse_edilemeyen_metin_none_doner():
    assert _tarihi_parse_et("bilinmiyor") is None


def test_deneyim_puani_min_deneyim_belirtilmemisse_elli_doner():
    puan, uyum = deneyim_puani_hesapla([], None)
    assert puan == 50


def test_deneyim_puani_tam_uyum():
    is_deneyimleri = [{"baslangic_tarihi": "Ocak 2020", "bitis_tarihi": "Ocak 2023"}]
    puan, uyum = deneyim_puani_hesapla(is_deneyimleri, 3)
    assert puan == 100


def test_deneyim_puani_eksik_deneyim():
    is_deneyimleri = [{"baslangic_tarihi": "Ocak 2022", "bitis_tarihi": "Ocak 2023"}]
    puan, uyum = deneyim_puani_hesapla(is_deneyimleri, 5)
    assert puan == 20


def test_deneyim_puani_halen_devam_eden_is():
    uc_yil_once = (datetime.now() - timedelta(days=3 * 365)).strftime("%m/%Y")
    is_deneyimleri = [{"baslangic_tarihi": uc_yil_once, "bitis_tarihi": "Halen"}]
    puan, uyum = deneyim_puani_hesapla(is_deneyimleri, 3)
    assert puan >= 95


def test_deneyim_puani_parse_edilemeyen_kayit_atlanir():
    is_deneyimleri = [{"baslangic_tarihi": "bilinmiyor", "bitis_tarihi": "bilinmiyor"}]
    puan, uyum = deneyim_puani_hesapla(is_deneyimleri, 3)
    assert puan == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_scoring_deterministic.py -v`
Expected: FAIL (`ImportError: cannot import name 'deneyim_puani_hesapla'`)

- [ ] **Step 3: Implement**

Append to `scoring/deterministic.py`:

```python
import re
from datetime import datetime

AY_ISIMLERI = {
    "ocak": 1, "şubat": 2, "subat": 2, "mart": 3, "nisan": 4,
    "mayıs": 5, "mayis": 5, "haziran": 6, "temmuz": 7,
    "ağustos": 8, "agustos": 8, "eylül": 9, "eylul": 9,
    "ekim": 10, "kasım": 11, "kasim": 11, "aralık": 12, "aralik": 12,
}

DEVAM_EDEN_ANAHTAR_KELIMELER = {"halen", "günümüz", "gunumuz", "devam", "present", "current", "now"}


def _tarihi_parse_et(tarih_metni):
    if not tarih_metni:
        return None
    metin = tarih_metni.strip().lower()
    if any(kelime in metin for kelime in DEVAM_EDEN_ANAHTAR_KELIMELER):
        return datetime.now()

    ay_pattern = "|".join(AY_ISIMLERI.keys())
    eslesme = re.search(rf"({ay_pattern})\s+(\d{{4}})", metin)
    if eslesme:
        ay = AY_ISIMLERI[eslesme.group(1)]
        yil = int(eslesme.group(2))
        return datetime(yil, ay, 1)

    eslesme = re.search(r"(\d{1,2})[./](\d{4})", metin)
    if eslesme:
        ay = int(eslesme.group(1))
        yil = int(eslesme.group(2))
        if 1 <= ay <= 12:
            return datetime(yil, ay, 1)

    eslesme = re.search(r"\b(\d{4})\b", metin)
    if eslesme:
        return datetime(int(eslesme.group(1)), 1, 1)

    return None


def deneyim_puani_hesapla(is_deneyimleri, min_deneyim_yili):
    if not min_deneyim_yili:
        return 50, "Deneyim gereksinimi belirtilmemiş"

    # Örtüşen iş deneyimleri (aynı döneme ait iki kayıt) toplamda ayrı ayrı
    # sayılır — kasıtlı basitleştirme, kapsam dışı.
    toplam_gun = 0
    for deneyim in (is_deneyimleri or []):
        baslangic = _tarihi_parse_et(deneyim.get('baslangic_tarihi'))
        bitis = _tarihi_parse_et(deneyim.get('bitis_tarihi'))
        if not baslangic:
            continue
        if not bitis or bitis < baslangic:
            bitis = datetime.now()
        toplam_gun += (bitis - baslangic).days

    toplam_yil = toplam_gun / 365.25
    puan = round(min(100, (toplam_yil / min_deneyim_yili) * 100))
    uyum = f"{toplam_yil:.1f} yıl deneyim (istenen: {min_deneyim_yili} yıl)"
    return puan, uyum
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_scoring_deterministic.py -v`
Expected: PASS (18/18)

- [ ] **Step 5: Commit**

```bash
git add scoring/deterministic.py tests/test_scoring_deterministic.py
git commit -m "feat: add date-math experience scoring"
```

---

### Task 4: Deterministic language and certificate scores

**Files:**
- Modify: `scoring/deterministic.py` (append)
- Modify: `tests/test_scoring_deterministic.py` (append)

**Interfaces:**
- Consumes: nothing new.
- Produces: `scoring.deterministic.dil_puani_hesapla(yabanci_diller: list[dict], dil_gereksinimleri: list[dict]) -> tuple[int, str]` (puan, dil_uyumu) — `yabanci_diller` items have `dil`/`seviye` keys (matches `functions.py:100-103`), `dil_gereksinimleri` items have `dil`/`min_seviye` keys (matches Task 5's extraction schema). `scoring.deterministic.sertifika_puani_hesapla(sertifikalar: list[dict], projeler: list, sertifika_gereksinimleri: list[str]) -> int`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_scoring_deterministic.py`:

```python
from scoring.deterministic import dil_puani_hesapla, sertifika_puani_hesapla


def test_dil_puani_gereksinim_yoksa_yuz_doner():
    puan, uyum = dil_puani_hesapla([{"dil": "İngilizce", "seviye": "Orta"}], [])
    assert puan == 100


def test_dil_puani_tam_uyum():
    aday = [{"dil": "İngilizce", "seviye": "İleri"}]
    gereksinim = [{"dil": "İngilizce", "min_seviye": "İleri"}]
    puan, uyum = dil_puani_hesapla(aday, gereksinim)
    assert puan == 100


def test_dil_puani_bir_seviye_dusuk():
    aday = [{"dil": "İngilizce", "seviye": "Orta"}]
    gereksinim = [{"dil": "İngilizce", "min_seviye": "İleri"}]
    puan, uyum = dil_puani_hesapla(aday, gereksinim)
    assert puan == 65


def test_dil_puani_iki_seviye_dusuk():
    aday = [{"dil": "İngilizce", "seviye": "Başlangıç"}]
    gereksinim = [{"dil": "İngilizce", "min_seviye": "Ana dil"}]
    puan, uyum = dil_puani_hesapla(aday, gereksinim)
    assert puan == 35


def test_dil_puani_dil_yoksa_sifir():
    puan, uyum = dil_puani_hesapla([], [{"dil": "Almanca", "min_seviye": "Orta"}])
    assert puan == 0


def test_sertifika_puani_gereksinim_yoksa_sayima_gore():
    puan = sertifika_puani_hesapla([{"sertifika_adi": "AWS"}, {"sertifika_adi": "Azure"}], [], [])
    assert puan == 60


def test_sertifika_puani_proje_bonusu():
    puan = sertifika_puani_hesapla([], [{"proje_adi": "X"}], [])
    assert puan == 60


def test_sertifika_puani_gereksinim_eslesirse():
    sertifikalar = [{"sertifika_adi": "AWS Certified Solutions Architect"}]
    puan = sertifika_puani_hesapla(sertifikalar, [], ["AWS"])
    assert puan == 100


def test_sertifika_puani_hicbiri_yoksa_baseline():
    puan = sertifika_puani_hesapla([], [], [])
    assert puan == 40
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_scoring_deterministic.py -v`
Expected: FAIL (`ImportError: cannot import name 'dil_puani_hesapla'`)

- [ ] **Step 3: Implement**

Append to `scoring/deterministic.py`:

```python
DIL_SEVIYE_SIRASI = {
    "başlangıç": 1, "baslangic": 1, "temel": 1,
    "orta": 2,
    "ileri": 3, "i̇leri": 3,
    "ana dil": 4, "anadil": 4, "native": 4, "fluent": 4, "akıcı": 4, "akici": 4,
}


def _seviye_numarasi(seviye_metni):
    if not seviye_metni:
        return 0
    return DIL_SEVIYE_SIRASI.get(seviye_metni.strip().lower(), 0)


def dil_puani_hesapla(yabanci_diller, dil_gereksinimleri):
    if not dil_gereksinimleri:
        return 100, "Dil gereksinimi belirtilmemiş"

    aday_dilleri = {
        d.get('dil', '').strip().lower(): _seviye_numarasi(d.get('seviye'))
        for d in (yabanci_diller or [])
    }

    puanlar = []
    uyum_parcalari = []
    for gereksinim in dil_gereksinimleri:
        gereken_dil = gereksinim.get('dil', '').strip().lower()
        gereken_seviye = _seviye_numarasi(gereksinim.get('min_seviye'))
        aday_seviye = aday_dilleri.get(gereken_dil, 0)

        if aday_seviye == 0:
            puan = 0
        elif aday_seviye >= gereken_seviye:
            puan = 100
        elif aday_seviye == gereken_seviye - 1:
            puan = 65
        else:
            puan = 35

        puanlar.append(puan)
        uyum_parcalari.append(f"{gereksinim.get('dil', '?')}: {puan}")

    ortalama = round(sum(puanlar) / len(puanlar))
    return ortalama, ", ".join(uyum_parcalari)


def sertifika_puani_hesapla(sertifikalar, projeler, sertifika_gereksinimleri):
    sertifikalar = sertifikalar or []
    aday_sertifika_adlari = [s.get('sertifika_adi', '').strip().lower() for s in sertifikalar]

    if sertifika_gereksinimleri:
        eslesen_sayisi = 0
        for gereken in sertifika_gereksinimleri:
            gereken_kucuk = gereken.strip().lower()
            if any(
                gereken_kucuk in aday or aday in gereken_kucuk
                for aday in aday_sertifika_adlari if aday
            ):
                eslesen_sayisi += 1
        puan = (eslesen_sayisi / len(sertifika_gereksinimleri)) * 80 + 20
    else:
        puan = 40 + min(40, len(sertifikalar) * 10)

    if projeler:
        puan += 20

    return round(min(100, max(0, puan)))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_scoring_deterministic.py -v`
Expected: PASS (27/27)

- [ ] **Step 5: Commit**

```bash
git add scoring/deterministic.py tests/test_scoring_deterministic.py
git commit -m "feat: add language and certificate scoring"
```

---

### Task 5: LLM job-requirement extraction

**Files:**
- Modify: `scoring/gemini_client.py` (append)
- Modify: `tests/test_scoring_gemini_client.py` (append)

**Interfaces:**
- Consumes: `functions._gemini_istegi_gonder(icerik, talimat, sema, temperature=0.3) -> tuple[dict | None, str | None]` (already imported in Task 1).
- Produces: `scoring.gemini_client.gereksinimleri_cikar(ilan_metni: str) -> tuple[dict | None, str | None]`. Success dict has keys `gereken_yetenekler: list[str]`, `min_deneyim_yili: float | None`, `egitim_gereksinimi: str`, `dil_gereksinimleri: list[{dil, min_seviye}]`, `sertifika_gereksinimleri: list[str]`. Task 7 passes these straight into `deterministic.teknik_puani_hesapla` / `deneyim_puani_hesapla` / `dil_puani_hesapla` / `sertifika_puani_hesapla`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_scoring_gemini_client.py`:

```python
@patch("scoring.gemini_client._gemini_istegi_gonder")
def test_gereksinimleri_cikar_returns_parsed_requirements(mock_istek):
    mock_istek.return_value = ({
        "gereken_yetenekler": ["Python", "Flask"],
        "min_deneyim_yili": 3,
        "egitim_gereksinimi": "Bilgisayar Mühendisliği",
        "dil_gereksinimleri": [{"dil": "İngilizce", "min_seviye": "İleri"}],
        "sertifika_gereksinimleri": [],
    }, None)

    sonuc, hata = gemini_client.gereksinimleri_cikar(
        "Python Flask geliştirici aranıyor, min 3 yıl deneyim gereklidir."
    )

    assert hata is None
    assert sonuc["gereken_yetenekler"] == ["Python", "Flask"]
    mock_istek.assert_called_once()


def test_gereksinimleri_cikar_returns_empty_defaults_for_short_text():
    sonuc, hata = gemini_client.gereksinimleri_cikar("kısa")
    assert hata is None
    assert sonuc["gereken_yetenekler"] == []
    assert sonuc["min_deneyim_yili"] is None


@patch("scoring.gemini_client._gemini_istegi_gonder")
def test_gereksinimleri_cikar_propagates_error(mock_istek):
    mock_istek.return_value = (None, "API hatası")
    sonuc, hata = gemini_client.gereksinimleri_cikar(
        "Python Flask geliştirici aranıyor, min 3 yıl deneyim, uzun metin burada devam ediyor."
    )
    assert sonuc is None
    assert hata == "API hatası"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_scoring_gemini_client.py -v`
Expected: FAIL (`AttributeError: module 'scoring.gemini_client' has no attribute 'gereksinimleri_cikar'`)

- [ ] **Step 3: Implement**

Append to `scoring/gemini_client.py`:

```python
def gereksinimleri_cikar(ilan_metni):
    if not ilan_metni or len(ilan_metni) < 30:
        return {
            "gereken_yetenekler": [],
            "min_deneyim_yili": None,
            "egitim_gereksinimi": "",
            "dil_gereksinimleri": [],
            "sertifika_gereksinimleri": [],
        }, None

    sema = {
        "type": "OBJECT",
        "properties": {
            "gereken_yetenekler": {"type": "ARRAY", "items": {"type": "STRING"}},
            "min_deneyim_yili": {"type": "NUMBER"},
            "egitim_gereksinimi": {"type": "STRING"},
            "dil_gereksinimleri": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
                "dil": {"type": "STRING"},
                "min_seviye": {"type": "STRING"}
            }}},
            "sertifika_gereksinimleri": {"type": "ARRAY", "items": {"type": "STRING"}}
        }
    }
    talimat = """Sen bir iş ilanı analiz uzmanısın. Verilen ilan metninden yapısal gereksinimleri çıkar.

Kurallar:
- gereken_yetenekler: İlanda istenen tüm teknik yetenekleri, teknolojileri, araçları ayrı ayrı listele
- min_deneyim_yili: İstenen minimum deneyim yılını sayı olarak ver (belirtilmemişse null)
- egitim_gereksinimi: İstenen bölüm/derece (belirtilmemişse boş string)
- dil_gereksinimleri: Her istenen dil için {dil, min_seviye} (min_seviye: Başlangıç/Orta/İleri/Ana dil)
- sertifika_gereksinimleri: İstenen sertifikaları listele (belirtilmemişse boş liste)"""

    return _gemini_istegi_gonder(ilan_metni, talimat, sema, temperature=0.1)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_scoring_gemini_client.py -v`
Expected: PASS (7/7)

- [ ] **Step 5: Commit**

```bash
git add scoring/gemini_client.py tests/test_scoring_gemini_client.py
git commit -m "feat: add LLM job requirement extraction"
```

---

### Task 6: LLM education score and narrative generation

**Files:**
- Modify: `scoring/gemini_client.py` (append)
- Modify: `tests/test_scoring_gemini_client.py` (append)

**Interfaces:**
- Consumes: `functions._gemini_istegi_gonder` (already imported).
- Produces: `scoring.gemini_client.egitim_ve_anlatim_uret(cv_verisi: dict, gereksinimler: dict, alt_puanlar: dict, eslesen_yetenekler: list[str], eksik_yetenekler: list[str], deneyim_uyumu: str, dil_uyumu: str) -> tuple[dict | None, str | None]`. Success dict has keys `egitim_puan: int`, `egitim_uyumu: str`, `uygunluk_nedeni: str`, `guclu_yonler: list[str]`, `gelistirilmesi_gerekenler: list[str]`, `tavsiyeler: list[str]`. Task 7 merges this dict's keys directly into the final result.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_scoring_gemini_client.py`:

```python
@patch("scoring.gemini_client._gemini_istegi_gonder")
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

    sonuc, hata = gemini_client.egitim_ve_anlatim_uret(
        cv_verisi, gereksinimler, alt_puanlar, ["Python"], ["AWS"], "3 yıl", "İngilizce: 100"
    )

    assert hata is None
    assert sonuc["egitim_puan"] == 85
    assert sonuc["guclu_yonler"] == ["Python bilgisi"]
    mock_istek.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scoring_gemini_client.py -v`
Expected: FAIL (`AttributeError: module 'scoring.gemini_client' has no attribute 'egitim_ve_anlatim_uret'`)

- [ ] **Step 3: Implement**

Add `import json` to the top of `scoring/gemini_client.py` (needed for `json.dumps` below), then append:

```python
def egitim_ve_anlatim_uret(
    cv_verisi, gereksinimler, alt_puanlar, eslesen_yetenekler, eksik_yetenekler,
    deneyim_uyumu, dil_uyumu,
):
    sema = {
        "type": "OBJECT",
        "properties": {
            "egitim_puan": {"type": "INTEGER"},
            "egitim_uyumu": {"type": "STRING"},
            "uygunluk_nedeni": {"type": "STRING"},
            "guclu_yonler": {"type": "ARRAY", "items": {"type": "STRING"}},
            "gelistirilmesi_gerekenler": {"type": "ARRAY", "items": {"type": "STRING"}},
            "tavsiyeler": {"type": "ARRAY", "items": {"type": "STRING"}}
        }
    }
    talimat = """Sen deneyimli bir İK değerlendirme uzmanısın. Sana adayın eğitim bilgileri, ilanın eğitim
gereksinimi ve önceden hesaplanmış puanlar veriliyor. Görevin:

1. egitim_puan (0-100): Eğitim uyumunu değerlendir
   - Bölüm tam uyuyor: 100
   - İlgili bölüm (örn. Yazılım Müh. yerine Bilgisayar Müh.): 85
   - Farklı mühendislik: 60
   - Tamamen farklı alan: 30
   - Eğitim istenmiyor: 80
2. egitim_uyumu: Eğitim uyumunu tek cümlede özetle
3. uygunluk_nedeni, guclu_yonler, gelistirilmesi_gerekenler, tavsiyeler: Verilen puanlara (teknik, deneyim,
   egitim, dil, sertifika) ve eşleşen/eksik yeteneklere dayanarak tutarlı, doğal bir değerlendirme anlatısı üret.
   Zaten hesaplanmış sayısal puanları DEĞİŞTİRME, sadece onlara dayanarak anlatı yaz."""

    prompt = f"""ADAY EĞİTİM BİLGİLERİ:
{json.dumps(cv_verisi.get('egitim_bilgileri', []), ensure_ascii=False, indent=2)}

İLAN EĞİTİM GEREKSİNİMİ: {gereksinimler.get('egitim_gereksinimi') or 'Belirtilmemiş'}

HESAPLANMIŞ PUANLAR: {json.dumps(alt_puanlar, ensure_ascii=False)}
EŞLEŞEN YETENEKLER: {eslesen_yetenekler}
EKSİK YETENEKLER: {eksik_yetenekler}
DENEYİM UYUMU: {deneyim_uyumu}
DİL UYUMU: {dil_uyumu}"""

    return _gemini_istegi_gonder(prompt, talimat, sema, temperature=0.3)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_scoring_gemini_client.py -v`
Expected: PASS (8/8)

- [ ] **Step 5: Commit**

```bash
git add scoring/gemini_client.py tests/test_scoring_gemini_client.py
git commit -m "feat: add LLM education score and narrative generation"
```

---

### Task 7: Hybrid scoring orchestrator

**Files:**
- Create: `scoring/hybrid_scorer.py`
- Test: `tests/test_scoring_hybrid_scorer.py`

**Interfaces:**
- Consumes: `scoring.gemini_client.gereksinimleri_cikar`, `scoring.gemini_client._gemini_gomlemesi_al`, `scoring.gemini_client.egitim_ve_anlatim_uret`, `scoring.deterministic.teknik_puani_hesapla`, `scoring.deterministic.deneyim_puani_hesapla`, `scoring.deterministic.dil_puani_hesapla`, `scoring.deterministic.sertifika_puani_hesapla`.
- Produces: `scoring.hybrid_scorer.ilani_karsilastir_hibrit(cv_verisi: dict, ilan_metni: str) -> tuple[dict | None, str | None]` and `scoring.hybrid_scorer.AGIRLIKLAR: dict` — Task 8 imports and calls `ilani_karsilastir_hibrit` from `app.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_scoring_hybrid_scorer.py`:

```python
from unittest.mock import patch

from scoring.hybrid_scorer import ilani_karsilastir_hibrit, AGIRLIKLAR


def test_agirliklar_toplami_bir():
    assert abs(sum(AGIRLIKLAR.values()) - 1.0) < 1e-9


@patch("scoring.hybrid_scorer.gemini_client")
@patch("scoring.hybrid_scorer.deterministic")
def test_ilani_karsilastir_hibrit_agirlikli_ortalama_hesaplar(mock_det, mock_gc):
    mock_gc.gereksinimleri_cikar.return_value = ({
        "gereken_yetenekler": ["Python"],
        "min_deneyim_yili": 3,
        "egitim_gereksinimi": "Bilgisayar Mühendisliği",
        "dil_gereksinimleri": [],
        "sertifika_gereksinimleri": [],
    }, None)
    mock_det.teknik_puani_hesapla.return_value = (80, ["Python"], [])
    mock_det.deneyim_puani_hesapla.return_value = (70, "3 yıl deneyim")
    mock_det.dil_puani_hesapla.return_value = (100, "Dil gereksinimi yok")
    mock_det.sertifika_puani_hesapla.return_value = 60
    mock_gc.egitim_ve_anlatim_uret.return_value = ({
        "egitim_puan": 90,
        "egitim_uyumu": "Tam uyum",
        "uygunluk_nedeni": "Güçlü aday",
        "guclu_yonler": ["Python"],
        "gelistirilmesi_gerekenler": [],
        "tavsiyeler": [],
    }, None)

    cv_verisi = {
        "yetenekler": ["Python"], "is_deneyimleri": [], "yabanci_diller": [],
        "sertifikalar": [], "projeler": [], "egitim_bilgileri": [],
    }

    sonuc, hata = ilani_karsilastir_hibrit(
        cv_verisi, "Yeterince uzun bir iş ilanı metni buraya gelir, elli karakterden uzun olmalı."
    )

    assert hata is None
    beklenen_skor = round(80 * 0.40 + 70 * 0.25 + 90 * 0.15 + 100 * 0.10 + 60 * 0.10)
    assert sonuc["uygunluk_skoru"] == beklenen_skor
    assert sonuc["alt_puanlar"] == {"teknik": 80, "deneyim": 70, "egitim": 90, "dil": 100, "sertifika": 60}
    assert sonuc["eslesen_yetenekler"] == ["Python"]
    assert sonuc["guclu_yonler"] == ["Python"]


@patch("scoring.hybrid_scorer.gemini_client")
def test_ilani_karsilastir_hibrit_gereksinim_hatasi_propagates(mock_gc):
    mock_gc.gereksinimleri_cikar.return_value = (None, "API hatası")
    sonuc, hata = ilani_karsilastir_hibrit(
        {}, "Yeterince uzun bir iş ilanı metni buraya gelir, elli karakterden uzun."
    )
    assert sonuc is None
    assert hata == "API hatası"


@patch("scoring.hybrid_scorer.gemini_client")
@patch("scoring.hybrid_scorer.deterministic")
def test_ilani_karsilastir_hibrit_anlatim_hatasi_propagates(mock_det, mock_gc):
    mock_gc.gereksinimleri_cikar.return_value = ({
        "gereken_yetenekler": [], "min_deneyim_yili": None, "egitim_gereksinimi": "",
        "dil_gereksinimleri": [], "sertifika_gereksinimleri": [],
    }, None)
    mock_det.teknik_puani_hesapla.return_value = (50, [], [])
    mock_det.deneyim_puani_hesapla.return_value = (50, "")
    mock_det.dil_puani_hesapla.return_value = (100, "")
    mock_det.sertifika_puani_hesapla.return_value = 40
    mock_gc.egitim_ve_anlatim_uret.return_value = (None, "Anlatim hatasi")

    sonuc, hata = ilani_karsilastir_hibrit(
        {}, "Yeterince uzun bir iş ilanı metni buraya gelir, elli karakterden uzun."
    )
    assert sonuc is None
    assert hata == "Anlatim hatasi"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_scoring_hybrid_scorer.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'scoring.hybrid_scorer'`)

- [ ] **Step 3: Implement**

Create `scoring/hybrid_scorer.py`:

```python
from scoring import gemini_client, deterministic

AGIRLIKLAR = {
    "teknik": 0.40,
    "deneyim": 0.25,
    "egitim": 0.15,
    "dil": 0.10,
    "sertifika": 0.10,
}


def ilani_karsilastir_hibrit(cv_verisi, ilan_metni):
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

    toplam_puan = sum(alt_puanlar[k] * AGIRLIKLAR[k] for k in AGIRLIKLAR)

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

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_scoring_hybrid_scorer.py -v`
Expected: PASS (4/4)

- [ ] **Step 5: Commit**

```bash
git add scoring/hybrid_scorer.py tests/test_scoring_hybrid_scorer.py
git commit -m "feat: add hybrid scoring orchestrator"
```

---

### Task 8: Wire into app.py and remove the old LLM-only scorer

**Files:**
- Modify: `app.py:1-14` (imports), `app.py:291` (tekil analiz route), `app.py:327` (toplu analiz helper)
- Modify: `functions.py:148-245` (delete `ilani_karsilastir`)
- Test: `tests/test_app_analiz.py`

**Interfaces:**
- Consumes: `scoring.hybrid_scorer.ilani_karsilastir_hibrit` (Task 7).
- Produces: nothing new for later tasks — this is the integration point.

- [ ] **Step 1: Write the failing test**

Create `tests/test_app_analiz.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_app_analiz.py -v`
Expected: FAIL (`AttributeError: module 'app' has no attribute 'scoring'`, since `app.py` still calls `functions.ilani_karsilastir`)

- [ ] **Step 3: Implement — app.py imports**

In `app.py`, after the existing `import job_search_service` (line 14), add:

```python
import scoring.hybrid_scorer
```

- [ ] **Step 4: Implement — app.py call sites**

In `app.py`, replace line 291:

```python
        sonuc, err = functions.ilani_karsilastir(cv.cikarilan_veriler, metin)
```

with:

```python
        sonuc, err = scoring.hybrid_scorer.ilani_karsilastir_hibrit(cv.cikarilan_veriler, metin)
```

Replace line 327:

```python
            sonuc, err = functions.ilani_karsilastir(cv_verisi, metin)
```

with:

```python
            sonuc, err = scoring.hybrid_scorer.ilani_karsilastir_hibrit(cv_verisi, metin)
```

- [ ] **Step 5: Implement — delete the old scorer from functions.py**

In `functions.py`, delete the entire `ilani_karsilastir` function (from `def ilani_karsilastir(cv_verisi, ilan_metni):` through its final `return sonuc, hata` and the trailing blank line — currently lines 148-245).

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/test_app_analiz.py -v`
Expected: PASS (1/1)

- [ ] **Step 7: Run the full test suite to check for regressions**

Run: `python -m pytest -v`
Expected: all tests pass (no test should still reference `functions.ilani_karsilastir`)

- [ ] **Step 8: Commit**

```bash
git add app.py functions.py tests/test_app_analiz.py
git commit -m "feat: wire hybrid scorer into app.py, remove old LLM-only scorer"
```

---

### Task 9: Upgrade url_den_ilan_cek to trafilatura

**Files:**
- Modify: `functions.py:1-9` (imports), `functions.py:131-146` (`url_den_ilan_cek`)
- Modify: `requirements.txt`
- Test: `tests/test_functions_url_den_ilan_cek.py`

**Interfaces:**
- Consumes: nothing from `scoring/`.
- Produces: nothing new for later tasks — `functions.url_den_ilan_cek`'s public signature (`url: str -> tuple[str | None, str | None]`) is unchanged, only its internals change.

- [ ] **Step 1: Add the dependency**

In `requirements.txt`, add a new section after `# HTTP & Web Scraping`:

```
# Metin Cikarma
trafilatura>=1.6.0
```

Install it:

```bash
pip install trafilatura>=1.6.0
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_functions_url_den_ilan_cek.py`:

```python
from unittest.mock import patch

from functions import url_den_ilan_cek


@patch("functions.trafilatura.extract")
@patch("functions.trafilatura.fetch_url")
def test_url_den_ilan_cek_returns_extracted_text(mock_fetch, mock_extract):
    mock_fetch.return_value = "<html>...</html>"
    mock_extract.return_value = "Bu bir iş ilanı metnidir. " * 10

    metin, hata = url_den_ilan_cek("example.com/ilan")

    assert hata is None
    assert "iş ilanı" in metin
    mock_fetch.assert_called_once_with("https://example.com/ilan")


@patch("functions.trafilatura.fetch_url")
def test_url_den_ilan_cek_returns_error_when_fetch_fails(mock_fetch):
    mock_fetch.return_value = None
    metin, hata = url_den_ilan_cek("example.com/ilan")
    assert metin is None
    assert hata == "Siteye erişilemedi."


@patch("functions.trafilatura.extract")
@patch("functions.trafilatura.fetch_url")
def test_url_den_ilan_cek_returns_error_when_content_too_short(mock_fetch, mock_extract):
    mock_fetch.return_value = "<html>...</html>"
    mock_extract.return_value = "kısa"
    metin, hata = url_den_ilan_cek("example.com/ilan")
    assert metin is None
    assert hata == "İçerik boş."


@patch("functions.trafilatura.fetch_url")
def test_url_den_ilan_cek_prepends_https_when_missing(mock_fetch):
    mock_fetch.return_value = None
    url_den_ilan_cek("example.com/ilan")
    mock_fetch.assert_called_once_with("https://example.com/ilan")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_functions_url_den_ilan_cek.py -v`
Expected: FAIL (`AttributeError: module 'functions' has no attribute 'trafilatura'`)

- [ ] **Step 4: Implement**

In `functions.py`, remove the now-unused import (line 8):

```python
from bs4 import BeautifulSoup
```

Add `import trafilatura` near the top (alongside the other imports, e.g. after `import requests`).

Replace the body of `url_den_ilan_cek` (lines 131-146):

```python
def url_den_ilan_cek(url):
    try:
        if not url.startswith('http'): url = 'https://' + url
        indirilen = trafilatura.fetch_url(url)
        if not indirilen:
            return None, "Siteye erişilemedi."

        metin = trafilatura.extract(indirilen)
        if not metin or len(metin) < 100:
            return None, "İçerik boş."
        return metin[:15000], None
    except Exception as e:
        return None, str(e)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_functions_url_den_ilan_cek.py -v`
Expected: PASS (4/4)

- [ ] **Step 6: Run the full test suite**

Run: `python -m pytest -v`
Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add functions.py requirements.txt tests/test_functions_url_den_ilan_cek.py
git commit -m "feat: upgrade url_den_ilan_cek to trafilatura for cleaner extraction"
```

---

## Notes for the final review

- After Task 9, run `python -m pytest -v` once more for the complete suite, then follow `superpowers:subagent-driven-development`'s final whole-branch review step (dispatch on the most capable available model) before `superpowers:finishing-a-development-branch`.
- Check `git status` for a dirty `proje.db` before generating any review diff/package; restore with `git checkout -- proje.db` if needed (recurred repeatedly during Plan 1).
- Plan 3 (feedback collection + auto-reweighting, spec section 5) is intentionally not covered here — it depends on this plan's `alt_puanlar` shape but needs its own plan document.
