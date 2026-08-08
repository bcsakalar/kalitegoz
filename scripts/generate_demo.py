"""KaliteGoz demo verisi ureteci (v2 — cok kanalli, kurumsal).

- 12 sentetik Turkce SESLI cagri diyalogu (icinde: KVKK okumayan, kaba/yasakli
  uslup, KRIZ (ofkeli musteri + hukuki soylem), YANLIS BILGI veren temsilci).
  Seslendirme GERCEK iki konusmaciyla yapilir (edge-tts): kadin=Emel, erkek=Ahmet.
  Temsilcinin cinsiyeti kadrodan, musterininki metindeki hitaptan ("Fatma Hanim")
  cikarilir; boylece ses her zaman metinle tutarlidir. Internet yoksa Piper'a
  dusulur (tek TR model + pitch — ayrim zayiftir, bkz. scripts/tts_engines.py).
  8kHz STEREO wav: SOL=musteri, SAG=temsilci (bedava kanal-ayrimi diarization).
- 6 CHAT gorusmesi (yazisma kanali) — STT gerektirmez, dogrudan puanlanir
  (robotik/gec yanit senaryosu dahil). Yalnizca --upload ile yuklenir.
- --upload ile ayrica 8 haftalik sentetik GECMIS veri eklenir (dashboard bos gorunmesin).

Kullanim:
    pip install -r scripts/requirements.txt
    python scripts/generate_demo.py                      # data/inbox'a wav yazar (watcher alir)
    python scripts/generate_demo.py --upload http://localhost:8000   # auth'lu tam demo
    python scripts/generate_demo.py --use-llm            # sesli diyaloglari Ollama'ya urettir
    python scripts/generate_demo.py --tts-engine piper   # cevrimdisi seslendirme

Varsayilan seslendirme edge-tts ile yapilir (internet ister, model indirmez).
--tts-engine piper secilirse HuggingFace'ten ~60 MB model indirilir.
"""

import argparse
import json
import random
import sys
import urllib.request
import uuid
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tr_gender import gender_from_name, infer_speaker_gender  # noqa: E402
from tts_engines import make_engine, speaker_variant  # noqa: E402

TARGET_SR = 8000  # telefon hatti

# Temsilci kadrosu — bu adlari biz uydurdugumuz icin cinsiyetleri BURASI
# belirler (sozluk tahminine birakmayiz; "deniz" gibi unisex adlarda tahmin
# zaten None doner). Musterinin cinsiyeti ise metindeki hitaptan cikarilir.
FEMALE_AGENTS = {
    "ayse.yilmaz", "zeynep.demir", "elif.arslan", "selin.koc",
    "gizem.celik", "pelin.acar", "deniz.yildiz",
}
MALE_AGENTS = {
    "mehmet.kaya", "emre.sahin", "burak.ozturk", "caner.aydin", "okan.dogan",
}


def agent_gender(name: str) -> str:
    """Temsilcinin ses cinsiyeti: once kadro, sonra ad sozlugu, son care erkek."""
    if name in FEMALE_AGENTS:
        return "kadin"
    if name in MALE_AGENTS:
        return "erkek"
    return gender_from_name(name) or "erkek"


def customer_gender(turns: list[dict], rng: random.Random) -> str:
    """Musterinin ses cinsiyeti — TEMSILCININ ona nasil HITAP ettigine gore.

    Onceki surumde musteri "temsilcinin ziddi" olarak atanirdi; bu kural 12
    cagrinin 7'sinde sesi metinle celiskiye dusuruyordu ("Fatma Hanim" erkek
    sesiyle konusuyordu). Hitap yoksa rastgele atanir — cinsiyet karisimini
    rastgelelik saglar, zorlama bir kural degil.

    Yalnizca temsilcinin replikleri taranir: "X Hanim" diyen MUSTERI ise
    hitap TEMSILCIYE gidiyordur ve musterinin cinsiyeti hakkinda hicbir sey
    soylemez. (Gomulu diyaloglarda hepsi temsilci repliginde, ama --use-llm
    ile uretilen diyaloglarda musteri de temsilciye hitap edebilir.)
    """
    agent_text = " ".join(t["m"] for t in turns if t["k"] == "t")
    return infer_speaker_gender(text=agent_text) or rng.choice(["kadin", "erkek"])

# =====================================================================
# Gomulu diyaloglar — LLM erisimi olmadan da demo uretilebilsin diye.
# Her satir: {"k": "t"|"m", "m": metin, "gap": onceki replige gore saniye
# (negatif = soz kesme / bindirme)}
# =====================================================================

