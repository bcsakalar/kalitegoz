"""Altin set senaryolari — uzman referansi (FAZ 1.2).

47 senaryo. Puanlar 15 yillik cagri merkezi QA pratigine gore, kriter basina
"10 puan neye benzer / 0 puan neye benzer" capasi kullanilarak verildi.

Kriter adlari rubrikteki `criteria.name` ile BIREBIR ayni olmak zorunda
(ASCII hali — FAZ 6'da Turkcelestirilecek, o zaman burasi da migrate edilir).
"""

from __future__ import annotations

from ._authoring import Expected, Scenario, Turn

T, M = "temsilci", "musteri"

CRITERIA = [
    "Acilis", "KVKK / Aydinlatma", "Kimlik Dogrulama", "Aktif Dinleme",
    "Ihtiyac Analizi", "Cozum / Yonlendirme", "Yasakli Kelime / Uslup",
    "Kapanis", "Script Uyumu", "Bilgi Dogrulugu",
]


def sc(**kw) -> dict:
    """Puan sozlugunu kisa yazmak icin: verilmeyen kriter `default` alir."""
    default = kw.pop("default", 8)
    out = {c: default for c in CRITERIA}
    for k, v in kw.items():
        name = k.replace("_", " ")
        match = next((c for c in CRITERIA if c.lower().replace(" / ", " ").replace("/", "") == name.lower()), None)
        out[match or k] = v
    return out


# --- Yeniden kullanilabilir replik bloklari -------------------------------

def open_full(agent: str, brand: str = "Netik İletişim") -> list[Turn]:
    return [Turn(T, f"{brand}'e hoş geldiniz, ben {agent}. Size nasıl yardımcı olabilirim?")]


def kvkk_std() -> list[Turn]:
    return [Turn(T, "Görüşmemiz kayıt altına alınmaktadır ve kişisel verileriniz KVKK kapsamında işlenmektedir.")]


def ident_std() -> list[Turn]:
    return [
        Turn(T, "Öncelikle adınızı ve müşteri numaranızı alabilir miyim?"),
        Turn(M, "Ayşe Kaya, müşteri numaram 448120."),
        Turn(T, "Teşekkür ederim Ayşe Hanım, kaydınızı görüyorum."),
    ]


def close_std() -> list[Turn]:
    return [
        Turn(T, "Başka yardımcı olabileceğim bir konu var mı?"),
        Turn(M, "Yok, teşekkürler."),
        Turn(T, "Aradığınız için teşekkür ederim, iyi günler dilerim."),
    ]


def full_good(agent: str, body: list[Turn]) -> list[Turn]:
    return open_full(agent) + kvkk_std() + ident_std() + body + close_std()


SCENARIOS: list[Scenario] = []


def add(s: Scenario) -> None:
    SCENARIOS.append(s)


# =========================================================================
# 1) REGRESYON VAKALARI — B1..B6 birebir. Bunlar bir daha asla gecmemeli.
# =========================================================================

add(Scenario(
    id="reg-b1-acilis-tam",
    title="B1: Acilis kriteri — kurum adi ve temsilci adi ilk cumlede var",
    bucket="regresyon", regression_for="B1",
    tags=["acilis", "deterministik"],
    turns=full_good("Mehmet", [
        Turn(M, "Dün için teknisyen randevusu verilmişti ama gelen olmadı."),
        Turn(T, "Bunun için özür dilerim, hemen kaydınıza bakıyorum."),
        Turn(T, "Randevunuz saha ekibi tarafından yanlışlıkla kapatılmış. Yarın 09.00-12.00 arası için yeniden açtım."),
        Turn(M, "Yarın kesin gelecekler mi?"),
        Turn(T, "Kaydı öncelikli statüde açtım, teknisyen yola çıkmadan yarım saat önce sizi arayacak."),
    ]),
    expected=Expected(
        scores=sc(default=9, Acilis=10, **{"KVKK / Aydinlatma": 10, "Kimlik Dogrulama": 10}),
        zeroed=False, alerts=[],
        evidence_must_contain={"Acilis": "ben Mehmet"},
        must_not_penalize=["Acilis"],
        notes="Kurum adi (Netik Iletisim) + temsilci adi (Mehmet) ilk replikte. "
              "Acilis 10 disinda bir puan ALAMAZ. B1'in birebir karsiligi.",
    ),
))

add(Scenario(
    id="reg-b2-kvkk-farkli-cumle",
    title="B2: KVKK anonsu YAPILDI ama standart kalibin disinda bir cumleyle",
    bucket="regresyon", regression_for="B2",
    tags=["kvkk", "uyum", "tuzak"],
    turns=[
        Turn(T, "Netik İletişim, ben Selin. Bilginiz olsun, bu konuşma hizmet kalitesi için kaydediliyor."),
        Turn(T, "Paylaşacağınız bilgiler kişisel verilerin korunması mevzuatı çerçevesinde saklanır."),
        Turn(M, "Tamam, anladım."),
        Turn(T, "Adınızı ve hizmet numaranızı alabilir miyim?"),
        Turn(M, "Burak Şen, 552310."),
        Turn(T, "Teşekkürler Burak Bey. Nasıl yardımcı olabilirim?"),
        Turn(M, "Faturam bu ay iki katına çıkmış."),
        Turn(T, "Kontrol ediyorum. Geçen ay tarifeniz değişmiş, kampanya süreniz dolmuş."),
        Turn(T, "İsterseniz size mevcut kullanımınıza uygun bir tarife seçeneği sunabilirim."),
        Turn(M, "Olur, bakalım."),
        Turn(T, "Aylık 40 GB veren paket 289 TL. Onaylarsanız gelecek dönemden geçerli olur."),
        Turn(M, "Onaylıyorum."),
    ] + close_std(),
    expected=Expected(
        scores=sc(default=9, **{"KVKK / Aydinlatma": 10}),
        zeroed=False, alerts=[],
        evidence_must_contain={"KVKK / Aydinlatma": "kaydediliyor"},
        must_not_penalize=["KVKK / Aydinlatma"],
        notes="'kayit altina alinmaktadir' kalibinin HICBIRI gecmiyor ama anons anlamca "
              "eksiksiz yapildi. Anlam kumesi eslesmesi calismali; ihlal URETILMEMELI.",
    ),
))

add(Scenario(
    id="reg-b3-musteri-kesiyor",
    title="B3: Sozu MUSTERI kesiyor, temsilci hic kesmiyor",
    bucket="regresyon", regression_for="B3",
    tags=["aktif_dinleme", "akustik"],
    turns=[
        Turn(T, "Netik İletişim, ben Caner. Görüşmemiz kayıt altına alınmakta, verileriniz KVKK kapsamında işlenmektedir."),
        Turn(T, "Adınızı ve müşteri numaranızı alabilir miyim?"),
        Turn(M, "Hasan Yıldız, 447821."),
        Turn(T, "Teşekkürler Hasan Bey. Kaydınıza bakıyorum, faturanızda"),
        Turn(M, "Ben zaten ödedim onu!", overlap=1.4),
        Turn(T, "Anlıyorum, ödemenizi kontrol ediyorum. Sistemde 12 Temmuz"),
        Turn(M, "Dekontu da var elimde!", overlap=1.6),
        Turn(T, "Elbette, dekontunuz varsa hemen eşleştirelim. Ödemeniz farklı bir"),
        Turn(M, "Yani sizin hatanız yine!", overlap=1.5),
        Turn(T, "Haklısınız, sistemsel bir eşleşme sorunu olmuş. Düzeltme kaydını açıyorum."),
        Turn(M, "Ne zaman düzelecek peki?", overlap=1.3),
        Turn(T, "24 saat içinde bakiyenize yansıyacak, size SMS ile bilgi vereceğim."),
        Turn(M, "Tamam, olur."),
    ] + close_std(),
    expected=Expected(
        scores=sc(default=9, Aktif_Dinleme=9, **{"Yasakli Kelime / Uslup": 10}),
        zeroed=False, alerts=[],
        must_not_penalize=["Aktif Dinleme", "Yasakli Kelime / Uslup"],
        notes="4 soz kesmenin 4'u de MUSTERI kaynakli (overlap alanlari musteri "
              "repliklerinde). Temsilci hicbir repligi kesmiyor ve her seferinde sakin "
              "devam ediyor. Aktif Dinleme CEZALANDIRILAMAZ — B3'un birebir karsiligi.",
    ),
))

