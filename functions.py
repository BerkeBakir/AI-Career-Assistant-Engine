import fitz
import docx
import os
import json
import requests
import re
import logging
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# .env dosyasini yukle
load_dotenv()

# API anahtarini environment variable'dan al
API_KEY = os.getenv('GEMINI_API_KEY')
if not API_KEY:
    logging.warning("GEMINI_API_KEY environment variable bulunamadi!")

# Logging yapilandirmasi
logger = logging.getLogger(__name__)

def _gemini_istegi_gonder(icerik, talimat, sema, temperature=0.3):
    modeller = [
        "gemini-2.0-flash",
        "gemini-2.5-flash",
        "gemini-2.0-flash-lite"
    ]

    payload = {
        "systemInstruction": {"parts": [{"text": talimat}]},
        "contents": [{"parts": [{"text": icerik}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": sema,
            "temperature": temperature
        }
    }

    son_hata = ""

    for model in modeller:
        try:
            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={API_KEY}"
            response = requests.post(api_url, headers={'Content-Type': 'application/json'}, data=json.dumps(payload))
            
            if response.status_code == 200:
                raw_text = response.json().get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '{}')
                if "```json" in raw_text:
                    raw_text = raw_text.replace("```json", "").replace("```", "")
                elif "```" in raw_text:
                    raw_text = raw_text.replace("```", "")
                return json.loads(raw_text.strip()), None
            else:
                hata_detay = response.json().get('error', {}).get('message', response.text[:200])
                son_hata = f"{model} Hatası: {response.status_code} - {hata_detay}"
                logger.warning(son_hata)
                continue
        except Exception as e:
            son_hata = str(e)
            continue
    
    return None, f"Yapay zeka yanıt vermedi. Son Hata: {son_hata}"

def metin_cikar(dosya_yolu):
    try:
        uzanti = os.path.splitext(dosya_yolu)[1].lower()
        metin = ""
        if uzanti == '.pdf':
            with fitz.open(dosya_yolu) as pdf:
                for sayfa in pdf: metin += sayfa.get_text()
        elif uzanti == '.docx':
            doc = docx.Document(dosya_yolu)
            for p in doc.paragraphs: metin += p.text + "\n"
        return metin, None
    except Exception as e:
        return None, str(e)

def bilgileri_cikar(metin):
    istenen_json_semasi = {
        "type": "OBJECT",
        "properties": {
            "isimler": {"type": "ARRAY", "items": {"type": "STRING"}},
            "epostalar": {"type": "ARRAY", "items": {"type": "STRING"}},
            "telefon_numaralari": {"type": "ARRAY", "items": {"type": "STRING"}},
            "lokasyonlar": {"type": "ARRAY", "items": {"type": "STRING"}},
            "yetenekler": {"type": "ARRAY", "items": {"type": "STRING"}},
            "egitim_bilgileri": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
                "okul_adi": {"type": "STRING"},
                "bolum_adi": {"type": "STRING"},
                "derece": {"type": "STRING"},
                "mezuniyet_yili": {"type": "STRING"}
            }}},
            "is_deneyimleri": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
                "sirket_adi": {"type": "STRING"},
                "pozisyon": {"type": "STRING"},
                "baslangic_tarihi": {"type": "STRING"},
                "bitis_tarihi": {"type": "STRING"},
                "sorumluluklar": {"type": "ARRAY", "items": {"type": "STRING"}}
            }}},
            "yabanci_diller": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
                "dil": {"type": "STRING"},
                "seviye": {"type": "STRING"}
            }}},
            "sertifikalar": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
                "sertifika_adi": {"type": "STRING"},
                "kurum": {"type": "STRING"},
                "tarih": {"type": "STRING"}
            }}},
            "projeler": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
                "proje_adi": {"type": "STRING"},
                "aciklama": {"type": "STRING"},
                "teknolojiler": {"type": "ARRAY", "items": {"type": "STRING"}}
            }}},
            "toplam_deneyim_yili": {"type": "STRING"},
            "ozet": {"type": "STRING"}
        }
    }
    talimat = """Sen deneyimli bir İK asistanısın. CV metnini detaylı analiz et ve JSON formatında çıkar.

Önemli kurallar:
- Yetenekler: Teknik beceriler, yazılım dilleri, frameworkler, araçlar, soft skills hepsini ayrı ayrı listele
- Yabancı diller: Dil adı ve seviyesini (Başlangıç/Orta/İleri/Ana dil) belirt
- İş deneyimleri: Tarihler, pozisyon ve sorumlulukları detaylı çıkar
- Toplam deneyim yılı: İş deneyimlerinden hesapla (örn: "3 yıl")
- Özet: Adayın profilini 2-3 cümleyle özetle
- Sertifikalar: Varsa tüm sertifikaları, kursları, eğitimleri ekle
- Projeler: Kişisel veya iş projelerini ve kullanılan teknolojileri çıkar"""

    return _gemini_istegi_gonder(metin, talimat, istenen_json_semasi)

def url_den_ilan_cek(url):
    try:
        if not url.startswith('http'): url = 'https://' + url
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200: return None, "Siteye erişilemedi."

        soup = BeautifulSoup(response.content, 'html.parser')
        for script in soup(["script", "style", "nav", "footer", "header", "aside"]): script.decompose()
        
        metin = soup.get_text(separator=' ', strip=True)[:15000]
        if len(metin) < 100: return None, "İçerik boş."
        return metin, None
    except Exception as e:
        return None, str(e)