DIALOGS = [
    {
        "agent": "ayse.yilmaz",
        "category": "fatura",
        "note": "iyi cagri — iade + ek paket cozumu",
        "turns": [
            {"k": "t", "m": "Netix İletişim'e hoş geldiniz, ben Ayşe. Görüşmemiz kalite standartları gereği kayıt altına alınmaktadır ve kişisel verileriniz KVKK kapsamında işlenmektedir. Size nasıl yardımcı olabilirim?"},
            {"k": "m", "m": "İyi günler. Bu ay faturam çok yüksek gelmiş. İki yüz seksen lira. Normalde yüz elli civarında ödüyordum."},
            {"k": "t", "m": "Hemen kontrol ediyorum. İşlem güvenliği için adınızı, soyadınızı ve müşteri numaranızı teyit edebilir miyim?"},
            {"k": "m", "m": "Mehmet Demir. Müşteri numaram bir iki üç dört beş altı."},
            {"k": "t", "m": "Teşekkür ederim Mehmet Bey. Faturanızı inceliyorum. Bu ay faturanıza yurt dışı arama ücreti eklenmiş. Kırk beş dakikalık bir görüşme görünüyor."},
            {"k": "m", "m": "Evet, kardeşim Almanya'da yaşıyor, onu aramıştım. Ama bu kadar tutacağını bilmiyordum açıkçası."},
            {"k": "t", "m": "Sizi çok iyi anlıyorum. Dilerseniz size aylık kırk dakika yurt dışı görüşme içeren ek paketi tanımlayayım, ücreti ayda otuz beş lira. Ayrıca bu görüşme ücretinin doksan lirasını tek seferlik iade edebiliyorum."},
            {"k": "m", "m": "Çok iyi olur, ikisini de yapalım lütfen."},
            {"k": "t", "m": "İşleminizi tamamladım. Faturanızdan doksan lira iade edildi, güncel tutarınız yüz doksan lira. Ek paketiniz de bir sonraki fatura döneminden itibaren geçerli olacak."},
            {"k": "m", "m": "Çok teşekkür ederim, sağ olun."},
            {"k": "t", "m": "Rica ederim. Başka bir konuda yardımcı olabilir miyim?"},
            {"k": "m", "m": "Yok, hepsi bu kadar."},
            {"k": "t", "m": "Bizi tercih ettiğiniz için teşekkür ederiz. İyi günler dilerim Mehmet Bey."},
        ],
    },
    {
        "agent": "mehmet.kaya",
        "category": "ariza",
        "note": "iyi cagri — modem arizasi cozumu",
        "turns": [
            {"k": "t", "m": "Netix İletişim teknik destek hattına hoş geldiniz, ben Mehmet. Görüşmemiz kalite amacıyla kayıt altındadır, kişisel verileriniz KVKK kapsamında işlenmektedir. Nasıl yardımcı olabilirim?"},
            {"k": "m", "m": "Merhaba. Dünden beri internetim çok yavaş, akşamları neredeyse hiç açılmıyor sayfalar."},
            {"k": "t", "m": "Hemen bakıyorum. Adınızı ve hizmet numaranızı alabilir miyim?"},
            {"k": "m", "m": "Ali Vural, hizmet numaram beş beş üç iki bir dokuz."},
            {"k": "t", "m": "Teşekkürler Ali Bey. Hattınıza sinyal testi gönderiyorum, yaklaşık bir dakika sürecek, hatta kalabilir misiniz?"},
            {"k": "m", "m": "Tabii, bekliyorum."},
            {"k": "t", "m": "Testiniz tamamlandı. Modeminizin sinyal seviyelerinde dalgalanma görüyorum. Modemin arkasındaki güç düğmesinden kapatıp on saniye bekleyip tekrar açar mısınız?"},
            {"k": "m", "m": "Tamam, kapattım. Açıyorum şimdi. Işıklar yandı, evet."},
            {"k": "t", "m": "Harika. Şu an hattınız temiz görünüyor ve hızınız normale döndü. Sorun devam ederse yarın için ücretsiz teknisyen randevusu oluşturabilirim, ister misiniz?"},
            {"k": "m", "m": "Şimdilik gerek yok, düzelmiş gibi. Teşekkür ederim."},
            {"k": "t", "m": "Rica ederim. Başka bir konuda yardımcı olabilir miyim?"},
            {"k": "m", "m": "Yok, iyi günler."},
            {"k": "t", "m": "İyi günler dilerim Ali Bey, sağlıcakla kalın."},
        ],
    },
    {
        "agent": "zeynep.demir",
        "category": "iptal",
        "note": "iyi cagri — iptal talebi, alternatif teklif, islem baslatildi",
        "turns": [
            {"k": "t", "m": "Netix İletişim'e hoş geldiniz, ben Zeynep. Görüşmemiz kayıt altına alınmaktadır ve verileriniz KVKK kapsamında korunmaktadır. Size nasıl yardımcı olabilirim?"},
            {"k": "m", "m": "Merhaba, hattımı iptal ettirmek istiyorum. Taşınıyorum ve yeni evde başka operatör kullanacağım."},
            {"k": "t", "m": "Üzüldüm bunu duyduğuma. İşlem için ad soyad ve doğum yılınızı teyit edebilir miyim?"},
            {"k": "m", "m": "Fatma Şahin, bin dokuz yüz doksan."},
            {"k": "t", "m": "Teşekkürler Fatma Hanım. Kaydınıza baktım, taahhüdünüz iki ay önce bitmiş, cayma bedeli çıkmayacak. Dilerseniz yeni adresinizde de hizmetimiz varsa nakil yapabiliriz, ilk üç ay yüzde elli indirimli olur."},
            {"k": "m", "m": "Teklif için teşekkürler ama binada altyapınız yokmuş, komşulara sordum. İptal edelim."},
            {"k": "t", "m": "Anlıyorum. İptal talebinizi oluşturuyorum. Hattınız yedi iş günü içinde kapanacak ve son faturanız kullanım gününe göre hesaplanacak. Modem cihazını da kargo ile ücretsiz iade edebilirsiniz, adresinize kod göndereceğim."},
            {"k": "m", "m": "Tamamdır, çok net oldu, teşekkürler."},
            {"k": "t", "m": "Rica ederim. Başka bir konuda yardımcı olabilir miyim?"},
            {"k": "m", "m": "Hayır, teşekkürler."},
            {"k": "t", "m": "Bizi tercih ettiğiniz için teşekkür ederiz, yeni evinizde mutluluklar dilerim. İyi günler."},
        ],
    },
    {
        "agent": "ayse.yilmaz",
        "category": "bilgi",
        "note": "iyi cagri — tarife bilgisi",
        "turns": [
            {"k": "t", "m": "Netix İletişim'e hoş geldiniz, ben Ayşe. Görüşmemiz kalite standartları gereği kayıt altına alınmaktadır, kişisel verileriniz KVKK kapsamında işlenmektedir. Nasıl yardımcı olabilirim?"},
            {"k": "m", "m": "İyi günler. Gençlere özel tarifeniz varmış, onun detaylarını öğrenmek istiyorum."},
            {"k": "t", "m": "Tabii, memnuniyetle. Genç tarifemiz yirmi altı yaş altı müşterilerimize özel. Aylık yirmi gigabayt internet, bin dakika ve sınırsız mesaj içeriyor, ücreti ayda yüz yirmi lira."},
            {"k": "m", "m": "Öğrenci belgesi gerekiyor mu peki?"},
            {"k": "t", "m": "Hayır, öğrenci belgesi gerekmiyor, kimlik yaşınız yeterli. Yalnızca e-devlet üzerinden yaş doğrulaması yapılıyor."},
            {"k": "m", "m": "Peki mevcut numaramı taşıyabilir miyim bu tarifeye?"},
            {"k": "t", "m": "Elbette, numara taşıma işlemi ücretsiz ve ortalama iki iş günü sürüyor. Dilerseniz şimdi başvurunuzu başlatabilirim."},
            {"k": "m", "m": "Şimdilik sadece bilgi almak istemiştim, ailemle konuşup karar vereceğim."},
            {"k": "t", "m": "Elbette, karar verdiğinizde yüz altmış bir numaralı hattımızdan bize ulaşabilirsiniz. Başka bir konuda yardımcı olabilir miyim?"},
            {"k": "m", "m": "Yok, teşekkür ederim."},
            {"k": "t", "m": "Ben teşekkür ederim, iyi günler dilerim."},
        ],
    },
    {
        "agent": "mehmet.kaya",
        "category": "sikayet",
        "note": "iyi cagri — teknisyen gelmedi sikayeti, kayit + net sure",
        "turns": [
            {"k": "t", "m": "Netix İletişim'e hoş geldiniz, ben Mehmet. Görüşmemiz kayıt altına alınmaktadır ve verileriniz KVKK kapsamında işlenmektedir. Size nasıl yardımcı olabilirim?"},
            {"k": "m", "m": "İyi günler ama hiç iyi değilim açıkçası. Dün için teknisyen randevusu verilmişti, bütün gün evde bekledim, gelen giden olmadı. Arayan da olmadı."},
            {"k": "t", "m": "Bunun için gerçekten çok üzgünüm, yaşattığımız mağduriyet için özür dilerim. Hemen kaydınıza bakıyorum. Adınızı ve hizmet numaranızı alabilir miyim?"},
            {"k": "m", "m": "Hasan Yıldız, dört dört yedi sekiz iki bir."},
            {"k": "t", "m": "Teşekkürler Hasan Bey. Görüyorum, dünkü randevunuz saha ekibi tarafından kapatılmamış, sistemsel bir aksaklık olmuş. Bu durum için şikayet kaydınızı oluşturuyorum ve randevunuzu yarın öncelikli olarak, saat dokuz ile on iki arasına alıyorum."},
            {"k": "m", "m": "Yarın kesin gelecekler mi peki? Yine izin alacağım işten."},
            {"k": "t", "m": "Kaydı öncelikli ve yöneticili takip statüsünde açtım. Teknisyen yola çıkmadan yarım saat önce sizi cep telefonunuzdan arayacak. Gelmezse bu kayıt numarasıyla faturanıza bir aylık indirim tanımlanacak: kayıt numaranız üç iki bir dokuz."},
            {"k": "m", "m": "Tamam, not aldım. Umarım bu sefer olur."},
            {"k": "t", "m": "Takibini bizzat yapacağım Hasan Bey. Tekrar özür diler, anlayışınız için teşekkür ederim. Başka bir konuda yardımcı olabilir miyim?"},
            {"k": "m", "m": "Yok, şimdilik bu."},
            {"k": "t", "m": "İyi günler dilerim, sağlıcakla kalın."},
        ],
    },
    {
        "agent": "zeynep.demir",
        "category": "fatura",
        "note": "iyi cagri — otomatik odeme talimati",
        "turns": [
            {"k": "t", "m": "Netix İletişim'e hoş geldiniz, ben Zeynep. Görüşmemiz kalite amacıyla kayıt altındadır, kişisel verileriniz KVKK kapsamında işlenmektedir. Nasıl yardımcı olabilirim?"},
            {"k": "m", "m": "Merhaba. Faturamı sürekli unutuyorum, geçen ay gecikme ücreti ödedim. Otomatik ödeme talimatı vermek istiyorum."},
            {"k": "t", "m": "Çok doğru bir tercih. İşlem için ad soyad ve müşteri numaranızı teyit edebilir miyim?"},
            {"k": "m", "m": "Elif Kara, yedi yedi üç beş sıfır sekiz."},
            {"k": "t", "m": "Teşekkürler Elif Hanım. Otomatik ödemeyi banka hesabınızdan mı yoksa kredi kartınızdan mı tanımlamak istersiniz?"},
            {"k": "m", "m": "Kredi kartımdan olsun."},
            {"k": "t", "m": "Güvenliğiniz için kart bilgilerinizi telefonda almıyorum; size mobil uygulamamızdan onaylayacağınız güvenli bir bağlantı gönderiyorum. Mesaj geldi mi?"},
            {"k": "m", "m": "Geldi, açtım. Bilgileri girdim, onay verdi."},
            {"k": "t", "m": "Harika, talimatınız tanımlandı. Bundan sonra faturalarınız son ödeme gününde otomatik tahsil edilecek ve size bilgilendirme mesajı gelecek."},
            {"k": "m", "m": "Süper, çok pratikmiş. Teşekkürler."},
            {"k": "t", "m": "Rica ederim. Başka bir konuda yardımcı olabilir miyim?"},
            {"k": "m", "m": "Hayır, iyi günler."},
            {"k": "t", "m": "İyi günler dilerim Elif Hanım."},
        ],
    },
    {
        "agent": "mehmet.kaya",
        "category": "fatura",
        "note": "KOTU cagri — KVKK yok, acilis eksik, cozumsuz, kapanis yok",
        "turns": [
            {"k": "t", "m": "Alo, buyrun."},
            {"k": "m", "m": "İyi günler. Faturamla ilgili aramıştım. Ödediğim halde hâlâ borç görünüyor."},
            {"k": "t", "m": "Müşteri numaranız?"},
            {"k": "m", "m": "Dokuz sekiz yedi altı beş dört."},
            {"k": "t", "m": "Bakıyorum. Ödemeniz sisteme düşmüş ama gecikme faizi eklenmiş."},
            {"k": "m", "m": "Nasıl yani? Ben son ödeme gününde ödedim, neden faiz ekleniyor?"},
            {"k": "t", "m": "Banka geç iletmiştir, bizlik bir durum yok."},
            {"k": "m", "m": "Peki bu faizi silebilir misiniz? On beş lira ama sonuçta haksız bir tutar."},
            {"k": "t", "m": "Telefonda yapamıyorum. Fatura itiraz formu dolduracaksınız, internet sitesinde var."},
            {"k": "m", "m": "Telefonda halledemiyor muyuz yani? Ben formu nereden bulacağım şimdi?"},
            {"k": "t", "m": "Sitede var dedim. Başka bir şey?"},
            {"k": "m", "m": "Yok yani, madem öyle."},
            {"k": "t", "m": "Tamamdır."},
        ],
    },
    {
        "agent": "ayse.yilmaz",
        "category": "ariza",
        "note": "iyi cagri — TV yayin arizasi",
        "turns": [
            {"k": "t", "m": "Netix İletişim teknik destek hattına hoş geldiniz, ben Ayşe. Görüşmemiz kayıt altına alınmaktadır ve kişisel verileriniz KVKK kapsamında işlenmektedir. Size nasıl yardımcı olabilirim?"},
            {"k": "m", "m": "Merhaba. Televizyonda kanalların yarısı sinyal yok diyor, dünden beri böyle."},
            {"k": "t", "m": "Hemen ilgileniyorum. Adınızı ve abone numaranızı alabilir miyim?"},
            {"k": "m", "m": "Ayten Koç, abone numaram altı bir üç dokuz beş yedi."},
            {"k": "t", "m": "Teşekkürler Ayten Hanım. Bölgenizi kontrol ediyorum. Bölgesel bir yayın sorunu görünmüyor, cihazınıza uzaktan yenileme sinyali gönderiyorum. Televizyonun açık kalmasını rica edeceğim, yaklaşık iki dakika sürecek."},
            {"k": "m", "m": "Tamam, açık, bekliyorum. Ha, şimdi kanallar tek tek gelmeye başladı."},
            {"k": "t", "m": "Çok güzel. Kanal listeniz güncellendi, tüm yayınlarınız açıldı. Sorun tekrar ederse cihazı fişten çekip takmanız çoğu zaman yeterli olur; olmazsa biz her zaman buradayız."},
            {"k": "m", "m": "Çok teşekkür ederim kızım, sağ ol."},
            {"k": "t", "m": "Rica ederim efendim. Başka bir konuda yardımcı olabilir miyim?"},
            {"k": "m", "m": "Yok, iyi günler."},
            {"k": "t", "m": "İyi günler dilerim Ayten Hanım, iyi seyirler."},
        ],
    },
    {
        "agent": "zeynep.demir",
        "category": "sikayet",
        "note": "KOTU cagri — kaba uslup, soz kesme, yasakli ifadeler",
        "turns": [
            {"k": "t", "m": "Netix İletişim, ben Zeynep, buyrun."},
            {"k": "m", "m": "Hanımefendi, üç gündür internetim yok. İki kere aradım, kayıt açıldı dediler ama hâlâ arayan soran..."},
            {"k": "t", "m": "Beyefendi bakın, arıza kaydınız zaten var. Tekrar tekrar aramanıza gerek yok, sıra size gelince yapılacak.", "gap": -1.2},
            {"k": "m", "m": "Ama kimse dönüş yapmadı, ben de haliyle tekrar..."},
            {"k": "t", "m": "Sözünüzü kesiyorum, ekipler yoğun. Herkes sırasını bekliyor, siz de bekleyeceksiniz.", "gap": -1.0},
            {"k": "m", "m": "Bu nasıl konuşma tarzı? Ben müşteriyim burada, üç gündür mağdurum."},
            {"k": "t", "m": "Saçmalamayın lütfen, size standart prosedürü söylüyorum. Benim sizinle uğraşacak başka işim yok mu?"},
            {"k": "m", "m": "Tamam, ben de bu görüşmeyi şikayet hattına bildireceğim o zaman."},
            {"k": "t", "m": "Nereye isterseniz bildirin. Başka bir şey var mı?"},
            {"k": "m", "m": "Yok, kapatıyorum. Yazıklar olsun."},
            {"k": "t", "m": "İyi günler."},
        ],
    },
    {
        "agent": "mehmet.kaya",
        "category": "iptal",
        "note": "iyi cagri — cayma bedeli bilgisi, dondurma alternatifi",
        "turns": [
            {"k": "t", "m": "Netix İletişim'e hoş geldiniz, ben Mehmet. Görüşmemiz kalite standartları gereği kayıt altına alınmaktadır, kişisel verileriniz KVKK kapsamında işlenmektedir. Nasıl yardımcı olabilirim?"},
            {"k": "m", "m": "Merhaba. Altı aylığına yurt dışına gidiyorum, hattımı iptal ettirmek istiyorum."},
            {"k": "t", "m": "Anladım, hemen bakalım. Ad soyad ve müşteri numaranızı teyit edebilir miyim?"},
            {"k": "m", "m": "Kerem Aydın, üç sıfır beş iki yedi dört."},
            {"k": "t", "m": "Teşekkürler Kerem Bey. Kaydınızı inceledim; taahhüdünüzün bitmesine dört ay var, bugün iptal ederseniz üç yüz yirmi lira cayma bedeli yansır. Ancak size daha uygun bir seçenek sunabilirim: hattınızı altı aya kadar dondurabiliyoruz, ayda sadece on beş lira hat koruma ücreti ödersiniz ve döndüğünüzde numaranız aynen açılır."},
            {"k": "m", "m": "Dondurma daha mantıklıymış aslında. Cayma bedeli ödemekten iyidir."},
            {"k": "t", "m": "Kesinlikle daha avantajlı. Dondurma işlemini hangi tarihten itibaren başlatalım?"},
            {"k": "m", "m": "Ayın on beşinden itibaren olsun, o gün uçuşum var."},
            {"k": "t", "m": "Ayarladım. Hattınız ayın on beşinde donacak, altı ay sonra otomatik açılacak. İşlem özetini mesajla da gönderiyorum. Başka bir konuda yardımcı olabilir miyim?"},
            {"k": "m", "m": "Yok, çok teşekkürler, iyi çalışmalar."},
            {"k": "t", "m": "Ben teşekkür ederim Kerem Bey, iyi yolculuklar dilerim. İyi günler."},
        ],
    },
    {
        "agent": "emre.sahin",
        "category": "sikayet",
        "note": "KRIZ cagrisi — ofkeli musteri, hukuki soylem; temsilci sakin ve empatik",
        "turns": [
            {"k": "t", "m": "Netix İletişim'e hoş geldiniz, ben Emre. Görüşmemiz kayıt altına alınmaktadır ve kişisel verileriniz KVKK kapsamında işlenmektedir. Size nasıl yardımcı olabilirim?"},
            {"k": "m", "m": "Bakın artık bıçak kemiğe dayandı! Üç aydır aynı sorun, faturama olmayan bir hizmet ekleniyor. Bu kez tüketici hakem heyetine ve avukatıma gidiyorum, haberiniz olsun!"},
            {"k": "t", "m": "Yaşadığınız bu tekrarlayan sorun için gerçekten çok üzgünüm ve haklı olarak kızgın olduğunuzu anlıyorum. İzin verirseniz bu işi bugün kökten çözelim. Adınızı ve müşteri numaranızı alabilir miyim?"},
            {"k": "m", "m": "Serkan Öz, dört beş altı yedi sekiz dokuz. Ama oyalarsanız gerçekten şikayet edeceğim."},
            {"k": "t", "m": "Sizi oyalamayacağım Serkan Bey, söz veriyorum. Kaydınızı inceliyorum... Evet, görüyorum: iptal ettiğiniz bir dijital paket sistemsel hatayla üç aydır faturanıza yansımış. Bu tamamen bizim hatamız."},
            {"k": "m", "m": "Yani kabul ediyorsunuz. Peki şimdi ne olacak, üç aydır fazladan ödedim ben bunu."},
            {"k": "t", "m": "Sonuna kadar haklısınız. Şu an yapıyorum: üç aylık fazla tahsilatın tamamını faturanıza iade ediyorum, paketi kalıcı olarak kapatıyorum ve yaşattığımız mağduriyet için bir sonraki faturanıza yüzde yirmi indirim tanımlıyorum. İşlem numaranız beş beş dört bir."},
            {"k": "m", "m": "Iyi... en azından bir muhatap bulabildim sonunda. Peki tekrar olmayacağından emin miyim?"},
            {"k": "t", "m": "Paketi kökünden kapattığım için tekrar yansıması teknik olarak mümkün değil. Ayrıca kaydınıza yönetici takip notu ekliyorum; önümüzdeki iki fatura döneminde ben bizzat kontrol edeceğim ve size bilgi vereceğim."},
            {"k": "m", "m": "Tamam, teşekkür ederim. Böyle konuşulunca insan rahatlıyor işte."},
            {"k": "t", "m": "Anlayışınız için ben teşekkür ederim Serkan Bey. Başka bir konuda yardımcı olabilir miyim?"},
            {"k": "m", "m": "Yok, bu kadarı yeterli. İyi günler."},
            {"k": "t", "m": "İyi günler dilerim, tekrar özür diler, iyi hafta sonları dilerim."},
        ],
    },
    {
        "agent": "caner.aydin",
        "category": "bilgi",
        "note": "KOTU cagri — temsilci YANLIS BILGI veriyor (iade suresi/ucret)",
        "turns": [
            {"k": "t", "m": "Netix İletişim, ben Caner, buyrun."},
            {"k": "m", "m": "Merhaba, internetten aldığım modemi iade etmek istiyorum. Süresi ve şartları nedir?"},
            {"k": "t", "m": "Modemde iade süresi bizde otuz gün. Otuz gün içinde getirirseniz sorun olmaz."},
            {"k": "m", "m": "Emin misiniz? Ben on dört gün diye biliyordum mesafeli satışta."},
            {"k": "t", "m": "Yok yok, bizde otuz gün. Bir de iade kargo ücretini maalesef siz ödüyorsunuz, o da yaklaşık iki yüz lira civarı."},
            {"k": "m", "m": "İki yüz lira mı? Kargo bu kadar tutar mı hiç?"},
            {"k": "t", "m": "Genelde o civarda oluyor efendim. Ha bir de açtıysanız iade alamayız, o ayrı."},
            {"k": "m", "m": "Peki tamam, bir düşüneyim o zaman."},
            {"k": "t", "m": "Tabii, iyi günler."},
        ],
    },
]

