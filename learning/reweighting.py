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
