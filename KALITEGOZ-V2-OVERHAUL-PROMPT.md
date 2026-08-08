# KaliteGöz v2 — Uçtan Uca Overhaul Prompt

> **Kullanım:** Bu dosyayı projenin kök dizinine koy (`KALITEGOZ-V2-OVERHAUL-PROMPT.md`).
> Claude Code'a kısa bir mesajla referans ver, o bu dosyayı okuyup FAZ 1'den başlasın.
> Hazırlanma tarihi: 2026-08-08 · Hedef: satılabilir, güvenilir, gerçekçi puanlayan kurumsal QA platformu

---

## 0. ROL VE ÇALIŞMA KURALLARI

Sen aynı anda üç şapkayı takan kıdemli bir mühendissin:

1. **15 yıllık çağrı merkezi kalite yönetimi (QA) uzmanı** — scorecard tasarımı, kalibrasyon, IRR, koçluk döngüsü bilir.
2. **Kıdemli backend + ML mühendisi** — LLM-as-a-judge güvenilirliği, deterministik doğrulama, regresyon testi kurar.
3. **Ürün tasarımcısı** — kurumsal, veri-yoğun arayüzleri sade ve okunur hale getirir.

### Çalışma disiplini

- **Otonom çalış.** Teknik kararları kendin ver. TODO, placeholder, "ileride eklenecek", `mock` veri bırakma.
- **Soru sorabilirsin — ama sadece iş kararı için, sadece faz başında.** Örn: "sıfırlayıcı ihlal eşiği kaç olsun?", "kaliteci onayı zorunlu mu opsiyonel mi?". Teknik detay için soru sorma, en iyi pratiği uygula ve raporda gerekçesini yaz.
- **Her fazın sonunda dur.** Faz raporunu yaz (aşağıdaki formatta), kabul kriterlerini kanıtla, sonra bir sonraki faza geç.
- **Kod yazmadan önce oku.** Her fazın başında ilgili modülleri gerçekten oku; varsayımla değiştirme.
- **Kırma.** Her faz sonunda sistem `docker compose up -d` ile ayağa kalkmalı ve testler yeşil olmalı.
- **Git disiplini:** her faz kendi branch'inde (`v2/faz-1-denetim` …), her mantıksal adım ayrı commit, faz sonunda `main`'e merge.

### Faz raporu formatı (her fazın sonunda `docs/v2/FAZ-N-RAPOR.md`)

```
## Ne değişti
- (dosya bazında özet)
## Neden
- (karar gerekçeleri, alternatifler)
## Kanıt
- (test çıktıları, önce/sonra metrikleri, ekran görüntüsü yolları)
## Bilinen açıklar / bir sonraki faza devreden
## Rio'nun karar vermesi gereken şeyler
```

### Kullanılacak skill'ler (ZORUNLU)

Kurulu değilse kur, kurulu ise fazlarda belirtilen yerlerde **fiilen oku ve uygula**:

```bash
npx skills add anthropics/skills --skill frontend-design -a claude-code
npx skills add vercel-labs/agent-skills --skill vercel-react-best-practices -a claude-code
npx skills add vercel-labs/agent-skills --skill web-interface-guidelines -a claude-code
npx skills add nextlevelbuilder/ui-ux-pro-max-skill -a claude-code
# repo içeriğini görmek için:  npx skills add vercel-labs/agent-skills --list
```

| Skill | Nerede kullanılacak |
|---|---|
| `frontend-design` | FAZ 5 — görsel kimlik, tipografi, palet, tasarım dili |
| `ui-ux-pro-max` | FAZ 5 — bilgi mimarisi, akış, bileşen davranışı |
| `web-interface-guidelines` | FAZ 5 — erişilebilirlik, form, tablo, klavye, odak denetimi |
| `vercel-react-best-practices` | FAZ 5 — React/Next.js performans, waterfall, bundle |

Skill kurulumu başarısız olursa GitHub'dan `SKILL.md` dosyalarını `~/.claude/skills/` altına manuel kopyala. Skill'siz UI fazına **başlama**.

---

## 1. ÜRÜN HEDEFİ (bunu aklından çıkarma)

KaliteGöz, çağrı merkezlerinde bugün **elle ve çağrıların %2-5'i üzerinde** yapılan kalite kontrolü, **%100 kapsamda ve yapay zekâ ile** yapan bir platformdur.

Nihai hedef: kalite kontrolün tamamı yapay zekâda olsun. Ama **geçiş modeli iki aşamalıdır ve bu ürünün satış argümanıdır:**

```
AŞAMA 1 — YAPAY ZEKÂ PUANLAR      → %100 çağrı, kanıtlı, tekrarlanabilir
AŞAMA 2 — KALİTECİ DOĞRULAR       → risk bazlı kuyruk, onayla / düzelt / itiraz
        ↓
    Her düzeltme, kalibrasyon verisidir. Uyum oranı yükseldikçe insan örneklemi düşer.
```

Sektörde kabul gören gerçek: iyi kalibre edilmiş otomatik puanlama, yapısal kriterlerde uzman insan puanlayıcıyla **%90-95 uyum** yakalar; sarkazm, ağır aksan ve muğlak ton hâlâ insan gerektirir. Ürün bunu gizlemez, **yönetir**: düşük güvenli kriteri insana yollar.

Bu yüzden sistemin en kritik özelliği hız veya görsellik değil — **puanın doğru ve savunulabilir olmasıdır.** Yanlış puanlanan tek bir çağrı, bir çağrı merkezi müdürünün ürüne güvenini komple bitirir.

---

## 2. TESPİT EDİLEN SOMUT HATALAR (kanıtlı — hepsini düzelt)

Bunlar mevcut sistemin ekran görüntülerinden doğrulanmış gerçek hatalardır. FAZ 1'de her birini regresyon testine çevir.

### 2.1 Puanlama doğruluğu — KRİTİK

| # | Hata | Kanıt |
|---|---|---|
| B1 | **Açılış kriteri yanlış puanlandı.** `deniz.yildiz_sikayet_05_v2.wav` → "Acilis 6/10 — Temsilci kurum adını ve ismini vermedi" | Transkript 00:01: *"Netik iletişime hoş geldiniz, ben Mehmet."* — hem kurum hem isim var. Kriter 10/10 olmalıydı. |
| B2 | **KVKK alarmı yanlış üretildi.** "Uyum ihlali (KVKK — eksik zorunlu açıklama): Görüşmenin kayıt altına alındığı bildirilmeli" | Transkript 00:04: *"Görüşmemiz kayıt altına alınmaktadır ve verileriniz KVKK kapsamında işlem etmektedir."* — anons yapılmış. |
| B3 | **Sinyal-kriter uyumsuzluğu.** "Aktif Dinleme 6/10 — Müşteriyi kesme ve tekrar sorma durumları var" | Aynı sayfada "Söz kesme: 4, **müşteri: 4**" yazıyor — yani sözü kesen müşteri, temsilci değil. Temsilci cezalandırılmış. |
| B4 | **Alarm metin şablonu bozuk.** "Yasakli kelime (yasak_vaat): 'kesin çözülür' — Kesinlikle daha avantajlı." | Tespit edilen ifade ile gösterilen alıntı birbirini tutmuyor. |
| B5 | **Kanıtsız sıfırlayıcı ihlal.** Puanı `0.0` olan çağrılar (`zeynep.demir_sikayet_09`, `pelin.acar_sikayet_09`) listede sadece "Tamamlandı" görünüyor; neden sıfırlandığı listeden anlaşılmıyor. | Çağrılar listesi + Temsilciler tablosu (`pelin.acar 0.0`) |
| B6 | **Aynı çağrı ~%100 benzer eşleşiyor ama puanları uçuk farklı.** `deniz.yildiz_sikayet_05` (89.6) ile `mehmet.kaya_sikayet_05` (%98 benzer) → 81.9; `pelin.acar_sikayet_09` ↔ `zeynep.demir_sikayet_09` → ikisi de 0. | "Benzer çağrılar" paneli. Aynı senaryonun farklı puan alması = puanlama kararsızlığı (judge instability). |