# =====================================================================
# Chat gorusmeleri (yazisma kanali) — STT gerektirmez, dogrudan puanlanir.
# messages: [{speaker: "musteri"|"temsilci", ts_sec, text}]
# =====================================================================

CHAT_DIALOGS: list[dict] = [
    {
        "agent": "elif.arslan", "category": "fatura",
        "note": "iyi chat — hizli yanit, cozum",
        "messages": [
            {"speaker": "temsilci", "ts_sec": 2, "text": "Netix İletişim canlı desteğe hoş geldiniz, ben Elif. Görüşmemiz kayıt altındadır, verileriniz KVKK kapsamında korunur. Nasıl yardımcı olabilirim?"},
            {"speaker": "musteri", "ts_sec": 15, "text": "Merhaba, faturamı e-posta olarak alamıyorum bir türlü."},
            {"speaker": "temsilci", "ts_sec": 28, "text": "Hemen bakıyorum. Kayıtlı e-posta adresinizi doğrulayabilir miyim?"},
            {"speaker": "musteri", "ts_sec": 40, "text": "serkan@ornek.com olması lazım."},
            {"speaker": "temsilci", "ts_sec": 52, "text": "Adresiniz eski görünüyordu, güncelledim ve son faturanızı tekrar gönderdim. Birkaç dakikaya ulaşır. Başka bir konuda yardımcı olabilir miyim?"},
            {"speaker": "musteri", "ts_sec": 70, "text": "Geldi, teşekkürler!"},
            {"speaker": "temsilci", "ts_sec": 78, "text": "Rica ederim, iyi günler dilerim."},
        ],
    },
    {
        "agent": "selin.koc", "category": "bilgi",
        "note": "iyi chat — tarife bilgisi",
        "messages": [
            {"speaker": "temsilci", "ts_sec": 3, "text": "Merhaba, ben Selin. Görüşmemiz kayıt altındadır, kişisel verileriniz KVKK kapsamında işlenir. Size nasıl yardımcı olabilirim?"},
            {"speaker": "musteri", "ts_sec": 14, "text": "Öğrenci tarifesi hakkında bilgi almak istiyorum."},
            {"speaker": "temsilci", "ts_sec": 26, "text": "Tabii! Genç tarifemiz 20 GB internet, 1000 dakika ve sınırsız mesaj içeriyor, aylık 120 TL. 26 yaş altı müşterilerimize özel."},
            {"speaker": "musteri", "ts_sec": 44, "text": "Numaramı taşıyabilir miyim?"},
            {"speaker": "temsilci", "ts_sec": 55, "text": "Elbette, numara taşıma ücretsiz ve ortalama 2 iş günü sürüyor. İsterseniz başvurunuzu şimdi başlatabilirim."},
            {"speaker": "musteri", "ts_sec": 70, "text": "Şimdilik bilgi almak istedim, teşekkürler."},
            {"speaker": "temsilci", "ts_sec": 80, "text": "Ben teşekkür ederim, iyi günler! Başka bir sorunuz olursa buradayız."},
        ],
    },
    {
        "agent": "burak.ozturk", "category": "sikayet",
        "note": "KOTU chat — robotik kopyala-yapistir yanit, gec yanit, cozumsuz",
        "messages": [
            {"speaker": "temsilci", "ts_sec": 3, "text": "Merhaba, size nasıl yardımcı olabilirim?"},
            {"speaker": "musteri", "ts_sec": 12, "text": "Siparişim 5 gündür kargoda görünüyor ama hareket yok, çok mağdur oldum."},
            {"speaker": "temsilci", "ts_sec": 95, "text": "Talebiniz alınmıştır. İlgili birime iletilmiştir. En kısa sürede dönüş sağlanacaktır."},
            {"speaker": "musteri", "ts_sec": 110, "text": "Ne zaman? Hep aynı şeyi yazıyorsunuz, somut bir tarih verin."},
            {"speaker": "temsilci", "ts_sec": 210, "text": "Talebiniz alınmıştır. İlgili birime iletilmiştir. En kısa sürede dönüş sağlanacaktır."},
            {"speaker": "musteri", "ts_sec": 225, "text": "Bu kadar mı yani? İnanılmaz."},
            {"speaker": "temsilci", "ts_sec": 240, "text": "Anlayışınız için teşekkürler."},
        ],
    },
    {
        "agent": "gizem.celik", "category": "ariza",
        "note": "iyi chat — adim adim sorun cozme",
        "messages": [
            {"speaker": "temsilci", "ts_sec": 2, "text": "Netix teknik destek, ben Gizem. Görüşmemiz kayıt altındadır (KVKK). Nasıl yardımcı olabilirim?"},
            {"speaker": "musteri", "ts_sec": 13, "text": "Modemim sürekli kırmızı ışık yakıyor, internet yok."},
            {"speaker": "temsilci", "ts_sec": 24, "text": "Anladım. Modemi 10 saniye kapatıp açar mısınız? Bu sırada arka kablo bağlantılarını da kontrol edelim."},
            {"speaker": "musteri", "ts_sec": 60, "text": "Kapatıp açtım, kablolar da yerinde. Şimdi turuncu oldu ışık."},
            {"speaker": "temsilci", "ts_sec": 72, "text": "Turuncu senkron demek, güzel. 1-2 dakikada yeşile dönmeli. Hattınıza da yenileme sinyali gönderiyorum."},
            {"speaker": "musteri", "ts_sec": 130, "text": "Yeşil oldu, internet geldi! Çok teşekkürler."},
            {"speaker": "temsilci", "ts_sec": 140, "text": "Ne mutlu bana. Tekrar olursa buradayız. Başka bir konuda yardımcı olabilir miyim?"},
            {"speaker": "musteri", "ts_sec": 155, "text": "Yok, teşekkürler."},
            {"speaker": "temsilci", "ts_sec": 162, "text": "İyi günler dilerim!"},
        ],
    },
    {
        "agent": "okan.dogan", "category": "iptal",
        "note": "iyi chat — iptal + alternatif",
        "messages": [
            {"speaker": "temsilci", "ts_sec": 3, "text": "Merhaba, ben Okan. Görüşmemiz KVKK kapsamında kayıt altındadır. Nasıl yardımcı olabilirim?"},
            {"speaker": "musteri", "ts_sec": 15, "text": "Aboneliğimi iptal etmek istiyorum, çok kullanmıyorum."},
            {"speaker": "temsilci", "ts_sec": 27, "text": "Anlıyorum. Dilerseniz aylık ücreti daha düşük mini pakete geçebilirsiniz; iptal yerine 49 TL'lik pakette hattınız açık kalır. Yine de iptal isterseniz hemen başlatırım."},
            {"speaker": "musteri", "ts_sec": 50, "text": "Mini paket iyiymiş aslında, ona geçelim."},
            {"speaker": "temsilci", "ts_sec": 62, "text": "Tanımladım, bir sonraki dönemde geçerli olacak. Başka bir konuda yardımcı olabilir miyim?"},
            {"speaker": "musteri", "ts_sec": 76, "text": "Yok, teşekkürler."},
            {"speaker": "temsilci", "ts_sec": 83, "text": "İyi günler dilerim!"},
        ],
    },
    {
        "agent": "pelin.acar", "category": "fatura",
        "note": "iyi chat — otomatik odeme",
        "messages": [
            {"speaker": "temsilci", "ts_sec": 2, "text": "Merhaba, ben Pelin. Görüşmemiz kayıt altındadır (KVKK). Size nasıl yardımcı olabilirim?"},
            {"speaker": "musteri", "ts_sec": 12, "text": "Otomatik ödeme talimatı vermek istiyorum, hep unutuyorum faturayı."},
            {"speaker": "temsilci", "ts_sec": 24, "text": "Çok pratik olur. Güvenliğiniz için kart bilgilerinizi burada istemiyorum; uygulamadan onaylayacağınız güvenli bir bağlantı gönderiyorum."},
            {"speaker": "musteri", "ts_sec": 45, "text": "Onayladım, oldu galiba."},
            {"speaker": "temsilci", "ts_sec": 55, "text": "Evet, talimatınız aktif. Bundan sonra son ödeme gününde otomatik tahsil edilecek. Başka bir konuda yardımcı olabilir miyim?"},
            {"speaker": "musteri", "ts_sec": 70, "text": "Hepsi bu, teşekkürler!"},
            {"speaker": "temsilci", "ts_sec": 77, "text": "İyi günler dilerim!"},
        ],
    },
]


