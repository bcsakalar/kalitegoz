# FAZ 1 RAPORU — Denetim ve Doğruluk Temeli

> Branch: `v2/faz-1-denetim` · Tarih: 2026-08-09
> Amaç: "Puanlama doğru mu?" sorusunun **sayısal** bir cevabının olması.
> Bu faz kod düzeltmez — ölçer.

---

## Ne değişti

### Yeni dokümanlar
| Dosya | İçerik |
|---|---|
| `docs/v2/00-MEVCUT-DURUM.md` | Mimari, 27 tablo veri modeli, puanlama akışının 18 adımlık izi, 10 ölü kod/hardcode bulgusu, 6 yeni hata (B27–B32) |
| `docs/v2/01-KOK-NEDEN.md` | B1–B6 + B32 için **ölçülmüş** kök nedenler; prompt dosyasının 6 kontrol sorusuna tek tek cevap |
| `docs/v2/SORULAR.md` | 5 iş kararı; hepsi varsayımla ilerledi, varsayımlar yazılı |
| `docs/v2/eval/2026-08-09-faz1-taban.json` | Taban çizgisi ölçümü (ham) |

### Yeni altın set — `data/golden/`, 50 senaryo
| Kova | Adet | İçerik |
|---|---|---|
| yuksek | 8 | eksiksiz açılış + KVKK + kimlik + çözüm + kapanış |
| orta | 8 | bir/iki belirgin eksik (kapanış yok, ihtiyaç analizi zayıf, kimlik geç…) |
| dusuk | 8 | ağır eksikler (açılış yok, empati yok, yanlış bilgi…) |
| sifirlayici | 6 | hakaret, KVKK anonsu yok, kimlik atlandı, yasak vaat, küfür, sahte kimlik |
| kriz | 4 | avukat, hakem heyeti, iptal tehdidi, sosyal medya |
| tuzak | 4 | kurum adı cümle ortasında, müşteri anlamıyor, müşteri küfrediyor, anons parçalı |
| ses_kalitesi | 2 | `[anlaşılmadı]` işaretli, ağır aksan |
| regresyon | 10 | **B1–B6 + B29, B30, B32 birebir vakalar** |

Her senaryo: `transcript.json` (konuşmacı etiketli, zaman damgalı) + `expected.json`
(10 kriter için uzman referans puanı, sıfırlama beklentisi, alarm listesi, kanıt cümlesi,
"ceza verilemez" kriter listesi, gerekçe notu). Sürüm kontrolünde.

### Yeni regresyon takımı
- `scripts/golden/` — yazarlık yardımcıları, üretici (tutarlılık denetimli), değerlendirici
- `make eval` / `make eval-baseline` — gerçek puanlama motorunu izole `__golden__`
  kiracısında koşar (gerçek veriyle karışmaz), metrikleri hesaplar, eşik ihlalinde
  çıkış kodu 1 döner
- `backend/tests/test_scoring_invariants.py` — B27, B28, B31 için 5 birim/entegrasyon
  testi, `xfail(strict=True)`
- CI'da altın set tutarlılık denetimi (senaryo sayısı, kova dolgunluğu, B1–B6 vaka varlığı)

### Tek kod düzeltmesi
`backend/app/services/scoring.py` — fonksiyon içi tekrarlanan `from . import knowledge`
importu, `knowledge` adını fonksiyon kapsamında yerele çevirip **RAG bağlamı çağrısını
her puanlamada `UnboundLocalError` ile düşürüyordu**. Hata `try/except` içinde yutulduğu
için sistem sessizce bilgi bankası olmadan puanlıyordu.

---

## Neden

### Altın set neden transkript seviyesinde?
Puanlama motorunun doğruluğunu ölçüyoruz. Ses hattını (Whisper + kanal ayrımı)
karıştırırsak sapmanın ne kadarının STT'den, ne kadarının yargıdan geldiğini ayıramayız
— bunlar ayrı düzeltilmesi gereken iki şey. Ayrıca §D'de ölçüldüğü gibi mevcut STT
hattı zaman damgalarını bozuyor; bozuk çıktıyı referans almak hatayı altın sete gömerdi.
Ses hattının doğruluğu FAZ 2'de ayrı bir diarizasyon regresyonuyla ölçülecek.

