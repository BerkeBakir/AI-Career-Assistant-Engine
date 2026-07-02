import os
import re
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort, jsonify
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask_wtf.csrf import CSRFProtect
from datetime import timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import functions
from extensions import db
import models
import job_search_service

# .env dosyasini yukle
load_dotenv()

# Logging yapilandirmasi
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)

# Guvenlik ayarlari - environment variable'lardan al
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'proje.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'uploads')

# Dosya yukleme sinirlari
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB maksimum dosya boyutu
ALLOWED_EXTENSIONS = {'pdf', 'docx'}

# CSRF korumasi
csrf = CSRFProtect(app)

db.init_app(app)

def allowed_file(filename):
    """Dosya uzantisini kontrol et"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_password(password):
    """Sifre guvenlik kontrolu - en az 8 karakter, 1 buyuk harf, 1 rakam"""
    if len(password) < 8:
        return False, "Sifre en az 8 karakter olmali"
    if not re.search(r'[A-Z]', password):
        return False, "Sifre en az 1 buyuk harf icermeli"
    if not re.search(r'[0-9]', password):
        return False, "Sifre en az 1 rakam icermeli"
    return True, None

def validate_email(email):
    """Basit email format kontrolu"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/kayit', methods=['GET', 'POST'])
def kayit():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        parola = request.form.get('parola', '')
        parola_tekrar = request.form.get('parola_tekrar', '')

        # Email validasyonu
        if not email or not validate_email(email):
            flash('Gecerli bir e-posta adresi girin!', 'danger')
            return redirect(url_for('kayit'))

        # Sifre eslestirme kontrolu
        if parola != parola_tekrar:
            flash('Sifreler eslesmiyor!', 'danger')
            return redirect(url_for('kayit'))

        # Sifre guclulik kontrolu
        is_valid, error_msg = validate_password(parola)
        if not is_valid:
            flash(error_msg, 'danger')
            return redirect(url_for('kayit'))

        # Email benzersizlik kontrolu
        if models.Kullanici.query.filter_by(email=email).first():
            flash('Bu e-posta adresi zaten kayitli!', 'danger')
            return redirect(url_for('kayit'))

        try:
            yeni = models.Kullanici(email=email, parola=generate_password_hash(parola))
            db.session.add(yeni)
            db.session.commit()
            logger.info(f"Yeni kullanici kaydi: {email}")
            flash('Kayit basarili! Giris yapabilirsiniz.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            logger.error(f"Kayit hatasi: {e}")
            db.session.rollback()
            flash('Kayit sirasinda bir hata olustu!', 'danger')
            return redirect(url_for('kayit'))

    return render_template('kayit.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        parola = request.form.get('parola', '')
        user = models.Kullanici.query.filter_by(email=email).first()
        if user and check_password_hash(user.parola, parola):
            session.permanent = True
            session['user_id'] = user.id
            logger.info(f"Kullanici girisi: {email}")
            return redirect(url_for('panel'))
        else:
            logger.warning(f"Basarisiz giris denemesi: {email}")
            flash('Hatali giris.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    user_id = session.get('user_id')
    session.clear()
    logger.info(f"Kullanici cikisi: user_id={user_id}")
    return redirect(url_for('index'))

@app.route('/panel')
def panel():
    if 'user_id' not in session: return redirect(url_for('login'))
    user_id = session['user_id']
    cv_sayisi = models.CV.query.filter_by(aday_id=user_id).count()
    # Sadece kullanicinin buldugu ilanlari say
    ilan_sayisi = models.IsIlani.query.filter_by(bulan_kullanici_id=user_id).count()
    return render_template('panel.html', cv_sayisi=cv_sayisi, ilan_sayisi=ilan_sayisi)

@app.route('/cv-islemleri', methods=['GET', 'POST'])
def cv_islemleri():
    if 'user_id' not in session: return redirect(url_for('login'))
    user_id = session['user_id']

    if request.method == 'POST' and 'cv' in request.files:
        file = request.files['cv']
        if file.filename != '':
            # Dosya tipi kontrolu
            if not allowed_file(file.filename):
                flash('Sadece PDF ve DOCX dosyalari yuklenebilir!', 'danger')
                return redirect(url_for('cv_islemleri'))

            filename = secure_filename(file.filename)
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])
            path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            try:
                file.save(path)
                metin, err = functions.metin_cikar(path)
                if err:
                    flash(f'Dosya okunamadi: {err}', 'danger')
                    return redirect(url_for('cv_islemleri'))

                analiz, err = functions.bilgileri_cikar(metin)
                if err:
                    flash(f'CV analiz edilemedi: {err}', 'danger')
                    return redirect(url_for('cv_islemleri'))

                if not models.CV.query.filter_by(aday_id=user_id, orjinal_dosya_adi=filename).first():
                    db.session.add(models.CV(orjinal_dosya_adi=filename, aday_id=user_id, cikarilan_veriler=analiz))
                    db.session.commit()
                    logger.info(f"CV yuklendi: {filename} (user_id={user_id})")
                    flash('CV basariyla yuklendi!', 'success')
                else:
                    flash('Bu CV daha once yuklenmis!', 'warning')
            except Exception as e:
                logger.error(f"CV yukleme hatasi: {e}")
                flash('CV yuklenirken bir hata olustu!', 'danger')

    cvler = models.CV.query.filter_by(aday_id=user_id).all()
    return render_template('cv_islemleri.html', cvler=cvler)

@app.route('/cv/sil/<int:cv_id>', methods=['POST'])
def cv_sil(cv_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    cv = models.CV.query.get_or_404(cv_id)
    if cv.aday_id != session['user_id']: abort(403)

    try:
        # Iliskili eslesmeleri sil
        models.Eslesme.query.filter_by(cv_id=cv.id).delete()

        # Dosyayi sil
        path = os.path.join(app.config['UPLOAD_FOLDER'], cv.orjinal_dosya_adi)
        if os.path.exists(path):
            os.remove(path)

        db.session.delete(cv)
        db.session.commit()
        logger.info(f"CV silindi: cv_id={cv_id}")
        flash('CV basariyla silindi!', 'success')
    except Exception as e:
        logger.error(f"CV silme hatasi: {e}")
        db.session.rollback()
        flash('CV silinirken bir hata olustu!', 'danger')

    return redirect(url_for('cv_islemleri'))

@app.route('/is-ara', methods=['GET', 'POST'])
def is_ara_sayfasi():
    if 'user_id' not in session: return redirect(url_for('login'))
    user_id = session['user_id']
    cvler = models.CV.query.filter_by(aday_id=user_id).all()

    if request.method == 'POST':
        cv = models.CV.query.get(request.form.get('secilen_cv_id'))
        if cv and cv.aday_id == user_id:
            try:
                sonuclar = job_search_service.search_jobs(cv.cikarilan_veriler.get('yetenekler', []))
                if sonuclar:
                    eklenen = 0
                    for ilan in sonuclar:
                        if not models.IsIlani.query.filter_by(kaynak_url=ilan['link']).first():
                            yeni_ilan = models.IsIlani(
                                baslik=ilan['baslik'],
                                sirket_adi=ilan.get('sirket', 'Belirsiz'),
                                kaynak_url=ilan['link'],
                                kaynak_site=ilan.get('kaynak', 'Web'),
                                aciklama_ozeti=ilan.get('aciklama', ''),
                                bulan_kullanici_id=user_id  # Kullanici iliskisi
                            )
                            db.session.add(yeni_ilan)
                            eklenen += 1
                    db.session.commit()
                    logger.info(f"Is arama tamamlandi: {eklenen} yeni ilan (user_id={user_id})")
                    flash(f'{eklenen} yeni is ilani bulundu!', 'success')
                    return redirect(url_for('kaydedilenler'))
                else:
                    flash('Is ilani bulunamadi.', 'warning')
            except Exception as e:
                logger.error(f"Is arama hatasi: {e}")
                flash('Arama sirasinda bir hata olustu!', 'danger')

    return render_template('is_ara.html', cvler=cvler)

@app.route('/kaydedilenler')
def kaydedilenler():
    if 'user_id' not in session: return redirect(url_for('login'))
    user_id = session['user_id']

    # Sadece kullanicinin buldugu ilanlari goster
    ilanlar = models.IsIlani.query.filter_by(bulan_kullanici_id=user_id).order_by(models.IsIlani.id.desc()).limit(100).all()
    cvler = models.CV.query.filter_by(aday_id=user_id).all()

    puanlar = {}
    analizler = {}
    if cvler:
        for e in models.Eslesme.query.filter_by(cv_id=cvler[0].id).all():
            puanlar[e.is_ilani_id] = e.skor
            analizler[e.is_ilani_id] = e.analiz_sonucu

    return render_template('kaydedilenler.html', ilanlar=ilanlar, puanlar=puanlar, analizler=analizler, cvler=cvler)

@app.route('/analiz-et/<int:ilan_id>/<int:cv_id>', methods=['POST'])
def tekil_analiz(ilan_id, cv_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    user_id = session['user_id']

    ilan = models.IsIlani.query.get_or_404(ilan_id)
    cv = models.CV.query.get_or_404(cv_id)

    # Yetki kontrolu
    if cv.aday_id != user_id:
        abort(403)
    if ilan.bulan_kullanici_id != user_id:
        abort(403)

    try:
        metin = ilan.gereksinimler_json.get('full_text') if ilan.gereksinimler_json else None
        if not metin:
            metin, _ = functions.url_den_ilan_cek(ilan.kaynak_url)
            if not metin:
                metin = f"{ilan.baslik} {ilan.sirket_adi} {ilan.aciklama_ozeti}"
            ilan.gereksinimler_json = {"full_text": metin}
            db.session.commit()

        sonuc, err = functions.ilani_karsilastir(cv.cikarilan_veriler, metin)
        if not err:
            eslesme = models.Eslesme.query.filter_by(cv_id=cv.id, is_ilani_id=ilan.id).first()
            if not eslesme:
                eslesme = models.Eslesme(cv_id=cv.id, is_ilani_id=ilan.id, skor=0)
                db.session.add(eslesme)
            eslesme.skor = sonuc.get('uygunluk_skoru', 0)
            eslesme.analiz_sonucu = sonuc
            db.session.commit()
            logger.info(f"Analiz tamamlandi: ilan_id={ilan_id}, cv_id={cv_id}, skor={eslesme.skor}")
        else:
            flash(f'Analiz hatasi: {err}', 'danger')
    except Exception as e:
        logger.error(f"Tekil analiz hatasi: {e}")
        flash('Analiz sirasinda bir hata olustu!', 'danger')

    return redirect(url_for('kaydedilenler'))

def _tek_ilan_analiz_et(ilan_id, cv_id, cv_verisi, user_id):
    """Tek bir ilanı analiz eder (paralel çalışma için)"""
    try:
        with app.app_context():
            ilan = models.IsIlani.query.get(ilan_id)
            if not ilan or ilan.bulan_kullanici_id != user_id:
                return {'ilan_id': ilan_id, 'success': False, 'error': 'Yetkisiz'}
            
            # İlan metnini al veya çek
            metin = ilan.gereksinimler_json.get('full_text') if ilan.gereksinimler_json else None
            if not metin:
                metin, _ = functions.url_den_ilan_cek(ilan.kaynak_url)
                if not metin:
                    metin = f"{ilan.baslik} {ilan.sirket_adi} {ilan.aciklama_ozeti}"
                ilan.gereksinimler_json = {"full_text": metin}
                db.session.commit()
            
            # AI analizi yap
            sonuc, err = functions.ilani_karsilastir(cv_verisi, metin)
            if err:
                return {'ilan_id': ilan_id, 'success': False, 'error': err}
            
            # Eşleşme kaydet
            eslesme = models.Eslesme.query.filter_by(cv_id=cv_id, is_ilani_id=ilan.id).first()
            if not eslesme:
                eslesme = models.Eslesme(cv_id=cv_id, is_ilani_id=ilan.id, skor=0)
                db.session.add(eslesme)
            eslesme.skor = sonuc.get('uygunluk_skoru', 0)
            eslesme.analiz_sonucu = sonuc
            db.session.commit()
            
            return {'ilan_id': ilan_id, 'success': True, 'skor': eslesme.skor, 'baslik': ilan.baslik}
    except Exception as e:
        logger.error(f"Paralel analiz hatası (ilan_id={ilan_id}): {e}")
        return {'ilan_id': ilan_id, 'success': False, 'error': str(e)}

@app.route('/toplu-analiz', methods=['POST'])
def toplu_analiz():
    """Analiz edilmemiş tüm ilanları paralel olarak analiz eder"""
    if 'user_id' not in session:
        return jsonify({'error': 'Oturum gerekli'}), 401
    
    user_id = session['user_id']
    cv = models.CV.query.filter_by(aday_id=user_id).first()
    
    if not cv:
        return jsonify({'error': 'CV bulunamadı'}), 400
    
    # Analiz edilmemiş ilanları bul
    ilanlar = models.IsIlani.query.filter_by(bulan_kullanici_id=user_id).all()
    mevcut_analizler = {e.is_ilani_id for e in models.Eslesme.query.filter_by(cv_id=cv.id).all()}
    
    analiz_edilecek = [ilan for ilan in ilanlar if ilan.id not in mevcut_analizler]
    
    if not analiz_edilecek:
        return jsonify({'message': 'Tüm ilanlar zaten analiz edilmiş', 'toplam': 0, 'basarili': 0})
    
    sonuclar = []
    basarili = 0
    
    # Paralel analiz - max 5 thread ile
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(_tek_ilan_analiz_et, ilan.id, cv.id, cv.cikarilan_veriler, user_id): ilan
            for ilan in analiz_edilecek
        }
        
        for future in as_completed(futures):
            sonuc = future.result()
            sonuclar.append(sonuc)
            if sonuc.get('success'):
                basarili += 1
    
    logger.info(f"Toplu analiz tamamlandi: {basarili}/{len(analiz_edilecek)} basarili (user_id={user_id})")
    
    return jsonify({
        'message': f'{basarili} ilan başarıyla analiz edildi',
        'toplam': len(analiz_edilecek),
        'basarili': basarili,
        'sonuclar': sonuclar
    })

# Hata sayfalari
@app.errorhandler(413)
def too_large(e):
    flash('Dosya cok buyuk! Maksimum 16 MB yuklenebilir.', 'danger')
    return redirect(url_for('cv_islemleri'))

@app.errorhandler(403)
def forbidden(e):
    flash('Bu islemi yapmaya yetkiniz yok!', 'danger')
    return redirect(url_for('panel'))

@app.errorhandler(404)
def not_found(e):
    flash('Sayfa bulunamadi!', 'danger')
    return redirect(url_for('index'))

if __name__ == '__main__':
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode)
