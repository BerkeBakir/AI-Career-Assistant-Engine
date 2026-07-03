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