### 2.2 Analitik / veri doğruluğu

| # | Hata | Kanıt |
|---|---|---|
| B7 | **Liderlik tablosu sıralaması bozuk.** 1: 94.1, 2: 90.4, 3: **88.9**, 4: **90.4**, 5: 89.6 | Kokpit → Ekip liderlik tablosu. Sıralama anahtarı yanlış. |
| B8 | **İstatistiksel olarak savunulamaz korelasyon iddiası.** n=24 ile "+0.68 Konuşma hızı arttıkça puan yükseliyor (güçlü ilişki)" | Kokpit. n<30'da Pearson gösterilmemeli veya güven aralığı + net uyarı ile gösterilmeli. |
| B9 | **Anlamsız VoC trendi.** Tüm konular "Son: N / Önceki: 0 / Değişim: ▲+100%" | Analitik. Önceki dönem verisi yokken yüzde değişim üretilmemeli → "karşılaştırma için yeterli geçmiş yok" durumu gösterilmeli. |
| B10 | **Boş grafik render ediliyor.** "Ortalama puan" zaman serisi bomboş çiziliyor. | Analitik. Tek veri noktasında çizgi grafik yerine tekil değer + açıklama gösterilmeli. |
| B11 | **Kategori/etiket iki kere sayılıyor.** `fatura` hem kategori (8) hem `fatura-itiraz` etiketi (6); `ariza` hem kategori (8) hem etiket (2). | Analitik → VoC tablosu. İki farklı taksonomi tek tabloda karışmış. |
| B12 | **Alarm tekrarları (deduplication yok).** #18 için 4 alarm, #13/#12/#11 için aynı KVKK alarmı ikişer kez. Rozet "22" ama çoğu kopya. | Görevler → Alarmlar |
| B13 | **Koçluk etkinliği paneli tamamen sıfır ve anlamsız.** "0 ölçülebilir koçluk / %0 iyileşme / Veri yok" | Kokpit |
| B14 | **ROI hesaplayıcı sonuç üretmiyor.** "Hesapla" butonunun altında sonuç alanı yok. | ROI / Getiri sayfası |

### 2.3 Dil / metin / son kullanıcı deneyimi

| # | Hata | Kanıt |
|---|---|---|
| B15 | **Rubrik kriter isimleri Türkçe karaktersiz.** "Acilis", "Kapanis", "Bilgi Dogrulugu", "Kimlik Dogrulama", "Cozum / Yonlendirme", "Yasakli Kelime / Uslup", "Ihtiyac Analizi" | Rubrik editörü + kriter kırılımı + karne |
| B16 | **Alarm ve koçluk metinleri de ASCII.** "Temsilci agir yasakli ifade kullandi", "Bu donem en zayif alanin 'Aktif Dinleme'... Onumuzdeki hafta bu kritere odaklan" | Görevler, Temsilci karnesi |
| B17 | **Geliştirici jargonu son kullanıcıya sızıyor.** `(bare_name)`, `zero=`, `assigned / in_review / completed`, `yasak_vaat`, `Strateji` alanı boş etiketli | Çağrı detay, QA kuyruğu, alarmlar |
| B18 | **Asistan sayfası ham ve İngilizce.** "Choose File / No file chosen", model adı `ollama · llama3.2-vision:11b` kullanıcıya çıplak gösteriliyor. | Asistan |
| B19 | **Tutarsız boş durum metinleri.** "Veri yok", "Yeterli veri yok", "Kayda değer bir artış yok", "Bu dönemde itiraz yok", "Henüz kayıtlı versiyon yok" — beş farklı ton, hiçbiri kullanıcıya ne yapacağını söylemiyor. | Kokpit, Analitik, Rubrik |
| B20 | **Rubrik editöründe açıklamasız kontroller.** "Ağırlık 1.5", "Eşik 3", boş bir dropdown, "Kritik (sıfırlayıcı)" — puana etkisi hiçbir yerde anlatılmıyor. | Rubrik editörü |

### 2.4 Arayüz / bilgi mimarisi

| # | Hata | Kanıt |
|---|---|---|
| B21 | **14 maddelik düz sidebar.** Çağrılar, Arama, Kokpit, Analitik, Asistan, Temsilciler, Lig, Görevler, Kalibrasyon, Rubrik, ROI, Güvenlik, Yönetim — gruplama yok, rol ayrımı yok. | Tüm sayfalar |
| B22 | **Gürültülü tablo.** "Sesli" kanal rozeti 24 satırda 24 kez tekrar; tarih 24 satırda neredeyse aynı; `_v2.wav` gibi dosya adları birincil kimlik olarak kullanılıyor. | Çağrılar |
| B23 | **Arama sayfası boş bir kutudan ibaret.** Sonuç alanı, son aramalar, boş durum yok. | Arama |
| B24 | **Yönetim'de 10 sekme tek satırda taşıyor**, "Demo & Bakım" alt satıra kayıyor. | Yönetim |
| B25 | **Güvenlik sayfası statik görünüyor** ve satışta zarar veren iki kırmızı var: "Tek oturum açma (SSO)" ve "Diskte şifreleme" kapalı. | Güvenlik |
| B26 | **Çağrı detayında en kritik iş akışı gömülü.** "Puanı düzelt (kalibrasyon)" butonu 8 kartın içine dağılmış; kaliteci onay akışı yok. | Çağrı detay |

---

## FAZ 1 — DENETİM VE DOĞRULUK TEMELİ

**Amaç:** Neyin bozuk olduğunu tahmin etmeyi bırakıp ölçmek. Bu fazdan sonra "puanlama doğru mu?" sorusunun sayısal bir cevabı olacak.

### 1.1 Kod ve veri denetimi
- Tüm repoyu gez: `backend/`, `frontend/`, `data/`, `scripts/`, `docker-compose.yml`, `.env.example`.
- `docs/v2/00-MEVCUT-DURUM.md` üret: mimari şeması, veri modeli (tablolar + ilişkiler), puanlama akışının adım adım izi (audio → STT → normalize → kriter → puan → alarm → DB), her adımda hangi dosya/fonksiyon.
- Ölü kod, kullanılmayan endpoint, çift implementasyon, hardcode değer listesi çıkar.

### 1.2 Altın set (golden set) — bu fazın kalbi
- `data/golden/` altında **en az 40 çağrı senaryosu** oluştur (mevcut demo üretecini kullan, gerekirse genişlet):
  - 8 temiz/yüksek puanlı, 8 orta, 8 düşük
  - 6 sıfırlayıcı ihlal içeren (hakaret, KVKK anonsu yok, kimlik doğrulama atlanmış, yasak vaat)
  - 4 kriz çağrısı (avukat/tüketici hakem heyeti tehdidi, iptal tehdidi)
  - 4 tuzak senaryo: **anons var ama farklı cümleyle**, kurum adı var ama cümle ortasında, müşteri sözü kesiyor (temsilci değil), temsilci doğru bilgi veriyor ama müşteri anlamıyor
  - 2 kötü ses kalitesi / ağır aksan
