# AI Career Assistant Engine 🚀

> Yapay zeka destekli, uçtan uca bir iş arama ve CV↔ilan eşleştirme platformu.

**Repo:** https://github.com/BerkeBakir/AI-Career-Assistant-Engine

---

## 💡 Fikir ve Problem Tanımı

İş arayan bir aday genelde onlarca farklı siteyi (LinkedIn, Indeed, Kariyer.net, Eleman.net...) tek tek gezer, her ilanı elle okur ve CV'sinin o ilana ne kadar uyduğunu tahmin etmeye çalışır. Bu hem zaman kaybettirir hem de "bu ilana gerçekten uygun muyum?" sorusuna öznel/belirsiz bir cevap verir.

**AI Career Assistant Engine** bu süreci otomatikleştirir: adayın CV'sini analiz eder, onlarca kaynaktan aynı anda ilan toplar, her ilanı CV ile **5 farklı boyutta** (teknik yetenek, deneyim, eğitim, dil, sertifika) puanlar ve adaya nereye başvurması gerektiğini, neden uygun olduğunu ve hangi konularda eksik kaldığını somut biçimde gösterir.

**Neden farklı/yaratıcı:** Çoğu "AI ile CV eşleştirme" projesi tek bir LLM çağrısına "şu CV'yi şu ilana göre puanla" diyip sonucu olduğu gibi kullanır — bu yaklaşım tutarsız, açıklanamaz ve pahalıdır. Bu projede puanlamanın büyük kısmı (teknik/deneyim/dil/sertifika) **deterministik** olarak hesaplanır (embedding tabanlı kosinüs benzerliği, tarih matematiği, seviye tabloları); LLM sadece gerçekten öznel yargı gerektiren kısımlarda (eğitim uyumu, doğal dilde gerekçe/tavsiye metni) devreye girer. Böylece sonuç hem daha tutarlı hem daha ucuz hem de "neden bu puanı aldım" sorusuna açıklanabilir bir cevap veriyor.

Ayrıca sistem **kullanıcı geri bildirimiyle kendini geliştiriyor**: adaylar her eşleştirmeye 👍/👎 verebiliyor, yeterli geri bildirim birikince (≥40 örnek) sistem sıfırdan yazılmış bir lojistik regresyon ile puanlama ağırlıklarını (teknik/deneyim/eğitim/dil/sertifika) yeniden öğreniyor — yani zamanla adayların gerçek tercihlerine göre kalibre oluyor.

## ⚙️ Teknik Uygulama

- **Modüler mimari:** Her iş ilanı kaynağı (`scrapers/`) ayrı bir dosya/sınıf; ortak bir `BaseScraper` arayüzü üzerinden `job_search_service.py` orkestratörü tarafından `ThreadPoolExecutor` ile **paralel** çalıştırılıyor. Bir kaynak çökerse/yavaşsa diğerlerini etkilemiyor (izole hata yönetimi + zaman aşımı bütçesi).
- **Kaynaklar:** LinkedIn, Indeed, Bing, Arbeitnow, Remotive, Himalayas, RemoteOK, WeWorkRemotely, Yenibiris.com, Eleman.net ve (opsiyonel ücretsiz key ile) Jooble. Kariyer.net ve SecretCV.com doğrudan scrape edilemediği için (bot koruması / login duvarı) DuckDuckGo `site:` aramasına düşüyor — bu kısıt kodda açıkça belirtiliyor, gizlenmiyor.
- **Hibrit puanlama motoru** (`scoring/`): tek bir LLM çağrısı ilan metninden yapısal gereksinimleri (`gereken_yetenekler`, `min_deneyim_yili`, ...) çıkarıyor; ardından Python tarafında saf matematikle (embedding kosinüs benzerliği, Türkçe serbest metin tarih ayrıştırma, seviye eşleştirme tabloları) 4 alt puan hesaplanıyor; sadece eğitim puanı ve anlatı metni LLM'e bırakılıyor.
- **Öğrenen sistem** (`learning/`): kullanıcı geri bildirimlerinden (`Geribildirim` tablosu) sıfırdan yazılmış (kütüphanesiz) bir **lojistik regresyon** ile puanlama ağırlıkları yeniden eğitiliyor, versiyonlu olarak (`ScoringConfig`) saklanıyor; admin panelinden tetikleniyor.
- **Test kapsamı:** 117 otomatik test (pytest), her modül mock'lanmış dış servislerle izole test ediliyor.
- **Güvenlik:** CSRF koruması (Flask-WTF), Werkzeug ile şifre hash'leme, rol bazlı yetkilendirme (admin/aday), dosya tipi/boyut doğrulama.
- **Bilinen kısıtlar (şeffaflık):** FindWork.dev artık ücretsiz API sunmuyor (401 döndürüyor — bilinçli olarak devre dışı bırakılabilir); Indeed/Bing bot korumasına takılabiliyor; bunlar sistemin geri kalanını bozmuyor çünkü her kaynak birbirinden bağımsız.

## 🤖 AI Kullanımı

AI burada süsleme değil, **ürünün var olma sebebi**:
1. **CV ayrıştırma (NER):** PDF/DOCX CV'den yapılandırılmış JSON (yetenekler, deneyimler, eğitim, diller, sertifikalar) çıkarımı.
2. **İlan gereksinim çıkarımı:** Serbest metin iş ilanından yapılandırılmış gereksinim listesi.
3. **Semantik yetenek eşleştirme:** "React" ile "React.js"in veya "Makine Öğrenmesi" ile "ML"in aynı şey olduğunu embedding tabanlı kosinüs benzerliğiyle anlıyor — düz string eşleşmesi değil.
4. **Doğal dilde değerlendirme:** Güçlü yönler, geliştirilmesi gerekenler, tavsiyeler ve ön yazı (cover letter) üretimi.

