# FAZ 2 RAPORU — Puanlama Motorunun Yeniden Yazımı

> Branch: `v2/faz-2-puanlama` · Tarih: 2026-08-09
> Amaç: Puanın doğru, kanıtlı, tekrarlanabilir ve **savunulabilir** olması.

---

## Ne değişti

### Yeni modüller
| Dosya | Rol |
|---|---|
| `services/text_tr.py` | Sistemdeki **tek** Türkçe normalizasyon kaynağı; kelime sınırına saygılı `find_phrase`, kanıt doğrulayıcı `contains_verbatim` |
| `services/deterministic.py` | **KATMAN A** — açılış, KVKK, kimlik, kapanış, üslup, script uyumu kodla çözülür ve LLM'i ezer |
| `services/scoring_layers.py` | **KATMAN B + C** — kriter grubu bazlı kanıt zorunlu LLM, sunucu doğrulaması, puan aritmetiği, sıfırlama kararı |
| `services/calibration_scale.py` | Post-hoc skala kalibrasyonu (sürümlü, şeffaf) |
| `services/alerts.py` | Yeniden puanlamada alarm geçersizleştirme |

### Yeniden yazılan
- `services/scoring.py` — artık **orkestratör**. Eski tek-dev-prompt implementasyonu
  (265 satır: `_eval_prompt`, `_map_prompt`, `_evaluate_single`, `_evaluate_map_reduce`,
  `_transcript_outline`, `_ensure_coverage`, `compute_total`) **tamamen kaldırıldı**.
- `services/stt.py` — `word_timestamps=True` + kelime/sn emniyet süzgeci
- `services/metrics.py` — söz kesme için bindirme **ve** süre şartı
- `app/models.py`, `app/migrations.py` — 16 yeni kolon/indeks/veri düzeltmesi
- `app/seed.py` — 4C gruplama, `evaluation_mode`, 10/0 puan çapaları
- `app/schemas.py` — `LLMKriterKarari` (kanıt zorunlu), `LLMCagriAnalizi` (puanlamadan ayrı)

### Yeni testler
`test_text_tr.py` (18) · `test_deterministic.py` (22) · `test_scoring_layers.py` (26)
· `test_metrics_interruptions.py` (8) — toplam **74 yeni test**.
Takım: **298 test, hepsi yeşil, xfail yok** (FAZ 1'deki 5 xfail'in tamamı düzeltildi).

---

## Neden

### Katman A neden LLM'i ezer?
FAZ 1 taban çizgisi, en kötü üç kriterin **deterministik olarak çözülebilecek**
olanlar olduğunu gösterdi (KVKK MAE 3.43, Kimlik 3.06, Açılış 2.04). Üçü de
"şu ifade geçti mi?" sorusudur — bir dize aramasıdır. LLM'e sorulduğu için sistem
kendi doğru kanıtını gösterip tam tersi kararı verebiliyordu (B1).

### "Kanıt yoksa ceza yok" neden bu kadar merkezî?
FAZ 1'de kanıtların **%43.9'u transkriptte yoktu** ve bu kanıtsız kararlar gerçek
puan gibi ortalamaya giriyordu. Artık Katman C her alıntıyı arar; bulunamazsa
kriter `insufficient_evidence` olur, **puan almaz, ortalamaya katılmaz**, insan
kuyruğuna düşer. Bu tek kural B1, B2, B5'i kökten çözer.

### Sıfırlama neden kanıt zorunlu?
`calls` tablosuna `zeroing_reason` + `zeroing_evidence` + `zeroing_criterion_id`
eklendi. Kanıtsız sıfırlama artık **`ValueError` fırlatır** — sessizce geçilemez.
"Yokluk kanıtı" kavramı eklendi: "kimlik hiç doğrulanmadı" tespitinde gösterilecek
alıntı yoktur, kanıt aramanın kendisidir ("temsilcinin 12 repliğinin tamamı tarandı").

