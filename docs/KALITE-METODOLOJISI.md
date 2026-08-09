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

Yapay zekânın tek başına yeterli olduğunu **iddia etmiyoruz.** Ölçtüğümüz şu:
yapısal/nesnel kriterlerde (açılış, KVKK, kimlik, kapanış, üslup) sistem
tanımlı kuralla **kappa 0.90–1.00** uyum yakalıyor. Yargı gerektiren
kriterlerde — sarkazm, ağır aksan, muğlak ton, "yeterince dinledi mi" — hâlâ
insan gerekiyor ve sistemin oradaki uyumu **düşük** (§4.1).

Ürün bunu gizlemez, **yönetir**: güvenilir olmadığını bildiği kriteri insana
yollar. Bu, ürünün zayıflığı değil tasarımıdır.

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

### 4.0 Referans setinin kaynağı — önce bunu okuyun

Aşağıdaki metrikler **50 senaryoluk sentetik bir referans sete** karşı ölçüldü.
Bu setin nasıl üretildiği, sayıların ne anlama geldiğini belirler:

| | Kim üretti | Ne anlama gelir |
|---|---|---|
| **Sentetik referans** (mevcut) | Sistemi geliştiren yapay zekâ asistanı, çağrı merkezi QA pratiğine göre transkriptleri ve beklenen puanları birlikte yazdı | **Bağımsız değil.** Motor, kendi tasarımcısının yazdığı cevap anahtarına karşı ölçülüyor |
| **İnsan referansı** (devam ediyor) | Kurumun kalite uzmanı, 20 senaryoyu bağımsız puanlıyor | Bağımsız doğrulama |

**"Uzman referansı" demiyoruz** — çünkü bu set bir insan uzman tarafından
üretilmedi. Buna "sentetik referans" diyoruz ve sınırını açıkça yazıyoruz:

- **Nesnel/deterministik kriterlerde** (açılış, KVKK, kimlik, kapanış, üslup)
  sentetik referans güvenilirdir: "şu ifade transkriptte geçti mi?" sorusunun
  cevabı okunarak doğrulanabilir. Burada referans bir *spesifikasyondur*,
  bir yargı değil.
- **Öznel kriterlerde** (aktif dinleme, ihtiyaç analizi, çözüm, bilgi doğruluğu)
  sentetik referans **döngüseldir**: puanlama prompt'unu tasarlayan ile cevap
  anahtarını yazan aynı taraftır. Bu kriterlerin sentetik kappa'sı
  **bağımsız bir doğruluk kanıtı sayılmaz.**

Bu yüzden metrikler ikiye ayrılarak raporlanır (§4.1 ve §4.2) ve insan
referansı hazır olduğunda ikisi yan yana yayımlanır (§4.3).

Ölçüm yöntemi ve ham çıktılar: `docs/v2/eval/`. Yeniden üretim: `make eval`.

### 4.1 Kriterler iki gruba ayrılır — ve ayrı raporlanır

Tek bir ortalama, iki farklı gerçeği gizliyordu. Sistemin en güçlü yanı
(uyum kriterlerinde kappa 0.94–1.00) en zayıf yanıyla (öznel kriterlerde
0.08–0.20) ortalanınca ikisi de yanlış görünüyordu.

