# KVKK Uyum Dokümanı

> Bu doküman, KaliteGöz'ün kişisel veri işleme yaklaşımını ve kurumun
> yükümlülüklerini açıklar. Güvenlik sayfasındaki her madde **çalışan bir
> kontrolden** okunur; bu doküman o kontrollerin arkasındaki gerekçedir.

---

## 1. Veri nerede duruyor?

| Veri | Nerede | Kurum dışına çıkıyor mu? |
|---|---|---|
| Ses kayıtları | Kurum sunucusundaki `data/storage/audio` | **Hayır** |
| Transkriptler | Kurum veritabanı (`segments`) | **Hayır** |
| Puanlar ve kanıtlar | Kurum veritabanı (`scores`) | **Hayır** |
| LLM istekleri | Yerel Ollama (varsayılan) | **Hayır** |

**On-prem varsayılandır.** Yapay zekâ yerel çalışır; transkript hiçbir bulut
servisine gönderilmez. Kurum bilinçli olarak bulut sağlayıcı seçerse
(Gemini/OpenAI), giden metin **her zaman maskelenir** ve güvenlik sayfası
durumu "veri kurum dışına çıkıyor" olarak gösterir.

## 2. Maskeleme

Transkriptte otomatik maskelenen alanlar:

- **TC kimlik numarası** — 11 haneli, doğrulama algoritmasıyla teyit edilir
- **Telefon numarası**
- **IBAN**
- **Kredi kartı numarası** — Luhn doğrulamasıyla teyit edilir
- **E-posta adresi**

Maskeleme, güvenlik sayfasında **örnek PII ile çalıştırılarak** doğrulanır —
bir ayar bayrağı değil, gerçek bir test.

Ham (maskesiz) veriye erişim yalnızca yetkili rolde açılır ve **her açılış
denetim günlüğüne yazılır**.

## 3. Diskte şifreleme

Ses dosyaları ve transkriptler uygulama seviyesinde şifrelenebilir
(zarf şifreleme, HMAC bütünlük doğrulamalı).

**Ana anahtar `.env` dosyasında DEĞİLDİR.** `KG_MASTER_KEY` ortam değişkeninden
okunur ve ayrı bir secret kaynağında tutulmalıdır (Docker secret, systemd
`EnvironmentFile`, KMS/Vault).

Anahtar tanımlı değilse şifreleme **kapalıdır** ve güvenlik sayfası bunu açıkça
söyler. Sessizce düz metin yazıp "şifreli" demek yapılmaz.

## 4. Saklama süresi (retention)

Kurum bazında yapılandırılır (varsayılan 365 gün). Süresi dolan ses dosyaları
zamanlanmış görevle **otomatik silinir** ve silme işlemi günlüğe yazılır.

Güvenlik sayfası, süresi dolup hâlâ duran kayıt olup olmadığını **sayarak**
kontrol eder — temizlik görevi çalışmıyorsa fark edilir.

## 5. Erişim denetimi — rol matrisi

| Rol | Kendi çağrıları | Takım çağrıları | Tüm çağrılar | Ham PII | Rubrik | Kullanıcılar |
|---|---|---|---|---|---|---|
| **Temsilci** | ✅ okur | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Kalite uzmanı** | ✅ | ✅ | ✅ | ✅ (loglanır) | ✅ okur | ❌ |
| **Süpervizör** | ✅ | ✅ (kendi takımı) | ❌ | ✅ (loglanır) | ✅ okur | ❌ |
| **Yönetici** | ✅ | ✅ | ✅ | ✅ (loglanır) | ✅ yazar | ✅ |

Çok kiracılı kurulumda her sorgu `tenant_id` ile sınırlıdır; kiracı izolasyonu
güvenlik sayfasında sayılarak doğrulanır.

## 6. Aydınlatma yükümlülüğü

Aydınlatma Tebliği m.5/1 uyarınca yükümlülük **sözlü ortamda da** yerine
getirilebilir. Çağrı merkezinde aydınlatma sözlüdür: arama başında veya veri
alınmadan hemen önce kısa bilgilendirme yapılır; ses kaydı alınıyorsa bu
**açıkça** belirtilmelidir.

KaliteGöz bunu **iki ayrı kontrol** olarak ölçer ve **ayrı kanıt** ister:
1. Görüşmenin kayıt altına alındığı bildirildi mi?
2. Kişisel verilerin işlendiği bilgisi verildi mi?

Anonsun birebir aynı cümleyle yapılması beklenmez — **anlam kümesi** eşleşmesi
aranır. "Bu konuşma hizmet kalitesi için kaydediliyor" da geçerlidir.

Konuşmacı ayrımı yapılamayan kayıtlarda (mono, diarizasyon yok) sistem
**"ihlal" demez**, "yeterli kanıt yok" der ve insana yollar.

## 7. Denetim günlüğü

Append-only. Kaydedilenler: giriş, çağrı görüntüleme, ham PII açma, puan
düzeltme, durum geçişleri, rubrik değişikliği, itiraz sonucu.

Her kayıt: kim, ne zaman, hangi kayıt, hangi gerekçe kodu, IP.

## 8. Kurumun yapması gerekenler

1. `KG_MASTER_KEY` tanımla (en az 32 karakter, `.env` dışında)
2. SSO'yu yapılandır (`OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`)
3. Saklama süresini kurum politikasına göre ayarla
4. Üretimde: güçlü `JWT_SECRET`, gerçek `CORS_ORIGINS`, `DEMO_MODE=false`

Bu maddelerin durumu **Güvenlik sayfasında canlı olarak** görülür.