add(Scenario(
    id="reg-b4-kesinlikle-haklisiniz",
    title="B4: 'Kesinlikle haklisiniz' — yasakli kelime DEGIL",
    bucket="regresyon", regression_for="B4",
    tags=["yasakli_kelime", "yanlis_pozitif"],
    turns=full_good("Elif", [
        Turn(M, "İki gündür internetim yok, kimse dönüş yapmadı."),
        Turn(T, "Kesinlikle haklısınız, bu süre kabul edilebilir değil. Özür dilerim."),
        Turn(T, "Arıza kaydınızı öncelikli statüye aldım. Kesin bir tarih veremiyorum ama"),
        Turn(T, "saha ekibi bugün 18.00'e kadar sizinle iletişime geçecek."),
        Turn(M, "Umarım bu sefer olur."),
        Turn(T, "Takibini bizzat yapacağım. Çözülmezse yarın ben sizi arayacağım."),
    ]),
    expected=Expected(
        scores=sc(default=9, **{"Yasakli Kelime / Uslup": 10}),
        zeroed=False, alerts=[],
        must_not_penalize=["Yasakli Kelime / Uslup"],
        notes="'Kesinlikle haklisiniz' ve 'Kesin bir tarih veremiyorum' — ikisi de DOGRU, "
              "kibar ifadeler. Mevcut fuzzy eslesme bunlari 'kesin cozulur' yasak vaadi "
              "sanip cagriyi SIFIRLIYOR. Sifirlama YASAK, yasakli kelime alarmi YASAK.",
    ),
))

add(Scenario(
    id="reg-b5-sifirlama-gerekceli",
    title="B5: Gercek sifirlayici ihlal — gerekce ve kanit ZORUNLU",
    bucket="regresyon", regression_for="B5",
    tags=["sifirlayici", "hakaret"],
    turns=[
        Turn(T, "Netik İletişim, ben Onur. Görüşmemiz kayıt altına alınmaktadır, verileriniz KVKK kapsamında işlenmektedir."),
        Turn(T, "Adınızı ve müşteri numaranızı alabilir miyim?"),
        Turn(M, "Murat Aslan, 663102."),
        Turn(M, "Üç kere aradım, hâlâ çözülmedi bu iş."),
        Turn(T, "Ya siz de anlamıyorsunuz ki, saçmalamayın artık."),
        Turn(M, "Nasıl konuşuyorsunuz siz öyle?"),
        Turn(T, "Ne yapayım, ben de insanım. Kayıt açtım işte, bekleyeceksiniz."),
        Turn(M, "Bu kadar mı yani?"),
        Turn(T, "Evet, başka bir şey yok."),
    ],
    expected=Expected(
        scores=sc(default=4, **{"Yasakli Kelime / Uslup": 0, "Aktif Dinleme": 2, "Kapanis": 2}),
        zeroed=True, zeroing_criterion="Yasakli Kelime / Uslup",
        alerts=["zeroing", "banned_word"],
        evidence_must_contain={"Yasakli Kelime / Uslup": "saçmalamayın"},
        notes="Temsilci musteriye hakaret ediyor. Cagri SIFIRLANMALI, gerekce "
              "kalici olarak saklanmali ve kanit cumlesi ('sacmalamayin artik') "
              "gosterilmeli. Kanitsiz sifirlama sistem hatasidir.",
    ),
))

add(Scenario(
    id="reg-b6-ikiz-a",
    title="B6: Ikiz senaryo A — B ile ayni akis, kucuk kelime farklari",
    bucket="regresyon", regression_for="B6",
    tags=["tekrarlanabilirlik"],
    turns=full_good("Deniz", [
        Turn(M, "Dün teknisyen randevum vardı, kimse gelmedi."),
        Turn(T, "Bunun için özür dilerim, hemen kaydınızı inceliyorum."),
        Turn(T, "Randevunuz saha ekibi tarafından hatalı kapatılmış. Yarın sabah için yeniden açıyorum."),
        Turn(M, "Yarın kesin gelirler mi?"),
        Turn(T, "Kaydı öncelikli statüde açtım, teknisyen yola çıkmadan önce sizi arayacak."),
        Turn(M, "Peki, tamam."),
    ]),
    expected=Expected(
        scores=sc(default=9, Acilis=10, **{"KVKK / Aydinlatma": 10, "Kimlik Dogrulama": 10}),
        zeroed=False, alerts=[],
        notes="reg-b6-ikiz-b ile toplam puan farki 5 puani (100 uzerinden) GECEMEZ.",
    ),
))

add(Scenario(
    id="reg-b6-ikiz-b",
    title="B6: Ikiz senaryo B — A ile ayni akis, kucuk kelime farklari",
    bucket="regresyon", regression_for="B6",
    tags=["tekrarlanabilirlik"],
    turns=full_good("Deniz", [
        Turn(M, "Dünkü teknisyen randevuma kimse gelmedi."),
        Turn(T, "Yaşattığımız mağduriyet için özür dilerim, kaydınızı hemen inceliyorum."),
        Turn(T, "Randevunuz saha ekibince yanlışlıkla kapatılmış. Yarın sabaha yeniden açıyorum."),
        Turn(M, "Yarın gerçekten gelecekler mi?"),
        Turn(T, "Kaydı öncelikli statüye aldım, teknisyen yola çıkmadan sizi arayacak."),
        Turn(M, "Tamam, peki."),
    ]),
    expected=Expected(
        scores=sc(default=9, Acilis=10, **{"KVKK / Aydinlatma": 10, "Kimlik Dogrulama": 10}),
        zeroed=False, alerts=[],
        notes="reg-b6-ikiz-a ile toplam puan farki 5 puani (100 uzerinden) GECEMEZ.",
    ),
))


# =========================================================================
# 2) YUKSEK PUANLI / TEMIZ CAGRILAR (8)
# =========================================================================

