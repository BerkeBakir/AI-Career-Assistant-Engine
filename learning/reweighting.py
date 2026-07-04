import math

from extensions import db
import models

OZELLIK_SIRASI = ["teknik", "deneyim", "egitim", "dil", "sertifika"]

VARSAYILAN_AGIRLIKLAR = {
    "teknik": 0.40,
    "deneyim": 0.25,
    "egitim": 0.15,
    "dil": 0.10,
    "sertifika": 0.10,
}


def guncel_agirliklari_al():
    kayit = models.ScoringConfig.query.order_by(models.ScoringConfig.id.desc()).first()
    if not kayit:
        return None
    return {ozellik: getattr(kayit, ozellik) for ozellik in OZELLIK_SIRASI}


def _sigmoid(z):
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    ez = math.exp(z)
    return ez / (1.0 + ez)


def _lojistik_regresyon_egit(X, y, ogrenme_orani=0.1, epoch_sayisi=1000):
    m = len(X)
    n = len(X[0])
    agirliklar = [0.0] * n
    bias = 0.0

    for _ in range(epoch_sayisi):
        tahminler = []
        for i in range(m):
            z = bias + sum(agirliklar[j] * X[i][j] for j in range(n))
            tahminler.append(_sigmoid(z))

        bias_gradyan = sum(tahminler[i] - y[i] for i in range(m)) / m
        bias -= ogrenme_orani * bias_gradyan

        for j in range(n):
            agirlik_gradyan = sum((tahminler[i] - y[i]) * X[i][j] for i in range(m)) / m
            agirliklar[j] -= ogrenme_orani * agirlik_gradyan

    return agirliklar


MIN_TOPLAM_ORNEK = 40
MIN_SINIF_ORNEK = 10


def yeniden_egit():
    geribildirimler = models.Geribildirim.query.all()

    X = []
    y = []
    for gb in geribildirimler:
        eslesme = models.Eslesme.query.get(gb.eslesme_id)
        if not eslesme or not eslesme.analiz_sonucu:
            continue
        alt_puanlar = eslesme.analiz_sonucu.get('alt_puanlar')
        if not alt_puanlar:
            continue
        try:
            ozellikler = [alt_puanlar[ozellik] / 100.0 for ozellik in OZELLIK_SIRASI]
        except (KeyError, TypeError):
            continue
        X.append(ozellikler)
        y.append(1 if gb.deger == 'olumlu' else 0)

    toplam = len(y)
    olumlu_sayisi = sum(y)
    olumsuz_sayisi = toplam - olumlu_sayisi

    if toplam < MIN_TOPLAM_ORNEK or olumlu_sayisi < MIN_SINIF_ORNEK or olumsuz_sayisi < MIN_SINIF_ORNEK:
        return None, f"Yetersiz veri ({toplam}/{MIN_TOPLAM_ORNEK})"

    agirliklar_ham = _lojistik_regresyon_egit(X, y)
    mutlak_degerler = [abs(w) for w in agirliklar_ham]
    toplam_mutlak = sum(mutlak_degerler)

    if toplam_mutlak == 0:
        normalize_edilmis = [VARSAYILAN_AGIRLIKLAR[ozellik] for ozellik in OZELLIK_SIRASI]
    else:
        normalize_edilmis = [w / toplam_mutlak for w in mutlak_degerler]

    yeni_agirliklar = dict(zip(OZELLIK_SIRASI, normalize_edilmis))

    kayit = models.ScoringConfig(
        teknik=yeni_agirliklar['teknik'],
        deneyim=yeni_agirliklar['deneyim'],
        egitim=yeni_agirliklar['egitim'],
        dil=yeni_agirliklar['dil'],
        sertifika=yeni_agirliklar['sertifika'],
        ornek_sayisi=toplam,
    )
    db.session.add(kayit)
    db.session.commit()

    return yeni_agirliklar, None