def ilani_karsilastir(cv_verisi, ilan_metni):
    if not ilan_metni or len(ilan_metni) < 50:
        ilan_metni = "İlan içeriğine tam erişilemedi. Başlık ve şirket bilgisine göre genel değerlendirme yap."

    istenen_sonuc_semasi = {
        "type": "OBJECT",
        "properties": {
            "teknik_puan": {"type": "INTEGER"},
            "deneyim_puan": {"type": "INTEGER"},
            "egitim_puan": {"type": "INTEGER"},
            "dil_puan": {"type": "INTEGER"},
            "sertifika_puan": {"type": "INTEGER"},
            "uygunluk_nedeni": {"type": "STRING"},
            "eslesen_yetenekler": {"type": "ARRAY", "items": {"type": "STRING"}},
            "eksik_yetenekler": {"type": "ARRAY", "items": {"type": "STRING"}},
            "deneyim_uyumu": {"type": "STRING"},
            "egitim_uyumu": {"type": "STRING"},
            "dil_uyumu": {"type": "STRING"},
            "guclu_yonler": {"type": "ARRAY", "items": {"type": "STRING"}},
            "gelistirilmesi_gerekenler": {"type": "ARRAY", "items": {"type": "STRING"}},
            "tavsiyeler": {"type": "ARRAY", "items": {"type": "STRING"}}
        }
    }

    talimat = """Sen deneyimli ve TUTARLI bir İK değerlendirme uzmanısın.
Her kategoriyi 0-100 arasında AYRI AYRI puanla. Yuvarlak sayılar kullanma (73, 67, 82 gibi kesin değerler ver).

PUANLAMA SİSTEMİ (Her kategori 0-100 arası):

1. teknik_puan (0-100): Teknik yetenek eşleşmesi
   - İlanda istenen her teknolojiyi say
   - Adayda bulunanları say
   - Formül: (eslesen / istenen) * 100
   - Benzer teknoloji varsa %50 say (React yerine Vue = 0.5 eşleşme)
   - Örnek: 8 teknoloji isteniyor, 5'i tam eşleşiyor, 2'si benzer = (5 + 1) / 8 * 100 = 75

2. deneyim_puan (0-100): Deneyim yılı uyumu
   - İstenen deneyim ile mevcut deneyimi karşılaştır
   - Formül: min(100, (aday_yil / istenen_yil) * 100)
   - 5 yıl istenip 3 yıl varsa: 3/5 * 100 = 60
   - Fazla deneyim: max 100 (overqualified durumu ayrıca belirt)
   - Deneyim belirtilmemişse: 50 ver

3. egitim_puan (0-100): Eğitim uyumu
   - Bölüm tam uyuyor: 100
   - İlgili bölüm (Yazılım Müh. yerine Bilgisayar Müh.): 85
   - Farklı mühendislik: 60
   - Tamamen farklı alan: 30
   - Eğitim istenmiyor: 80

4. dil_puan (0-100): Yabancı dil uyumu
   - Seviye tam uyuyor: 100
   - Bir seviye düşük: 65
   - İki seviye düşük: 35
   - Dil yok: 0
   - Dil istenmiyorsa: 100

5. sertifika_puan (0-100): Sertifika ve proje uyumu
   - İlgili sertifika sayısına göre puanla
   - Projeler varsa +20 bonus
   - Hiç yoksa: 40 (baseline)

ÖNEMLİ KURALLAR:
- ASLA 70, 75, 80, 85, 90 gibi 5'in katları verme
- 67, 73, 81, 88 gibi kesin rakamlar kullan
- Her değerlendirmede AYNI mantığı uygula
- Eksik bilgi varsa orta değer ver (45-55 arası)"""

    prompt = f"ADAY BİLGİLERİ:\n{json.dumps(cv_verisi, ensure_ascii=False, indent=2)}\n\nİŞ İLANI:\n{ilan_metni}"

    # Düşük temperature ile tutarlı sonuç al
    sonuc, hata = _gemini_istegi_gonder(prompt, talimat, istenen_sonuc_semasi, temperature=0.1)

    if sonuc:
        # Alt puanlardan ağırlıklı ortalama hesapla
        teknik = sonuc.get('teknik_puan', 50)
        deneyim = sonuc.get('deneyim_puan', 50)
        egitim = sonuc.get('egitim_puan', 50)
        dil = sonuc.get('dil_puan', 50)
        sertifika = sonuc.get('sertifika_puan', 50)

        # Ağırlıklı ortalama: Teknik %40, Deneyim %25, Eğitim %15, Dil %10, Sertifika %10
        toplam_puan = (teknik * 0.40) + (deneyim * 0.25) + (egitim * 0.15) + (dil * 0.10) + (sertifika * 0.10)

        # Sonuca hesaplanan puanı ekle
        sonuc['uygunluk_skoru'] = round(toplam_puan)

        # Alt puanları da döndür (frontend'de göstermek için)
        sonuc['alt_puanlar'] = {
            'teknik': teknik,
            'deneyim': deneyim,
            'egitim': egitim,
            'dil': dil,
            'sertifika': sertifika
        }

    return sonuc, hata