_HIGH = [
    ("yuksek-01-fatura-itiraz", "Fatura itirazi — eksiksiz cozum", "Zeynep", [
        Turn(M, "Faturamda tanımadığım 45 TL'lik bir kalem var."),
        Turn(T, "Hemen bakıyorum. 12 Temmuz'da bir dijital içerik aboneliği başlatılmış görünüyor."),
        Turn(M, "Ben böyle bir şey yapmadım."),
        Turn(T, "Anlıyorum. Aboneliği iptal ediyorum ve bu ayki 45 TL'yi faturanızdan düşüyorum."),
        Turn(T, "İade 2 iş günü içinde bakiyenize yansıyacak, onay SMS'i geleceğ."),
        Turn(M, "Çok teşekkür ederim."),
    ]),
    ("yuksek-02-ariza-cozuldu", "Ariza — ilk temasta cozum", "Kerem", [
        Turn(M, "İnternetim sabahtan beri çok yavaş."),
        Turn(T, "Hattınızı test ediyorum. Hat senkron hızınız düşmüş görünüyor."),
        Turn(T, "Modeminizi 30 saniye prizden çeker misiniz? Ben bu sırada hattı yeniden profilliyorum."),
        Turn(M, "Taktım, ışıklar yandı."),
        Turn(T, "Şu an 48 Mbps görüyorum, önceki 6 Mbps idi. Bir test yapar mısınız?"),
        Turn(M, "Evet, şimdi hızlı."),
        Turn(T, "Sorunu kalıcı hale getirdim, bu profil kaydınızda sabit kalacak."),
    ]),
    ("yuksek-03-iptal-kazanim", "Iptal talebi — ihtiyac analiziyle kazanim", "Melis", [
        Turn(M, "Hattımı iptal etmek istiyorum."),
        Turn(T, "Tabii, işlemi yapabilirim. İzin verirseniz sebebini öğrenebilir miyim?"),
        Turn(M, "Faturam çok yüksek, ayda 400 TL ödüyorum."),
        Turn(T, "Kullanımınıza baktım, ayda ortalama 25 GB kullanıyorsunuz ama 100 GB'lık paketiniz var."),
        Turn(T, "Size uygun 40 GB'lık paket 249 TL. İhtiyacınızı fazlasıyla karşılar."),
        Turn(M, "Bu daha mantıklı gerçekten."),
        Turn(T, "Onaylarsanız gelecek dönemden geçerli olacak şekilde geçişi yapıyorum."),
        Turn(M, "Onaylıyorum, teşekkürler."),
    ]),
    ("yuksek-04-bilgi-talebi", "Bilgi talebi — dogru ve eksiksiz bilgi", "Tolga", [
        Turn(M, "Yurt dışına çıkacağım, roaming nasıl açılıyor?"),
        Turn(T, "Hattınızda uluslararası dolaşım şu an kapalı görünüyor, hemen açabilirim."),
        Turn(T, "Gideceğiniz ülkeyi öğrenebilir miyim? Paket seçenekleri ülkeye göre değişiyor."),
        Turn(M, "Almanya."),
        Turn(T, "Almanya için 7 günlük 5 GB paket 350 TL. Paketsiz kullanımda MB başına ücretlendirme olur."),
        Turn(T, "Paketi şimdi tanımlarsam yurt dışına çıktığınız gün otomatik başlar."),
        Turn(M, "Tanımlayın lütfen."),
    ]),
    ("yuksek-05-tasinma", "Tasinma talebi — proaktif yonlendirme", "Burcu", [
        Turn(M, "Başka bir eve taşınıyorum, hattımı taşıtmak istiyorum."),
        Turn(T, "Yeni adresinizin ilçesini alabilir miyim? Altyapı uygunluğuna bakacağım."),
        Turn(M, "Kadıköy, Caferağa."),
        Turn(T, "O bölgede fiber altyapımız mevcut, mevcut hızınızdan daha yükseğine çıkabilirsiniz."),
        Turn(T, "Taşıma işlemi ücretsiz, 3 iş günü sürüyor. Taşınma tarihinizi öğrenebilir miyim?"),
        Turn(M, "20 Ağustos."),
        Turn(T, "18 Ağustos'a randevu oluşturdum, teknisyen 09.00-13.00 arası gelecek."),
    ]),
    ("yuksek-06-sikayet-empati", "Sikayet — guclu empati ve telafi", "Serkan", [
        Turn(M, "Üç gündür internetim yok, evden çalışıyorum, çok mağdur oldum."),
        Turn(T, "Yaşadığınız mağduriyet için gerçekten üzgünüm, evden çalışırken bu ciddi bir sorun."),
        Turn(T, "Kaydınıza baktım, saha ekibi iki kez randevuyu ertelemiş. Bu kabul edilebilir değil."),
        Turn(T, "Kaydı yönetici takibine aldım, bugün içinde teknisyen yönlendirileceğ."),
        Turn(T, "Ayrıca hizmet alamadığınız 3 gün için faturanıza orantılı iade tanımlıyorum."),
        Turn(M, "Bunu duymak iyi geldi, teşekkürler."),
    ]),
    ("yuksek-07-teknik-detay", "Teknik detay — anlasilir anlatim", "Ayla", [
        Turn(M, "Modemin ışıklarından hangisi ne demek, anlamıyorum."),
        Turn(T, "Tabii açıklayayım. Soldan ikinci ışık internet bağlantınızı gösterir."),
        Turn(T, "Sabit yeşilse bağlantı var, yanıp sönüyorsa bağlantı kurulmaya çalışılıyor demektir."),
        Turn(M, "Benimki yanıp sönüyor."),
        Turn(T, "O zaman hat henüz senkron olmamış. Hattınızı buradan yeniden başlatıyorum, 2 dakika sürer."),
        Turn(M, "Tamam, bekliyorum."),
        Turn(T, "Şimdi kontrol eder misiniz? Sabit yeşil olmalı."),
        Turn(M, "Evet, sabit yandı."),
    ]),
    ("yuksek-08-odeme-plani", "Odeme guclugu — cozum odakli", "Gizem", [
        Turn(M, "Bu ay faturayı ödeyemeyeceğim, hattım kesilir mi?"),
        Turn(T, "Bunu paylaştığınız için teşekkür ederim, birlikte bir çözüm bulalım."),
        Turn(T, "Hattınız için 15 günlük ek ödeme süresi tanımlayabilirim, bu sürede kesinti olmaz."),
        Turn(M, "15 gün yeterli olur."),
        Turn(T, "Tanımladım. Ayrıca isterseniz faturanızı 3 taksite bölebiliriz, ek ücret yok."),
        Turn(M, "Taksit daha iyi olur."),
        Turn(T, "3 taksite böldüm, ilk taksit 20 Ağustos'ta. Detayları SMS ile göndereceğim."),
    ]),
]

for _id, _title, _agent, _body in _HIGH:
    add(Scenario(
        id=_id, title=_title, bucket="yuksek", tags=["temiz"],
        turns=full_good(_agent, _body),
        expected=Expected(
            scores=sc(default=9, Acilis=10, **{"KVKK / Aydinlatma": 10, "Kimlik Dogrulama": 10}),
            zeroed=False, alerts=[],
            notes="Eksiksiz acilis + KVKK + kimlik + cozum + kapanis. Toplam 85-100 bandinda olmali.",
        ),
    ))


# =========================================================================
# 3) ORTA PUANLI CAGRILAR (8) — bir veya iki belirgin eksik
# =========================================================================

