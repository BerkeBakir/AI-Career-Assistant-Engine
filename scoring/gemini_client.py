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