# =====================================================================
# Ses isleme
# =====================================================================
# TTS motorlari scripts/tts_engines.py icinde: varsayilan edge-tts (gercek
# kadin/erkek konusmaci), cevrimdisi fallback Piper.


def resample(x: np.ndarray, sr: int, target_sr: int) -> np.ndarray:
    if sr == target_sr:
        return x
    n_out = int(round(len(x) * target_sr / sr))
    return np.interp(
        np.linspace(0, len(x) - 1, n_out), np.arange(len(x)), x
    ).astype(np.float32)


def telephone_effect(x: np.ndarray) -> np.ndarray:
    """Basit telefon hatti benzetimi: hafif kirpma + dusuk seviyeli hat gurultusu."""
    x = np.tanh(x * 1.4) * 0.85
    noise = np.random.normal(0, 0.003, size=x.shape).astype(np.float32)
    return x + noise


def build_stereo_call(
    turns: list[dict],
    synth,
    genders: dict[str, str],
    speakers: dict[str, str],
    rng: random.Random,
) -> np.ndarray:
    """Repliklerden 8kHz stereo (n, 2) int16 uretir. SOL=musteri, SAG=temsilci.

    genders:  {"t": "kadin"|"erkek", "m": ...} — konusmacinin ses cinsiyeti.
    speakers: {"t": "ayse.yilmaz", "m": "cust-3"} — ses varyanti icin kimlik;
              ayni cinsiyetteki farkli kisiler ayni sesle cikmasin diye.
    """
    # Temsilci ve musteri AYNI cinsiyetteyse (orn. erkek temsilci + erkek
    # musteri) ikisi ayni tonu alabilir ve kayit "tek kisi konusuyor" gibi
    # duyulur. Musterinin tonunu temsilciden uzaklastirarak bunu engelle.
    avoid = None
    if genders["t"] == genders["m"]:
        avoid = speaker_variant(speakers["t"])[1]

    placed: list[tuple[int, np.ndarray, str]] = []  # (baslangic_ornek, ses, kanal)
    cursor = int(0.6 * TARGET_SR)  # basta kisa sessizlik
    for turn in turns:
        audio, sr = synth.tts(
            turn["m"],
            gender=genders[turn["k"]],
            speaker=speakers[turn["k"]],
            avoid_pitch=avoid if turn["k"] == "m" else None,
        )
        audio = resample(audio, sr, TARGET_SR)
        gap = turn.get("gap")
        if gap is None:
            gap = rng.uniform(0.35, 0.9)
        start = max(0, cursor + int(gap * TARGET_SR))
        placed.append((start, audio, turn["k"]))
        cursor = start + len(audio)

    total = cursor + int(0.8 * TARGET_SR)
    left = np.zeros(total, dtype=np.float32)   # musteri
    right = np.zeros(total, dtype=np.float32)  # temsilci
    for start, audio, key in placed:
        target = right if key == "t" else left
        target[start : start + len(audio)] += audio

    left = telephone_effect(left)
    right = telephone_effect(right)
    stereo = np.stack([left, right], axis=1)
    peak = np.abs(stereo).max()
    if peak > 0.99:
        stereo = stereo / peak * 0.95
    return (stereo * 32767).astype(np.int16)