_MED = [
    ("orta-01-kapanis-eksik", "Kapanis eksik — 'baska yardim?' sorulmadi",
     [Turn(T, "Netik İletişim, ben Hakan. Görüşmemiz kayıt altına alınmakta, verileriniz KVKK kapsamında işlenmektedir.")]
     + [Turn(T, "Adınızı ve müşteri numaranızı alabilir miyim?"), Turn(M, "Ali Vural, 771290."), Turn(T, "Teşekkürler Ali Bey.")]
     + [
         Turn(M, "Faturamı nasıl otomatik ödemeye bağlarım?"),
         Turn(T, "Kredi kartı bilgilerinizi internet şubesinden tanımlayabilirsiniz."),
         Turn(M, "Tamam anladım."),
         Turn(T, "İyi günler."),
     ],
     sc(default=7, Kapanis=4, **{"Ihtiyac Analizi": 6}),
     "Kapanis kalibi yok, 'baska yardim' sorulmadi. Kapanis 5 ve alti olmali."),

    ("orta-02-ihtiyac-analizi-zayif", "Ihtiyac analizi yapilmadan cozum onerildi",
     [Turn(T, "Netik İletişim, ben Pınar. Görüşmemiz kayıt altına alınmakta, verileriniz KVKK kapsamında işlenmektedir.")]
     + [Turn(T, "Adınızı ve müşteri numaranızı alabilir miyim?"), Turn(M, "Sema Toprak, 334512."), Turn(T, "Teşekkürler Sema Hanım.")]
     + [
         Turn(M, "Faturam yüksek geldi."),
         Turn(T, "Size en ucuz paketimizi tanımlayayım, 149 TL."),
         Turn(M, "Ama ben çok internet kullanıyorum."),
         Turn(T, "O paket 10 GB veriyor."),
         Turn(M, "Yetmez ki bana."),
         Turn(T, "Peki o zaman mevcut paketinizde kalın."),
     ] + close_std(),
     sc(default=7, **{"Ihtiyac Analizi": 3, "Cozum / Yonlendirme": 4}),
     "Kullanim sorulmadan paket onerildi, sonuc cozumsuz. Ihtiyac Analizi 4 ve alti."),

    ("orta-03-kimlik-gec", "Kimlik dogrulama cok gec yapildi",
     [Turn(T, "Netik İletişim, ben Umut. Görüşmemiz kayıt altına alınmakta, verileriniz KVKK kapsamında işlenmektedir.")]
     + [
         Turn(M, "Faturamda bir sorun var."),
         Turn(T, "Bakıyorum, evet bir düzeltme yapmam gerekiyor."),
         Turn(T, "Düzeltmeyi yaptım, 30 TL indirim tanımladım."),
         Turn(M, "Teşekkürler."),
         Turn(T, "Bu arada adınızı ve müşteri numaranızı alabilir miyim?"),
         Turn(M, "Ozan Demir, 220145."),
     ] + close_std(),
     sc(default=7, **{"Kimlik Dogrulama": 4, "Script Uyumu": 5}),
     "Kimlik, islem YAPILDIKTAN sonra soruldu. Uyum acisindan ciddi eksik ama "
     "tamamen atlanmadigi icin sifirlama YOK — Kimlik Dogrulama 3-5 bandinda."),

    ("orta-04-bilgi-eksik", "Dogru ama eksik bilgi verildi",
     [Turn(T, "Netik İletişim, ben Ceren. Görüşmemiz kayıt altına alınmakta, verileriniz KVKK kapsamında işlenmektedir.")]
     + [Turn(T, "Adınızı ve müşteri numaranızı alabilir miyim?"), Turn(M, "Nur Aydın, 887420."), Turn(T, "Teşekkürler Nur Hanım.")]
     + [
         Turn(M, "Cayma bedeli ne kadar?"),
         Turn(T, "Taahhüdünüz varsa cayma bedeli çıkar."),
         Turn(M, "Ne kadar peki?"),
         Turn(T, "Sözleşmenize göre değişiyor."),
         Turn(M, "Yani bilmiyor musunuz?"),
         Turn(T, "Kalan aya göre hesaplanıyor."),
     ] + close_std(),
     sc(default=7, **{"Bilgi Dogrulugu": 5, "Cozum / Yonlendirme": 5}),
     "Verilen bilgi YANLIS degil ama somut degil; musteri cevabini alamadi."),

    ("orta-05-monoton-uslup", "Islem dogru, uslup mekanik",
     [Turn(T, "Netik İletişim, ben Fatih. Görüşmemiz kayıt altına alınmakta, verileriniz KVKK kapsamında işlenmektedir.")]
     + [Turn(T, "Adınızı ve müşteri numaranızı alabilir miyim?"), Turn(M, "Emre Kılıç, 119003."), Turn(T, "Teşekkürler.")]
     + [
         Turn(M, "Babam vefat etti, hattını kapatmam gerekiyor."),
         Turn(T, "Vefat işlemi için veraset ilamı gerekiyor."),
         Turn(M, "Nereye götüreceğim?"),
         Turn(T, "Bayiye."),
         Turn(M, "Peki."),
         Turn(T, "Başka bir şey var mı?"),
         Turn(M, "Yok."),
         Turn(T, "İyi günler."),
     ],
     sc(default=6, **{"Aktif Dinleme": 4, "Yasakli Kelime / Uslup": 6, "Kapanis": 6}),
     "Bilgi dogru ama hassas durumda taziye/empati yok, cevaplar tek kelimelik."),

    ("orta-06-acilis-yarim", "Acilis: kurum adi var, temsilci adi YOK",
     [Turn(T, "Netik İletişim'e hoş geldiniz, buyurun."),
      Turn(T, "Görüşmemiz kayıt altına alınmaktadır, verileriniz KVKK kapsamında işlenmektedir.")]
     + [Turn(T, "Adınızı ve müşteri numaranızı alabilir miyim?"), Turn(M, "Derya Şahin, 660012."), Turn(T, "Teşekkürler Derya Hanım.")]
     + [
         Turn(M, "Paket değişikliği yapmak istiyorum."),
         Turn(T, "Mevcut kullanımınıza baktım, size 60 GB'lık paketi öneririm, 279 TL."),
         Turn(M, "Uygun, geçelim."),
         Turn(T, "Geçişi yaptım, gelecek dönemden geçerli olacak."),
     ] + close_std(),
     sc(default=8, Acilis=6),
     "Kurum adi VAR, temsilci adi YOK. Acilis KISMEN karsilandi: 5-7 bandi. "
     "0-2 vermek de 10 vermek de hatali."),

    ("orta-07-cozum-yonlendirme", "Cozum yerine baska birime yonlendirme",
     [Turn(T, "Netik İletişim, ben Sinem. Görüşmemiz kayıt altına alınmakta, verileriniz KVKK kapsamında işlenmektedir.")]
     + [Turn(T, "Adınızı ve müşteri numaranızı alabilir miyim?"), Turn(M, "Kaan Öz, 445188."), Turn(T, "Teşekkürler Kaan Bey.")]
     + [
         Turn(M, "Kurumsal hattımı bireysele çevirmek istiyorum."),
         Turn(T, "Bu işlem bizim ekranımızda yapılmıyor, kurumsal müşteri hizmetlerini aramanız gerekiyor."),
         Turn(M, "Numarayı verebilir misiniz?"),
         Turn(T, "444 0 555."),
         Turn(M, "Peki, arayayım."),
     ] + close_std(),
     sc(default=7, **{"Cozum / Yonlendirme": 6, "Ihtiyac Analizi": 6}),
     "Yonlendirme dogru ama transfer teklif edilmedi, musteri yeniden aramak zorunda."),

    ("orta-08-tekrar-soru", "Musteri ayni seyi iki kez sormak zorunda kaldi",
     [Turn(T, "Netik İletişim, ben Barış. Görüşmemiz kayıt altına alınmakta, verileriniz KVKK kapsamında işlenmektedir.")]
     + [Turn(T, "Adınızı ve müşteri numaranızı alabilir miyim?"), Turn(M, "Leyla Ak, 552901."), Turn(T, "Teşekkürler Leyla Hanım.")]
     + [
         Turn(M, "Taahhüdüm ne zaman bitiyor?"),
         Turn(T, "Faturanızda bir gecikme görünüyor, onu ödediniz mi?"),
         Turn(M, "Onu sormadım, taahhüdüm ne zaman bitiyor?"),
         Turn(T, "Bir saniye... Taahhüdünüz 14 Kasım'da bitiyor."),
         Turn(M, "Teşekkürler."),
     ] + close_std(),
     sc(default=7, **{"Aktif Dinleme": 5}),
     "Temsilci ilk soruyu dinlemeden farkli konuya gecti; musteri tekrar sordu."),
]

for _id, _title, _turns, _scores, _note in _MED:
    add(Scenario(
        id=_id, title=_title, bucket="orta", tags=["kismi_eksik"], turns=_turns,
        expected=Expected(scores=_scores, zeroed=False, alerts=[], notes=_note),
    ))


# =========================================================================
# 4) DUSUK PUANLI CAGRILAR (8) — sifirlamayan ama agir eksikler
# =========================================================================

