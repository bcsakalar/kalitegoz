# FAZ 3 RAPORU — İki Aşamalı Kalite Kontrol ve Kalibrasyon

> Branch: `v2/faz-3-kalite-kontrol` · Tarih: 2026-08-09
> Amaç: Yapay zekâ puanlar, kaliteci doğrular. Her insan müdahalesi sistemi kalibre eder.

---

## Ne değişti

### Yeni modüller
| Dosya | Rol |
|---|---|
| `services/qa_workflow.py` | Durum makinesi + yedi insan-kuyruğu kuralı + denetim günlüğü |
| `services/review_feedback.py` | Kalibrasyon örnekleri, few-shot üretimi, overturn istatistiği |
| `api/review_queue.py` | Kaliteci inceleme kuyruğu ve tek-istekte-karar akışı |
| `scripts/golden/seed_calibration.py` | Eğitim/sınav bölünmesiyle kalibrasyon örneği üretimi |
| `scripts/golden/compare.py` | İki eval raporunu **aynı altkümede** karşılaştırma |

### Veri modeli
- `calls`: `qa_state`, `queue_reasons`, `finalized_at`, `finalized_by`
- `scores`: `override_reason_code`, `reviewed_at`, `reviewed_by`
- Yeni tablo: `calibration_examples`
- Yeni enum: `QAState`, `OverrideReasonCode`; `ReviewReason` 4 → 8 değere genişletildi

### Bağlantılar
- `pipeline._apply_outcome` → `qa_workflow.route_after_scoring`
- `api/workflow.py` itiraz uçları → durum makinesi (yeni uç **eklenmedi**, mevcut akış bağlandı)
- `api/supervisor.py` liderlik tablosu → **yalnızca `kesinlesti` puanlar**

### Yeni testler
`test_qa_workflow.py` (28) · `test_reliability_gate.py` (12) · `test_deterministic.py` +6
→ Takım: **334 test, hepsi yeşil**.

---

## Neden

### Durum makinesi neden `CallStatus`'tan ayrı?
`CallStatus` "ses çözüldü mü, puanlandı mı" sorusunu cevaplar. `QAState` ise
"bu puan geçerli mi, insan onayladı mı" sorusunu. İkisini tek alana sıkıştırmak,
işleme hatası ile onay bekleyen puanı aynı kovaya koymak olurdu.

### Kural 6 ve 7 neden tek çekilişte birleşti?
İlk uygulamada yeni temsilci oranı (%20), kiracının yapılandırdığı rastgele
oranın **yerine** geçiyordu. Kiracı %50 ayarlasa bile yeni temsilciler %20'ye
düşüyordu — yani "daha sıkı takip" ayarı, yeni temsilciyi **daha az** denetler
hale getiriyordu. Test bunu yakaladı (`test_yeni_temsilci_orani_kiraci_oranini_DUSURMEZ`).
Artık yeni temsilci kuralı oranı yalnızca **yükseltir**.

### Kaliteci ekranı neden tek istek?
Hedef "bir inceleme ≤ 2 dakika". Kriter başına ayrı istek, 10 kriterlik bir
çağrıda 10 tur demekti. `GET /review-queue/next` tam bağlamı (transkript +
kriter kartları + kanıt + kuyruk sebebi) tek seferde verir; `POST .../submit`
tüm kararları tek seferde alır ve **bir sonraki çağrıyı döner**.

### İtiraz uçları neden yeniden yazılmadı?
`api/workflow.py`'de eksiksiz bir itiraz akışı zaten vardı. Kendi kopyamı
yazmak, aynı yola iki handler koymak ve FAZ 1'de "çift implementasyon" diye
işaretlediğim hatayı tekrar üretmek olurdu. Mevcut akış durum makinesine bağlandı.

---

## Kanıt

### Durum makinesi ve kuyruk kuralları
28 test; yedi kuralın her biri ayrı ayrı doğrulandı:

| Kural | Test | Sonuç |
|---|---|---|
| 1. Sıfırlayıcı ihlal → her zaman | `test_kural1_...` | ✅ |
| 2. Kriz sinyali → her zaman | `test_kural2_...` | ✅ |
| 3. Güven < 0.70 / yetersiz kanıt | `test_kural3_...` ×2 | ✅ |
| 4. Alt %10 dilim (n≥20 şartıyla) | `test_kural4_...` ×2 | ✅ |
| 5. Duygu ↔ puan uyumsuzluğu | `test_kural5_...` | ✅ |
| 6. Rastgele örneklem | `test_kural6_...` ×2 | ✅ |
| 7. Yeni temsilci (oranı yükseltir) | `test_kural7_...` ×2 + regresyon | ✅ |

Geçersiz durum geçişi `InvalidTransition` fırlatır; her geçiş `audit_logs`'a
kim/ne zaman/hangi gerekçe ile yazılır.

### FAZ 3.4 — few-shot geri besleme döngüsü: **iddia ölçüldü, doğrulanmadı**

Yöntem: altın set ikiye bölündü (25 eğitim / 25 sınav). Eğitim yarısında AI ile
uzman referansı arasındaki farklardan **34 kalibrasyon örneği** üretildi (4/4
öznel kriterde few-shot aktif). Metrikler **yalnızca sınav yarısından** okundu —
örnek gören senaryolar ölçüme dahil edilmedi.

Aynı 25 senaryoda önce/sonra:

| Metrik | FAZ 2 | FAZ 3 (few-shot) | Değişim |
|---|---|---|---|
| Kriter MAE | 0.887 | 0.866 | −0.021 |
| Kappa ortalama | 0.492 | 0.499 | +0.007 |
| Bant isabet | 0.748 | 0.755 | +0.007 |

**Bu bir iyileşme değil, gürültü.** Mekanizma kuruldu, çalışıyor ve prompt'a
gerçekten örnek enjekte ediyor — ama sentetik olarak üretilmiş düzeltmeler
kappa'yı kapatmadı.

Nedeni ölçümden okunabiliyor: otomatik üretilen örnekler jenerik bir not
("AI çok cömert davrandı") ve kritere özgü olmayan bir transkript parçası
taşıyor. Gerçek bir kaliteci düzeltmesi *neden* yanlış olduğunu anlatır;
bu bilgi olmadan model dört örnekten genelleme yapamıyor.

### Aktif Dinleme deterministik tavanı — kısmen etkili
Ölçülmüş söz kesme sayısından tavan uygulandı (0 kesme→sınır yok, 2→7, 4→4, 5+→2).
`must_not_penalize` ihlali 1'den **0'a** indi. Kappa'yı taşımadı.

### En önemli bulgu — güvenilirlik kriter bazında ikiye ayrılıyor

| Kriter | Katman | kappa (sınav) | Değerlendirme |
|---|---|---|---|
| KVKK / Aydinlatma | A | **1.000** | güvenilir |
| Yasakli Kelime / Uslup | A | **1.000** | güvenilir |
| Acilis | A | **1.000** | güvenilir |
| Kapanis | A | **0.902** | güvenilir |
| Kimlik Dogrulama | A | 0.487 | sınırda |
| Bilgi Dogrulugu | B | 0.188 | **güvenilmez** |
| Script Uyumu | A | 0.190 | **güvenilmez** |
| Cozum / Yonlendirme | B | 0.122 | **güvenilmez** |
| Ihtiyac Analizi | B | 0.032 | **güvenilmez** |
| Aktif Dinleme | B | 0.033 | **güvenilmez** |

Dört öznel kriterde qwen2.5:7b'nin uzmanla uyumu rastlantıdan zor ayırt ediliyor.
Üç ayrı müdahale (few-shot, skala kalibrasyonu, deterministik tavan) bunu
taşımadı. Bu, model boyutunun ve kriterin doğasının sınırıdır.