### Cohen's kappa neden 3 banda indirgendi?
Kappa ordinal 0-10 üzerinde anlamlı çalışmaz. Çağrı merkezi QA pratiğinde karar bantları
üçtür: **0-4 karşılanmadı · 5-7 kısmen · 8-10 karşılandı**. Kappa bu bantlar üzerinde
hesaplanıyor; ayrıca ham MAE ve tam isabet oranı da raporlanıyor.

### Regresyon vakaları neden `xfail(strict=True)`?
FAZ 1 DoD "B1–B6 vakaları şu an kırmızı" diyor, çalışma disiplini "testler yeşil olmalı"
diyor. `xfail(strict=True)` ikisini birden sağlar: test şu an başarısız (hata gerçek),
takım yeşil, ve FAZ 2'de düzeltme yapılınca test "beklenmedik şekilde geçti" diye
**takımı kırar** ve işaretçiyi kaldırmaya zorlar. Düzeltme sessizce atlanamaz.

### Git deposu neden şimdi kuruldu?
Proje versiyon kontrolü altında değildi (`git rev-parse` hata veriyordu). Prompt dosyası
faz başına branch + adım başına commit istiyor. Mevcut durum `0eb6ba2` olarak donduruldu.

---

## Kanıt

### Taban çizgisi — `make eval`, 50 senaryo, qwen2.5:7b-instruct

| Metrik | Taban | FAZ 2 hedefi | Durum |
|---|---|---|---|
| **Sıfırlayıcı ihlal yanlış-pozitif oranı** | **%38.5** | %0 | 🔴 en kritik |
| Sıfırlayıcı ihlal yanlış-negatif oranı | %18.2 | — | 🔴 |
| Kriter bazlı MAE (0-10) | 2.163 | ≤ 1.0 | 🔴 |
| Cohen's kappa (ortalama) | 0.322 | ≥ 0.75 | 🔴 |
| Tam isabet oranı | %21.4 | — | 🔴 |
| Bant isabet oranı | %60.2 | — | 🔴 |
| Kanıt doğrulanabilirlik | %56.1 | ≥ %95 | 🔴 |
| Tekrarlanabilirlik (std, 3 koşum) | 1.95 | ≤ 1.5 | 🔴 |
| Kanıtsız ceza ihlali | 4 | 0 | 🔴 |

**Sekiz metriğin sekizi de hedefin altında.** Bu, FAZ 1 için beklenen sonuç —
amaç düzeltmek değil, ölçmekti.

### Kriter bazlı kırılım

| Kriter | n | MAE | tam | bant | kappa | ort. sapma |
|---|---|---|---|---|---|---|
| KVKK / Aydinlatma | 49 | **3.429** | 0.306 | 0.571 | 0.317 | **−1.51** |
| Kimlik Dogrulama | 49 | **3.061** | 0.286 | 0.612 | 0.364 | **−1.51** |
| Yasakli Kelime / Uslup | 49 | **2.714** | 0.163 | 0.571 | **0.112** | **+2.71** |
| Acilis | 49 | 2.041 | 0.061 | 0.653 | 0.422 | −0.86 |
| Cozum / Yonlendirme | 49 | 1.918 | 0.204 | 0.571 | 0.286 | −0.16 |
| Script Uyumu | 49 | 1.898 | 0.082 | 0.653 | 0.420 | −0.18 |
| Aktif Dinleme | 49 | 1.878 | 0.224 | 0.612 | 0.310 | +0.29 |
| Ihtiyac Analizi | 49 | 1.673 | 0.265 | 0.592 | 0.354 | −0.49 |
| Kapanis | 49 | 1.551 | 0.306 | 0.612 | 0.380 | −0.25 |
| Bilgi Dogrulugu | 49 | 1.469 | 0.245 | 0.571 | 0.251 | +0.33 |

**Okunuşu — bu tablo FAZ 2'nin yol haritasıdır:**