_LOW = [
    ("dusuk-01-acilis-yok", "Acilis hic yapilmadi", [
        Turn(T, "Alo, buyurun."),
        Turn(M, "İyi günler, faturamla ilgili arıyorum."),
        Turn(T, "Görüşmemiz kayıt altına alınmakta, verileriniz KVKK kapsamında işlenmektedir. Adınız?"),
        Turn(M, "Cem Arslan, 220118."),
        Turn(T, "Faturanız 340 TL, son ödeme 25'i."),
        Turn(M, "Neden bu kadar yüksek?"),
        Turn(T, "Kullanımınız fazla olmuş."),
        Turn(M, "Detayını görebilir miyim?"),
        Turn(T, "İnternet şubesinden bakın."),
    ], sc(default=4, Acilis=1, **{"Ihtiyac Analizi": 3, "Cozum / Yonlendirme": 3, "Kapanis": 1}),
     "Kurum adi da temsilci adi da YOK. Acilis 0-2. Kapanis kalibi da yok."),

    ("dusuk-02-empati-yok", "Magdur musteriye empatisiz yanit", [
        Turn(T, "Netik İletişim, ben Tuna. Görüşmemiz kayıt altına alınmakta, verileriniz KVKK kapsamında işlenmektedir."),
        Turn(T, "Adınızı ve müşteri numaranızı alabilir miyim?"),
        Turn(M, "Hülya Er, 663400."),
        Turn(M, "Beş gündür internetim yok, çocuğumun sınavı vardı, giremedi."),
        Turn(T, "Kayıt açılmış zaten, bekleyeceksiniz."),
        Turn(M, "Beş gün oldu ama."),
        Turn(T, "Sistemde öyle görünüyor, yapabileceğim bir şey yok."),
        Turn(M, "Peki."),
        Turn(T, "İyi günler."),
    ], sc(default=4, **{"Aktif Dinleme": 2, "Cozum / Yonlendirme": 2, "Yasakli Kelime / Uslup": 4, "Kapanis": 3}),
     "Agir magduriyete sifir empati, cozum girisimi yok. Ama hakaret/yasak vaat "
     "YOK — sifirlama URETILEMEZ."),

    ("dusuk-03-yanlis-bilgi", "Yanlis bilgi verildi", [
        Turn(T, "Netik İletişim, ben Yasin. Görüşmemiz kayıt altına alınmakta, verileriniz KVKK kapsamında işlenmektedir."),
        Turn(T, "Adınızı ve müşteri numaranızı alabilir miyim?"),
        Turn(M, "Aslı Tan, 118872."),
        Turn(M, "Cayma hakkım kaç gün?"),
        Turn(T, "Cayma hakkı 7 gündür."),
        Turn(M, "Emin misiniz? Bana 14 gün demişlerdi."),
        Turn(T, "Hayır, 7 gün."),
        Turn(M, "Peki."),
    ] + close_std(),
     sc(default=5, **{"Bilgi Dogrulugu": 1, "Aktif Dinleme": 4}),
     "Mesafeli satista cayma hakki 14 gundur. Temsilci yanlis bilgi verdi ve "
     "musteri duzeltince israr etti. Bilgi Dogrulugu 0-2."),

    ("dusuk-04-kvkk-yok", "KVKK anonsu yok (kritik kriter esikte)", [
        Turn(T, "Netik İletişim, ben Aylin, buyurun."),
        Turn(T, "Adınızı ve müşteri numaranızı alabilir miyim?"),
        Turn(M, "Volkan Kaya, 990211."),
        Turn(M, "Paketimi öğrenmek istiyorum."),
        Turn(T, "60 GB'lık paketiniz var, 279 TL."),
        Turn(M, "Tamam, teşekkürler."),
    ] + close_std(),
     sc(default=7, **{"KVKK / Aydinlatma": 0}),
     "KVKK anonsu HIC yapilmadi. Kritik kriter, esik 3 -> CAGRI SIFIRLANIR. "
     "Bu senaryo 'dusuk' kovasinda ama sifirlama BEKLENIYOR."),

    ("dusuk-05-sozu-temsilci-kesiyor", "Temsilci musterinin sozunu surekli kesiyor", [
        Turn(T, "Netik İletişim, ben Doruk. Görüşmemiz kayıt altına alınmakta, verileriniz KVKK kapsamında işlenmektedir."),
        Turn(T, "Adınızı ve müşteri numaranızı alabilir miyim?"),
        Turn(M, "Serpil Uz, 447120."),
        Turn(M, "Geçen ay bir kampanyaya girmiştim, o kampanya"),
        Turn(T, "Kampanyanız iptal olmuş.", overlap=1.5),
        Turn(M, "Ama ben iptal etmedim, sadece"),
        Turn(T, "Sistemde iptal görünüyor.", overlap=1.6),
        Turn(M, "Bir dakika, izah edeyim"),
        Turn(T, "Gerek yok, kayıt böyle.", overlap=1.4),
        Turn(M, "Beni dinlemiyorsunuz."),
        Turn(T, "Dinliyorum efendim."),
    ], sc(default=4, **{"Aktif Dinleme": 1, "Yasakli Kelime / Uslup": 5, "Ihtiyac Analizi": 3}),
     "3 soz kesmenin 3'u de TEMSILCI kaynakli. Aktif Dinleme 0-2 olmali. "
     "reg-b3'un aynasi: burada ceza DOGRU."),

    ("dusuk-06-cozumsuz-kapanis", "Cagri cozumsuz kapandi", [
        Turn(T, "Netik İletişim, ben Gökhan. Görüşmemiz kayıt altına alınmakta, verileriniz KVKK kapsamında işlenmektedir."),
        Turn(T, "Adınızı ve müşteri numaranızı alabilir miyim?"),
        Turn(M, "Bahar Yalçın, 335678."),
        Turn(M, "Modemim bozuldu, değişim istiyorum."),
        Turn(T, "Modem değişimi için teknik ekip randevusu gerekiyor."),
        Turn(M, "Randevu alabilir miyiz?"),
        Turn(T, "Şu an sistem randevu vermiyor."),
        Turn(M, "Ne yapacağım peki?"),
        Turn(T, "Yarın tekrar arayın."),
        Turn(M, "Tamam."),
    ], sc(default=4, **{"Cozum / Yonlendirme": 2, "Kapanis": 3, "Ihtiyac Analizi": 4}),
     "Musteri sorunu cozulmeden, somut bir sonraki adim verilmeden kapatildi."),

    ("dusuk-07-script-disi", "Script tamamen atlandi", [
        Turn(T, "Efendim?"),
        Turn(M, "İyi günler, hattımla ilgili."),
        Turn(T, "Ne olmuş hattınıza?"),
        Turn(M, "Sinyal çekmiyor."),
        Turn(T, "Telefonu kapatıp açın."),
        Turn(M, "Denedim, olmadı."),
        Turn(T, "O zaman arıza vardır."),
        Turn(M, "Kayıt açar mısınız?"),
        Turn(T, "Açtım."),
    ], sc(default=3, Acilis=0, **{"KVKK / Aydinlatma": 0, "Kimlik Dogrulama": 0, "Kapanis": 1, "Script Uyumu": 1}),
     "Acilis yok, KVKK yok, kimlik yok, kapanis yok. Iki kritik kriter esik "
     "altinda -> SIFIRLANIR."),

    ("dusuk-08-gecistirme", "Musteri sorusu gecistirildi", [
        Turn(T, "Netik İletişim, ben Ege. Görüşmemiz kayıt altına alınmakta, verileriniz KVKK kapsamında işlenmektedir."),
        Turn(T, "Adınızı ve müşteri numaranızı alabilir miyim?"),
        Turn(M, "Tuğçe Bal, 771003."),
        Turn(M, "Geçen hafta söz verilen indirim faturama yansımamış."),
        Turn(T, "Sistemde indirim kaydı göremiyorum."),
        Turn(M, "Ama telefonda söylediniz."),
        Turn(T, "Kim söylediyse ona sorun."),
        Turn(M, "Nasıl yani?"),
        Turn(T, "Ben göremiyorum efendim."),
    ] + close_std(),
     sc(default=4, **{"Cozum / Yonlendirme": 2, "Aktif Dinleme": 3, "Yasakli Kelime / Uslup": 4}),
     "'Kim soylediyse ona sorun' — sorumluluk reddi. Kaba ama hakaret degil, "
     "sifirlama URETILEMEZ."),
]

for _id, _title, _turns, _scores, _note in _LOW:
    _zero = _id in ("dusuk-04-kvkk-yok", "dusuk-07-script-disi")
    add(Scenario(
        id=_id, title=_title, bucket="dusuk", tags=["agir_eksik"], turns=_turns,
        expected=Expected(
            scores=_scores, zeroed=_zero,
            zeroing_criterion="KVKK / Aydinlatma" if _zero else None,
            alerts=["zeroing"] if _zero else ["low_score"], notes=_note,
        ),
    ))


# =========================================================================
# 5) SIFIRLAYICI IHLAL SENARYOLARI (6)
# =========================================================================

