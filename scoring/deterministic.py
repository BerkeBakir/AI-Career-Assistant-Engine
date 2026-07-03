import math
import re
from datetime import datetime

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

    eslesme = re.fullmatch(r"\s*(\d{4})\s*", metin)
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