1. **En kötü üç kriter, deterministik olarak çözülebilecek olanlar.** KVKK, Kimlik
   Doğrulama ve Açılış'ın hepsi "şu ifade geçti mi?" sorusudur. LLM'e sorulduğu için
   MAE 2-3.4 arasında. Katman A bu üçünü doğrudan kapatır.
2. **Sapmanın yönü kritere göre değişiyor.** KVKK ve Kimlik'te AI **cimri**
   (−1.51: uzmandan 1.5 puan düşük veriyor), Yasaklı Kelime'de **cömert**
   (+2.71: 2.7 puan yüksek veriyor). Yani tek bir "kalibrasyon kayması" yok;
   kriter bazlı düzeltme gerekiyor.
3. **Yasaklı Kelime / Uslup kappa 0.112** — rastlantıdan neredeyse ayırt edilemiyor.
   Bu kriter şu an fiilen ölçmüyor.
4. **Açılış tam isabet %6.1** — 49 senaryonun 3'ünde doğru puan. Bant isabeti %65
   olduğu için "yaklaşık doğru" ama hiç kesin değil.

### Regresyon vakalarının durumu (FAZ 1 DoD: kırmızı olmalı)

| Hata | Vaka | Sonuç | Durum |
|---|---|---|---|
| B1 | `reg-b1-acilis-tam` | Açılış **8/10** (kurum + isim ilk cümlede, 10 olmalıydı) | 🔴 |
| B2 | `reg-b2-kvkk-farkli-cumle` | 94.1, ihlal üretilmedi ✅ ama kanıt cümlesi tutmuyor | 🟡 kısmen |
| B3 | `reg-b3-musteri-kesiyor` | **SIFIRLANDI** — müşteri kesiyor, temsilci cezalandırıldı | 🔴 |
| B4 | `reg-b4-kesinlikle-haklisiniz` | 87.4, sıfırlanmadı ✅ (transkript seviyesinde tetiklenmedi) | 🟡 |
| B5 | `reg-b5-sifirlama-gerekceli` | Sıfırlandı ✅ ama **gerekçe DB'de saklı değil** | 🔴 |
| B6 | `reg-b6-ikiz-a/b` | 91.9 vs 86.7 → **fark 5.2** (hedef ≤5) | 🔴 |
| B29 | `reg-b29-konusmaci-bilinmiyor` | — | 🔴 |
| B30 | `reg-b30-uzun-cagri-orta-ihlal` | Sıfırlandı ✅ ama kanıt cümlesi tutmuyor | 🟡 |
| B32 | `reg-b32-kvkk-yok-sifirlanmali` | **91.9, sıfırlanmadı** — anons hiç yok | 🔴 |

### En çarpıcı tekil bulgular

**1. Sıfırlama hem yanlış yere basıyor hem gerçek ihlali kaçırıyor.**
15 senaryo haksız yere sıfırlandı; bunların arasında `tuzak-02-musteri-anlamiyor`
(temsilci örnek davranış sergiliyor), `tuzak-03-musteri-kufrediyor` (küfreden müşteri),
`kriz-01-avukat` (temsilci sakin ve çözüm odaklı) var. Aynı anda `dusuk-04-kvkk-yok` ve
`reg-b32` — KVKK anonsunun **hiç yapılmadığı** iki çağrı — 92.6 ve 91.9 alıp geçti.

**2. Kanıtların %43.9'u transkriptte bulunamıyor.** 490 puan satırının 215'inin
kanıtı, normalize edilmiş transkriptte 6 kelimelik pencere toleransıyla bile
aranıp bulunamadı. Yani sistemin gösterdiği "kanıt"ın neredeyse yarısı uydurma
veya çarpıtılmış.

**3. Belirtilen kanıt cümlesi 7 vakada tutmuyor.** `reg-b5` ve `sifir-05`'te
temsilci açıkça *"saçmalamayın"* / *"Salak mısınız"* diyor; sistem çağrıyı doğru
sıfırlıyor ama **gösterdiği kanıt o cümle değil**. Doğru karar, yanlış gerekçe —
kaliteci ekranında savunulamaz.