Ancak "nesnel" olmak tek başına yüksek kappa garanti etmiyor: nesnel
kriterlerden **ikisi düşük** ve bunun sebebi model değil, **tanımın kendisi**
(§4.3'teki tabloya bakın). Deterministik bir kural, yanlış tanımlanmışsa
kusursuz tutarlılıkla yanlış cevap verir.

| | Nesnel / deterministik | Öznel |
|---|---|---|
| **Kriterler** | Açılış, KVKK, Kimlik Doğrulama, Kapanış, Yasaklı Kelime, Script Uyumu | Aktif Dinleme, İhtiyaç Analizi, Çözüm/Yönlendirme, Bilgi Doğruluğu |
| **Cevabı ne belirler** | Transkriptte bir ifadenin varlığı | Yargı |
| **Nasıl puanlanır** | Katman A — kodla, LLM'e sorulmadan | Katman B — kanıt zorunlu LLM |
| **Referans güvenilir mi** | Evet — bir *spesifikasyon*, doğrulanabilir | Hayır — sentetik referans döngüsel (§4.0) |
| **Kappa hedefi** | Çekirdek 4 kriter: her biri **≥ 0.90** | **İnsan-insan uyumunun %85'i** (§4.2) |

**"%100 kapsam" iddiası yalnızca nesnel kriterler için kurulur.** Öznel
kriterlerde sistem bir **öneri** üretir; geçerli puan kalite uzmanı onayından
sonra oluşur. Ürünün iki aşamalı yapısı tam olarak bu ayrımın sonucudur.

### 4.2 Öznel kriterlerde hedef neden sabit değil?

Sabit bir kappa hedefi, kriterin doğasını yok sayar. İki deneyimli kalite
uzmanı "aktif dinleme"de birbiriyle 0.55 uyum yakalıyorsa, yapay zekâdan 0.75
beklemek bir hedef değil, **imkânsız bir şarttır** — insanın kendisi o eşiği
geçemiyor.

Bu yüzden öznel kriterlerde hedef **ölçülen insan-insan uyumuna** bağlanır:

```
AI hedefi (öznel kriter) = insan-insan kappa × 0.85
```

İnsanlar birbirine 0.60 uyuyorsa AI hedefi 0.51; 0.90 uyuyorsa 0.77 olur.
Hedef, uydurulmuş bir sayıya değil ölçülmüş bir gerçeğe bağlanır.

**İnsan-insan IRR henüz ölçülmediği için öznel kriterlerde şu an hedef
KOYULMUYOR.** `make eval` kapısı yalnızca nesnel kriterleri denetler; öznel
kriterler raporlanır ama build'i kırmaz. IRR ölçümü için altyapı hazır:
`scripts/golden/human_ref.py`.

### 4.3 Genel metrikler — v1 tabanı → v2

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

50 senaryoluk tam koşum, varsayılan kurulum (`qwen2.5:7b-instruct`):

| Kriter | Katman | kappa | MAE | Yorum |
|---|---|---|---|---|
| Açılış | A | **1.00** | 0.02 | Kuralla tam mutabık |
| KVKK / Aydınlatma | A | **1.00** | 0.00 | Kuralla tam mutabık |
| Yasaklı Kelime / Üslup | A | **1.00** | 0.00 | Kuralla tam mutabık |
| Kapanış | A | **0.94** | 0.08 | Güvenilir |
| Kimlik Doğrulama | A | 0.54 | 0.39 | **Tanım sorunu** — "geç doğrulama kaç puan?" bir *politika* kararı, teknik değil |
| Çözüm / Yönlendirme | B | 0.20 | 1.67 | Öznel → insana gider |
| Bilgi Doğruluğu | B | 0.19 | 1.54 | Öznel → insana gider |
| İhtiyaç Analizi | B | 0.11 | 1.71 | Öznel → insana gider |
| Script Uyumu | A | 0.10 | 0.47 | **Tanım sorunu** — kriter diğer dördünün türevi, bağımsız bilgi taşımıyor |
| Aktif Dinleme | B | 0.08 | 1.98 | Öznel → insana gider |

**İki farklı düşük kappa sebebi var, karıştırılmamalı:**

- **Tanım sorunu** (Kimlik Doğrulama, Script Uyumu): Kural deterministik ve
  %100 tekrarlanabilir; referansla ayrıştığı yer *kuralın ne olması gerektiği*.
  Bir insan kuralı ve transkripti okuyup kimin haklı olduğuna karar verebilir.
  Bunlar **çözülebilir** sorulardır — kurumun politikası belirlenince biter.
- **Yargı sorunu** (dört öznel kriter): Cevap tartışmaya açık. Burada
  "doğru cevap" ancak insan-insan uyumu ölçülerek tanımlanabilir (§4.2).

Çekirdek dört kriterin ortalaması **0.985**. `make eval` kapısı bu dördünü
**tek tek** denetler (≥0.90), çünkü ortalama tek bir kriterin bozulmasını
gizleyebilir.

**Nesnel kriterlerde sistem spesifikasyonla tam mutabık. Öznel kriterlerde
değil — ve bunu biliyor.** Ölçülen kappa'sı 0.40'ın altındaki kriterlerde
güven skoru otomatik tavanlanır ve çağrı **garantili** insan onayına düşer.

> ⚠️ **Öznel kriterlerin kappa'sı bağımsız bir doğruluk kanıtı değildir**
> (§4.0). Bu satırlar "AI kötü puanlıyor" demez; "sentetik referans bu
> kriterlerde bir doğruluk ölçüsü sayılamaz" der. Gerçek yargı, insan
> referansı ve IRR ölçüldüğünde çıkacak.

### Ne denendi, ne işe yaramadı
Öznel kriterlerdeki uyumu artırmak için üç mekanizma denendi ve **ölçüldü**:
few-shot geri besleme (kappa 0.492→0.499), skala kalibrasyonu, deterministik
tavan. Hiçbiri anlamlı fark yaratmadı.

Dördüncü deneme — **daha büyük model** — işe yaradı. §4.4.

### 4.4 Daha büyük model ne kazandırıyor? — ölçüldü

Aynı 50 senaryo, aynı prompt, aynı doğrulama. Tek fark: dört öznel kriter
`qwen2.5:14b-instruct` ile puanlandı, geri kalan her şey aynı kaldı.

| Kriter | 7B kappa | 14B kappa | Fark |
|---|---|---|---|
| İhtiyaç Analizi | 0.113 | **0.462** | +0.349 |
| Çözüm / Yönlendirme | 0.197 | **0.448** | +0.251 |
| Aktif Dinleme | 0.081 | **0.226** | +0.145 |
| Bilgi Doğruluğu | 0.195 | 0.175 | −0.019 |
| **Öznel ortalama** | **0.146** | **0.328** | **+0.182** |

**Nesnel kriterlerin altısı da kuruşu kuruşuna aynı kaldı** (fark 0.0000).
Bu bir tesadüf değil, yönlendirmenin doğru çalıştığının kanıtı: büyük model
yalnızca öznel kriterlere dokundu.

### Bu farkın ne kadarı gerçek? — gürültü ölçüldü

Tek koşumluk bir kappa farkı, o metriğin doğal oynamasından büyük değilse
bir şey kanıtlamaz. Bu yüzden **aynı yapılandırma iki kez** koşuldu:

| Kriter | 7B koşum A | 7B koşum B | 14B | Sonuç |
|---|---|---|---|---|
| İhtiyaç Analizi | 0.113 | 0.098 | **0.462** | Fark gürültünün ~20 katı — **gerçek** |
| Çözüm / Yönlendirme | 0.197 | 0.197 | **0.448** | 7B iki koşumda birebir aynı — **gerçek** |
| Aktif Dinleme | 0.081 | 0.076 | **0.226** | Fark gürültünün ~10 katı — **gerçek** |
| Bilgi Doğruluğu | 0.195 | **0.350** | 0.175 | **Sonuçsuz** — 7B'nin kendi oynaması daha büyük |

**Nesnel kriterlerin altısı da her üç koşumda kuruşu kuruşuna aynı çıktı.**
Katman A'nın gerçekten deterministik olduğunun kanıtı budur.

Dolayısıyla dürüst ifade şudur: **dört öznel kriterin üçünde büyük model
belirgin ve gürültüyü aşan bir kazanç sağlıyor; dördüncüsünde (Bilgi
Doğruluğu) ölçüm sonuç vermiyor.** Ortalama üzerinden konuşmak
(0.146 → 0.328) bu ayrımı gizler.

> **Bilinen ölçüm sınırı:** `tekrarlanabilirlik_std` metriği üç senaryonun
> **toplam puanını** ölçer ve 0.00 çıkar. Bu doğru ama dardır — toplam puan
> sabitken kriter bazında oynama olabiliyor. Kriter seviyesinde varyans
> ölçümü yol haritasında.


**Cevap: tavan hem modelden hem metodolojiden geliyor — ama bu ölçüm ikisini
ayırdı.**

- **Model payı gerçek ve büyük.** Öznel uyum 2.2 katına çıktı. "7B bu işi
  yapamıyor" iddiası artık bir tahmin değil, ölçüm.
- **Model payı yetmiyor.** 0.33 hâlâ nesnel kriterlerin (0.94–1.00) çok
  altında. Model büyütmek tavanı kaldırdı ama kaldırmadı.
- **Kritik ayrıntı: MAE neredeyse hiç düzelmedi** (1.98→1.94, 1.71→1.69).
  Yani 14B *sayısal olarak daha doğru puan* vermiyor; **bant kararlarında**
  daha tutarlı. Bu, kalan farkın büyük ölçüde "doğru sayı kaç?" sorusunun
  cevapsızlığından geldiğini söylüyor — yani **metodolojiden**, ölçüldüğü
  referansın döngüselliğinden (§4.0).
- **Bilgi Doğruluğu hiç düzelmedi.** Bu kriter bilgi *doğruluğunu* ölçüyor;
  model daha büyük olsa da transkriptte olmayan kurumsal gerçeği bilemez.
  Buranın çözümü model değil, **bilgi tabanı (RAG)**.

**Bedeli — ölçüldü:** 14B modeli 9 GB yer kaplar. Aynı donanımda (3 senaryo,
aynı koşullar) senaryo başına süre **21.7 sn → 64.3 sn**, yani yaklaşık **3
kat**. Nesnel kriterler zaten kodla çözüldüğü için bu maliyet **yalnızca öznel
kriterler** için ödenir; tüm çağrıyı büyük modele vermek gereksiz olurdu.

**Varsayılan: kapalı.** Her kurulumda 9 GB model bulunmaz ve model yoksa
sistem sessizce varsayılana düşer. Açmak için kurumun ayarlarında:

```json
{"ai": {"subjective_model": "qwen2.5:14b-instruct"}}
```

Ölçümü tekrarlamak için:
```
make eval EVAL_ARGS="--subjective-model qwen2.5:14b-instruct --etiket 14b"
```

**Bu sonuç bir hedefe ulaşıldığı anlamına GELMEZ.** Öznel kriterlerde meşru
bir hedef ancak insan-insan IRR ölçülünce doğar (§4.2). 0.33'ün iyi mi kötü
mü olduğunu, iki kalite uzmanının birbirine ne kadar uyduğu belirleyecek.

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

- ✅ **Nesnel kriterlerde %100 kapsam**: her çağrının açılışı, KVKK anonsu,
  kimlik doğrulaması, kapanışı ve üslubu denetlenir — hiçbiri atlanmaz.
  Öznel kriterlerde sistem **öneri** üretir; geçerli puan insan onayıyla oluşur
- ✅ **Her puanın kanıtı var**: alıntı transkriptte doğrulanır (%100)
- ✅ **Tekrarlanabilir**: aynı çağrı üç kez puanlandığında aynı sonuç (std 0.00)
- ✅ **Nesnel kriterlerde kuralla tam mutabık**: kappa 0.90–1.00
  *(karşılaştırma bir insan uzmanla değil, tanımlı kuralla yapıldı — §4.0)*
- ✅ **Haksız sıfırlama yok**: yanlış-pozitif %0
- ✅ **Sistem sınırını biliyor**: güvenilmediği kriteri insana yollar
- ✅ **Veri kurumdan çıkmaz**: yerel model (Ollama) ile on-prem çalışır

---

*Bu dokümandaki metrikler `make eval` ile yeniden üretilebilir.
Ham ölçüm çıktıları: `docs/v2/eval/`.*
