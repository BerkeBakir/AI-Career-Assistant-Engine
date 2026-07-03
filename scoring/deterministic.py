import math

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