_ZERO = [
    ("sifir-01-hakaret", "Temsilci musteriye hakaret etti", "Yasakli Kelime / Uslup", [
        Turn(T, "Netik İletişim, ben Kemal. Görüşmemiz kayıt altına alınmakta, verileriniz KVKK kapsamında işlenmektedir."),
        Turn(T, "Adınızı ve müşteri numaranızı alabilir miyim?"),
        Turn(M, "Necla Sarı, 118990."),
        Turn(M, "Bu ne biçim hizmet, rezalet!"),
        Turn(T, "Aptalca konuşmayı bırakın da derdinizi anlatın."),
        Turn(M, "Ne dediniz siz?"),
        Turn(T, "Duydunuz işte."),
    ], "Aptalca", ["zeroing", "banned_word"]),

    ("sifir-02-kvkk-anons-yok", "KVKK anonsu hic yapilmadi", "KVKK / Aydinlatma", [
        Turn(T, "Netik İletişim, ben Rüya, buyurun."),
        Turn(T, "Adınızı ve müşteri numaranızı alabilir miyim?"),
        Turn(M, "Tarık Güneş, 990887."),
        Turn(M, "Kredi kartımla ödeme yapmak istiyorum."),
        Turn(T, "Tabii, kart bilgilerinizi alayım."),
        Turn(M, "Peki."),
        Turn(T, "Ödemeniz alındı, teşekkürler."),
    ] + close_std(), None, ["zeroing"]),

    ("sifir-03-kimlik-atlandi", "Kimlik dogrulama hic yapilmadan islem yapildi", "Kimlik Dogrulama", [
        Turn(T, "Netik İletişim, ben Nazlı. Görüşmemiz kayıt altına alınmakta, verileriniz KVKK kapsamında işlenmektedir."),
        Turn(M, "Hattımdaki tüm ek paketleri iptal edin."),
        Turn(T, "Hemen iptal ediyorum."),
        Turn(M, "Bir de fatura adresimi değiştirin."),
        Turn(T, "Yeni adresi söyleyin, güncelleyeyim."),
        Turn(M, "Bağdat Caddesi No 12."),
        Turn(T, "Güncelledim."),
    ] + close_std(), None, ["zeroing"]),

    ("sifir-04-yasak-vaat", "Gercek yasak vaat verildi", "Yasakli Kelime / Uslup", [
        Turn(T, "Netik İletişim, ben Arda. Görüşmemiz kayıt altına alınmakta, verileriniz KVKK kapsamında işlenmektedir."),
        Turn(T, "Adınızı ve müşteri numaranızı alabilir miyim?"),
        Turn(M, "Selim Doğan, 445009."),
        Turn(M, "Arıza ne zaman düzelir?"),
        Turn(T, "Merak etmeyin, bu sorun kesin çözülür, garanti veriyorum, yarın halledilecek."),
        Turn(M, "Kesin mi?"),
        Turn(T, "Kesinlikle garanti, söz veriyorum."),
    ] + close_std(), "kesin çözülür", ["zeroing", "banned_word"]),

    ("sifir-05-agir-kufur", "Temsilci kufretti", "Yasakli Kelime / Uslup", [
        Turn(T, "Netik İletişim, ben Berk. Görüşmemiz kayıt altına alınmakta, verileriniz KVKK kapsamında işlenmektedir."),
        Turn(T, "Adınızı ve müşteri numaranızı alabilir miyim?"),
        Turn(M, "Filiz Ateş, 220990."),
        Turn(M, "Bir saattir bekletiyorsunuz!"),
        Turn(T, "Salak mısınız, sıra var burada."),
        Turn(M, "Şikayet edeceğim sizi."),
        Turn(T, "Edin bakalım."),
    ], "Salak", ["zeroing", "banned_word"]),

    ("sifir-06-kritik-yanlis-bilgi", "Kimlik dogrulama sahte bilgiyle gecildi", "Kimlik Dogrulama", [
        Turn(T, "Netik İletişim, ben Ilgın. Görüşmemiz kayıt altına alınmakta, verileriniz KVKK kapsamında işlenmektedir."),
        Turn(M, "Eşimin hattındaki görüşme dökümünü istiyorum."),
        Turn(T, "Tabii, hemen gönderiyorum."),
        Turn(M, "Numarası 0555 118 90 21."),
        Turn(T, "Döküm mail adresinize gönderildi."),
    ] + close_std(), None, ["zeroing"]),
]

for _id, _title, _crit, _turns, _ev, _alerts in _ZERO:
    _s = sc(default=5)
    _s[_crit] = 0 if "Uslup" in _crit else 1
    add(Scenario(
        id=_id, title=_title, bucket="sifirlayici", tags=["sifirlayici"], turns=_turns,
        expected=Expected(
            scores=_s, zeroed=True, zeroing_criterion=_crit, alerts=_alerts,
            evidence_must_contain={_crit: _ev} if _ev else {},
            notes="SIFIRLAMA ZORUNLU. Gerekce ve kanit kalici olarak saklanmali.",
        ),
    ))


# =========================================================================
# 6) KRIZ SENARYOLARI (4)
# =========================================================================

_CRISIS = [
    ("kriz-01-avukat", "Musteri avukat tehdidi", "avukat", [
        Turn(M, "Bu işi avukatıma vereceğim, hukuki süreç başlatacağım."),
        Turn(T, "Sizi anlıyorum, bu noktaya gelmesini istemezdik."),
        Turn(T, "Konuyu yönetici seviyesine taşıyorum ve bugün içinde size dönüş yapılacak."),
        Turn(M, "Umarım."),
        Turn(T, "Kayıt numaranızı SMS ile göndereceğim, takibini bizzat yapacağım."),
    ]),
    ("kriz-02-hakem-heyeti", "Tuketici hakem heyeti tehdidi", "hakem", [
        Turn(M, "Tüketici hakem heyetine başvuracağım, bu kadar oldu artık."),
        Turn(T, "Başvuru hakkınız elbette saklı, ancak önce burada çözmeyi çok isterim."),
        Turn(T, "Faturanızdaki itiraz ettiğiniz tutarı incelemeye alıyorum, 3 iş günü içinde sonuçlanacak."),
        Turn(M, "Peki, bekleyeceğim."),
        Turn(T, "İnceleme sonucunu size telefonla bildireceğim."),
    ]),
    ("kriz-03-iptal-tehdidi", "Iptal tehdidi", "iptal", [
        Turn(M, "Bugün iptal ediyorum, başka operatöre geçeceğim."),
        Turn(T, "Bu kararınızı anlıyorum, yaşadığınız sorunlar için özür dilerim."),
        Turn(T, "İptal işlemini yapabilirim ama önce sorununuzu çözmeme izin verir misiniz?"),
        Turn(M, "Deneyin bakalım."),
        Turn(T, "Arıza kaydınızı yönetici takibine aldım, ayrıca 2 aylık ücret iadesi tanımladım."),
        Turn(M, "Tamam, bir şans daha vereyim."),
    ]),
    ("kriz-04-medya", "Sosyal medyada tesir etme tehdidi", "sosyal medya", [
        Turn(M, "Bunu sosyal medyada paylaşacağım, herkes görsün bu rezaleti."),
        Turn(T, "Yaşadıklarınız için gerçekten üzgünüm, bu tepkinizi hak ettiniz."),
        Turn(T, "Konuyu şikayet yönetimi ekibine kritik olarak aktarıyorum."),
        Turn(M, "Ne zaman dönüş olacak?"),
        Turn(T, "En geç yarın 12.00'ye kadar sizi arayacaklar, kayıt numaranız 8842."),
    ]),
]

for _id, _title, _kw, _body in _CRISIS:
    add(Scenario(
        id=_id, title=_title, bucket="kriz", tags=["kriz", "eskalasyon"],
        turns=full_good("Nihan", _body),
        expected=Expected(
            scores=sc(default=8, Acilis=10, **{"KVKK / Aydinlatma": 10, "Kimlik Dogrulama": 10,
                                               "Yasakli Kelime / Uslup": 10, "Aktif Dinleme": 9}),
            zeroed=False, alerts=["crisis"],
            must_not_penalize=["Yasakli Kelime / Uslup", "Aktif Dinleme"],
            notes=f"Kriz sinyali ('{_kw}') MUSTERI kaynakli. Kriz alarmi URETILMELI ama "
                  "temsilci sakin ve cozum odakli davrandigi icin PUANI DUSMEMELI. "
                  "Musterinin davranisi temsilciyi cezalandirmaz.",
        ),
    ))


# =========================================================================
# 7) TUZAK SENARYOLARI (4)
# =========================================================================

add(Scenario(
    id="tuzak-01-kurum-adi-cumle-ortasinda",
    title="Kurum adi cumlenin ORTASINDA geciyor",
    bucket="tuzak", tags=["acilis", "tuzak"],
    turns=[
        Turn(T, "İyi günler, ben Mert; Netik İletişim müşteri hizmetlerinden arıyorsunuz, buyurun."),
        Turn(T, "Görüşmemiz kayıt altına alınmakta, verileriniz KVKK kapsamında işlenmektedir."),
        Turn(T, "Adınızı ve müşteri numaranızı alabilir miyim?"),
        Turn(M, "Sibel Kurt, 337720."),
        Turn(M, "Faturamı taksitlendirmek istiyorum."),
        Turn(T, "Faturanızı 3 taksite bölebilirim, ek ücret yok. Onaylıyor musunuz?"),
        Turn(M, "Onaylıyorum."),
        Turn(T, "İşlemi tamamladım, detaylar SMS olarak gelecek."),
    ] + close_std(),
    expected=Expected(
        scores=sc(default=9, Acilis=10),
        zeroed=False, alerts=[],
        evidence_must_contain={"Acilis": "Netik İletişim"},
        must_not_penalize=["Acilis"],
        notes="Kurum adi cumle BASINDA degil ORTASINDA. Konum degil VARLIK aranmali. "
              "Acilis tam puan almali.",
    ),
))