def write_wav(path: Path, stereo: np.ndarray) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(TARGET_SR)
        w.writeframes(stereo.tobytes())


# =====================================================================
# Opsiyonel: diyaloglari LLM'e urettir (--use-llm)
# =====================================================================

LLM_DIALOG_PROMPT = """10 adet sentetik Turkce cagri merkezi diyalogu uret (telekom operatoru).
Kategoriler: fatura, iptal, ariza, sikayet, bilgi. Temsilciler: ayse.yilmaz, mehmet.kaya, zeynep.demir.
8 cagri iyi olsun (KVKK bilgilendirmesi, kendini tanitma, cozum, 'baska bir konuda yardimci
olabilir miyim' + veda icersin). 2 cagri kasitli KOTU olsun: biri KVKK okumayan ve cozumsuz,
digeri kaba/yasakli uslup kullanan (ornegin 'sacmalamayin') ve musterinin sozunu kesen.
Her diyalog 8-13 replik olsun. SADECE su semada JSON dondur:
{"diyaloglar": [{"agent": "...", "category": "...", "turns": [{"k": "t", "m": "..."}]}]}
k alani: "t" = temsilci, "m" = musteri."""


def generate_dialogs_via_llm(ollama_url: str, model: str) -> list[dict] | None:
    body = json.dumps(
        {
            "model": model,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.7},
            "messages": [{"role": "user", "content": LLM_DIALOG_PROMPT}],
        }
    ).encode()
    req = urllib.request.Request(
        f"{ollama_url}/api/chat", data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            content = json.loads(resp.read())["message"]["content"]
        data = json.loads(content)
        dialogs = data["diyaloglar"]
        valid = [
            d
            for d in dialogs
            if d.get("agent")
            and d.get("category")
            and isinstance(d.get("turns"), list)
            and len(d["turns"]) >= 4
            and all(t.get("k") in ("t", "m") and t.get("m") for t in d["turns"])
        ]
        if len(valid) < 5:
            raise ValueError(f"LLM'den yalnizca {len(valid)} gecerli diyalog geldi")
        print(f"  LLM {len(valid)} diyalog uretti")
        return valid
    except Exception as exc:
        print(f"  LLM diyalog uretimi basarisiz ({exc}), gomulu diyaloglar kullanilacak")
        return None


# =====================================================================
# Opsiyonel: API'ye upload (--upload) — auth + kampanya farkinda
# =====================================================================

# Kategori -> kampanya adi eslesmesi
CAMPAIGN_FOR_CATEGORY = {
    "iptal": "Satış Hattı",
    "bilgi": "Satış Hattı",
    "fatura": "Destek Hattı",
    "ariza": "Destek Hattı",
    "sikayet": "Destek Hattı",
}


def _post_json(url: str, payload: dict, token: str | None = None, timeout: int = 120) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def api_login(api_base: str) -> str:
    """Demo modunda admin olarak giris yap, access token dondur."""
    data = _post_json(f"{api_base.rstrip('/')}/api/v1/auth/demo-login", {"role": "admin"})
    return data["access_token"]


def fetch_campaign_map(api_base: str, token: str) -> dict[str, int]:
    req = urllib.request.Request(
        f"{api_base.rstrip('/')}/api/v1/admin/campaigns",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        campaigns = json.loads(resp.read())
    return {c["name"]: c["id"] for c in campaigns}


def seed_history(api_base: str, token: str) -> None:
    """8 haftalik sentetik gecmis veriyi tetikle (dashboard dolu gorunsun)."""
    try:
        res = _post_json(f"{api_base.rstrip('/')}/api/v1/admin/seed-demo-history", {}, token)
        print(f"  gecmis veri: {res.get('message', res)}")
    except Exception as exc:
        print(f"  gecmis veri eklenemedi: {exc}")


def seed_knowledge(api_base: str, token: str) -> None:
    """Resmi prosedur dokumanini bilgi bankasina indeksle (RAG yanlis bilgi tespiti).

    'caner.aydin_bilgi_12' cagrisinda temsilci iade suresini 30 gun (dogrusu 14) ve
    kargo ucretini musteriye yikiyor (dogrusu ucretsiz) — RAG bunu yakalamali.
    """
    try:
        res = _post_json(f"{api_base.rstrip('/')}/api/v1/knowledge/seed-demo", {}, token, timeout=300)
        print(f"  bilgi bankasi: '{res.get('title')}' indekslendi ({res.get('chunk_count')} parca)")
    except Exception as exc:
        print(f"  bilgi bankasi indekslenemedi ({exc}) — RAG'siz devam ediliyor")
        print(f"  ipucu: embedding modeli yuklu mu? (host Ollama) ollama pull nomic-embed-text")


def upload_file(api_base: str, path: Path, agent_name: str, token: str,
                campaign_id: int | None) -> None:
    boundary = uuid.uuid4().hex
    file_bytes = path.read_bytes()
    parts = [
        (f"--{boundary}\r\n"
         f'Content-Disposition: form-data; name="agent_name"\r\n\r\n{agent_name}\r\n').encode()
    ]
    if campaign_id is not None:
        parts.append(
            (f"--{boundary}\r\n"
             f'Content-Disposition: form-data; name="campaign_id"\r\n\r\n{campaign_id}\r\n').encode()
        )
    parts.append(
        (f"--{boundary}\r\n"
         f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
         f"Content-Type: audio/wav\r\n\r\n").encode()
    )
    parts.append(file_bytes)
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    req = urllib.request.Request(
        f"{api_base.rstrip('/')}/api/v1/calls/upload",
        data=b"".join(parts),
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Authorization": f"Bearer {token}",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        info = json.loads(resp.read())
        print(f"  yuklendi: {path.name} -> cagri #{info['id']}")


def upload_chat(api_base: str, token: str, chat: dict, campaign_id: int | None) -> None:
    payload = {
        "filename": f"{chat['agent']}_{chat['category']}_chat.json",
        "agent_name": chat["agent"],
        "campaign_id": campaign_id,
        "messages": chat["messages"],
    }
    info = _post_json(f"{api_base.rstrip('/')}/api/v1/chats", payload, token)
    print(f"  chat yuklendi: {chat['agent']}/{chat['category']} -> cagri #{info['id']}")


# =====================================================================


def main() -> None:
    parser = argparse.ArgumentParser(description="KaliteGoz demo verisi ureteci")
    root = Path(__file__).resolve().parents[1]
    # Varsayilan cikti: --upload YOKSA watch-folder (watcher alsin),
    # --upload VARSA ayri klasor (yoksa watcher da alir ve cagri MUKERRER olur).
    parser.add_argument("--outdir", type=Path, default=None)
    parser.add_argument("--voices-dir", type=Path, default=root / "data" / "voices")
    parser.add_argument("--tts-engine", choices=["auto", "edge", "piper"], default="auto",
                        help="auto: edge-tts dene, olmazsa Piper. edge: gercek "
                             "kadin/erkek ses (internet ister). piper: cevrimdisi "
                             "(tek TR model + pitch; cinsiyet ayrimi zayif).")
    parser.add_argument("--upload", metavar="API_URL", default=None,
                        help="wav/chat'leri API'ye yukle (ornek: http://localhost:8000)")
    parser.add_argument("--use-llm", action="store_true",
                        help="diyaloglari gomulu liste yerine Ollama'ya urettir")
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    parser.add_argument("--ollama-model", default="qwen2.5:7b")
    # Sentetik gecmis, dashboard'u doldurur AMA kayitlarin gercek ses dosyasi
    # YOKTUR (dinlenemez). Bu yuzden varsayilan KAPALI; yalnizca "dashboard dolu
    # gorunsun" istendiginde acilir.
    parser.add_argument("--with-history", action="store_true",
                        help="8 haftalik sentetik gecmis veri ekle (sesi olmayan sahte kayitlar)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    # --upload ile watch-folder'a yazmak cagriyi MUKERRER kaydeder (hem API hem watcher alir)
    if args.outdir is None:
        args.outdir = root / "data" / ("demo_out" if args.upload else "inbox")

    rng = random.Random(args.seed)
    np.random.seed(args.seed)

    dialogs = DIALOGS
    if args.use_llm:
        print("Diyaloglar LLM ile uretiliyor...")
        dialogs = generate_dialogs_via_llm(args.ollama_url, args.ollama_model) or DIALOGS

    token = None
    campaign_map: dict[str, int] = {}
    if args.upload:
        print("API'ye giris yapiliyor (demo admin)...")
        token = api_login(args.upload)
        campaign_map = fetch_campaign_map(args.upload, token)
        if args.with_history:
            print("8 haftalik sentetik gecmis veri ekleniyor (bu kayitlarin sesi yoktur)...")
            seed_history(args.upload, token)
        print("Bilgi bankasi (RAG) indeksleniyor...")
        seed_knowledge(args.upload, token)

    def campaign_id_for(category: str) -> int | None:
        return campaign_map.get(CAMPAIGN_FOR_CATEGORY.get(category, ""), None)

    print(f"Seslendirme motoru hazirlaniyor (--tts-engine {args.tts_engine})...")
    synth = make_engine(args.tts_engine, args.voices_dir, root / "data" / "tts_cache")
    print(f"  motor: {synth.name}")

    args.outdir.mkdir(parents=True, exist_ok=True)
    for i, dialog in enumerate(dialogs, start=1):
        name = f"{dialog['agent']}_{dialog['category']}_{i:02d}.wav"
        note = dialog.get("note", "")
        # Temsilci cinsiyeti kadrodan; musteri cinsiyeti metindeki hitaptan
        # ("Fatma Hanim" -> kadin). Ses metinle daima tutarli olur.
        genders = {
            "t": agent_gender(dialog["agent"]),
            "m": customer_gender(dialog["turns"], rng),
        }
        # Ses varyanti kimligi: temsilci adi sabit; musteri her cagrida farkli
        # bir kisi oldugu icin cagri numarasindan turetilir.
        speakers = {"t": dialog["agent"], "m": f"musteri-{i:02d}"}
        print(f"[{i}/{len(dialogs)}] {name} [{genders['t']}/{genders['m']}]"
              + (f"  ({note})" if note else ""))
        stereo = build_stereo_call(dialog["turns"], synth, genders, speakers, rng)
        out_path = args.outdir / name
        write_wav(out_path, stereo)
        if args.upload:
            upload_file(args.upload, out_path, dialog["agent"], token,
                        campaign_id_for(dialog["category"]))

    # Chat gorusmeleri (yalnizca --upload ile; STT gerektirmez)
    if args.upload:
        print(f"\n{len(CHAT_DIALOGS)} chat gorusmesi yukleniyor...")
        for chat in CHAT_DIALOGS:
            upload_chat(args.upload, token, chat, campaign_id_for(chat["category"]))

    print(f"\nTamamlandi. Cikti klasoru: {args.outdir}")
    if args.upload:
        try:
            req = urllib.request.Request(
                f"{args.upload.rstrip('/')}/api/v1/admin/processing",
                headers={"Authorization": f"Bearer {token}"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                st = json.loads(resp.read())
            if st.get("paused"):
                bekleyen = st.get("pending_calls", 0)
                print("\n" + "=" * 62)
                print(f"  {bekleyen} cagri yuklendi ama ISLENMEDI (isleme duraklatilmis).")
                print("  Agir STT+LLM isi makinenizi mesgul etmesin diye bu boyle.")
                print("  Baslatmak icin: http://localhost:3000 -> Yonetim -> Isleme")
                print("                  -> 'Islemeyi baslat'")
                print("=" * 62)
        except Exception:
            pass
    else:
        print("Watcher servisi calisiyorsa ses dosyalari otomatik islenecek.")
        print("(Chat gorusmeleri yalnizca --upload ile yuklenir.)")


if __name__ == "__main__":
    main()
