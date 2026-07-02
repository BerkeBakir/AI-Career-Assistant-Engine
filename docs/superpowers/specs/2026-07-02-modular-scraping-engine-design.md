# Modüler İş İlanı Arama & Doğruluk Motoru — Tasarım

**Tarih:** 2026-07-02
**Durum:** Onay bekliyor

## Bağlam

Repo: `BerkeBakir/AI-Career-Assistant-Engine` (Flask, Türkçe UI, Gemini tabanlı CV parse + iş ilanı eşleştirme).
İş: bağımsız bir workspace'te (`Desktop/AI-Career-Assistant-Engine`, notvia/stellarfund'dan ayrık) geliştiriliyor.

Mevcut durumun sorunları:
1. `functions.py:internette_is_ara()` 8 kaynağı **sıralı** tarıyor (README "ThreadPoolExecutor" diyor ama bu sadece `toplu_analiz`'de kullanılıyor, scraping'de değil) → arama başına muhtemelen 30-60sn+.
2. Kaynaklar tek bir ~300 satırlık fonksiyonda iç içe — yeni kaynak eklemek mevcut kodu büyütmekten başka yol sunmuyor.
3. Türk siteleri (Kariyer.net, Yenibiris, SecretCV, Eleman.net) gerçek scraper değil, DuckDuckGo `site:` arama hack'i ile "aranıyor" — çoğu zaman az/boş sonuç.
4. LinkedIn/Indeed/Bing HTML scraping'i sabit CSS selector'lara dayanıyor, retry/UA rotasyonu yok — site değiştiğinde sessizce kırılıyor.
5. `ilani_karsilastir()` skorlama tamamen LLM'e (Gemini) dayanıyor; teknik/deneyim gibi aritmetik/sayma gerektiren kategorilerde LLM tutarsız sonuç üretebiliyor.
6. Hiç geri bildirim/öğrenme mekanizması yok — ağırlıklar (40/25/15/10/10) sabit kodlanmış, hiçbir zaman gerçek kullanım verisiyle kalibre olmuyor.

## Doğrulanan teknik bulgular (canlı test edildi)