### Sınırı ürün davranışına çevirdik
`calibration_scale.MEASURED_KAPPA` tablosu eklendi. Ölçülen kappa'sı 0.40'ın
altındaki kriterlerde AI'nin güven skoru **0.60 ile tavanlanır**. Kuyruk kuralı 3'ün
eşiği 0.70 olduğundan bu, o kriterleri içeren çağrının **insan incelemesine
düşmesini garanti eder** (`test_tavan_insan_incelemesini_GARANTI_eder`).

Prompt dosyasının "asla yapma" 10. maddesi: *"Yapay zekâ %100 doğru" iddiası
kurma.* Sistem artık neyi bilmediğini biliyor ve onu insana yolluyor.

### Sistem sağlığı
| Kontrol | Sonuç |
|---|---|
| `docker compose up -d` | ✅ 7 servis |
| `pytest -q` | ✅ **334 geçti**, 0 başarısız |
| `npx tsc --noEmit` | ✅ 0 hata |
| Migrasyonlar | ✅ 39 uygulandı, 0 atlandı |
| Sıfırlayıcı FP / FN | ✅ %0 / %0 (korundu) |
| Kanıt doğrulanabilirlik | ✅ %100 (korundu) |

---

## Bilinen açıklar / bir sonraki faza devreden

1. **Kappa ≥ 0.75 hedefi karşılanmadı (0.495).** Üç mekanizma denendi ve
   ölçüldü; taşımadı. Kapanma yolu ikiden biri:
   (a) öznel kriterleri `evaluation_mode='human_only'` yapmak — prompt dosyasının
       kendi önerisi ("öznel sorular insana işaretlensin"), kapsamı düşürür;
   (b) o kriterler için daha büyük model kullanmak (14B/32B veya bulut).
   Bu bir **iş kararıdır**, `SORULAR.md` S10'a yazıldı.
2. **Kaliteci ekranı UI'ı yok.** Backend hazır; ekran FAZ 5'te tasarlanacak
   (klavye kısayolları, kanıt→ses atlama, toplu onay).
3. **≤2 dakika hedefi ölçülmedi.** Ölçüm için gerçek kaliteci oturumu gerekiyor;
   `/review-queue/stats` altyapısı hazır, FAZ 5 sonrası ölçülecek.
4. **IRR (insan↔insan uyumu)** hesaplanmıyor. `calibration_sessions` ve
   `manual_evaluations` tabloları mevcut ama IRR raporu FAZ 4'e kaldı.
5. **Rubrik sürümleme yarım** (FAZ 2'den devir) — `scores.rubric_version_id`
   hâlâ otomatik doldurulmuyor.

---

## Rio'nun karar vermesi gereken şeyler

**S10 — Öznel kriterler AI tarafından puanlansın mı?** (`SORULAR.md`)
Ölçüm net: Aktif Dinleme, İhtiyaç Analizi, Çözüm/Yönlendirme ve Bilgi Doğruluğu'nda
7B modelin uzmanla uyumu düşük. Şu an varsayım: **puanlanıyor ama düşük güvenle
işaretlenip insana gönderiliyor.** Alternatif: hiç puanlanmasın (`human_only`).
Fark, "%100 kapsam" iddiasının ne kadarının AI'ya ait olacağıdır.

---

## FAZ 3 DoD

- [x] Durum makinesi uçtan uca çalışıyor, her geçiş denetim günlüğünde
- [ ] Kaliteci inceleme ekranı klavyeyle tam kullanılabilir → **backend hazır, UI FAZ 5'te**
- [ ] Bir çağrı ≤2 dakikada kapatılabiliyor → **ölçülmedi, UI sonrası**
- [x] Kalibrasyon oturumu oluşturulabiliyor, overturn hesaplanıyor
      (IRR + kappa raporu FAZ 4'e devir)
- [x] Düzeltmeler few-shot olarak prompt'a besleniyor; **öncesi/sonrası eval
      farkı raporlandı** (sonuç: anlamlı fark yok — dürüst kayıt)
- [x] İtiraz akışı uçtan uca çalışıyor ve durum makinesine bağlı
- [x] Onaylanmamış puanlar liderlik tablosunu kirletmiyor