**4. Tekrarlanabilirlik ölçüldü.** Aynı senaryo 3 kez puanlandığında:
- `orta-01-kapanis-eksik`: 88.1 / 84.4 / 85.2 → **std 1.95, aralık 3.7**
- `reg-b1-acilis-tam`: 83.0 / 83.7 / 81.5 → std 1.12
- `yuksek-01-fatura-itiraz`: 91.9 / 91.1 / 90.4 → std 0.75

B6 artık tahmin değil ölçüm: `temperature=0.1` + tek dev prompt, aynı girdide
100 üzerinden 3.7 puanlık oynama üretiyor.

**5. B27 (tekrarlanan kriter) bu koşumda tetiklenmedi** — 50 senaryonun hiçbirinde
çift kriter üretilmedi. Hata canlı veride ölçülmüştü (çağrı #24); nadir ama gerçek.
Birim testle korunuyor.

### Sistem sağlığı (faz sonu koşulu)
| Kontrol | Sonuç |
|---|---|
| `docker compose up -d` | ✅ 7 servis, api healthy |
| `pytest -q` | ✅ 221 geçti + 5 xfail |
| `npx tsc --noEmit` | ✅ 0 hata |
| `python -m scripts.golden.build` | ✅ 50 senaryo, tutarlılık denetimi geçti |
| `make eval` | ✅ çalışıyor, rapor üretiyor, eşik kapısı işliyor |

---

## Bilinen açıklar / bir sonraki faza devreden

1. **`make eval` CI'da koşmuyor.** LLM gerektiriyor; GitHub Actions'ta Ollama yok.
   CI şu an yalnız senaryo tutarlılığını denetliyor. FAZ 2'de self-hosted runner
   veya nightly job olarak bağlanacak. Eşikler `evaluate.py:GATES`'te tanımlı ve
   `make eval` yerelde build'i kırıyor.
2. **Altın set STT hatalarını yakalamaz** (bilinçli sınır, S1). Ses hattı için ayrı
   diarizasyon regresyonu FAZ 2'de.
3. **B4 transkript seviyesinde tetiklenmedi.** Fuzzy yanlış pozitifi doğrudan
   `_match_in()` üzerinde kanıtlandı (4 denemenin 3'ü yanlış) ama altın set koşumunda
   `sifir-04`'ün terimi eşleşmediği için sıfırlama yolu tetiklenmedi. FAZ 2'de
   yasaklı kelime listesi altın set kiracısına da senkronlanacak.
4. **Uzman referans puanları tek kişinin (benim) yargısı.** IRR ölçülmedi.
   `SORULAR.md` S2'de Rio'nun gözden geçirmesi istenen 3 tartışmalı senaryo işaretli.
5. **Rubrik grupları 4C çerçevesine oturmuyor** (7 grup, 4'ü tek kriterlik) ve kriter
   adları ASCII. FAZ 2 (grup) ve FAZ 6 (Türkçe karakter) kapsamında.

---

## Rio'nun karar vermesi gereken şeyler

Hepsi `docs/v2/SORULAR.md`'de, hiçbiri beklemede değil — varsayımla ilerlendi:

1. **S2 — Altın setteki uzman puanları.** Bu, sistemin "doğru" saydığı şeydir.
   Özellikle 3 senaryo tartışmaya açık: `orta-03-kimlik-gec` (kimlik işlem sonrası
   soruldu — 4 mü 0 mı?), `orta-06-acilis-yarim` (kurum var isim yok — 6 mı 0 mı?),
   `dusuk-03-yanlis-bilgi` (yanlış bilgi sıfırlayıcı olmalı mı?).
2. **S3 — Sıfırlayıcı eşik 3/10.** FAZ 2'de altın set verisiyle ölçülerek ayarlanacak;
   Rio farklı bir politika isterse şimdi söylemeli.

---

## FAZ 1 DoD

- [x] `make eval` çalışıyor ve **taban çizgisi raporlandı** (8 metriğin 8'i hedefin altında)
- [x] Altın set ≥40 senaryo (**50**), `expected.json` dosyaları tam
- [x] B1–B6 için birebir regresyon vakası mevcut ve şu an **kırmızı**
- [x] `docs/v2/00-MEVCUT-DURUM.md` ve `01-KOK-NEDEN.md` yazıldı
- [x] Sistem ayakta, testler yeşil