- **RemoteOK API** (`remoteok.com/api`) — 200 OK, key gerektirmiyor, temiz JSON.
- **WeWorkRemotely RSS** (`weworkremotely.com/categories/remote-programming-jobs.rss`) — 200 OK, temiz XML.
- **Eleman.net, Yenibiris.com, SecretCV.com** — hepsi 200 OK, gerçek CSS selector'larla scrape edilebilir (`jobTitleLnk`/`jobCompanyLnk` — Yenibiris, `map-job-card` — Eleman, ilan listeleme sayfası çalışıyor — SecretCV).
- **Kariyer.net** — PerimeterX bot koruması (CAPTCHA duvarı), browser User-Agent ile bile 403. Bypass etmek CAPTCHA-solving/proxy gerektirir — bu kapsam dışı (anti-bot sistemini atlatmak, scraping bug'ı düzeltmek değil). DuckDuckGo discovery fallback olarak kalır, README'de bu sınırlama açıkça belirtilir.
- **Adzuna** — Türkiye'yi desteklemiyor (12 ülke: GB/US/DE/FR/AU/NZ/CA/IN/PL/BR/AT/ZA, TR yok) — eklenmeyecek.
- **Jooble** — ücretsiz API key ile global arama (Türkiye dahil, location parametresiyle) — opsiyonel kaynak.

## Mimari

### 1. Modül yapısı

```
scrapers/
  base.py          # JobListing dataclass + BaseScraper arayüzü
  linkedin.py, indeed.py, bing.py                          # sağlamlaştırılmış, mevcut
  arbeitnow.py, remotive.py, himalayas.py, findwork.py     # mevcut, aynen taşınır
  remoteok.py, weworkremotely.py                            # yeni
  eleman.py, yenibiris.py, secretcv.py                      # yeni, gerçek scraper
  kariyer_ddg.py                                            # DuckDuckGo fallback, açıkça belgelenmiş sınırlama
  jooble.py                                                 # opsiyonel, JOOBLE_API_KEY varsa aktif
  registry.py                                                # aktif scraper listesi
job_search_service.py                                        # orchestration
```

Her scraper: `name`, `search(keywords: list[str], limit: int) -> list[JobListing]`. Yeni kaynak eklemek = yeni dosya + registry'e 1 satır.

### 2. Orchestration & hız

- `job_search_service.search_jobs(keywords)`: tüm aktif scraper'lar `ThreadPoolExecutor` ile paralel çalışır.
- Scraper başına ayrı timeout (~8-10sn, `future.result(timeout=...)`), yavaş/engellenmiş kaynak diğerlerini bekletmez.
- Toplam süre ≈ en yavaş kaynağın süresi (paralel), bugünkü gibi tüm sürelerin toplamı değil.
- Scraper hatası yakalanır/loglanır/atlanır — merkezi, tek yerde (bugünkü 8 ayrı try/except yerine).
- `JobListing` dataclass (`baslik, sirket, link, kaynak, aciklama, lokasyon`) — tüm scraper'lar aynı formatta döner.
- Merkezi dedup: link normalize edilir (tracking query param, trailing slash temizlenir) sonra karşılaştırılır.

### 3. Yeni/sağlamlaştırılmış kaynaklar

**Yeni:** RemoteOK, WeWorkRemotely (key yok), Eleman.net/Yenibiris.com/SecretCV.com (gerçek scraper), Jooble (opsiyonel key).
**Kariyer.net:** DuckDuckGo discovery fallback olarak kalır, README'de dürüstçe belirtilir.
**Sağlamlaştırma (LinkedIn/Indeed/Bing):** UA havuzundan rotasyon, timeout/5xx'te retry-with-backoff (2 deneme), implementasyon sırasında canlı selector doğrulaması.

### 4. Eşleştirme doğruluğu — deterministik + LLM hibrit

**Sorun:** LLM aritmetik/sayma gerektiren skorlamada (teknik_puan, deneyim_puan) tutarsız.

**Çözüm — iki aşamalı:**

1. **Gereksinim çıkarma** (1 LLM çağrısı): ilan metninden `gereken_yetenekler, min_deneyim_yili, egitim_gereksinimi, dil_gereksinimleri, sertifika_gereksinimleri` şema bazlı JSON olarak çıkarılır.
2. **Deterministik Python skorlama** (4/5 kategori, ağırlığın ~%85'i):
   - `teknik_puan`: Gemini embedding (`text-embedding-004`) ile aday yetenekleri ↔ gereken yetenekler anlamsal benzerlik skoru. Tam eşleşme = tam puan, benzer teknoloji = kısmi puan (kosinüs benzerliğine göre, LLM'in gevşek "%50 say" talimatı yerine).
   - `deneyim_puan`: CV'nin `is_deneyimleri` alanındaki başlangıç/bitiş tarihleri Python'da parse edilip (Türkçe ay adları, "Halen" dahil) toplam deneyim hesaplanır; `min(100, aday_yil/istenen_yil*100)` formülü Python'da uygulanır.
   - `dil_puan`: Seviye lookup tablosu (Başlangıç/Orta/İleri/Ana dil → sayısal), Python'da hesaplanır.
   - `sertifika_puan`: Sayım + proje bonusu, Python'da hesaplanır.
3. **LLM'e kalan:** `egitim_puan` (bağlamsal yargı gerektiriyor — "Bilgisayar Müh. ↔ Yazılım Müh. ne kadar ilgili?") ve açıklama metinleri (`uygunluk_nedeni`, `guclu_yonler`, `gelistirilmesi_gerekenler`, `tavsiyeler`) — hesaplanmış puanları bağlam alıp tutarlı anlatı üretir.
4. `url_den_ilan_cek` içindeki ham `BeautifulSoup.get_text()` yerine **trafilatura** (boilerplate temizleme) kullanılır — özellikle yeni Türk sitelerinde daha temiz girdi metni sağlar.

### 5. Sürekli öğrenen skorlama — geri bildirim + otomatik yeniden ağırlıklama

**Geri bildirim toplama:**
- Yeni model `Geribildirim`: `id, eslesme_id (FK→Eslesme), kullanici_id, deger (olumlu/olumsuz), olusturulma_tarihi`.
- `kaydedilenler.html`'de her analiz için 👍/👎 widget'ı (AJAX, `POST /geribildirim/<eslesme_id>`, sahiplik kontrollü, upsert).

**Otomatik yeniden ağırlıklama:**
- Sabit ağırlıklar (0.40/0.25/0.15/0.10/0.10) yeni bir `ScoringConfig` tablosuna taşınır; `ilani_karsilastir` ağırlıkları oradan okur, kayıt yoksa varsayılana döner.
- `learning/reweighting.py`: yeterli geri bildirim birikince (en az 40 örnek, her iki sınıftan da en az 10 tane), `Eslesme.analiz_sonucu.alt_puanlar` özellik, `Geribildirim.deger` etiket olarak lojistik regresyon (scikit-learn) eğitir; normalize edilmiş katsayılar yeni ağırlık olarak `ScoringConfig`'e yazılır (versiyonlu). Eşik altında buton "yetersiz veri (X/40)" mesajı gösterir, eğitim çalıştırılmaz.
- Admin panelinde "Ağırlıkları Yeniden Eğit" butonu — manuel tetikleme, önce/sonra ağırlıklar + örnek sayısı gösterilir. Otomatik cron/zamanlı servis **yok** (kapsam dışı, veri yeterli olana kadar zaten anlamsız).

### 6. Test stratejisi

- Canlı test edilen gerçek HTML/JSON örnekleri (`eleman.net`, `yenibiris.com`, `secretcv.com`, RemoteOK, WeWorkRemotely) fixture olarak saklanır; her scraper TDD ile (önce fixture'a karşı test, sonra implementasyon) yazılır.
- Deterministik skorlama fonksiyonları için unit test (embedding çağrısı mock'lanır).

### 7. Teslim / repo yönetimi

- `origin` zaten `BerkeBakir/AI-Career-Assistant-Engine` (kullanıcının kendi reposu).
- Çalışma `feature/modular-scraping-engine` branch'inde yapılır, local'de commit edilir.
- Push/PR/main'e merge kararı kullanıcıya ait — otomatik push yapılmaz.
- `proje.db` dokunulmaz; yeni tablolar (`Geribildirim`, `ScoringConfig`) mevcut şemaya eklenir (migration).

## Kapsam dışı (bu turda yapılmayacak)

- Kariyer.net için CAPTCHA/anti-bot bypass.
- Tam otomatik/zamanlanmış model yeniden eğitimi (cron/Celery).
- CV parse (`bilgileri_cikar`) mantığında değişiklik.
- Auth/UI/genel route refactoring (scope: "Sadece scraping motoru" + "eşleştirme doğruluğu" olarak onaylandı, tüm backend refactor değil).