- Her senaryo için `expected.json`: kriter bazında **beklenen puan (uzman referansı)**, beklenen sıfırlayıcı ihlal var/yok, beklenen alarm listesi, beklenen kanıt cümlesi.
- Bölüm 2'deki B1–B6 hatalarının **her biri** için birebir bir golden vaka yaz. Bu vakalar bir daha asla geçmemeli.

### 1.3 Regresyon koşum takımı
- `make eval` komutu: golden set'i uçtan uca işler ve rapor basar.
- Ölçülecek metrikler:
  - **Kriter bazlı MAE** (0-10 ölçek) ve **tam isabet oranı**
  - **Cohen's kappa** (AI vs uzman referansı) — kriter bazında
  - **Sıfırlayıcı ihlal yanlış-pozitif oranı** (en kritik metrik — hedef %0)
  - **Sıfırlayıcı ihlal yanlış-negatif oranı**
  - **Kanıt doğrulanabilirlik oranı** (aşağıda tanımlı)
  - **Tekrarlanabilirlik:** aynı çağrı 3 kez puanlanır, puan standart sapması (hedef ≤ 1.5 puan / 100)
- `make eval` çıktısını `docs/v2/eval/YYYY-MM-DD.json` olarak sakla; fazlar arası karşılaştırma yapılabilsin.
- CI'a bağla: golden set metrikleri düşerse build kırılır.

### 1.4 Kök neden analizi
B1–B6 için gerçek kök nedeni bul ve `docs/v2/01-KOK-NEDEN.md`'ye yaz. Şunları özellikle kontrol et:
- LLM'e giden prompt'ta transkriptin **tamamı** var mı, kırpılıyor mu? Token limiti aşılıyor mu?
- Transkript LLM'e hangi formatta gidiyor — konuşmacı etiketleri doğru mu, zaman damgaları var mı?
- Kriter değerlendirmesi tek bir dev prompt'ta mı yapılıyor? (Öyleyse kriter sayısı arttıkça bozulur.)
- STT çıktısı normalize ediliyor mu — Türkçe karakter, büyük/küçük harf (`i/İ/ı/I` tuzağı), noktalama?
- Sıcaklık (temperature) kaç? Deterministik mi?
- Akustik sinyaller (söz kesme vb.) puanlamaya hangi mantıkla giriyor — kim kesti bilgisi taşınıyor mu?

### Kabul kriterleri (FAZ 1 DoD)
- [ ] `make eval` çalışıyor ve mevcut sistemin **taban çizgisi** raporlanmış (kötü olması normal — ölçülmüş olması yeterli)
- [ ] Golden set ≥40 senaryo, `expected.json` dosyaları tam
- [ ] B1–B6 için birebir regresyon vakası mevcut ve şu an **kırmızı**
- [ ] `docs/v2/00-MEVCUT-DURUM.md` ve `01-KOK-NEDEN.md` yazılmış

---

## FAZ 2 — PUANLAMA MOTORUNUN YENİDEN YAZIMI

**Amaç:** Puanın doğru, kanıtlı, tekrarlanabilir ve savunulabilir olması. Bu faz projenin en önemli fazı.

### 2.1 Mimari: üç katmanlı hibrit puanlama

Tek bir LLM çağrısına "şu çağrıyı puanla" demek yanlış. Katmanlı yap:

```
KATMAN A — DETERMİNİSTİK ÖN KONTROL   (kod, LLM yok)
   ↓ kesin cevabı olan her şey burada biter
KATMAN B — KANIT ZORUNLU LLM DEĞERLENDİRME  (kriter grubu bazında, ayrı çağrılar)
   ↓ her kararın yanında transkriptten birebir alıntı
KATMAN C — SUNUCU TARAFI DOĞRULAMA + KALİBRASYON
   ↓ alıntı gerçekten transkriptte var mı? puan skalası hizalı mı?
```

