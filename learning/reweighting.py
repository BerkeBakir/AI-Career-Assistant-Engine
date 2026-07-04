import math

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