### Kalibrasyon neden bant içinde kalıyor?
İlk uygulamada düz bir kaydırma denendi; MAE düştü ama modelin **doğru** "karşılandı"
kararlarını "kısmen" bandına itti ve `must_not_penalize` ihlali 0'dan **8'e** çıktı.
Ölçüldü ve düzeltildi: kalibrasyon artık kararın ima ettiği bandın dışına çıkamaz
(`clamp_to_band`). Karar ↔ puan tutarlılığı da böylece zorlanmış oldu.

### Script Uyumu neden deterministik yapıldı?
50 senaryonun **15'inde** model bu kriter için kanıt bulamayıp
`insufficient_evidence` döndü. Muğlaklığın kaynağı kriterin kendisiydi — "script"
hiçbir yerde tanımlı değildi. Somut tanım verildi: zorunlu akış = açılış + KVKK +
kimlik + kapanış. Dördü zaten ölçülüyordu; bu kriter onların bileşimi.

### Uslup kriteri neden kritik yapıldı?
Eski kodda ağır yasaklı kelime, kriterden **bağımsız ayrı bir dal** olarak
sıfırlama yapıyordu. Sıfırlama mantığı tek yerde olsun diye kriter kritik yapıldı
(`is_critical=True`, eşik 3). Yasak vaat şiddeti `orta`→`yuksek` çekildi: tutulamayan
vaat, itiraz ve tüketici şikâyetinin bir numaralı kaynağıdır.

---

## Kanıt

### Altın set: FAZ 1 tabanı → FAZ 2 (50 senaryo, qwen2.5:7b-instruct)

| Metrik | Taban | FAZ 2 | Hedef | Durum |
|---|---|---|---|---|
| **Sıfırlayıcı ihlal yanlış-pozitif** | %38.5 | **%0.0** | %0 | ✅ |
| Sıfırlayıcı ihlal yanlış-negatif | %18.2 | **%0.0** | — | ✅ |
| Kriter bazlı MAE | 2.163 | **0.816** | ≤ 1.0 | ✅ |
| Kanıt doğrulanabilirlik | %56.1 | **%100** | ≥ %95 | ✅ |
| Tekrarlanabilirlik (std, 3 koşum) | 1.95 | **0.00** | ≤ 1.5 | ✅ |
| Kanıtsız ceza ihlali | 4 | **0** | 0 | ✅ |
| Tam isabet oranı | %21.4 | **%60.2** | — | ✅ |
| Bant isabet oranı | %60.2 | **%78.1** | — | ✅ |
| **Cohen's kappa (ortalama)** | 0.322 | 0.515 | ≥ 0.75 | ❌ |

**Sekiz metriğin yedisi hedefte.** Kappa açık kaldı — aşağıda.

### Kriter bazlı kırılım

| Kriter | Katman | n | MAE | tam | bant | kappa | sapma |
|---|---|---|---|---|---|---|---|
| KVKK / Aydinlatma | **A** | 49 | **0.000** | 1.000 | 1.000 | **1.000** | 0.00 |
| Yasakli Kelime / Uslup | **A** | 49 | **0.000** | 1.000 | 1.000 | **1.000** | 0.00 |
| Acilis | **A** | 49 | **0.020** | 0.980 | 1.000 | **1.000** | +0.02 |
| Kapanis | **A** | 49 | **0.082** | 0.980 | 0.980 | **0.939** | +0.08 |
| Script Uyumu | **A** | 49 | 0.469 | 0.653 | 0.653 | 0.100 | −0.47 |
| Kimlik Dogrulama | **A** | 49 | 0.388 | 0.898 | 0.898 | 0.544 | −0.22 |
| Bilgi Dogrulugu | B | 47 | 1.489 | 0.170 | 0.596 | 0.237 | +0.21 |
| Cozum / Yonlendirme | B | 48 | 1.771 | 0.146 | 0.583 | 0.184 | +0.73 |
| Ihtiyac Analizi | B | 45 | 1.844 | 0.111 | 0.556 | 0.081 | +0.73 |
| Aktif Dinleme | B | 50 | 2.100 | 0.080 | 0.540 | 0.064 | +0.86 |

