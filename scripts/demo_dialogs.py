"""Kurulumla gelen 20 örnek çağrı — diyalog metinleri.

## Neden ayrı bir dosya

`generate_demo.py` satış demosu için 220 çağrılık **puanlanmış** geçmiş üretir.
Bu dosya farklı bir işe yarar: ürünü ilk kez açan kişinin **kendi başlatacağı**
20 çağrı. Puan yok, transkript yok, alarm yok — sadece ses ve "bekliyor".

İkisini aynı dosyada tutmak, "demo verisi" teriminin iki farklı şeye
karışmasına yol açardı.

## Dağılım — istenen ve gerçekleşen

| Kova | Adet | Ne gösterir |
|---|---|---|
| `yuksek` | 6 | Sistemin normal, iyi bir çağrıda ne dediği |
| `orta` | 6 | Kısmi eksiklikler — puanın gri bölgesi |
| `dusuk` | 4 | Belirgin kalite sorunları |
| `sifirlayici` | 2 | KVKK anonsu yok · hakaret/yasaklı üslup |
| `kriz` | 2 | Avukat · hakem heyeti |

Kadın/erkek temsilci karışık, altı farklı temsilci, beş kategori.

## Yazım kuralı

Diyaloglar **Katman A'nın aradığı ifadeleri gerçekten içerir ya da bilinçli
olarak içermez.** Yani "KVKK anonsu yok" senaryosunda anons cümlesi gerçekten
yoktur; sistem onu bulamadığı için sıfırlar. Metin ile beklenen davranış
arasında uyumsuzluk olursa demo, ürünü yanlış tanıtır.
"""

from __future__ import annotations