add(Scenario(
    id="tuzak-02-musteri-anlamiyor",
    title="Temsilci dogru bilgi veriyor, musteri anlamiyor",
    bucket="tuzak", tags=["bilgi_dogrulugu", "tuzak"],
    turns=full_good("Ozan", [
        Turn(M, "Faturamda 'ek paket' diye bir şey var, bu ne?"),
        Turn(T, "Geçen ay kotanız dolduğu için otomatik 5 GB ek paket tanımlanmış, 49 TL."),
        Turn(M, "Ben öyle bir şey istemedim ki."),
        Turn(T, "Bu, hattınızda açık olan otomatik ek paket ayarından kaynaklanıyor."),
        Turn(M, "Anlamadım, ben istemedim diyorum."),
        Turn(T, "Haklısınız, karışık geliyor. Şöyle anlatayım: kotanız bitince internetiniz kesilmesin diye"),
        Turn(T, "sistem otomatik ek paket veriyor. Bu ayarı isterseniz şimdi kapatabilirim."),
        Turn(M, "Kapatın lütfen."),
        Turn(T, "Kapattım. Bundan sonra kota bitince ek paket tanımlanmayacak."),
    ]),
    expected=Expected(
        scores=sc(default=9, **{"Bilgi Dogrulugu": 10, "Aktif Dinleme": 10, "Cozum / Yonlendirme": 10}),
        zeroed=False, alerts=[],
        must_not_penalize=["Bilgi Dogrulugu", "Aktif Dinleme"],
        notes="Musterinin anlamamasi temsilcinin hatasi DEGIL. Temsilci bilgiyi dogru "
              "verdi, anlasilmadigini fark edip BASKA sekilde anlatti ve cozdu. "
              "Bu ORNEK davranistir; ceza verilemez.",
    ),
))

add(Scenario(
    id="tuzak-03-musteri-kufrediyor",
    title="Musteri kufrediyor, temsilci sakin kaliyor",
    bucket="tuzak", tags=["yasakli_kelime", "tuzak"],
    turns=[
        Turn(T, "Netik İletişim, ben Cansu. Görüşmemiz kayıt altına alınmakta, verileriniz KVKK kapsamında işlenmektedir."),
        Turn(T, "Adınızı ve müşteri numaranızı alabilir miyim?"),
        Turn(M, "Ne adı be, saçmalamayın, aptal sistem!"),
        Turn(T, "Sizi anlıyorum, sinirlenmenizde haklısınız. İsminizi alabilirsem hemen yardımcı olacağım."),
        Turn(M, "Ferhat Uçar, 118004. Bu ne rezalet böyle."),
        Turn(T, "Teşekkür ederim Ferhat Bey. Kaydınıza bakıyorum."),
        Turn(M, "Üç haftadır bekliyorum, salaklık bu."),
        Turn(T, "Üç hafta gerçekten çok uzun, bunun için özür dilerim."),
        Turn(T, "Kaydınızı yönetici takibine aldım, bugün içinde size dönüş yapılacak."),
        Turn(M, "Tamam."),
    ] + close_std(),
    expected=Expected(
        scores=sc(default=9, **{"Yasakli Kelime / Uslup": 10, "Aktif Dinleme": 10}),
        zeroed=False, alerts=[],
        must_not_penalize=["Yasakli Kelime / Uslup", "Aktif Dinleme"],
        notes="'sacmalamayin', 'aptal', 'salaklik' kelimelerinin UCU DE MUSTERI "
              "replikinde. Temsilci sakin ve cozum odakli. SIFIRLAMA YASAK, "
              "yasakli kelime alarmi temsilciye YAZILAMAZ.",
    ),
))

add(Scenario(
    id="tuzak-04-anons-parcali",
    title="KVKK anonsu iki ayri replige bolunmus",
    bucket="tuzak", tags=["kvkk", "tuzak"],
    turns=[
        Turn(T, "Netik İletişim, ben Yiğit."),
        Turn(M, "İyi günler."),
        Turn(T, "Öncelikle bilgilendirmem gereken bir konu var."),
        Turn(T, "Bu görüşme hizmet kalitesi amacıyla kaydedilmektedir."),
        Turn(M, "Tamam."),
        Turn(T, "Ayrıca paylaşacağınız kişisel veriler mevzuata uygun şekilde işlenecektir."),
        Turn(T, "Adınızı ve müşteri numaranızı alabilir miyim?"),
        Turn(M, "Pelin Acar, 552018."),
        Turn(M, "Hattımı yurt dışı kullanıma açtırmak istiyorum."),
        Turn(T, "Uluslararası dolaşımı açıyorum. Hangi ülkeye gideceksiniz?"),
        Turn(M, "İtalya."),
        Turn(T, "İtalya için 7 günlük 5 GB paket 350 TL, tanımlayayım mı?"),
        Turn(M, "Tanımlayın."),
        Turn(T, "Tanımladım, çıkış gününüzde otomatik başlayacak."),
    ] + close_std(),
    expected=Expected(
        scores=sc(default=9, **{"KVKK / Aydinlatma": 10}),
        zeroed=False, alerts=[],
        must_not_penalize=["KVKK / Aydinlatma"],
        notes="Kayit bildirimi ve kisisel veri aydinlatmasi AYRI repliklerde ve "
              "standart kalibin disinda. Ikisi de yapilmis; ihlal URETILEMEZ.",
    ),
))


# =========================================================================
# 8) SES KALITESI / AKSAN (2)
# =========================================================================

add(Scenario(
    id="ses-01-dusuk-kalite",
    title="Dusuk ses kalitesi — anlasilmayan bolumler isaretli",
    bucket="ses_kalitesi", tags=["stt_guven_dusuk"],
    turns=[
        Turn(T, "Netik İletişim, ben Doğan. Görüşmemiz kayıt altına alınmakta, verileriniz KVKK kapsamında işlenmektedir."),
        Turn(T, "Adınızı ve müşteri numaranızı alabilir miyim?"),
        Turn(M, "[anlaşılmadı] Yılmaz, [anlaşılmadı] 21."),
        Turn(T, "Bağlantımız kopuk geliyor, müşteri numaranızı tekrar alabilir miyim?"),
        Turn(M, "447 [anlaşılmadı] 21."),
        Turn(T, "Anlıyorum, hattımız zayıf. Adınıza kayıtlı numaradan doğrulayabilir miyim?"),
        Turn(M, "Evet, bu numaradan."),
        Turn(T, "Teşekkürler, kaydınızı buldum. Nasıl yardımcı olabilirim?"),
        Turn(M, "[anlaşılmadı] fatura [anlaşılmadı]"),
        Turn(T, "Fatura konusunda yardımcı olayım. Sizi daha net duyabilmem için sizi geri arayabilir miyim?"),
        Turn(M, "Olur."),
        Turn(T, "5 dakika içinde bu numaradan arayacağım."),
    ],
    expected=Expected(
        scores=sc(default=8, **{"Kimlik Dogrulama": 8, "Ihtiyac Analizi": 6, "Cozum / Yonlendirme": 8}),
        zeroed=False, alerts=[],
        must_not_penalize=["Kimlik Dogrulama", "Bilgi Dogrulugu"],
        notes="[anlasilmadi] isaretli bolumlere DAYANARAK ceza verilemez. Temsilci "
              "zayif baglantiyi fark edip geri arama teklif etti — dogru davranis. "
              "Duyulamayan kisimlar 'yetersiz kanit' olmali, dusuk puan degil.",
    ),
))

# =========================================================================
# 9) DENETIMDE BULUNAN YENI HATALAR — B29, B30, B32 regresyonu
# (B27/B28/B31 motor degismezleridir; birim testle korunur —
#  backend/tests/test_scoring_invariants.py)
# =========================================================================

