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