# k: "t" = temsilci, "m" = musteri
DEMO_CALLS: list[dict] = [

    # ================================================================
    # YÜKSEK KALİTE (6)
    # ================================================================
    {
        "id": "01-yuksek-fatura-itiraz",
        "agent": "ayse.yilmaz", "category": "fatura", "bucket": "yuksek",
        "note": "Fatura itirazı — açılış, KVKK, kimlik, çözüm, kapanış tam",
        "turns": [
            {"k": "t", "m": "Netix İletişim'e hoş geldiniz, ben Ayşe. Görüşmemiz kalite standartları gereği kayıt altına alınmakta ve kişisel verileriniz KVKK kapsamında işlenmektedir. Size nasıl yardımcı olabilirim?"},
            {"k": "m", "m": "Merhaba, bu ayki faturam beklediğimden yüksek geldi. Üç yüz yirmi lira görünüyor."},
            {"k": "t", "m": "Hemen inceleyelim. İşlem güvenliği için adınızı, soyadınızı ve müşteri numaranızı teyit edebilir miyim?"},
            {"k": "m", "m": "Serkan Aydın, müşteri numaram dört beş altı yedi sekiz."},
            {"k": "t", "m": "Teşekkür ederim Serkan Bey. Faturanızda yurt dışı arama kalemi görüyorum, otuz sekiz dakikalık bir görüşme. Tarifenize dahil olmadığı için ek ücretlendirilmiş."},
            {"k": "m", "m": "Doğru, geçen ay Almanya'yı aramıştım ama bu kadar tutacağını bilmiyordum."},
            {"k": "t", "m": "Anlıyorum, önceden bilinmemesi can sıkıcı. Size iki seçenek sunabilirim: aylık yirmi dokuz liraya yurt dışı paketi ekleyebiliriz, ya da bu görüşmenin ücretini bir defalık iyi niyet indirimi olarak düşebilirim."},
            {"k": "m", "m": "İkisi de olur mu?"},
            {"k": "t", "m": "Bu seferlik ikisini de yapabiliyorum. İndirimi işledim, paketi de tanımladım. Yeni fatura tutarınız iki yüz on beş lira olacak, önümüzdeki hafta güncellenecek."},
            {"k": "m", "m": "Çok teşekkür ederim, beklediğimden iyi oldu."},
            {"k": "t", "m": "Rica ederim Serkan Bey. Başka yardımcı olabileceğim bir konu var mı? Yoksa iyi günler dilerim, bizi tercih ettiğiniz için teşekkürler."},
        ],
    },
    {
        "id": "02-yuksek-modem-ariza",
        "agent": "mehmet.kaya", "category": "ariza", "bucket": "yuksek",
        "note": "Modem arızası — adım adım teşhis, teknisyen randevusu",
        "turns": [
            {"k": "t", "m": "Netix İletişim teknik destek, ben Mehmet. Görüşmemiz kayıt altına alınmakta, verileriniz KVKK kapsamında işlenmektedir. Nasıl yardımcı olabilirim?"},
            {"k": "m", "m": "İnternetim iki gündür sürekli kesiliyor. Çalışamıyorum artık."},
            {"k": "t", "m": "İki gündür sürüyorsa gerçekten zor olmuştur. Hemen bakalım. Kimlik doğrulaması için adınızı ve müşteri numaranızı alabilir miyim?"},
            {"k": "m", "m": "Fatma Şen, numaram bir bir iki üç dört."},
            {"k": "t", "m": "Teşekkürler Fatma Hanım. Hattınızda sinyal seviyesi düşük görünüyor. Modemin ışıklarından kırmızı yanan var mı?"},
            {"k": "m", "m": "Evet, ortadaki ışık kırmızı yanıp sönüyor."},
            {"k": "t", "m": "Bu, hat bağlantısında sorun olduğunu gösteriyor. Önce uzaktan hat testi yapayım, otuz saniye sürecek."},
            {"k": "m", "m": "Tamam bekliyorum."},
            {"k": "t", "m": "Test sonucu geldi: bina girişindeki kabloda zayıflama var, bu uzaktan düzeltilemiyor. Yarın öğleden sonra iki ile beş arası teknisyen gönderebilirim. Uygun mudur?"},
            {"k": "m", "m": "Yarın olur, evde olacağım."},
            {"k": "t", "m": "Randevunuzu oluşturdum, kayıt numaranız yedi yedi dört. Teknisyen gelmeden önce sizi arayacak. Arıza süresince kesinti gün sayısı faturanızdan düşülecek. Başka bir konuda yardımcı olabilir miyim? İyi günler dilerim."},
        ],
    },
    {
        "id": "03-yuksek-iptal-tutundurma",
        "agent": "zeynep.demir", "category": "iptal", "bucket": "yuksek",
        "note": "İptal talebi — dinleme, alternatif teklif, müşteri karar veriyor",
        "turns": [
            {"k": "t", "m": "Netix İletişim, ben Zeynep. Görüşmemiz kayıt altındadır, kişisel verileriniz KVKK kapsamında korunmaktadır. Nasıl yardımcı olabilirim?"},
            {"k": "m", "m": "Aboneliğimi iptal etmek istiyorum."},
            {"k": "t", "m": "Tabii, işleme alabilirim. Öncesinde adınızı ve müşteri numaranızı teyit edebilir miyim?"},
            {"k": "m", "m": "Kemal Arslan, dokuz sekiz yedi altı."},
            {"k": "t", "m": "Teşekkürler Kemal Bey. İptal sebebini paylaşmak ister misiniz? Belki çözebileceğimiz bir konu vardır."},
            {"k": "m", "m": "Açıkçası fiyat. Rakip firma aynı hızı daha ucuza veriyor."},
            {"k": "t", "m": "Anlıyorum, bütçe önemli. Şu an yüz altmış lira ödüyorsunuz. Sadakat indirimiyle aynı paketi yüz on dokuz liraya sunabiliyorum, on iki ay taahhütle. İsterseniz taahhütsüz yüz otuz dokuz lira da mümkün."},
            {"k": "m", "m": "Taahhütsüz olan iyi. Ama düşünmek istiyorum."},
            {"k": "t", "m": "Elbette, acele etmeyin. Teklifi hesabınıza yedi gün geçerli olacak şekilde not düştüm. Karar verirseniz aramanız yeterli, tekrar anlatmanıza gerek kalmayacak. İptal talebinizi de bekletiyorum, siz onaylamadan işleme almıyorum."},
            {"k": "m", "m": "Böylesi iyi oldu, teşekkürler."},
            {"k": "t", "m": "Rica ederim Kemal Bey, iyi günler dilerim."},
        ],
    },
    {
        "id": "04-yuksek-tarife-bilgi",
        "agent": "emre.sahin", "category": "bilgi", "bucket": "yuksek",
        "note": "Tarife bilgisi — ihtiyaç analizi, doğru yönlendirme",
        "turns": [
            {"k": "t", "m": "Netix İletişim, ben Emre. Görüşmemiz kayıt altına alınmaktadır, verileriniz KVKK kapsamında işlenmektedir. Nasıl yardımcı olabilirim?"},
            {"k": "m", "m": "Tarifemi değiştirmek istiyorum ama hangisi bana uygun bilmiyorum."},
            {"k": "t", "m": "Birlikte bakalım. Önce adınızı ve müşteri numaranızı alabilir miyim?"},
            {"k": "m", "m": "Elif Korkmaz, üç üç iki iki bir."},
            {"k": "t", "m": "Teşekkürler Elif Hanım. Doğru öneriyi yapabilmem için birkaç soru soracağım. Ayda ne kadar internet kullanıyorsunuz, çoğunlukla video mu izliyorsunuz?"},
            {"k": "m", "m": "Evden çalışıyorum, sürekli görüntülü toplantı var. Akşamları da dizi izliyoruz."},
            {"k": "t", "m": "Anladım, hem yükleme hızı hem kota önemli. Son üç aylık kullanımınıza baktım, ortalama iki yüz seksen gigabayt. Şu anki paketiniz iki yüz gigabayt, yani her ay aşım yaşıyorsunuz."},
            {"k": "m", "m": "Evet, o yüzden fatura hep şaşırtıyor."},
            {"k": "t", "m": "O zaman sınırsız paket sizin için hem daha rahat hem büyük ihtimalle daha ucuz. Aylık yüz seksen dokuz lira, aşım ücreti yok. Şu an ortalama iki yüz on lira ödüyorsunuz."},
            {"k": "m", "m": "Hem sınırsız hem ucuz mu? Geçelim o zaman."},
            {"k": "t", "m": "Değişikliği yaptım, bir sonraki fatura döneminde başlıyor. Kesinti olmayacak. Başka bir konuda yardımcı olabilir miyim? İyi günler dilerim Elif Hanım."},
        ],
    },
    {
        "id": "05-yuksek-otomatik-odeme",
        "agent": "elif.arslan", "category": "fatura", "bucket": "yuksek",
        "note": "Otomatik ödeme talimatı — güvenlik uyarısı doğru verilmiş",
        "turns": [
            {"k": "t", "m": "Netix İletişim, ben Elif. Görüşmemiz kayıt altındadır, kişisel verileriniz KVKK kapsamında işlenmektedir. Nasıl yardımcı olabilirim?"},
            {"k": "m", "m": "Otomatik ödeme talimatı vermek istiyorum, hep unutuyorum faturayı."},
            {"k": "t", "m": "Tabii, kolaylık sağlar. Adınızı ve müşteri numaranızı teyit edebilir miyim?"},
            {"k": "m", "m": "Okan Doğan, beş beş dört dört üç."},
            {"k": "t", "m": "Teşekkürler Okan Bey. Talimatı iki şekilde verebilirsiniz: kredi kartı veya banka hesabı. Hangisini tercih edersiniz?"},
            {"k": "m", "m": "Kredi kartı. Numarayı söyleyeyim mi?"},
            {"k": "t", "m": "Kart bilgilerinizi telefonda paylaşmanıza gerek yok, güvenliğiniz için almıyoruz. Size güvenli ödeme bağlantısı göndereceğim; bilgileri doğrudan bankanın sayfasına gireceksiniz, biz görmeyeceğiz."},
            {"k": "m", "m": "Daha iyi, öyle yapalım."},
            {"k": "t", "m": "Bağlantıyı kayıtlı cep telefonunuza gönderdim, kırk sekiz saat geçerli. İşlemi tamamladığınızda size bilgilendirme mesajı gelecek. Başka bir konuda yardımcı olabilir miyim? İyi günler dilerim."},
        ],
    },
    {
        "id": "06-yuksek-sikayet-cozum",
        "agent": "burak.ozturk", "category": "sikayet", "bucket": "yuksek",
        "note": "Teknisyen gelmedi şikâyeti — sahiplenme, net taahhüt",
        "turns": [
            {"k": "t", "m": "Netix İletişim, ben Burak. Görüşmemiz kayıt altına alınmaktadır, verileriniz KVKK kapsamında işlenmektedir. Nasıl yardımcı olabilirim?"},
            {"k": "m", "m": "Dün teknisyen gelecekti, bütün gün bekledim gelmedi. Kimse de aramadı."},
            {"k": "t", "m": "Bütün gün beklemiş olmanız gerçekten haksızlık, bunun için özür dilerim. Hemen kaydınıza bakayım. Adınızı ve müşteri numaranızı alabilir miyim?"},
            {"k": "m", "m": "Selin Koç, iki iki bir bir sıfır."},
            {"k": "t", "m": "Teşekkürler Selin Hanım. Kayıtta randevunun 'ulaşılamadı' olarak kapatıldığını görüyorum, ancak arama kaydı yok. Yani teknisyen sizi aramadan kapatmış. Bu bizim hatamız."},
            {"k": "m", "m": "Aynen öyle, telefonum hep açıktı."},
            {"k": "t", "m": "Kaydı yeniden açtım ve öncelikli olarak işaretledim. Yarın sabah dokuz ile on iki arası kesin randevu verdim; teknisyen yola çıkmadan sizi arayacak. Ayrıca bu aksaklık için faturanıza elli lira indirim tanımladım."},
            {"k": "m", "m": "Teşekkür ederim, en azından ciddiye alındı."},
            {"k": "t", "m": "Takibini şahsen yapacağım Selin Hanım. Yarın işlem tamamlanmazsa siz aramadan ben sizi arayacağım. Başka bir konuda yardımcı olabilir miyim? İyi günler dilerim."},
        ],
    },

    # ================================================================
    # ORTA (6) — kısmi eksiklikler, gri bölge
    # ================================================================
    {
        "id": "07-orta-kapanis-eksik",
        "agent": "ayse.yilmaz", "category": "bilgi", "bucket": "orta",
        "note": "Açılış ve KVKK tam, çözüm iyi, ama kapanış yok — aniden bitiyor",
        "turns": [
            {"k": "t", "m": "Netix İletişim, ben Ayşe. Görüşmemiz kayıt altındadır, kişisel verileriniz KVKK kapsamında işlenmektedir. Nasıl yardımcı olabilirim?"},
            {"k": "m", "m": "Roaming açtırmak istiyorum, yurt dışına çıkacağım."},
            {"k": "t", "m": "Tabii. Adınızı ve müşteri numaranızı alabilir miyim?"},
            {"k": "m", "m": "Caner Aydın, sekiz sekiz yedi yedi."},
            {"k": "t", "m": "Teşekkürler. Hangi ülkeye gidiyorsunuz ve kaç gün kalacaksınız?"},
            {"k": "m", "m": "Almanya, on gün."},
            {"k": "t", "m": "Avrupa paketi on günlük iki yüz kırk dokuz lira, beş gigabayt internet ve yüz dakika konuşma içeriyor. Tanımlayayım mı?"},
            {"k": "m", "m": "Evet tanımlayın."},
            {"k": "t", "m": "Tanımladım, uçağa binmeden aktif olacak."},
            {"k": "m", "m": "Tamam."},
        ],
    },
    {
        "id": "08-orta-kimlik-gec",
        "agent": "mehmet.kaya", "category": "fatura", "bucket": "orta",
        "note": "Kimlik doğrulama işlemden SONRA yapılıyor — sıralama hatası",
        "turns": [
            {"k": "t", "m": "Netix İletişim, ben Mehmet. Görüşmemiz kayıt altına alınmaktadır, verileriniz KVKK kapsamında işlenmektedir. Nasıl yardımcı olabilirim?"},
            {"k": "m", "m": "Son faturamı öğrenebilir miyim?"},
            {"k": "t", "m": "Tabii, bakıyorum. Son faturanız iki yüz on lira, son ödeme tarihi ayın yirmi beşi."},
            {"k": "m", "m": "Peki geçen ay ne kadardı?"},
            {"k": "t", "m": "Geçen ay yüz doksan beş liraydı. Bu ay on beş lira artmış."},
            {"k": "m", "m": "Neden artmış?"},
            {"k": "t", "m": "Bir dakika, işlem güvenliği için adınızı ve müşteri numaranızı teyit etmem gerekiyor."},
            {"k": "m", "m": "Gizem Çelik, dört dört üç üç."},
            {"k": "t", "m": "Teşekkürler Gizem Hanım. Artış, ek SMS paketinden kaynaklanmış. İsterseniz kaldırabilirim."},
            {"k": "m", "m": "Kaldırın lütfen."},
            {"k": "t", "m": "Kaldırdım. Başka bir konuda yardımcı olabilir miyim? İyi günler."},
        ],
    },
    {
        "id": "09-orta-dinleme-zayif",
        "agent": "emre.sahin", "category": "sikayet", "bucket": "orta",
        "note": "Çözüm doğru ama temsilci müşteriyi tam dinlemeden çözüme atlıyor",
        "turns": [
            {"k": "t", "m": "Netix İletişim, ben Emre. Görüşmemiz kayıt altındadır, verileriniz KVKK kapsamında işlenmektedir. Nasıl yardımcı olabilirim?"},
            {"k": "m", "m": "İnternetim yavaş, özellikle akşamları film izlerken sürekli"},
            {"k": "t", "m": "Modemi kapatıp açın, çoğu sorun düzeliyor."},
            {"k": "m", "m": "Denedim zaten, düzelmiyor. Diyecektim ki sadece akşam saatlerinde oluyor."},
            {"k": "t", "m": "Anladım. Adınızı ve müşteri numaranızı alabilir miyim?"},
            {"k": "m", "m": "Deniz Yıldız, yedi yedi altı altı."},
            {"k": "t", "m": "Teşekkürler. Akşam saatlerinde bölgesel yoğunluk olabiliyor. Hattınızı yüksek öncelikli profile aldım, akşam düşüşü azalacak."},
            {"k": "m", "m": "Tamam, bakalım."},
            {"k": "t", "m": "Bir hafta içinde düzelmezse tekrar arayın. İyi günler."},
        ],
    },
    {
        "id": "10-orta-belirsiz-taahhut",
        "agent": "zeynep.demir", "category": "ariza", "bucket": "orta",
        "note": "Empati var ama taahhüt belirsiz — 'en kısa sürede'",
        "turns": [
            {"k": "t", "m": "Netix İletişim, ben Zeynep. Görüşmemiz kayıt altındadır, kişisel verileriniz KVKK kapsamında korunmaktadır. Nasıl yardımcı olabilirim?"},
            {"k": "m", "m": "Telefon hattımda cızırtı var, karşımdaki beni duyamıyor."},
            {"k": "t", "m": "Bu can sıkıcı bir durum, anlıyorum. Adınızı ve müşteri numaranızı alabilir miyim?"},
            {"k": "m", "m": "Pelin Acar, bir bir bir bir iki."},
            {"k": "t", "m": "Teşekkürler Pelin Hanım. Hat kaydınızı açtım, teknik ekibe ilettim."},
            {"k": "m", "m": "Ne zaman düzelir peki?"},
            {"k": "t", "m": "En kısa sürede ilgilenecekler."},
            {"k": "m", "m": "En kısa süre ne demek, bir gün mü bir hafta mı?"},
            {"k": "t", "m": "Yoğunluğa göre değişiyor, ama takipteler."},
            {"k": "m", "m": "Peki."},
            {"k": "t", "m": "Başka bir konuda yardımcı olabilir miyim? İyi günler dilerim."},
        ],
    },
    {
        "id": "11-orta-yonlendirme-yarim",
        "agent": "elif.arslan", "category": "iptal", "bucket": "orta",
        "note": "Doğru bilgi ama işlem tamamlanmıyor, müşteri tekrar aramak zorunda",
        "turns": [
            {"k": "t", "m": "Netix İletişim, ben Elif. Görüşmemiz kayıt altındadır, kişisel verileriniz KVKK kapsamında işlenmektedir. Nasıl yardımcı olabilirim?"},
            {"k": "m", "m": "Hattımı dondurmak istiyorum, üç ay yurt dışındayım."},
            {"k": "t", "m": "Adınızı ve müşteri numaranızı alabilir miyim?"},
            {"k": "m", "m": "Okan Doğan, beş beş dört dört üç."},
            {"k": "t", "m": "Teşekkürler Okan Bey. Dondurma işlemi mümkün, aylık yirmi dokuz lira sabit ücretle en fazla altı ay."},
            {"k": "m", "m": "Tamam, yapalım."},
            {"k": "t", "m": "Bu işlemi abonelik biriminin yapması gerekiyor, ben buradan başlatamıyorum. Onları arayıp talep etmeniz gerekecek."},
            {"k": "m", "m": "Siz aktaramaz mısınız?"},
            {"k": "t", "m": "Şu an hat yoğun görünüyor. Numarayı vereyim, siz arayın daha hızlı olur."},
            {"k": "m", "m": "Peki, not alıyorum."},
            {"k": "t", "m": "Başka bir konuda yardımcı olabilir miyim? İyi günler."},
        ],
    },
    {
        "id": "12-orta-script-atlama",
        "agent": "burak.ozturk", "category": "bilgi", "bucket": "orta",
        "note": "Hızlı ve çözücü ama açılışta kurum adı yok — script eksik",
        "turns": [
            {"k": "t", "m": "Merhaba, ben Burak. Görüşmemiz kayıt altındadır, verileriniz KVKK kapsamında işlenmektedir. Nasıl yardımcı olabilirim?"},
            {"k": "m", "m": "Şifremi unuttum, online işlemlere giremiyorum."},
            {"k": "t", "m": "Hemen çözelim. Adınızı ve müşteri numaranızı alabilir miyim?"},
            {"k": "m", "m": "Kerem Aydın, altı altı beş beş."},
            {"k": "t", "m": "Teşekkürler Kerem Bey. Kayıtlı cep telefonunuza sıfırlama kodu gönderdim. Kodu girdikten sonra yeni şifrenizi belirleyebilirsiniz."},
            {"k": "m", "m": "Geldi, giriyorum. Tamam oldu."},
            {"k": "t", "m": "Harika. Başka bir konuda yardımcı olabilir miyim? İyi günler dilerim."},
        ],
    },

    # ================================================================
    # DÜŞÜK (4)
    # ================================================================
    {
        "id": "13-dusuk-yanlis-bilgi",
        "agent": "mehmet.kaya", "category": "bilgi", "bucket": "dusuk",
        "note": "Temsilci YANLIŞ bilgi veriyor (cayma süresi 7 gün değil 14 gün)",
        "turns": [
            {"k": "t", "m": "Netix İletişim, ben Mehmet. Görüşmemiz kayıt altındadır, verileriniz KVKK kapsamında işlenmektedir. Nasıl yardımcı olabilirim?"},
            {"k": "m", "m": "Geçen hafta abone oldum ama vazgeçtim. Cayma hakkım var mı?"},
            {"k": "t", "m": "Adınızı ve müşteri numaranızı alabilir miyim?"},
            {"k": "m", "m": "Gizem Çelik, dört dört üç üç."},
            {"k": "t", "m": "Teşekkürler. Cayma hakkı yedi gün, siz o süreyi geçirmişsiniz. Artık cayamazsınız, taahhüt bedeli ödemeniz gerekir."},
            {"k": "m", "m": "Emin misiniz? Ben on dört gün diye biliyordum."},
            {"k": "t", "m": "Hayır, mevzuat yedi gün. Sistemde de öyle görünüyor."},
            {"k": "m", "m": "Peki ne kadar ödemem gerekiyor?"},
            {"k": "t", "m": "Kalan taahhüt süresine göre yaklaşık sekiz yüz lira çıkar."},
            {"k": "m", "m": "Bu çok fazla, araştıracağım."},
            {"k": "t", "m": "Nasıl isterseniz. İyi günler."},
        ],
    },
    {
        "id": "14-dusuk-soz-kesme",
        "agent": "caner.aydin", "category": "sikayet", "bucket": "dusuk",
        "note": "Temsilci sürekli sözünü kesiyor, empati yok, çözüm yarım",
        "turns": [
            {"k": "t", "m": "Netix İletişim, ben Caner. Görüşmemiz kayıt altındadır, verileriniz KVKK kapsamında işlenmektedir. Buyurun."},
            {"k": "m", "m": "Üç haftadır aynı sorunu anlatıyorum, her seferinde"},
            {"k": "t", "m": "Kayıt numaranız neydi?"},
            {"k": "m", "m": "Bilmiyorum, her seferinde başka biri çıkıyor ve ben"},
            {"k": "t", "m": "Adınızı söyleyin yeter."},
            {"k": "m", "m": "Selin Koç. Anlatmaya çalıştığım şey şu, sorun çözülmüyor ve"},
            {"k": "t", "m": "Sistemde kaydınız açık görünüyor, teknik ekipte."},
            {"k": "m", "m": "Üç haftadır teknik ekipte diyorsunuz."},
            {"k": "t", "m": "Ben oradan bir şey yapamam, süreç öyle işliyor."},
            {"k": "m", "m": "Yani bekleyeceğim yine."},
            {"k": "t", "m": "Evet. Başka bir şey var mı?"},
            {"k": "m", "m": "Yok."},
        ],
    },
    {
        "id": "15-dusuk-cozumsuz",
        "agent": "caner.aydin", "category": "ariza", "bucket": "dusuk",
        "note": "Çözüm üretilmiyor, müşteri kendi başına bırakılıyor",
        "turns": [
            {"k": "t", "m": "Netix İletişim, ben Caner. Görüşmemiz kayıt altındadır, verileriniz KVKK kapsamında işlenmektedir. Nasıl yardımcı olabilirim?"},
            {"k": "m", "m": "Televizyon yayınım donuyor, kanallar açılmıyor."},
            {"k": "t", "m": "Adınız ve müşteri numaranız?"},
            {"k": "m", "m": "Kerem Aydın, altı altı beş beş."},
            {"k": "t", "m": "Sistemde bir arıza görünmüyor. Cihazı fişten çekip takın."},
            {"k": "m", "m": "Üç kez yaptım, olmuyor."},
            {"k": "t", "m": "O zaman cihaz arızalı olabilir. Mağazaya götürün."},
            {"k": "m", "m": "Cihaz sizin, garanti kapsamında değil mi?"},
            {"k": "t", "m": "Mağaza bakar, ben buradan göremiyorum."},
            {"k": "m", "m": "Randevu falan alamıyor muyum?"},
            {"k": "t", "m": "Mağazadan alırsınız. İyi günler."},
        ],
    },
    {
        "id": "16-dusuk-bilgi-eksik",
        "agent": "okan.dogan", "category": "fatura", "bucket": "dusuk",
        "note": "Sorulan soruya cevap vermiyor, geçiştiriyor",
        "turns": [
            {"k": "t", "m": "Netix İletişim, ben Okan. Görüşmemiz kayıt altındadır, verileriniz KVKK kapsamında işlenmektedir. Nasıl yardımcı olabilirim?"},
            {"k": "m", "m": "Faturamda 'hizmet bedeli' diye bir kalem var, bu ne?"},
            {"k": "t", "m": "Adınızı ve müşteri numaranızı alabilir miyim?"},
            {"k": "m", "m": "Pelin Acar, bir bir bir bir iki."},
            {"k": "t", "m": "Teşekkürler. O standart bir kalem."},
            {"k": "m", "m": "Standart ama ne için alınıyor?"},
            {"k": "t", "m": "Faturalandırma sisteminde öyle geçiyor."},
            {"k": "m", "m": "Yani ne olduğunu siz de bilmiyor musunuz?"},
            {"k": "t", "m": "Detayını abonelik birimi bilir. İsterseniz onlara sorun."},
            {"k": "m", "m": "Tamam boş verin."},
            {"k": "t", "m": "İyi günler."},
        ],
    },

    # ================================================================
    # SIFIRLAYICI İHLAL (2)
    # ================================================================
    {
        "id": "17-sifirlayici-kvkk-yok",
        "agent": "okan.dogan", "category": "fatura", "bucket": "sifirlayici",
        "note": "KVKK anonsu HİÇ yapılmıyor — kayıt bildirimi yok. Sıfırlamalı.",
        "turns": [
            {"k": "t", "m": "Alo, buyurun."},
            {"k": "m", "m": "İyi günler, faturamla ilgili arıyorum."},
            {"k": "t", "m": "Numaranızı verin."},
            {"k": "m", "m": "Kerem Aydın, altı altı beş beş."},
            {"k": "t", "m": "Faturanız üç yüz kırk lira, son ödeme ayın yirmi beşi."},
            {"k": "m", "m": "Neden bu kadar yüksek?"},
            {"k": "t", "m": "Kullanmışsınız demek ki."},
            {"k": "m", "m": "Geçen ay yüz seksendi ama."},
            {"k": "t", "m": "Detayı online işlemlerden bakın."},
            {"k": "m", "m": "Peki."},
            {"k": "t", "m": "Başka?"},
            {"k": "m", "m": "Yok."},
        ],
    },
    {
        "id": "18-sifirlayici-hakaret",
        "agent": "caner.aydin", "category": "sikayet", "bucket": "sifirlayici",
        "note": "Temsilci müşteriye hakaret ediyor — yasaklı üslup. Sıfırlamalı.",
        "turns": [
            {"k": "t", "m": "Netix İletişim, ben Caner. Görüşmemiz kayıt altındadır. Buyurun."},
            {"k": "m", "m": "İki gündür internetim yok, kimse ilgilenmiyor."},
            {"k": "t", "m": "Kaydınız var mı?"},
            {"k": "m", "m": "Var ama sonuç yok. Bu nasıl bir hizmet anlayışı?"},
            {"k": "t", "m": "Beyefendi saçmalamayın, sistemde ne varsa onu söylüyorum."},
            {"k": "m", "m": "Ne dediniz siz?"},
            {"k": "t", "m": "Anlamıyorsanız ben ne yapayım. Boş yere hattı meşgul ediyorsunuz."},
            {"k": "m", "m": "Bu tavrınızı şikâyet edeceğim."},
            {"k": "t", "m": "Edin, bana ne."},
            {"k": "m", "m": "İnanılmaz."},
        ],
    },

    # ================================================================
    # KRİZ (2)
    # ================================================================
    {
        "id": "19-kriz-avukat",
        "agent": "ayse.yilmaz", "category": "sikayet", "bucket": "kriz",
        "note": "Müşteri avukata gideceğini söylüyor — temsilci sakin ve profesyonel",
        "turns": [
            {"k": "t", "m": "Netix İletişim, ben Ayşe. Görüşmemiz kayıt altındadır, kişisel verileriniz KVKK kapsamında işlenmektedir. Nasıl yardımcı olabilirim?"},
            {"k": "m", "m": "Bakın artık sabrım kalmadı. İptal ettiğim hat üç aydır faturalanıyor ve icra takibi başlatmışsınız."},
            {"k": "t", "m": "Bu gerçekten ciddi bir durum, hemen inceliyorum. Adınızı ve müşteri numaranızı alabilir miyim?"},
            {"k": "m", "m": "Serkan Aydın, dört beş altı yedi sekiz. Avukatımla görüştüm, dava açacağım."},
            {"k": "t", "m": "Sizi anlıyorum Serkan Bey, yaşadığınız şey haklı bir şikâyet sebebi. Kaydınıza baktım: iptal talebiniz on beş Mayıs'ta alınmış ama sistemde işlenmemiş görünüyor."},
            {"k": "m", "m": "Yani hatanız olduğunu kabul ediyorsunuz."},
            {"k": "t", "m": "Kayıtlar bunu gösteriyor, evet. Şu an yapabileceklerim: icra takibini durdurma talebini bugün ileteceğim, üç aylık faturaları iptal kaydıyla sileceğim ve konuyu hukuk birimine acil olarak açacağım."},
            {"k": "m", "m": "Bunlar ne zaman olacak?"},
            {"k": "t", "m": "Fatura iptallerini şimdi işliyorum. İcra takibinin durdurulması hukuk biriminde en geç iki iş günü sürer. Size işlem numarası veriyorum: dokuz dört bir iki."},
            {"k": "m", "m": "İki gün içinde dönüş almazsam avukatım devreye girecek."},
            {"k": "t", "m": "Anlıyorum ve bu hakkınız. İki iş günü içinde size bizzat dönüş yapılacak; ben de takibini yapacağım. Yaşattığımız mağduriyet için özür dilerim Serkan Bey."},
        ],
    },
    {
        "id": "20-kriz-hakem-heyeti",
        "agent": "zeynep.demir", "category": "sikayet", "bucket": "kriz",
        "note": "Müşteri tüketici hakem heyetine gideceğini söylüyor",
        "turns": [
            {"k": "t", "m": "Netix İletişim, ben Zeynep. Görüşmemiz kayıt altındadır, kişisel verileriniz KVKK kapsamında korunmaktadır. Nasıl yardımcı olabilirim?"},
            {"k": "m", "m": "Taahhüt bittiği halde cayma bedeli kesmişsiniz. İade etmezseniz tüketici hakem heyetine başvuracağım."},
            {"k": "t", "m": "Konuyu hemen inceleyeyim. Adınızı ve müşteri numaranızı teyit edebilir miyim?"},
            {"k": "m", "m": "Fatma Şen, bir bir iki üç dört."},
            {"k": "t", "m": "Teşekkürler Fatma Hanım. Sözleşmenize bakıyorum: taahhüdünüz on iki Nisan'da sona ermiş, iptal talebiniz ise yirmi Nisan'da alınmış. Yani taahhüt bitmiş, cayma bedeli alınmaması gerekiyordu."},
            {"k": "m", "m": "Ben de bunu söylüyorum ama kimse dinlemiyor."},
            {"k": "t", "m": "Haklısınız ve kayıtlar sizi doğruluyor. Kesilen dört yüz otuz liralık cayma bedelinin iadesi için talep açıyorum."},
            {"k": "m", "m": "Ne kadar sürer bu iade?"},
            {"k": "t", "m": "İade talepleri en geç yedi iş günü içinde hesabınıza yansıyor. Talep numaranız üç sekiz iki beş. Yansımazsa bu numarayla arayın, baştan anlatmanıza gerek kalmaz."},
            {"k": "m", "m": "Yedi gün içinde gelmezse hakem heyetine gideceğim."},
            {"k": "t", "m": "Anlıyorum, bu hakkınız ve başvurunuz için gerekli belgeleri talep ederseniz size iletebiliriz. Ama iadenin süresinde yapılacağını düşünüyorum. Yaşattığımız zorluk için özür dilerim Fatma Hanım."},
        ],
    },
]


def dagilim() -> dict[str, int]:
    """Kova başına senaryo sayısı — testte doğrulanır."""
    out: dict[str, int] = {}
    for d in DEMO_CALLS:
        out[d["bucket"]] = out.get(d["bucket"], 0) + 1
    return out
