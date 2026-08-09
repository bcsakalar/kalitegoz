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

**Ana anahtar `.env` dosyasında DEĞİLDİR.** Anahtar üç kaynaktan okunabilir;
öncelik sırası aşağıdadır ve bu sıra bilinçlidir:

| Öncelik | Kaynak | Ortam değişkeni | Ne zaman |
|---|---|---|---|
| 1 | **Dosya** | `KG_MASTER_KEY_FILE` | Üretim — Docker/K8s secret |
| 2 | Ortam değişkeni | `KG_MASTER_KEY` | Geliştirme, tek makine |
| 3 | — | (yok) | Şifreleme **kapalı** |

**Dosya, ortam değişkenini EZER.** Sebep: ortam değişkenleri `docker inspect`,
`/proc/<pid>/environ` ve çöken süreçlerin log'larında görünür; dosya ise dosya
sistemi izinleriyle (0400, uygulama kullanıcısına ait) korunur. Bir kurulum
yanlışlıkla ikisini birden tanımlarsa güvenli olan kazanır.

Anahtar tanımlı değilse şifreleme **kapalıdır** ve güvenlik sayfası bunu açıkça
söyler. Sessizce düz metin yazıp "şifreli" demek yapılmaz.

### 3.1 Anahtar rotasyonu

Anahtar değişince eski veriyi okuyamamak veri kaybıdır. Bu yüzden sistem bir
**rotasyon penceresi** destekler: yeni anahtarla yazar, eski anahtarlarla okur.

```
KG_MASTER_KEY_FILE=/run/secrets/kg_master_key        # AKTIF — yeni yazimlar
KG_MASTER_KEY_OLD_FILES=/run/secrets/kg_key_2025     # ESKI — yalniz okuma
KG_MASTER_KEY_ID=2026-08                             # denetim izi icin etiket
```

`KG_MASTER_KEY_OLD_FILES` virgülle ayrılmış birden çok dosya alabilir.
Çözme sırası: önce aktif anahtar, sonra eski anahtarlar sırayla. HMAC bütünlük
etiketi tutmayan anahtar denenmiş sayılır ve sıradakine geçilir — yanlış
anahtarla "başarıyla çözülmüş" bozuk veri üretilemez.

**Rotasyon prosedürü (kesintisiz):**

1. Yeni anahtar üret: `openssl rand -base64 48 > kg_key_yeni`
2. Eski anahtarı `KG_MASTER_KEY_OLD_FILES` listesine ekle
3. `KG_MASTER_KEY_FILE` → yeni dosyayı gösterecek şekilde değiştir
4. `KG_MASTER_KEY_ID` → yeni etiket (örn. `2026-08`)
5. Servisleri yeniden başlat. Bu andan sonra **yeni yazımlar** yeni anahtarla,
   **eski kayıtlar** eski anahtarla okunur — kesinti yok.
6. Yönetim → Güvenlik sayfasından `anahtar_kimligi` alanının yeni etikete
   döndüğünü doğrula.
7. (İsteğe bağlı) Eski kayıtları yeniden şifreleyen bakım görevi çalıştırıldıktan
   sonra eski anahtar listeden çıkarılabilir. Bu adım **atlanabilir**; eski
   anahtarı listede tutmak da geçerli bir işletme kararıdır.

Durum sorgusu: `GET /api/v1/enterprise/encryption/status` — aktif mi, kaynak
nedir (`dosya` / `ortam` / `yok`), anahtar kimliği ne, kaç eski anahtar tanımlı.
**Anahtarın kendisi hiçbir uçtan dönmez.**

### 3.2 Harici KMS / Vault entegrasyonu

Kurumsal ihalelerde "anahtar HSM/KMS'te durmalı" maddesi sık çıkar. Sistem bunu
**dosya arayüzü üzerinden** karşılar — uygulamaya KMS SDK'sı gömülü değildir ve
bu bilinçlidir: her müşterinin KMS'i farklıdır (AWS KMS, Azure Key Vault,
HashiCorp Vault, Thales HSM), hepsini uygulamaya gömmek bakım borcudur.

Entegrasyon deseni: **KMS'ten çekip dosyaya yaz, uygulama dosyayı okusun.**

| Ortam | Yöntem |
|---|---|
| **Kubernetes** | External Secrets Operator / Vault Agent Injector anahtarı `/run/secrets/`e mount eder |
| **Docker Swarm** | `docker secret create` → `/run/secrets/kg_master_key` |
| **AWS** | Secrets Manager + `sidecar` ya da `awscli` ile başlangıç betiğinde dosyaya yaz |
| **Azure** | Key Vault + CSI Secrets Store driver |
| **Vault** | `vault agent` template ile dosyaya render |

Uygulama açısından hepsi aynıdır: `KG_MASTER_KEY_FILE` bir dosyayı gösterir.
Anahtarın oraya nasıl geldiği **altyapının sorumluluğudur**, uygulamanın değil.
Bu sınır, KMS değiştiğinde uygulama kodunun değişmemesini sağlar.

**Anahtar bellekte tutulmaz:** her şifreleme/çözme işleminde dosya yeniden
okunur. Böylece KMS anahtarı döndürdüğünde uygulama yeniden başlatılmadan da
yeni anahtarı görebilir (dosya güncellenmişse).

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
