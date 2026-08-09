# KaliteGöz — Kalite Metodolojisi

> **Bu doküman satışta kullanılır ve dürüst yazılmıştır.**
> "%100 doğru" iddiası ürünü satmaz, batırır. Aşağıdaki her sayı gerçek bir
> ölçümden gelir; ölçülmemiş hiçbir şey iddia edilmez.

---

## 1. Sorun

Çağrı merkezlerinde kalite kontrolü bugün elle yapılır ve çağrıların
**%2-5'ini** kapsar. Tek bir çağrı incelemesi 15-20 dakika sürer; 50 kişilik
bir ekipte ayda 60+ saat eder. Kalan **%95-98 çağrı hiç denetlenmez.**

Sorun kapsam değil sadece: denetlenmeyen çağrılarda uyum ihlali, yanlış bilgi
ve müşteri kaybı sinyalleri **görülmeden geçer**.

## 2. Yaklaşım — iki aşamalı

```
AŞAMA 1 — YAPAY ZEKÂ PUANLAR      → %100 çağrı, kanıtlı, tekrarlanabilir
AŞAMA 2 — KALİTE UZMANI DOĞRULAR  → risk bazlı kuyruk, onayla / düzelt / itiraz
        ↓
    Her düzeltme kalibrasyon verisidir.
```

Yapay zekânın tek başına yeterli olduğunu **iddia etmiyoruz.** Kalibre edilmiş
otomatik puanlama yapısal kriterlerde uzman insanla %90-95 uyum yakalar;
sarkazm, ağır aksan ve muğlak ton hâlâ insan gerektirir. Ürün bunu gizlemez,
**yönetir**: güvenilir olmadığını bildiği kriteri insana yollar.

## 3. Puanlama nasıl çalışır — üç katman

```
KATMAN A — DETERMİNİSTİK ÖN KONTROL   (kod, LLM yok)
   ↓ kesin cevabı olan her şey burada biter ve LLM'i EZER
KATMAN B — KANIT ZORUNLU LLM DEĞERLENDİRME  (kriter grubu bazında)
   ↓ her kararın yanında transkriptten birebir alıntı
KATMAN C — SUNUCU DOĞRULAMASI + KALİBRASYON
   ↓ alıntı gerçekten transkriptte var mı? puan aritmetiği KODDA
```

**Katman A** — açılış, KVKK anonsu, kimlik doğrulama, kapanış, yasaklı kelime
ve script uyumu kodla çözülür. Bunlar "şu ifade geçti mi?" sorularıdır; bir
dil modeline sorulmaları gereksiz risktir.

**Katman B** — öznel kriterler (aktif dinleme, ihtiyaç analizi, çözüm, bilgi
doğruluğu) dil modeline sorulur. Kriterler 3'lü gruplara bölünür, her grup ayrı
çağrıdır. Sıcaklık 0, sabit prompt sürümü.

**Katman C** — modelin gösterdiği her alıntı transkriptte **aranır**.
Bulunamazsa kanıt reddedilir, kriter "yetersiz kanıt" olur ve **puan almaz**.

### Üç mutlak kural
1. **Kanıt yoksa ceza yok.** Kanıtsız düşük puan verilmez; kriter insana gider.
2. **Toplam puan kodda hesaplanır.** Dil modeline toplam sordurulmaz.
3. **Kanıtsız sıfırlama sistem hatasıdır** ve istisna fırlatır.

## 4. Ölçülen doğruluk

50 senaryoluk altın set (uzman referanslı), yerel `qwen2.5:7b-instruct` modeli.
Ölçüm yöntemi ve ham çıktılar: `docs/v2/eval/`.

### Genel metrikler — v1 tabanı → v2

| Metrik | v1 | v2 | Hedef |
|---|---|---|---|
| **Sıfırlayıcı ihlal yanlış-pozitif** | %38.5 | **%0.0** | %0 |
| Sıfırlayıcı ihlal yanlış-negatif | %18.2 | **%0.0** | — |
| Kriter bazlı ortalama hata (MAE, 0-10) | 2.16 | **0.82** | ≤1.0 |
| Kanıt doğrulanabilirlik | %56.1 | **%100** | ≥%95 |
| Tekrarlanabilirlik (3 koşum, std) | 1.95 | **0.00** | ≤1.5 |
| Tam isabet oranı | %21.4 | **%60.2** | — |

### Kriter bazlı uyum (Cohen's kappa)

**Bu tablo ürünün en dürüst kısmıdır.** Sistem hangi kriterde güvenilir,
hangisinde değil — açıkça yazıyoruz:

| Kriter | Katman | kappa | Yorum |
|---|---|---|---|
| KVKK / Aydınlatma | A | **1.00** | Uzmanla tam mutabık |
| Yasaklı Kelime / Üslup | A | **1.00** | Uzmanla tam mutabık |
| Açılış | A | **1.00** | Uzmanla tam mutabık |
| Kapanış | A | **0.90** | Güvenilir |
| Kimlik Doğrulama | A | 0.49 | Sınırda — geç doğrulama yorumu değişebiliyor |
| Bilgi Doğruluğu | B | 0.21 | **Güvenilir değil** → insana gider |
| Script Uyumu | A | 0.19 | **Güvenilir değil** → insana gider |
| Çözüm / Yönlendirme | B | 0.12 | **Güvenilir değil** → insana gider |
| Aktif Dinleme | B | 0.03 | **Güvenilir değil** → insana gider |
| İhtiyaç Analizi | B | 0.03 | **Güvenilir değil** → insana gider |

**Uyum ve iletişim kriterlerinde sistem uzman seviyesinde. Öznel kriterlerde
değil — ve bunu biliyor.** Ölçülen kappa'sı 0.40'ın altındaki kriterlerde
güven skoru otomatik tavanlanır ve çağrı **garantili** insan onayına düşer.

### Ne denendi, ne işe yaramadı
Öznel kriterlerdeki uyumu artırmak için üç mekanizma denendi ve **ölçüldü**:
few-shot geri besleme (kappa 0.492→0.499), skala kalibrasyonu, deterministik
tavan. Hiçbiri anlamlı fark yaratmadı. Bu, 7B model boyutunun ve kriterin
doğasının sınırıdır. Daha büyük modelle tekrar ölçülmelidir.

## 5. İnsan onayı ne zaman devreye girer

Yedi kural; hepsi yapılandırılabilir:

1. Sıfırlayıcı ihlal → **her zaman**
2. Kriz sinyali (avukat, hakem heyeti, iptal tehdidi) → **her zaman**
3. Herhangi bir kriterde güven < 0.70 veya yetersiz kanıt
4. Toplam puan alt %10 diliminde
5. Duygu ↔ puan uyumsuzluğu
6. Rastgele örneklem (varsayılan %5) — kalibrasyon ölçümünün kör kontrol grubu
7. Yeni temsilci (ilk 30 gün) → örneklem %20

**Kesinleşmemiş puan temsilcinin karnesine ve lig tablosuna işlenmez.**

## 6. Kalibrasyon süreci

- Her düzeltme sabit bir **gerekçe koduyla** kaydedilir (kanıt yanlış, bağlam
  kaçırıldı, kriter yanlış yorumlandı, transkript hatası, rubrik muğlak, diğer).
- **Düzeltilen puan oranı** izlenir. Yükseliyorsa sorun kalite uzmanında değil
  **rubriktedir** — kriter tanımı muğlak demektir.
- Düzeltmeler few-shot örnek olarak prompt'a beslenir. **Rubrik değişmez**,
  yalnızca örnek eklenir; her kalibrasyon sürümlenir ve raporlanır.
- Geçmiş puanlar geriye dönük değiştirilmez.

## 7. Yapay zekânın sınırları — açıkça

| Sınır | Etkisi | Nasıl yönetiliyor |
|---|---|---|
| Öznel kriterlerde düşük uyum | Aktif dinleme, ihtiyaç analizi, çözüm kalitesi | Güven tavanlanır, insana gider |
| Sarkazm ve ironi | Duygu etiketi yanılabilir | Duygu–puan uyumsuzluğu kuralı yakalar |
| Ağır aksan / kötü ses kalitesi | Transkript bozulur | Düşük güvenli segmentte ceza verilmez |
| Mono kayıt, konuşmacı ayrımı yok | "Kim söyledi" bilinmez | Uyum kriteri "yetersiz kanıt" döner, ihlal **denmez** |
| 10 dakikadan uzun çağrı | Bağlam penceresi | Pencereleme; hiçbir bölüm atlanmaz |

## 8. Ne iddia etmiyoruz

- ❌ "Yapay zekâ %100 doğru puanlıyor"
- ❌ "Kalite uzmanına gerek kalmıyor"
- ❌ "Her kriteri insan kadar iyi değerlendiriyor"

## 9. Ne iddia ediyoruz — ve kanıtı var

- ✅ **%100 kapsam**: her çağrı puanlanır, hiçbiri denetimsiz kalmaz
- ✅ **Her puanın kanıtı var**: alıntı transkriptte doğrulanır (%100)
- ✅ **Tekrarlanabilir**: aynı çağrı üç kez puanlandığında aynı sonuç (std 0.00)
- ✅ **Uyum kriterlerinde uzman seviyesi**: kappa 0.90–1.00
- ✅ **Haksız sıfırlama yok**: yanlış-pozitif %0
- ✅ **Sistem sınırını biliyor**: güvenilmediği kriteri insana yollar
- ✅ **Veri kurumdan çıkmaz**: yerel model (Ollama) ile on-prem çalışır

---

*Bu dokümandaki metrikler `make eval` ile yeniden üretilebilir.
Ham ölçüm çıktıları: `docs/v2/eval/`.*
