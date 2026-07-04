from extensions import db
from datetime import datetime

class Kullanici(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    parola = db.Column(db.String(128), nullable=False)
    rol = db.Column(db.String(10), nullable=False, default='aday')
    cvler = db.relationship('CV', backref='kullanici', lazy=True, cascade='all, delete-orphan')
    bulunan_ilanlar = db.relationship('IsIlani', backref='bulan_kullanici', lazy=True)

class CV(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    orjinal_dosya_adi = db.Column(db.String(300), nullable=False)
    cikarilan_veriler = db.Column(db.JSON, nullable=True)
    aday_id = db.Column(db.Integer, db.ForeignKey('kullanici.id'), nullable=False)
    eslesmeler = db.relationship('Eslesme', backref='cv', lazy=True, cascade='all, delete-orphan')

class IsIlani(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    baslik = db.Column(db.String(300), nullable=True)
    sirket_adi = db.Column(db.String(255), nullable=True)
    kaynak_url = db.Column(db.String(500), unique=True, nullable=False)
    kaynak_site = db.Column(db.String(100), nullable=True)
    aciklama_ozeti = db.Column(db.Text, nullable=True)
    bulunma_tarihi = db.Column(db.DateTime, default=datetime.utcnow)
    gereksinimler_json = db.Column(db.JSON, nullable=True)
    # Ilani bulan kullanici (gizlilik icin)
    bulan_kullanici_id = db.Column(db.Integer, db.ForeignKey('kullanici.id'), nullable=True)
    eslesmeler = db.relationship('Eslesme', backref='is_ilani', lazy=True, cascade='all, delete-orphan')

class Eslesme(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cv_id = db.Column(db.Integer, db.ForeignKey('cv.id'), nullable=False)
    is_ilani_id = db.Column(db.Integer, db.ForeignKey('is_ilani.id'), nullable=False)
    skor = db.Column(db.Integer, nullable=False)
    analiz_sonucu = db.Column(db.JSON, nullable=True)


class Geribildirim(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    eslesme_id = db.Column(db.Integer, db.ForeignKey('eslesme.id'), nullable=False)
    kullanici_id = db.Column(db.Integer, db.ForeignKey('kullanici.id'), nullable=False)
    deger = db.Column(db.String(10), nullable=False)  # 'olumlu' veya 'olumsuz'
    olusturulma_tarihi = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('eslesme_id', 'kullanici_id', name='uq_geribildirim_eslesme_kullanici'),
    )


class ScoringConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teknik = db.Column(db.Float, nullable=False)
    deneyim = db.Column(db.Float, nullable=False)
    egitim = db.Column(db.Float, nullable=False)
    dil = db.Column(db.Float, nullable=False)
    sertifika = db.Column(db.Float, nullable=False)
    ornek_sayisi = db.Column(db.Integer, nullable=False)
    olusturulma_tarihi = db.Column(db.DateTime, default=datetime.utcnow)