**Katman A — Deterministik kontroller.** Şu kriterler LLM'e sorulmadan, kodla çözülür:
- **Açılış / kurum tanıtımı:** tenant'ın marka adları listesi (`Netik`, `Netik İletişim`, …) + temsilcinin adı ilk N saniyedeki temsilci repliklerinde geçiyor mu? Türkçe normalizasyon zorunlu (küçük harf dönüşümünde `İ→i`, `I→ı`; aksan/noktalama temizliği; ASCII-fold **karşılaştırma için**, gösterimde asla).
- **KVKK aydınlatma anonsu:** "kayıt altına alın-", "kaydedilmekte", "KVKK", "kişisel veri" gibi **anlam grupları** — tek kalıp değil, eşanlamlı kalıp kümesi. Sadece kelime eşleşmesi değil, ilk N saniye + temsilci konuşmacısı kısıtıyla.
- **Kimlik doğrulama:** ad-soyad + müşteri/hizmet no talebi kalıpları.
- **Kapanış:** "başka bir konuda yardımcı" + veda kalıbı.
- **Yasaklı kelime / yasak vaat:** kelime listesi + regex, **kelime sınırı** ve Türkçe ek toleransı ile. Eşleşen ifadenin **tam alıntısı ve zaman damgası** zorunlu (B4'ü bu çözer).
- **Söz kesme / sessizlik / konuşma hızı:** kim kesti bilgisi taşınmalı. `interruptions.by_agent` ve `interruptions.by_customer` ayrı alanlar; **sadece `by_agent` aktif dinleme kriterini etkiler** (B3'ü bu çözer).

Her deterministik kontrol, LLM'in kararını **ezer** (override). LLM "kurum adı söylenmedi" dese bile Katman A "söylendi, işte alıntısı" diyorsa, sonuç Katman A'nındır.

**Katman B — Kanıt zorunlu LLM değerlendirme.**
- Kriterleri **3-4 kriterlik gruplara böl**, her grup ayrı LLM çağrısı. Tek dev prompt yok.
- Her kriter için zorunlu JSON şeması (structured output / json schema ile zorla):
  ```json
  {
    "criterion_id": "aktif_dinleme",
    "decision": "met | partially_met | not_met | not_applicable | insufficient_evidence",
    "score": 0-10,
    "evidence": [
      { "speaker": "agent|customer", "start_sec": 35, "quote": "transkriptten BİREBİR alıntı" }
    ],
    "rationale_tr": "tek cümle, son kullanıcı diliyle",
    "confidence": 0.0-1.0
  }
  ```
- **Altın kural:** Kanıt yoksa ceza yok. `evidence` boşsa veya alıntı doğrulanamıyorsa, kriter **düşük puan almaz** — `insufficient_evidence` olur ve insan kuyruğuna düşer. Bu kural B1, B2, B5'i kökten çözer.
- Bias önlemleri (literatürde ölçülmüş, uygula):
  - `temperature=0`, sabit `seed`, sabit prompt sürümü
  - Kriterleri prompt'ta **azalan puan sırasıyla** ve **harf/roma rakamı ID** ile sun (sayısal sıra bias yaratıyor)
  - Uzunluk bias'ına karşı: uzun çağrı ≠ iyi çağrı; prompt'ta açıkça belirt
  - **Sıfırlayıcı ihlal ve kriz kriterlerinde self-consistency:** aynı kriter 3 kez çalıştırılır, çoğunluk kararı alınır, ihtilaf varsa insan kuyruğuna
- Transkript LLM'e her zaman **tam**, konuşmacı etiketli ve zaman damgalı gider. Uzun çağrılarda kırpma yerine pencereleme (windowing) + kriter bazlı ilgili pencere seçimi.
- STT güven skoru düşük segmentler prompt'ta `[düşük ses kalitesi]` olarak işaretlenir; LLM bu segmentlere dayanarak ceza veremez.

**Katman C — Sunucu doğrulaması.**
- Her `quote` alanı, normalize edilmiş transkript içinde **gerçekten aranır**. Bulunamazsa kanıt reddedilir, kriter `insufficient_evidence` olur ve `evidence_verification_failed` bayrağı loglanır.
- Puan hesabı **kodda** yapılır, LLM'e toplam puan sordurulmaz: `toplam = Σ(kriter_puanı × ağırlık) / Σ(ağırlık) × 10`.
- Sıfırlayıcı ihlal mantığı tek yerde: kritik kriter eşiğin altındaysa `final_score = 0`, `zeroing_reason` + `zeroing_evidence` **zorunlu** doldurulur. Kanıtsız sıfırlama sistem hatası olarak fırlatılır.
- Post-hoc kalibrasyon: golden set'ten öğrenilen basit skala hizalama (izotonik/lineer) uygulanır, `calibration_version` kaydedilir.

### 2.2 Rubrik yönetimi
- **Rubrik sürümlenir ve kilitlenir.** Her puanlama kaydı `rubric_version_id` taşır. Rubrik değiştiğinde eski puanlar değişmez; istenirse "yeni rubrikle yeniden puanla" ayrı bir işlemdir.
- Rubrik kriter sayısı **8-15 arasında** tutulmalı (sektör pratiği; 30 kriterli scorecard ne tutarlı puanlanır ne koçlukta kullanılır). Mevcut rubriği bu aralığa çek, gerekçesini yaz.
- Kategori dengesi 4C çerçevesine oturtulsun: **Uyum (Compliance) / İletişim / Yetkinlik / Müşteri Odağı**. Her kriter tam bir kategoriye ait olsun.
- Her kriter tanımı üç parça içermeli: **ne ölçülüyor**, **10 puan neye benzer**, **0 puan neye benzer**. Muğlak sıfat yasak ("iyi", "yeterli", "profesyonel").
- Her kriter `evaluation_mode` alanı taşır: `deterministic` | `llm_evidence` | `human_only`. Öznel kriterler (`insan_only`) AI tarafından puanlanmaz, direkt kaliteciye gider.

### 2.3 Türkçe metin işleme temeli
- Tek bir `normalize_tr()` yardımcı fonksiyonu: Türkçe'ye özel küçük harf dönüşümü, noktalama temizliği, çoklu boşluk, sayı/telefon maskeleme.
- Karşılaştırma normalize metin üzerinde, **gösterim her zaman orijinal metin üzerinde**. Kullanıcıya asla ASCII'ye düşürülmüş metin gösterilmez.
- Kelime listeleri (yasaklı kelime, zorunlu ifade) hem düz hem normalize halde saklanır.

### Kabul kriterleri (FAZ 2 DoD)
- [ ] `make eval` sonuçları: **sıfırlayıcı ihlal yanlış-pozitif = %0**
- [ ] Kriter bazlı Cohen's kappa ≥ 0.75 (uyum/deterministik kriterlerde ≥ 0.90)
- [ ] Kriter bazlı MAE ≤ 1.0 (0-10 ölçeğinde)
- [ ] Aynı çağrı 3 kez puanlandığında toplam puan std sapması ≤ 1.5
- [ ] Kanıt doğrulanabilirlik oranı ≥ %95
- [ ] B1–B6 regresyon vakaları **yeşil**
- [ ] Kanıtsız ceza veren tek bir kod yolu kalmamış (test ile kanıtla)

---

## FAZ 3 — İKİ AŞAMALI KALİTE KONTROL VE KALİBRASYON

**Amaç:** Yapay zekâ puanlar, kaliteci doğrular. Her insan müdahalesi sistemi kalibre eder.

### 3.1 Durum makinesi
```
yuklendi → isleniyor → ai_puanlandi
                          ├─ (risk kuralı tetiklenmedi) → kesinlesti
                          └─ (risk kuralı tetiklendi)   → insan_kuyrugunda
                                                              ├─ onaylandi        → kesinlesti
                                                              ├─ duzeltildi       → kesinlesti
                                                              └─ temsilci_itirazi → itiraz_incelemede → kesinlesti
```
- `kesinlesti` olmayan puan, temsilci karnesinde ve liderlik tablosunda **ham puan olarak sayılmaz** (ayrı gösterilir: "onay bekliyor").
- Her durum geçişi denetim günlüğüne yazılır: kim, ne zaman, hangi gerekçe kodu.

### 3.2 İnsan kuyruğuna düşme kuralları (yapılandırılabilir, varsayılanlar)
1. Sıfırlayıcı ihlal tespit edildi → **her zaman** insan onayı
2. Kriz sinyali (avukat, tüketici hakem heyeti, iptal tehdidi) → her zaman
3. Herhangi bir kriterde `confidence < 0.70` veya `insufficient_evidence`
4. Toplam puan alt %10 diliminde
5. Duygu ↔ puan uyumsuzluğu (müşteri öfkeli ama puan yüksek)
6. Rastgele örneklem (varsayılan %5) — bu, kalibrasyon ölçümünün kör kontrol grubudur
7. Yeni temsilci (ilk 30 gün) → örneklem oranı %20

### 3.3 Kaliteci inceleme ekranı (iş akışının kalbi)
Tek ekranda, sekme değiştirmeden:
- Solda: ses oynatıcı + zaman damgalı transkript (kriter kanıtına tıklayınca ses o saniyeye atlar)
- Sağda: kriter kartları — AI puanı, AI kanıtı, AI güven skoru, gerekçesi
- Her kriterde tek tıkla: **Onayla** / **Düzelt** (yeni puan + gerekçe kodu + serbest not)
- Gerekçe kodları sabit liste: `kanit_yanlis`, `baglam_kacirildi`, `kriter_yanlis_yorumlandi`, `stt_hatasi`, `rubrik_mugak`, `diger`
- Klavye kısayolları: `J/K` kriterler arası, `A` onayla, `D` düzelt, `Space` oynat/durdur, `Enter` kaydet ve sıradaki çağrı
- Toplu onay: tüm kriterler onaylandıysa tek tuşla çağrıyı kapat
- **Hedef: bir çağrı incelemesi 8-10 dakikadan 2 dakikaya insin.** Bu ürünün ROI vaadi.

### 3.4 Kalibrasyon modülü (mevcut sayfayı gerçek bir şeye çevir)
- **Kalibrasyon oturumu:** aynı çağrı, birden fazla kaliteci (+ AI) tarafından bağımsız puanlanır, sonuçlar yan yana karşılaştırılır.
- Hesaplanan metrikler ve gösterimi:
  - **AI ↔ insan uyumu** (kriter bazında kappa + ortalama sapma)
  - **İnsan ↔ insan uyumu (IRR)** — hedef ≥ %85 (sektör standardı)
  - **Overturn oranı** = düzeltilen kriter / incelenen kriter. Yükseliyorsa rubrik muğlak demektir, alarm üret.
  - **Sapmanın yönü:** AI sistematik olarak cömert mi cimri mi? (kriter bazında ortalama fark grafiği)
- **Geri besleme döngüsü:** her düzeltme `calibration_examples` tablosuna yazılır. Bir kriterde N düzeltme birikince:
  - o kriterin prompt'una **few-shot örnek** olarak enjekte edilir (rubrik değişmez, örnek eklenir)
  - kriter tanımı muğlaksa süpervizöre "bu kriteri netleştir" görevi açılır
- **Ne yapmayacaksın:** düzeltmeleri gizli bir şekilde ağırlıklara işleyip puanları geçmişe dönük değiştirmek. Her kalibrasyon etkisi sürümlenir ve raporlanır.

### 3.5 İtiraz akışı
- Temsilci kendi karnesinden bir kritere itiraz eder (gerekçe zorunlu)
- Süpervizör kuyruğuna düşer → kabul / ret + gerekçe
- Kabul edilen itiraz → puan güncellenir + kalibrasyon örneği olur
- Kokpitteki "İtiraz analitiği" kartı gerçek veriyle çalışır: itiraz oranı, kabul oranı, en çok itiraz edilen kriter

### Kabul kriterleri (FAZ 3 DoD)
- [ ] Durum makinesi uçtan uca çalışıyor, her geçiş denetim günlüğünde
- [ ] Kaliteci inceleme ekranı klavyeyle tam kullanılabilir; bir çağrı ≤2 dakikada kapatılabiliyor (kendi ölçümünü raporla)
- [ ] Kalibrasyon oturumu oluşturulabiliyor, IRR + kappa + overturn hesaplanıyor
- [ ] Düzeltmeler few-shot olarak prompt'a besleniyor; öncesi/sonrası eval farkı raporlanmış
- [ ] İtiraz akışı uçtan uca çalışıyor
- [ ] Onaylanmamış puanlar liderlik tablosunu kirletmiyor

---

## FAZ 4 — BACKEND SAĞLAMLAŞTIRMA VE ANALİTİK DOĞRULUĞU

**Amaç:** Puanlama dışındaki her şeyin de doğru, hızlı ve güvenli olması.

### 4.1 Analitik hataları (B7–B14)
- Liderlik tablosu sıralaması düzelt; **eşitlik ve az örneklem kuralı**: n<5 çağrısı olan temsilci sıralamada yıldızlı ("yeterli örneklem yok") gösterilir, ilk sırada asla görünmez.
- İstatistik gösterim kuralı: **n < 30 ise korelasyon katsayısı gösterme.** Onun yerine "eğilim gözlemi — henüz istatistiksel olarak anlamlı değil (n=24)" de. Gösterilecekse güven aralığı ile göster.
- Dönem karşılaştırmasında önceki dönem boşsa yüzde üretme → "karşılaştırma için yeterli geçmiş yok".
- Tek veri noktalı zaman serilerinde çizgi grafik yerine tekil metrik kartı + "eğilim için en az 7 gün veri gerekir".
- Kategori ve etiket taksonomilerini ayır. Kategori = çağrının türü (tekil, zorunlu). Etiket = niyet/konu (çoklu, opsiyonel). VoC tablosunda ayrı bölümler.
- ROI hesaplayıcı sonucu göstersin: aylık kazanılan kaliteci saati, TL karşılığı, kapsam farkı (%3 → %100), geri ödeme süresi. Formüller ekranda açık ve düzenlenebilir olsun.
- Koçluk etkinliği: koçluk görevi atanan temsilcinin **görev öncesi/sonrası aynı kriterdeki** puan farkı. Yeterli veri yoksa panel "ilk ölçüm için en az 2 hafta ve 10 çağrı gerekir" desin, sıfır göstermesin.

### 4.2 Alarm motoru (B12, B4)
- **Deduplication:** `(call_id, rule_id, evidence_hash)` üçlüsünde tekillik kısıtı. Aynı ihlal aynı çağrıda tek alarm, `occurrence_count` alanı ile.
- Alarm şiddet seviyeleri: `kritik` (sıfırlayıcı, kriz) / `yuksek` / `bilgi`. Rozet sayacı sadece `kritik` + `yuksek` sayar.
- Her alarm zorunlu alanlar: `title_tr`, `explanation_tr`, `evidence_quote`, `evidence_timestamp`, `suggested_action_tr`, `call_id`. Şablon motoru bu alanları doldurmadan alarm üretemez (B4 çözülür).
- Alarm yaşam döngüsü: `yeni → okundu → aksiyon_alindi | gecersiz_isaretlendi`. "Geçersiz" işaretlenen alarmlar da kalibrasyon sinyalidir, raporlanır.

### 4.3 Veri modeli ve API
- Çağrılara insan-okur bir kimlik ver: `#0024` gibi kısa referans. Dosya adı birincil kimlik olmaktan çıksın.
- Tüm liste endpoint'leri: sunucu tarafı sayfalama, sıralama, filtreleme. Frontend'e 10.000 satır gönderilmez.
- Ağır sorgular için materialized view / özet tabloları (günlük agregasyon). Kokpit tek sayfa açılışında 2 saniyeyi geçmemeli.
- OpenAPI şeması güncel ve tam. Tüm hata cevapları standart zarf: `{ error: { code, message_tr, details } }`.
- İdempotent işleme: aynı ses dosyası iki kez yüklenirse hash ile tespit et, tekrar işleme.
- Kuyruk dayanıklılığı: worker çökerse iş kaybolmaz, `retry` sayacı ve `dead_letter` kuyruğu var. Yönetim ekranından yeniden denenebilir.

### 4.4 Güvenlik ve uyum (B25)
- **Diskte şifreleme** ve **SSO** açık hale getir. Bu iki kırmızı, kurumsal satışta doğrudan blocker.
  - Diskte şifreleme: ses dosyaları ve transkriptler için uygulama seviyesi şifreleme (envelope encryption, anahtar `.env` dışında), veya en azından şifreli volume dokümante edilmiş kurulum + ekranda gerçek durum kontrolü.
  - SSO: OIDC/SAML desteği (Keycloak ile lokal test edilebilir şekilde).
- Güvenlik sayfası **statik metin olmasın** — her satır gerçek bir sistem kontrolünden okunsun (yeşil/kırmızı gerçek durumu yansıtsın).
- PII maskeleme: transkriptte TC kimlik, telefon, IBAN, kart numarası otomatik maskelensin; ham veri sadece yetkili rolde açılsın ve açılma denetim günlüğüne yazılsın.
- Rol tabanlı erişim gerçekten uygulansın: `temsilci` (sadece kendi karnesi), `kaliteci`, `supervizor`, `yonetici`. Her endpoint'te yetki testi.
- Veri saklama (retention) politikası gerçekten işlesin: süresi dolan ses dosyaları otomatik silinsin, silme günlüğe yazılsın.

### 4.5 Test ve gözlemlenebilirlik
- Birim testler: normalize, deterministik kontroller, puan hesabı, sıfırlama mantığı, alarm dedup
- Entegrasyon testleri: yükleme → işleme → puanlama → inceleme → kesinleşme akışı
- Yapılandırılmış loglama (JSON), her puanlamada `trace_id`; bir çağrının puanı neden o olduğu loglardan tam yeniden kurulabilmeli
- `/health` ve `/ready` uçları; Ollama/DB/Redis bağımlılık kontrolü

### Kabul kriterleri (FAZ 4 DoD)
- [ ] B7–B14 ve B25 kapalı
- [ ] Kokpit ilk yükleme < 2 sn (1000 çağrılık seed veriyle ölçülmüş)
- [ ] Alarm tekrarları sıfır (test ile kanıtlı)
- [ ] Rol bazlı yetki testleri geçiyor
- [ ] Test kapsamı: puanlama ve alarm modüllerinde ≥ %80

---

## FAZ 5 — ARAYÜZ YENİDEN TASARIMI (SKILL'LERLE)

**Amaç:** Karışık, yoğun, jargon dolu arayüzü; bir çağrı merkezi kalitecisinin vardiya boyunca yorulmadan kullanacağı sade bir çalışma aracına çevirmek.

> Bu fazda **önce skill'leri oku**: `frontend-design` (görsel dil), `ui-ux-pro-max` (akış ve bilgi mimarisi), `web-interface-guidelines` (erişilebilirlik/bileşen kuralları), `vercel-react-best-practices` (performans). Okumadan kod yazma.

### 5.1 Tasarım öncesi: plan
Kod yazmadan önce `docs/v2/05-TASARIM-PLANI.md` üret:
- Tasarım token sistemi: 4-6 renk (semantik: başarı/uyarı/hata/bilgi/nötr — dekoratif renk yok), 2 tipografi rolü + 1 sayısal/veri yüzü, 8px spacing ızgarası, 3 seviyeli tipografi hiyerarşisi
- Karanlık **ve** aydınlık tema; sistem tercihine saygı. Karanlık tema izleme ekranları için varsayılan, ama tablo/rapor ekranları aydınlıkta da kusursuz olmalı.
- Ürünün "imza" öğesi ne olacak (skill'in dediği gibi cesareti tek yere harca) — öneri: **kanıt-transkript bağı**. Puanın yanındaki alıntıya tıklayınca sesin o saniyeye atlaması ve transkriptte vurgulanması. Ürünün tüm iddiası bu: "her puanın kanıtı var."
- Yapay zekâ görünümlü klişelerden kaçın: krem arkaplan + terracotta aksan, near-black + asit yeşili tek aksan, kenarlıksız gazete kolonları. Bu bir çağrı merkezi operasyon aracı — ciddi, sakin, yüksek okunurluk.

### 5.2 Bilgi mimarisi (B21, B24)
14 düz menü öğesini **rol bazlı, gruplu** yapıya çevir:

```
İZLEME       → Kokpit · Analitik
ÇALIŞMA      → Çağrılar · İnceleme Kuyruğum · Kalibrasyon · Arama
EKİP         → Temsilciler · Lig · Koçluk
KURULUM      → Rubrik · Kampanyalar · Bilgi Bankası · Yasaklı Kelimeler
SİSTEM       → Kullanıcılar · Güvenlik · ROI · Denetim Günlüğü
```
- Rol bazlı varsayılan açılış: `kaliteci` → İnceleme Kuyruğum · `supervizor` → Kokpit · `temsilci` → Kendi Karnem · `yonetici` → Kokpit
- Kullanıcının rolüyle ilgisi olmayan menü öğeleri **gizlenir**, gri gösterilmez.
- Yönetim'deki 10 sekme, sol dikey alt-navigasyona çevrilsin (taşma biter).
- Her sayfada breadcrumb + net sayfa başlığı + tek birincil eylem.

### 5.3 Ekran ekran gereksinimler

**Kokpit**
- Ters piramit: en üstte 4 karar metriği (ortalama puan · onay bekleyen · kritik alarm · kapsam %), altında eğilimler, en altta detay.
- Her metrik kartı tıklanabilir ve **filtrelenmiş listeye götürür** (metrik → aksiyon).
- Her kart bir "peki ne yapmalıyım?" satırı taşır.

**Çağrılar listesi (B22)**
- Sütunlar: `#Ref · Temsilci · Kategori · Süre · Puan · Durum · Tarih`. Kanal ikonu tekrar eden rozet değil, küçük simge.
- Yoğunluk anahtarı (sıkışık/rahat), sticky başlık, sütun seçici, kayıtlı görünümler (zaten var — görünür yap).
- Sanal kaydırma + sunucu sayfalama. Satır seçimi → toplu aksiyon (kuyruğa ata, dışa aktar, yeniden puanla).
- Puan rozeti eşik renkleri **tek merkezden**; sıfırlanmış çağrılarda rozet "0 — sıfırlayıcı ihlal" ve tooltip'te sebep (B5).

**Çağrı detayı (B26)**
- İki kolon: sol sabit (oynatıcı + transkript), sağ kaydırılabilir (kriter kartları).
- Üstte tek satırlık karar şeridi: toplam puan · durum · **birincil eylem** (kaliteci ise "İncelemeye başla", süpervizör ise "Koçluk görevi ata").
- Kriter kartı: puan, tek cümle gerekçe, kanıt alıntısı (tıkla → ses atlar), güven göstergesi, "Düzelt" eylemi.
- "Puanı düzelt" 8 ayrı yere dağılmasın; tek inceleme moduna gir, kriterler arasında klavyeyle ilerle.
- Ham veri / geliştirici alanları (`bare_name`, `zero=`) varsayılan gizli, "Geliştirici görünümü" arkasında.

**İnceleme kuyruğu (yeni ana ekran)**
- Kart yığını değil, tek çağrı odaklı akış: aç → incele → kaydet → otomatik sıradaki.
- Üstte ilerleme: "Bugün 12/30 · ortalama 1dk 47sn".

**Arama (B23)**
- Sonuç listesi: eşleşen cümle, çevresi, temsilci, tarih, çağrı içi konuma atlayan bağlantı.
- Boş durum: son aramalar + hazır arama önerileri + "ne aranabilir" örneği.

**Rubrik editörü (B20)**
- Her kontrolün yanında ne işe yaradığı: "Ağırlık: bu kriterin toplam puandaki payı", "Kritik: bu kriter eşiğin altında kalırsa çağrı puanı 0 olur".
- Canlı önizleme: ayarları değiştirdikçe "bu rubrikle örnek çağrı kaç alırdı" göstergesi (simülasyon zaten var, görünür ve anlaşılır yap).
- Kaydetmeden çıkışta uyarı; sürüm geçmişi ve geri alma net.

**Asistan (B18)**
- Model adı kullanıcıya çıplak gösterilmez → "Yerel yapay zekâ · görsel analiz" + detay tooltip'inde teknik bilgi.
- Dosya seçici Türkçeleştirilmiş, sürükle-bırak destekli, kabul edilen formatlar yazılı.

### 5.4 Bileşen ve davranış standartları
- **Dört durum zorunlu:** yükleniyor (iskelet) · boş · hata · dolu. Tek bir ekran bu dördünü karşılamadan bitmiş sayılmaz.
- Boş durum metni şablonu: **ne yok + neden + tek eylem.** Örn: "Henüz inceleme yok. Çağrılar puanlandıkça kuyruk dolar. → Çağrı yükle"
- Hata mesajı şablonu: **ne oldu + ne yapmalı.** Özür dileme, "bir şeyler ters gitti" yok.
- İskelet yükleyiciler; spinner sadece 1 saniyeden kısa işlemlerde.
- Yıkıcı işlemlerde onay + geri alma.
- Erişilebilirlik: WCAG AA kontrast, görünür odak halkası, tam klavye navigasyonu, tablo başlıkları semantik, `prefers-reduced-motion` saygısı.
- Sayısal veri tabular-nums ile hizalı; puanlar her yerde tek ondalık.

### 5.5 Performans (`vercel-react-best-practices`)
- İstek şelalelerini kır: sayfa verisi paralel çekilir, sıralı `await` zinciri yok.
- Ağır grafik kütüphaneleri dinamik import.
- Gereksiz client component yok; veri çekimi sunucuda.
- Uzun listelerde sanallaştırma.
- Ölçüm zorunlu: önce/sonra LCP, INP, bundle boyutu raporla.

### Kabul kriterleri (FAZ 5 DoD)
- [ ] Dört skill de fiilen okunmuş ve `docs/v2/05-TASARIM-PLANI.md`'de hangisinin neyi belirlediği yazılmış
- [ ] Tüm ekranlarda dört durum (yükleniyor/boş/hata/dolu) mevcut
- [ ] Klavyeyle inceleme akışı fareye dokunmadan tamamlanabiliyor
- [ ] WCAG AA kontrast denetimi geçiyor; odak halkaları görünür
- [ ] Kokpit ve Çağrılar sayfalarında LCP/INP önce-sonra ölçümü raporlanmış
- [ ] Karanlık ve aydınlık temanın her ikisinde tüm ekranların ekran görüntüleri `docs/v2/screens/` altında

---

## FAZ 6 — DİL, İÇERİK, DEMO VE SATIŞA HAZIRLIK

**Amaç:** Ürünün ağzından çıkan her kelimenin, ürünü satan bir çağrı merkezi profesyoneline mantıklı gelmesi.

### 6.1 Metin altyapısı (B15, B16, B17, B19)
- **Tek kaynak:** `messages/tr.json` + `messages/en.json`. Kodda gömülü kullanıcı metni kalmaz. Eksik anahtar CI'da hata verir.
- Türkçe metinlerde **tam Türkçe karakter** — veritabanındaki rubrik isimleri dahil migration ile düzeltilir: `Acilis → Açılış`, `Kapanis → Kapanış`, `Bilgi Dogrulugu → Bilgi Doğruluğu`, `Kimlik Dogrulama → Kimlik Doğrulama`, `Cozum / Yonlendirme → Çözüm / Yönlendirme`, `Yasakli Kelime / Uslup → Yasaklı Kelime / Üslup`, `Ihtiyac Analizi → İhtiyaç Analizi`, `Aktif Dinleme` ✓
- **Terim sözlüğü** (`docs/v2/SOZLUK.md`) oluştur ve her yerde ona sadık kal. Aynı kavrama iki isim verilmez.
- Sistem jargonu → kullanıcı dili dönüşüm tablosu:

| Şimdi | Olacak |
|---|---|
| `assigned / in_review / completed` | Atandı / İnceleniyor / Tamamlandı |
| `bare_name`, `zero=`, `yasak_vaat` | (kullanıcıya hiç gösterilmez) |
| "Sıfırlayıcı ihlal" | Kalır — ama ilk görünümde tooltip: "Bu kriterde eşiğin altında kalan çağrının puanı sıfırlanır" |
| "Overturn oranı" | "Düzeltilen puan oranı" |
| "Kohort karşılaştırma" | "Ekip karşılaştırması" |
| "Çağrı yükle" | Kalır ✓ |
| "Örnek işaretle" | "Eğitim örneği olarak işaretle" |
| "Koçluk görevi ata" | Kalır ✓ |

- Yazım kuralları: cümle sonu noktalama tutarlı, buton metinleri emir kipi ve eylemi birebir söyler ("Kaydet" → "Kaydedildi" bildirimi), etiketler cümle düzeni (Sentence case).
- **Yapay zekâ çıktısı metinler de Türkçe kalite denetiminden geçer.** Koçluk önerisi, çağrı özeti, alarm açıklaması → prompt'ta Türkçe karakter ve doğal Türkçe zorunlu; ASCII çıktı reddedilip yeniden istenir.
- Tüm boş/hata durumları 6.1'deki şablonlara göre yeniden yazılır (B19).

### 6.2 Onboarding ve içi boş sayfalar
- İlk kurulumda 4 adımlı rehber: kurum bilgisi → rubrik seçimi (hazır şablon: Telekom / Bankacılık / E-ticaret) → kullanıcı davet → ilk çağrı yükleme.
- Her sayfanın ilk ziyaretinde tek cümlelik "bu sayfa ne işe yarar" satırı (kapatılabilir).
- Rubrik hazır şablonları gerçek olsun — sıfırdan kriter yazmak zorunda kalan müşteri ürünü bırakır.

### 6.3 Demo modu (satış için)
- `make demo` tek komut: 200+ gerçekçi Türkçe çağrı üretir (kadın/erkek ses karışık), 12 temsilci, 30 günlük dağılım, gerçekçi puan dağılımı (mükemmel değil — çan eğrisi), birkaç kriz ve sıfırlayıcı ihlal.
- Demo verisi **zaman içinde iyileşme** göstersin: koçluk sonrası puan artışı, alarm azalması. Satışta anlatılacak hikâye bu.
- `make demo-reset` ile temizlenir. Demo verisi gerçek veriden `is_demo` bayrağıyla ayrılır ve raporlara karışmaz.
- Beyaz etiket (white-label): logo, ana renk, kurum adı ayarlardan değişir ve PDF karnede de görünür.

### 6.4 Çıktılar
- **PDF karne** (temsilci): puanlar, kriter kırılımı, güçlü/gelişim alanı, örnek alıntılar, koçluk notu. Kurum logolu.
- **Excel ekip raporu**: temsilci × kriter matrisi, dönem karşılaştırması.
- **Yönetici brifingi** (Kokpit'teki "Özet üret" gerçek çalışsın): 5 madde — dönemin kazanımı, riski, en kritik 3 aksiyon.

### 6.5 Dokümantasyon
- `README.md`: 5 dakikada ayağa kaldırma
- `docs/KURULUM.md`: on-prem kurulum, donanım gereksinimi, Ollama model seçimi, ölçekleme notları
- `docs/KALITE-METODOLOJISI.md`: **satışta kullanılacak doküman.** Puanlama nasıl çalışıyor, kanıt zorunluluğu, kalibrasyon süreci, ölçülen doğruluk metrikleri (golden set sonuçları buraya gider), yapay zekânın sınırları ve insan onayının rolü. Dürüst yaz — "%100 doğru" iddiası ürünü satmaz, batırır.
- `docs/KVKK-UYUM.md`: verinin nerede durduğu, maskeleme, saklama süresi, erişim denetimi, rol matrisi
- `CHANGELOG.md`: v2 fazları

### Kabul kriterleri (FAZ 6 DoD)
- [ ] Kodda gömülü kullanıcı metni sıfır; `tr.json`/`en.json` tam ve senkron
- [ ] Veritabanı ve arayüzde Türkçe karakter hatası sıfır (otomatik denetim scripti ile kanıtla)
- [ ] `make demo` temiz kurulumda çalışıyor ve satılabilir bir demo veriyor
- [ ] PDF karne, Excel rapor, yönetici brifingi gerçek veriyle çalışıyor
- [ ] `docs/KALITE-METODOLOJISI.md` golden set metrikleriyle dolu
- [ ] Tüm dokümantasyon güncel

---

## 3. GENEL BİTİŞ TANIMI (tüm fazlar sonrası)

- [ ] `docker compose up -d` → temiz makinede sistem ayağa kalkıyor
- [ ] `make eval` → FAZ 2 kabul metrikleri korunuyor
- [ ] `make demo` → satış demosu hazır
- [ ] `make test` → tüm testler yeşil
- [ ] Bölüm 2'deki B1–B26 hatalarının **hepsi** kapalı ve her biri için regresyon testi var
- [ ] Kodda `TODO`, `FIXME`, `mock`, `placeholder`, `lorem` sıfır
- [ ] `docs/v2/FAZ-1..6-RAPOR.md` yazılmış

---

## 4. ASLA YAPMA LİSTESİ

1. **Kanıtsız ceza verme.** Kanıt yoksa "yetersiz kanıt" der, insana yollar. Düşük puan vermez.
2. **LLM'e toplam puan hesaplatma.** Puan aritmetiği kodda.
3. **Tek dev prompt'ta 12 kriteri birden değerlendirme.**
4. **Sıcaklığı 0'dan yukarı çıkarma** puanlama yolunda.
5. **Rubriği sürümsüz değiştirme.** Geçmiş puanlar geriye dönük bozulmaz.
6. **n<30 ile korelasyon/anlamlılık iddia etme.**
7. **Kullanıcıya ASCII'ye düşürülmüş Türkçe gösterme.**
8. **Geliştirici jargonunu arayüze sızdırma.**
9. **Test verisi ile gerçek veriyi karıştırma.**
10. **"Yapay zekâ %100 doğru" iddiası kurma.** Ürünün dürüstlüğü satış argümanıdır: %100 kapsam + kanıtlı puan + insan onayı.
11. **Faz atlamayı veya birleştirmeyi teklif etme.** Sıra bilinçli: doğruluk → iş akışı → arayüz.

---

## 5. ARAŞTIRMA NOTLARI (kararların dayanağı)

Bu prompt aşağıdaki bulgulara dayanıyor; uygulama sırasında bunlara sadık kal:

**LLM-as-a-judge güvenilirliği**
- Rubrik tabanlı LLM puanlamasında üç tekrarlayan hata modu tanımlı: *rubrik uygulama sapması*, *doğrulanamayan puan atfı*, *insan ölçeğiyle hizasızlık*. Çözüm üçlüsü: kilitli/sürümlü rubrik spesifikasyonu, tipli ve alıntıyla doğrulanan kanıt, sonradan kalibrasyon. (arXiv 2601.08654 — "Rulers")
- LLM yargıçlar prompt ifadesi, format ve sıralamaya duyarlı; uzun cevabı ve belirli pozisyonları kayırıyorlar. Azaltıcılar: azalan rubrik sırası, harf/roma rakamı ID, tam puan referansı verme. (arXiv 2506.22316)
- En iyi modeller bile zor vakaların yaklaşık dörtte birinde tutarlı kalamıyor → kritik kararlarda self-consistency ve insan onayı şart. (arXiv 2512.16041 — SAGE)
- Muğlak sıfat yerine somut kanıt tanımlayan rubrikler (alıntı, sayısal kontrol, mantıksal sıra) güvenilirliği belirgin artırıyor.

**Çağrı merkezi QA pratiği**
- Scorecard kriter sayısında tatlı nokta **8-15**; 30 kriterli kart ne tutarlı puanlanır ne koçlukta kullanılır. (Scorebuddy)
- 4C çerçevesi (Uyum / İletişim / Yetkinlik / Müşteri Odağı) yaygın başlangıç yapısı; ağırlıklar sektöre göre değişir (tahsilat merkezinde uyum %40+).
- Puanlayıcılar arası uyum (IRR) hedefi **%85+**; program başlangıcında haftalık, oturduktan sonra aylık kalibrasyon.
- Elle QA çağrıların **%2-5'ini** kapsıyor; tek çağrı incelemesi 15-20 dakika. 50 temsilcilik ekipte ayda 62+ saat. ROI hikâyesi buradan çıkıyor.
- Otomatik puanlamanın kabul gördüğü tasarım kuralı: sorular mümkün olduğunca **ikili/kural tabanlı** olsun; öznel sorular (empati, ton) **insana işaretlensin**. Scorecard tasarımı, AI QA doğruluğundaki en büyük tek değişken. (Aircall)
- Tam yayına almadan önce **20-30 çağrıda AI ve analist puanlarını karşılaştır**; soru bazlı fark, hangi kriterin düzeltilmesi gerektiğini gösterir.
- Kalibre edilmiş sistemler yapısal kriterlerde uzman insanla **%90-95 uyum** bildiriyor; sarkazm, ağır aksan, muğlak ton hâlâ zayıf nokta. Paralel çalıştırma (AI + manuel) ile geçiş öneriliyor.
- İnsan düzeltmeleri (override + gerekçe kodu) ve "rate-the-rater" kontrolleri, hem AI'yı hem insanı dürüst tutan mekanizma.
- Kritik benimseme koşulu: **puanı konuşmaya geri izleyebilmek.** İzlenemeyen puanı QA ekipleri benimsemiyor.

**Kurumsal arayüz**
- Kurumsal araçta değer görsel cilalamadan değil, işlevsel netlik ve iyi düzenlenmiş veri yoğunluğundan geliyor; aşırı boşluk ve katman altına saklanan veri, tüm veriyi aynı anda görmesi gereken kullanıcıyı yoruyor.
- Ters piramit: en üstte kritik KPI ve sistem sağlığı, sonra destekleyici metrikler, sonra detay. Kullanıcı panoyu birkaç saniye tarayıp derine inip inmeyeceğine karar veriyor.
- 8px ızgara ile tutarlı boşluk, kenarlık/ayraçtan daha etkili gruplama sağlıyor. Semantik renk **3-5** ile sınırlı; dekoratif renk gürültü.
- Tipografi hiyerarşisi en fazla 3 seviye; taramada boyut ve ağırlık renkten daha çok iş görüyor.
- Karanlık tema izleme merkezleri ve uzun vardiyalar için; aydınlık tema metin yoğun tablolar, dışa aktarılan rapor ve karma izleyici için. Her ikisi + sistem tercihi.

**KVKK (uyum kriterinin hukuki dayanağı)**
- Aydınlatma yükümlülüğü Tebliğ m.5/1 uyarınca **çağrı merkezi ve ses kaydı** dahil sözlü ortamda da yerine getirilebilir.
- Çağrı merkezinde aydınlatma sözlüdür: **arama başında veya veri alınmadan hemen önce** kısa bilgilendirme yapılır; ses kaydı alınıyorsa bu **açıkça** belirtilmelidir.
- Muğlak, genel ifadeler kullanılmamalı; dil anlaşılır ve sade olmalı.
- → Bu yüzden KVKK kriteri iki ayrı kontrol içermeli: (a) kayıt bildirimi yapıldı mı, (b) kişisel veri işleme bilgisi verildi mi. İkisi ayrı ayrı puanlanır ve **ayrı kanıt** gerektirir. Anonsun birebir aynı cümleyle yapılması beklenmez — anlam kümesi eşleşmesi aranır.

---

## 6. FAZ BAŞINDA SORULABİLECEK SORULAR (örnek)

Bunlar teknik değil iş kararlarıdır; faz başında toplu sor, cevap gelmezse en makul varsayımı uygula ve raporda belirt:

- FAZ 2: Sıfırlayıcı ihlal eşiği kaç olsun (şu an 3/10)? Rubrik kriter sayısını 15'e indirirken hangi kriterler birleşsin?
- FAZ 3: Kaliteci onayı olmadan puan temsilciye görünsün mü? Rastgele örneklem oranı %5 uygun mu?
- FAZ 5: Ana hedef kullanıcı kim — kaliteci mi süpervizör mü? (Varsayılan açılış ekranı buna göre belirlenecek.)
- FAZ 6: Hazır rubrik şablonları hangi sektörler için olsun?

---

**Başlangıç:** FAZ 1, madde 1.1.
