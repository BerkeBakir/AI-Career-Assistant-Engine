import json
import logging

import requests

from functions import API_KEY, _llm_istegi_gonder

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"


def _llm_gomlemesi_al(metin):
    if not metin or not metin.strip():
        return None
    try:
        response = requests.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {API_KEY}',
            },
            data=json.dumps({"model": EMBEDDING_MODEL, "input": metin}),
            timeout=10,
        )
        if response.status_code != 200:
            logger.warning(f"Embedding istegi basarisiz: {response.status_code}")
            return None
        return response.json().get('data', [{}])[0].get('embedding')
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

    return _llm_istegi_gonder(ilan_metni, talimat, sema, temperature=0.1)


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

    return _llm_istegi_gonder(prompt, talimat, sema, temperature=0.3)
