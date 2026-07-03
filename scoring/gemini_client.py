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