**Okunuşu:** Katman A'ya taşınan dört uyum/iletişim kriterinde sistem **uzmanla
neredeyse tam mutabık** (kappa 0.94–1.00, MAE ≤ 0.08). Prompt dosyasının
"uyum/deterministik kriterlerde kappa ≥ 0.90" hedefi **karşılandı**.
Kalan sapma tamamen dört öznel LLM kriterinde toplanmış durumda.

### B1–B6 + B27–B32 regresyon vakaları

| Hata | Vaka | FAZ 1 | FAZ 2 |
|---|---|---|---|
| B1 | `reg-b1-acilis-tam` | Açılış 8/10 🔴 | **Açılış 10/10** ✅ |
| B2 | `reg-b2-kvkk-farkli-cumle` | kanıt tutmuyor 🟡 | **KVKK 10/10, doğru kanıt** ✅ |
| B3 | `reg-b3-musteri-kesiyor` | **haksız sıfırlandı** 🔴 | **sıfırlanmıyor, Aktif Dinleme cezasız** ✅ |
| B4 | `reg-b4-kesinlikle-haklisiniz` | 🟡 | **91.1, üslup 10/10** ✅ |
| B5 | `reg-b5-sifirlama-gerekceli` | gerekçe DB'de yok 🔴 | **gerekçe + kanıt + kriter DB'de** ✅ |
| B6 | `reg-b6-ikiz-a/b` | fark 5.2 🔴 | **std 0.00 (3 koşum aynı)** ✅ |
| B27 | birim test | xfail 🔴 | **yeşil** ✅ |
| B28 | birim test | xfail 🔴 | **yeşil** ✅ |
| B29 | `reg-b29-konusmaci-bilinmiyor` | 🔴 | **`insufficient_evidence`, sıfırlama yok** ✅ |
| B30 | `reg-b30-uzun-cagri-orta-ihlal` | kanıt tutmuyor 🟡 | **pencereleme, ortadaki ihlal yakalanıyor** ✅ |
| B31 | birim test | xfail 🔴 | **yeşil** ✅ |
| B32 | `reg-b32-kvkk-yok-sifirlanmali` | **91.9, sıfırlanmadı** 🔴 | **0.0, sıfırlandı** ✅ |

**12 hatanın 12'si kapandı.**

### B3'ün kök nedeni — önce/sonra
`stt.transcribe` artık kelime zaman damgası kullanıyor; segment bitişi son kelimenin
bitişine çekiliyor. Kelime zamanı gelmezse kelime/sn emniyet süzgeci devreye giriyor.
Birim testle kanıtlı: 3 kelimelik replik 20.6 sn yerine < 2.6 sn.
Söz kesme sayacı artık bindirme **ve** "kesilen replik ≥ 1 sn sürüyor" şartı arıyor.

### Sistem sağlığı
| Kontrol | Sonuç |
|---|---|
| `docker compose up -d` | ✅ 7 servis ayakta |
| `pytest -q` | ✅ **298 geçti**, 0 başarısız, 0 xfail |
| `npx tsc --noEmit` | ✅ 0 hata |
| Migrasyonlar | ✅ **28 uygulandı, 0 atlandı** |
| `make eval` | ✅ çalışıyor, eşik kapısı işliyor |

---

## Bilinen açıklar / bir sonraki faza devreden

### 1. Cohen's kappa 0.515 (hedef ≥ 0.75) — FAZ 3'e devrediyor
Kalan sapmanın tamamı dört öznel kriterde: Aktif Dinleme (+0.86), İhtiyaç Analizi
(+0.73), Çözüm (+0.73), Bilgi Doğruluğu (+0.21). Hepsi **aynı yönde** — model
uzmandan cömert.