add(Scenario(
    id="reg-b32-kvkk-yok-sifirlanmali",
    title="B32: Deterministik KVKK tespiti SIFIRLAMAYA baglanmali",
    bucket="regresyon", regression_for="B32",
    tags=["kvkk", "uyum", "katman_a"],
    turns=[
        Turn(T, "Netik İletişim, ben Ceyda, buyurun."),
        Turn(T, "Adınızı ve müşteri numaranızı alabilir miyim?"),
        Turn(M, "Okan Yılmaz, 771450."),
        Turn(T, "Teşekkürler Okan Bey, kaydınızı görüyorum."),
        Turn(M, "Faturamı taksitlendirmek istiyorum."),
        Turn(T, "Faturanızı 3 taksite bölebilirim, ek ücret çıkmaz."),
        Turn(M, "Olur, bölün."),
        Turn(T, "Böldüm, detaylar SMS ile gelecek."),
    ] + close_std(),
    expected=Expected(
        scores=sc(default=8, **{"KVKK / Aydinlatma": 0}),
        zeroed=True, zeroing_criterion="KVKK / Aydinlatma",
        alerts=["zeroing"],
        notes="Kayit bildirimi ve aydinlatma anonsunun IKISI DE yok. Deterministik "
              "motor bunu zaten dogru tespit ediyor (compliance_packs ihlal uretiyor) "
              "ama sifirlama karari YALNIZ LLM puanina bakiyor. Katman A bulgusu "
              "kriter puanini EZMELI ve cagri SIFIRLANMALI.",
    ),
))

add(Scenario(
    id="reg-b29-konusmaci-bilinmiyor",
    title="B29: Konusmaci ayrimi yoksa uyum kriteri 'yetersiz kanit' olmali",
    bucket="regresyon", regression_for="B29",
    tags=["diarizasyon", "mono", "yetersiz_kanit"],
    turns=[
        Turn("bilinmeyen", "Netik İletişim, ben Tolga. Görüşmemiz kayıt altına alınmaktadır, verileriniz KVKK kapsamında işlenmektedir."),
        Turn("bilinmeyen", "Adınızı ve müşteri numaranızı alabilir miyim?"),
        Turn("bilinmeyen", "Sinan Er, 336720."),
        Turn("bilinmeyen", "Teşekkürler Sinan Bey. Nasıl yardımcı olabilirim?"),
        Turn("bilinmeyen", "İnternetim iki gündür yavaş."),
        Turn("bilinmeyen", "Hattınızı test ediyorum, senkron hızınız düşmüş. Profili yeniliyorum."),
        Turn("bilinmeyen", "Şimdi nasıl?"),
        Turn("bilinmeyen", "48 Mbps görüyorum, önceden 6 Mbps idi."),
        Turn("bilinmeyen", "Başka yardımcı olabileceğim bir konu var mı?"),
        Turn("bilinmeyen", "Yok, teşekkürler."),
    ],
    expected=Expected(
        scores=sc(default=5, **{"KVKK / Aydinlatma": 5, "Kimlik Dogrulama": 5,
                                "Yasakli Kelime / Uslup": 5}),
        zeroed=False, alerts=[],
        must_not_penalize=[],
        notes="Mono kayit + HF_TOKEN yok -> tum segmentler 'bilinmeyen'. KVKK anonsu "
              "metinde VAR ama kimin soyledigi BILINMIYOR. Sistem 'ihlal' DIYEMEZ "
              "(yanlis pozitif) ama 'tam puan' da VEREMEZ. Dogru cevap: yetersiz "
              "kanit -> insan kuyrugu. SIFIRLAMA KESINLIKLE YASAK.",
    ),
))

add(Scenario(
    id="reg-b30-uzun-cagri-orta-ihlal",
    title="B30: Uzun cagrida ihlal ORTADA — kirpma yuzunden kacirilmamali",
    bucket="regresyon", regression_for="B30",
    tags=["uzun_cagri", "pencereleme"],
    turns=(
        [Turn(T, "Netik İletişim, ben Gamze. Görüşmemiz kayıt altına alınmaktadır, verileriniz KVKK kapsamında işlenmektedir."),
         Turn(T, "Adınızı ve müşteri numaranızı alabilir miyim?"),
         Turn(M, "Ahmet Korkmaz, 118445."),
         Turn(T, "Teşekkürler Ahmet Bey, kaydınızı görüyorum.")]
        # --- dolgu: cagriyi 10 dk esiginin uzerine tasiyan gercek diyalog ---
        + [t for i in range(22) for t in (
            Turn(M, f"Peki {i + 1}. faturamdaki kalemleri de tek tek açıklar mısınız, hangisi ne için?"),
            Turn(T, f"Elbette. {i + 1}. dönemde sabit ücret, kullanım bedeli ve vergi kalemleri var; "
                    "sabit ücret paket bedeliniz, kullanım bedeli kota aşımı, vergiler ise yasal kesintiler."),
        )]
        # --- IHLAL TAM ORTADA ---
        + [Turn(T, "Ya yeter artık, saçmalamayın, bir saattir aynı şeyi anlatıyorum."),
           Turn(M, "Nasıl konuşuyorsunuz siz?")]
        + [t for i in range(22) for t in (
            Turn(M, f"Peki {i + 23}. dönem için de aynı dökümü alabilir miyim?"),
            Turn(T, f"{i + 23}. dönem için de sabit ücret, kullanım bedeli ve vergi kalemleri "
                    "aynı şekilde hesaplanıyor, tutarlar kullanımınıza göre değişiyor."),
        )]
        + close_std()
    ),
    expected=Expected(
        scores=sc(default=5, **{"Yasakli Kelime / Uslup": 0, "Aktif Dinleme": 3}),
        zeroed=True, zeroing_criterion="Yasakli Kelime / Uslup",
        alerts=["zeroing", "banned_word"],
        evidence_must_contain={"Yasakli Kelime / Uslup": "saçmalamayın"},
        notes="Cagri 10 dk esigini asiyor -> map-reduce yoluna giriyor. Hakaret "
              "transkriptin TAM ORTASINDA. Mevcut _transcript_outline ilk 25 + son 25 "
              "satiri aliyor, ortayi ATIYOR. Ihlal KACIRILAMAZ.",
    ),
))

add(Scenario(
    id="ses-02-agir-aksan",
    title="Agir aksanli musteri — transkript bozuk ama temsilci dogru anladi",
    bucket="ses_kalitesi", tags=["aksan"],
    turns=[
        Turn(T, "Netik İletişim, ben Sıla. Görüşmemiz kayıt altına alınmakta, verileriniz KVKK kapsamında işlenmektedir."),
        Turn(T, "Adınızı ve müşteri numaranızı alabilir miyim?"),
        Turn(M, "Mamet Şahan, numara altı altı üç bir sıfır iki."),
        Turn(T, "Teşekkürler Mehmet Bey, 663102 numaralı kaydınızı görüyorum."),
        Turn(M, "Fatora çok gelmiş bu ay, neden ola?"),
        Turn(T, "Faturanızı inceliyorum. Geçen ay kotanız aşılmış, ek kullanım ücreti yansımış."),
        Turn(M, "Ben ne yapayım şimdi?"),
        Turn(T, "Size iki seçenek sunayım: kotası daha yüksek bir pakete geçebiliriz,"),
        Turn(T, "ya da kota bitince internetin durmasını sağlayan ayarı açabilirim, ek ücret çıkmaz."),
        Turn(M, "İkincisi iyi ola."),
        Turn(T, "Ayarı açtım. Bundan sonra kotanız bitince ek ücret oluşmayacak."),
    ] + close_std(),
    expected=Expected(
        scores=sc(default=9, **{"Aktif Dinleme": 10, "Ihtiyac Analizi": 9, "Cozum / Yonlendirme": 10}),
        zeroed=False, alerts=[],
        must_not_penalize=["Aktif Dinleme", "Kimlik Dogrulama", "Bilgi Dogrulugu"],
        notes="Musterinin konusma bicimi (transkriptte 'Mamet', 'fatora', 'ola') "
              "temsilciyi CEZALANDIRMAZ. Temsilci dogru anladi, teyit etti ve iki "
              "secenek sunarak cozdu. Aktif Dinleme tam puan.",
    ),
))
