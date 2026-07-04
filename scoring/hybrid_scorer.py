from scoring import gemini_client, deterministic

AGIRLIKLAR = {
    "teknik": 0.40,
    "deneyim": 0.25,
    "egitim": 0.15,
    "dil": 0.10,
    "sertifika": 0.10,
}


def ilani_karsilastir_hibrit(cv_verisi, ilan_metni, agirliklar=None):
    aktif_agirliklar = agirliklar if agirliklar is not None else AGIRLIKLAR

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

    toplam_puan = sum(alt_puanlar[k] * aktif_agirliklar[k] for k in AGIRLIKLAR)

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