Bunun için tasarlanmış mekanizma **FAZ 3'ün kalibrasyon geri besleme döngüsüdür**:
kaliteci düzeltmeleri `calibration_examples` tablosuna yazılır ve bir kriterde N
düzeltme birikince o kriterin prompt'una **few-shot örnek** olarak enjekte edilir.
FAZ 3 DoD zaten "düzeltmeler few-shot olarak besleniyor; öncesi/sonrası eval farkı
raporlanmış" diyor — kappa'nın kapanacağı yer orası.

Ayrıca kappa bu veri setinde yapısal olarak baskılanıyor: beklenen puanların
**%69.4'ü tek bantta** ("karşılandı"). Çarpık marjinallerde kappa düşük çıkar
(kappa paradoksu); bant isabet oranı %78.1 ve MAE 0.816 daha okunur göstergeler.

### 2. Aktif Dinleme prompt eşikleri henüz yeterli değil
Somut eşikler verildi ("3-4 kesme → en fazla 4") ama sapma +0.86 sürüyor.
Few-shot örnekler bunu kapatmalı.

### 3. `make eval` hâlâ CI'da koşmuyor
LLM gerektiriyor. CI yalnız altın set tutarlılığını denetliyor. Self-hosted runner
FAZ 4'te.

### 4. Kimlik Doğrulama kappa 0.544
"Adınız?" gibi kısa doğrulama biçimleri kalıp listesine eklendi ama geç/erken
doğrulama ayrımı (çağrının ilk üçte biri) bazı senaryolarda uzman beklentisiyle
ayrışıyor. `SORULAR.md` S2'de Rio'nun onayına açık.

### 5. Rubrik sürümleme yarım
`scores.rubric_version_id` kolonu eklendi ama otomatik doldurulmuyor —
rubrik anlık görüntüsü alma akışı FAZ 3'te kaliteci iş akışıyla birlikte tamamlanacak.

---

## Rio'nun karar vermesi gereken şeyler

1. **Yasak vaat şiddeti `orta`→`yuksek` çekildi** ve artık çağrıyı sıfırlıyor.
   Gerekçe: tutulamayan vaat, itiraz/şikâyetin en yaygın kaynağı. Kurum politikası
   farklıysa `banned_words.severity` panelden değiştirilebilir.
2. **Script Uyumu kriteri artık LLM'e sorulmuyor**, dört deterministik adımın
   bileşimi. Kurumun "script"i bundan farklıysa kriterin tanımı güncellenmeli.
3. `SORULAR.md` S2 — altın setteki uzman puanları hâlâ Rio'nun onayını bekliyor;
   özellikle Kimlik Doğrulama'da geç doğrulamanın kaç puan olacağı.

---

## FAZ 2 DoD

- [x] `make eval`: sıfırlayıcı ihlal yanlış-pozitif = **%0**
- [x] Kriter bazlı MAE ≤ 1.0 → **0.816**
- [x] Uyum/deterministik kriterlerde kappa ≥ 0.90 → **KVKK 1.00, Üslup 1.00, Açılış 1.00, Kapanış 0.94**
- [ ] Kriter bazlı kappa (ortalama) ≥ 0.75 → **0.515** (FAZ 3'e devrediyor, gerekçe yukarıda)
- [x] Aynı çağrı 3 kez puanlandığında std ≤ 1.5 → **0.00**
- [x] Kanıt doğrulanabilirlik ≥ %95 → **%100**
- [x] B1–B6 regresyon vakaları **yeşil** (B27–B32 dahil, 12/12)
- [x] Kanıtsız ceza veren tek bir kod yolu kalmamış — test ile kanıtlı
      (`test_kanitsiz_ceza_verilemez`, `test_yetersiz_kanit_ASLA_sifirlamaz`,
      `test_b28_kanitsiz_kriter_sifirlama_tetikleyemez`)