**Kullanılan AI araçları:** OpenAI API (`gpt-4o-mini` → `gpt-4.1-mini` → `gpt-4o` fallback zinciri ile yapılandırılmış JSON üretimi; `text-embedding-3-small` ile semantik embedding). Geliştirme sürecinde **Claude Code (Anthropic)** ajan tabanlı olarak kod yazımı, test-driven development ve kod review için kullanıldı.

## 🎨 Kullanıcı Deneyimi

- **Etkileşimli panel:** CV ve ilan sayılarının canlı takibi.
- **Radar grafik analizi:** Chart.js ile adayın 5 boyutlu profilinin görselleştirilmesi.
- **Tek tık iş arama:** CV'ye göre otomatik anahtar kelime çıkarımı + çoklu kaynaktan paralel arama.
- **Geri bildirim döngüsü:** Her eşleştirme sonucunda 👍/👎 ile hızlı geri bildirim verme.
- **Admin paneli:** Puanlama ağırlıklarını ve yeniden eğitim durumunu görme/tetikleme.
- **Güvenli & sade arayüz:** Bootstrap 5 tabanlı, CSRF korumalı formlar, anlaşılır hata mesajları.

## 📄 Dokümantasyon ve Sunum

Bu README; problem tanımı, teknik mimari, AI kullanımı ve kullanıcı deneyimini kapsıyor. Daha derin teknik detay isteyenler için `docs/superpowers/plans/` altında geliştirme sürecinde yazılan uygulama planları ve `docs/superpowers/specs/` altında tasarım dokümanları mevcut (mimari kararların "neden"ini gösteriyor).

---

## 🏛️ System Architecture (EN)

The platform is built on a modular **Flask** backend with a focus on high-performance parallel processing and sophisticated AI integration.

### Core Engineering Features:
- **AI-Powered CV Parsing:** Uses **OpenAI's GPT models** to perform Named Entity Recognition (NER) on PDF/DOCX files, extracting structured JSON data (Skills, Experience, Education) with high accuracy.
- **Distributed Meta-Search Engine:** A modular `scrapers/` package (one file per source) runs concurrently via `ThreadPoolExecutor` with a shared timeout budget, aggregating LinkedIn, Indeed, Bing, Arbeitnow, Remotive, Himalayas, RemoteOK, WeWorkRemotely, Yenibiris.com, Eleman.net, and (optionally, with a free API key) Jooble. Kariyer.net (bot protection) and SecretCV.com (login-gated listings) fall back to DuckDuckGo `site:` discovery, which is lower-coverage and clearly labeled as such in the code (`scrapers/ddg_fallback.py`).
- **Hybrid Match Scoring:** Combines deterministic computation (embedding cosine similarity for skills, date-math for experience, lookup tables for language level) with targeted LLM judgment (education fit, narrative feedback) — see `scoring/`.
- **Self-Improving Weights:** Candidate 👍/👎 feedback feeds a from-scratch (no ML library) logistic regression trainer (`learning/reweighting.py`) that periodically re-derives the five scoring weights, versioned in `ScoringConfig`.
- **Automated Cover Letter Generation:** Generates professional, HTML-formatted cover letters tailored to each job listing and candidate profile.
- **Parallel Analysis Pipeline:** Bulk analysis mode processes multiple job listings concurrently.

## ✨ Key Features
- **Interactive Dashboard:** Real-time statistics for job listings and CVs.
- **Smart Analytics:** Radar chart visualizations (Chart.js) comparing candidate profiles against the ideal match.
- **Admin Control Center:** Manage scoring weights, retraining, and user roles.
- **Security & Validation:** CSRF protection, secure password hashing (Werkzeug), strict file validation.

## 🛠️ Tech Stack
- **Backend:** Python 3.x, Flask, Flask-SQLAlchemy, Flask-WTF
- **AI/LLM:** OpenAI API (`gpt-4o-mini`/`gpt-4.1-mini`/`gpt-4o`, `text-embedding-3-small`)
- **Database:** SQLite with SQLAlchemy ORM
- **Scraping:** BeautifulSoup4, trafilatura, DuckDuckGo Search (DDGS), Requests
- **File Processing:** PyMuPDF (PDF), python-docx (DOCX)
- **Frontend:** HTML5, CSS3, Bootstrap 5, Chart.js
- **Testing:** pytest (117 tests)

## 📂 Installation & Execution

### 1. Clone & Setup Environment
```bash
git clone https://github.com/BerkeBakir/AI-Career-Assistant-Engine.git
cd AI-Career-Assistant-Engine
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` and fill in the values:
```bash
cp .env.example .env
```
- `OPENAI_API_KEY` — required for CV parsing, matching, and embeddings ([platform.openai.com](https://platform.openai.com))
- `SECRET_KEY` — Flask session/CSRF signing key (`python -c "import secrets; print(secrets.token_hex(32))"`)
- `JOOBLE_API_KEY` — optional, free at [jooble.org/api/about](https://jooble.org/api/about); the app works fine without it

### 3. Initialize the Database
```bash
python create_db.py
```

### 4. Run
```bash
python app.py
```
The app runs at `http://127.0.0.1:5000`.

### 5. Run Tests
```bash
pytest tests/ -q
```
