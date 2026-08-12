# Terim Sözlüğü

> **Kural: aynı kavrama iki isim verilmez.** Bir kullanıcı arayüzde "sıfırlayıcı
> ihlal" öğrendiyse, raporda "kritik ihlal", API'de "zeroing" görmemeli.
> Bu dosya tek doğru kaynaktır; yeni metin yazan buradan bakar.

---

## Puanlama

| Terim | Anlamı | Kullanılmayacak eşanlamlılar |
|---|---|---|
| **Kriter** | Rubrikteki tek bir değerlendirme maddesi | soru, madde, başlık |
| **Rubrik** | Kriterlerin bütünü, kurumun puanlama kartı | scorecard, karne (karne temsilciye ait) |
| **Ağırlık** | Bir kriterin toplam puandaki payı | katsayı, çarpan |
| **Sıfırlayıcı ihlal** | Kritik kriter eşiğin altında kalınca çağrı puanının 0 olması | kritik ihlal, zeroing, fatal error |
| **Eşik** | Kritik kriterin sıfırlamayı tetiklediği puan | limit, sınır değer |
| **Kanıt** | Puanın dayandığı, transkriptten birebir alıntı | referans, delil, gerekçe (gerekçe ayrı) |
| **Gerekçe** | Puanın nedenini anlatan tek cümle | açıklama, yorum |
| **Yetersiz kanıt** | Kriteri değerlendirecek kanıt bulunamadı; puan verilmedi | bilinmiyor, N/A, değerlendirilemedi |
| **Güven** | AI'nin kararına ne kadar emin olduğu (0–1) | olasılık, skor |

## İş akışı

| Terim | Anlamı | Kullanılmayacak |
|---|---|---|
| **Yapay zekâ puanladı** | Puan üretildi, henüz onaylanmadı | ai_scored, taslak |
| **İnsan kuyruğunda** | Kalite uzmanı onayı bekliyor | pending review, assigned |
| **Kesinleşti** | Puan geçerli; karneye ve lige sayılır | final, onaylandı |
| **İtiraz incelemede** | Temsilci itiraz etti, süpervizör bakıyor | appeal, dispute |
| **İnceleme kuyruğu** | Kalite uzmanının bugün bakacağı çağrılar | görev listesi, iş listesi |
| **Onayla** | AI puanının doğru olduğunu teyit etmek | kabul et, geç |
| **Düzelt** | AI puanını değiştirmek | override, ez, revize et |
| **Düzeltilen puan oranı** | İncelenen kriterlerin kaçının düzeltildiği | overturn oranı |

## Roller

| Terim | Anlamı |
|---|---|
| **Temsilci** | Çağrıyı yapan kişi (agent) |
| **Kalite uzmanı** | Puanları inceleyip onaylayan kişi (quality) — kısaca "kaliteci" |
| **Süpervizör** | Takım yöneticisi (supervisor) |
| **Yönetici** | Kurum yöneticisi (admin) |

## Analitik

| Terim | Anlamı | Kullanılmayacak |
|---|---|---|
| **Ekip karşılaştırması** | Takımların/kampanyaların yan yana kıyaslanması | kohort karşılaştırma |
| **Eğilim** | Zaman içindeki yön | trend |
| **Yeterli veri yok** | Metrik güvenilir hesaplanamıyor | veri yok, N/A, — |
| **Kapsam** | Puanlanan çağrıların yüzdesi | coverage, örnekleme |
| **Eğitim örneği olarak işaretle** | Bir çağrıyı kalibrasyon örneği yapmak | örnek işaretle, golden yap |

## Alarm

| Terim | Anlamı |
|---|---|
| **Kritik** | Sıfırlayıcı ihlal veya kriz — hemen bakılmalı |
| **Yüksek** | Ciddi ama acil değil |
| **Bilgi** | Bilgilendirme; rozet sayacına girmez |
| **Geçersiz işaretle** | "Bu alarm yanlış" demek — kalibrasyon sinyalidir |

---

## Asla kullanıcıya gösterilmeyecekler

Bunlar sistem içi kimliklerdir; arayüzde görünürlerse hata sayılır
(`scripts/tr_audit.py` denetler):

`assigned` · `in_review` · `completed` · `bare_name` · `zero=` · `yasak_vaat`
· `insufficient_evidence` · `not_met` · `partially_met` · `qa_state` ·
`rule_id` · `evidence_hash`

## Yazım kuralları

- **Cümle düzeni (Sentence case)** — "Çağrı yükle", "Kalite uzmanı onayı" ("Çağrı Yükle" değil)
- **Buton emir kipi ve eylemi birebir söyler** — "Kaydet" → bildirim "Kaydedildi"
- Bir eylem akış boyunca **aynı adı** taşır: "Düzelt" düğmesi "Düzeltildi" bildirimi üretir
- Puanlar her yerde **tek ondalık**: `89.6`, `0.0`
- Sayısal veri **tabular-nums** ile hizalı
- Hata mesajı: **ne oldu + ne yapmalı**. Özür yok, "bir şeyler ters gitti" yok
- Boş durum: **ne yok + neden + tek eylem**
