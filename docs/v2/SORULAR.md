# Rio'nun Karar Vermesi Gereken İş Kararları

> Bu defter fazlar ilerledikçe büyür. **Hiçbiri beklemede değil** — her biri için
> en makul varsayımla ilerlendi, varsayım burada ve ilgili faz raporunda yazılı.
> Rio farklı karar verirse ilgili varsayım tek yerden değiştirilebilir.
>
> **Durum (2026-08-09): açık soru kalmadı.** 5'i Rio tarafından karara bağlandı,
> 12'si varsayımla kapatıldı. Kapatılmış bir soru "tartışılmaz" demek değildir;
> "cevabı yazılı ve gerekçeli, itiraz gelene kadar geçerli" demektir.

**Durum kodları:** 🟢 Rio karar verdi · 🔵 varsayımla **kapatıldı** (Rio itiraz
edene kadar geçerli) · 🟡 varsayımla ilerlendi, hâlâ açık

---

## Rio'nun kararları — 2026-08-09

| # | Karar | Nereye işlendi |
|---|---|---|
| **S2** | Altın set puanları "uzman" değil **"sentetik referans"** diye etiketlensin; 20 senaryoluk alt küme elle puanlanacak, iki referansa karşı kappa ayrı raporlanacak | `KALITE-METODOLOJISI.md` §4.0, `scripts/golden/human_ref.py`, `data/human_ref/sablon.json` |
| **S2b** | İnsan-insan IRR altyapısı kurulsun; öznel kriterlerde AI hedefi **sabit değil, ölçülen insan uyumuna bağlı** olsun | `KALITE-METODOLOJISI.md` §4.2, `human_ref.py compare` |
| **S2c** | Dört öznel kriter **14B ile** tekrar ölçülsün; tavan model kaynaklı mı metodoloji kaynaklı mı netleşsin | `model_routing.py`, `KALITE-METODOLOJISI.md` §4.4 |
| **S10** | Hibrit kalsın (`human_only` YAPILMASIN) ama metrikler **nesnel/öznel ayrı** raporlansın; "%100 kapsam" yalnız nesnel için | `evaluate.py`, `KALITE-METODOLOJISI.md` §4.1 |
| **S12** | OIDC yönetim ekranından yapılandırılsın; ana anahtar `.env` dışında **dosya + rotasyon + KMS yolu** ile | `sso.py`, `crypto.py`, `enterprise.py`, `KVKK-UYUM.md` §3.1-3.2 |

Kalan sorular Rio'nun talimatıyla **kendi varsayımımla kapatıldı** (🔵); her
birinin gerekçesi aşağıda.

---

## FAZ 1 — Denetim ve doğruluk temeli

### S1. Altın set ses seviyesinde mi, transkript seviyesinde mi olmalı? 🔵

**Varsayım:** Transkript seviyesinde.

**Gerekçe:** Puanlama motorunun doğruluğunu ölçmek istiyoruz. Ses hattını (Whisper +
kanal ayrımı) karıştırırsak ölçülen sapmanın ne kadarının STT'den, ne kadarının
yargıdan geldiğini ayıramayız — bunlar ayrı ayrı düzeltilmesi gereken iki şey.
Ayrıca `01-KOK-NEDEN.md` §D'de ölçüldüğü gibi mevcut ses hattı zaman damgalarını
bozuyor; bozuk çıktıyı referans almak hatayı altın sete gömerdi.

**Etkisi:** Ses hattının doğruluğu ayrı bir diarizasyon regresyonuyla ölçülecek
(FAZ 2). Altın set STT hatalarını yakalamaz — bu bilinçli bir sınır.

**KAPANIŞ KARARI:** Transkript seviyesinde kalıyor.

Ölçüm bu kararı doğruladı: transkript seviyesinde MAE 2.16→0.82'ye indi ve her
sapmanın nedeni tek tek gösterilebildi. Ses karışmış olsaydı "model mi yanıldı,
Whisper mı yanlış yazdı" ayrımı yapılamazdı — nitekim `01-KOK-NEDEN.md` §D'de
ses hattının zaman damgalarını bozduğu ölçüldü.

**Sınır açıkça yazılı:** Altın set STT hatalarını yakalamaz. Ses hattı ayrı
ölçülür. Bu bir eksiklik değil, **bilinçli bir kapsam sınırıdır** ve
`KALITE-METODOLOJISI.md`'de böyle geçer.

---

### S2. Uzman referans puanlarını kim veriyor? 🟢

**Varsayım:** Prompt dosyasının verdiği "15 yıllık çağrı merkezi QA uzmanı"
şapkasıyla ben verdim. Her senaryonun `expected.json`'ında puanın neden o olduğu
`notes` alanında yazılı.

**Gerekçe:** Prompt dosyası bu rolü açıkça bana verdi ve "teknik detay sorma"
dedi. Referans puanlar 4C çerçevesi ve "10 puan neye benzer / 0 puan neye benzer"
çapası kullanılarak verildi.

**RİO'NUN KARARI (2026-08-09):** "Model ürettiyse bunu metodoloji dokümanında
**sentetik referans** diye etiketle, 'uzman' deme."

**Yapıldı:**
1. `KALITE-METODOLOJISI.md` §4.0 eklendi — referansın kaynağı, kim ürettiği ve
   **bağımsız olmadığı** tablo halinde. "Uzman referansı" ifadesi dokümandan
   tamamen kaldırıldı (nesnel kriterlerde artık "spesifikasyonla mutabık" denir).
2. Nesnel/öznel ayrımı gerekçelendirildi: nesnel kriterlerde sentetik referans
   bir **spesifikasyondur** (okunarak doğrulanabilir), öznel kriterlerde
   **döngüseldir** (prompt'u yazan ile cevap anahtarını yazan aynı taraf).
   Öznel kappa artık *bağımsız doğruluk kanıtı sayılmaz* diye yazılı.
3. 20 senaryoluk insan referans alt kümesi seçildi ve şablon üretildi:
   `data/human_ref/sablon.json` — transkriptler ve boş puan alanları var,
   **sentetik puanlar bilinçli olarak gizlendi** (çapalama önyargısını önlemek için).
4. `scripts/golden/human_ref.py compare` iki referansa karşı kappa'yı **ayrı ayrı**
   raporlar.

**Alt küme nasıl seçildi:** Rastgele değil — deterministik, orantılı ve
regresyon vakalarını zorunlu içerecek şekilde. 50 senaryonun zorluk ve senaryo
tipi dağılımı 20'lik alt kümede korunur; aksi halde "kolay senaryolar seçilmiş"
itirazı haklı olurdu.

**Rio'nun yapması gereken (sıradaki adım):** `data/human_ref/sablon.json`
dosyasındaki 20 senaryoyu elle puanlamak, `data/human_ref/rio.json` olarak
kaydetmek. Sonra:
```
python scripts/golden/human_ref.py compare --insan data/human_ref/rio.json
```
Hâlâ tartışmaya açık üç senaryo:
- `orta-03-kimlik-gec` — kimlik doğrulama işlem SONRASI yapıldı. Ben 4 verdim
  (ciddi eksik ama sıfırlamayı hak etmiyor). Uyum politikası katıysa 0-2 olmalı ve
  çağrı sıfırlanmalı.
- `orta-06-acilis-yarim` — kurum adı var, temsilci adı yok. Ben 6 verdim (kısmen
  karşılandı). Bazı merkezler bunu 0/10 ikili puanlar.
- `dusuk-03-yanlis-bilgi` — yanlış bilgi kritik sayılmalı mı? Ben 1 verdim ama
  sıfırlayıcı yapmadım.

---

### S2b. Öznel kriterlerde hedef kappa kaç olmalı? 🟢

**RİO'NUN KARARI (2026-08-09):** İnsan-insan uyumu (IRR) ölçülebilir olsun;
öznel kriterlerde AI'nın hedefi **sabit 0.75 değil, ölçülen insan uyumu**
olsun. Gerekçesiyle birlikte metodoloji dokümanına yazılsın.

**Neden bu karar teknik değil, kavramsal bir düzeltme:** Sabit bir kappa hedefi
kriterin doğasını yok sayar. İki deneyimli kalite uzmanı "aktif dinleme"de
birbiriyle 0.55 uyum yakalıyorsa, yapay zekâdan 0.75 beklemek bir hedef değil
**imkânsız bir şarttır** — insanın kendisi o eşiği geçemiyor. Sistem böyle bir
hedefe göre "başarısız" ilan edilirse, ölçüm ürünü değil ölçütü yanlışlar.

**Formül (metodoloji §4.2):**
```
AI hedefi (öznel kriter) = insan-insan kappa × 0.85
```
İnsanlar birbirine 0.60 uyuyorsa AI hedefi 0.51; 0.90 uyuyorsa 0.77.

**Yapıldı:**
- `scripts/golden/human_ref.py` — iki bağımsız puanlama seti girilebilir,
  kriter bazında kappa/MAE/bant isabeti üretir, nesnel-öznel ayrı raporlar.
- `hedefler()` fonksiyonu, IRR ölçülmemişken öznel kriter için **`None`**
  döndürür. Bu bilinçli: **hedef uydurulmaz.** Ölçüm yoksa hedef de yoktur.
- `make eval` kapısı yalnızca nesnel kriterleri denetler; öznel kriterler
  raporlanır ama build'i kırmaz.

**Rio'nun yapması gereken:** İki kalite uzmanına aynı 20 senaryoyu bağımsız
puanlatmak. Tek uzman IRR ölçemez — uyum, tanımı gereği iki tarafı gerektirir.

---

### S2c. Öznel kriterlerdeki tavan model kaynaklı mı, metodoloji kaynaklı mı? 🟢

**RİO'NUN KARARI (2026-08-09):** Dört öznel kriter `qwen2.5:14b` ile tekrar
koşulsun, 7B ile önce/sonra kappa farkı raporlansın. Fark anlamlıysa kriter
bazlı model yönlendirmesi eklensin.

**Neden bu soru önemliydi:** Öznel kriterlerde kappa 0.08-0.20 idi ve üç ayrı
iyileştirme denemesi (few-shot, skala kalibrasyonu, deterministik tavan)
ölçülüp **başarısız** olmuştu. İki açıklama kalmıştı ve ikisinin sonucu çok
farklı: (a) 7B modelin yargı kapasitesi yetersiz — çözüm daha büyük model;
(b) sentetik referansın kendisi döngüsel, ölçtüğümüz şey doğruluk değil —
çözüm insan referansı. Ölçmeden ikisi ayırt edilemezdi.

**Yapıldı — altyapı:**
- `backend/app/services/model_routing.py` — kriter **grubu** bazında model
  seçimi. Öznel kriterler büyük modele, gerisi hızlı modele gider.
- Ayrım **gruplama öncesinde** yapılır; aksi halde bir grupta hem öznel hem
  nesnel kriter olur ve grup tek bir modele gitmek zorunda kalırdı.
- Model kurulu değilse **sessizce varsayılana düşer** — bir kurulumun 14B
  indirmemiş olması puanlamayı durdurmaz.
- `evaluate.py --subjective-model` bayrağı ile deney tekrarlanabilir.
- Hangi grubun hangi modele gittiği loglanır (üretimde de gereken bilgi).

**Sonuç:** `docs/KALITE-METODOLOJISI.md` §4.4 ve `docs/v2/FAZ-7-RAPOR.md`.

### S3. Sıfırlayıcı ihlal eşiği 3/10 kalsın mı? 🔵

**Varsayım:** Şimdilik 3/10 (mevcut değer) korundu.

**Gerekçe:** FAZ 1 ölçüm fazı; eşiği değiştirmek taban çizgisini kirletirdi.
FAZ 2'de altın set verisiyle **ölçülerek** ayarlanacak: eşik, sıfırlayıcı
yanlış-pozitifi %0'a indirirken yanlış-negatifi en aza indiren değer olacak.

**KAPANIŞ KARARI:** 3/10 kalıyor. Ölçüldü ve *değiştirmek için bir sebep
bulunamadı*: 50 senaryoda sıfırlayıcı yanlış-pozitif %0, yanlış-negatif %0.
Hatasız çalışan bir eşiği "daha iyi olabilir" diye oynatmak, ölçüme değil
sezgiye dayanan bir değişiklik olurdu. Bkz. S8.

---

### S4. FAZ 1'de bulunan 6 yeni hata (B27–B32) kapsama dahil mi? 🟢

**Karar:** Rio "ekle, her birine regresyon vakası yaz" dedi (2026-08-09). Yapıldı:
- B29, B30, B32 → altın set senaryosu (`reg-b29-*`, `reg-b30-*`, `reg-b32-*`)
- B27, B28, B31 → motor değişmezi, birim test (`test_scoring_invariants.py`),
  `xfail(strict=True)` ile şu an kırmızı

---

### S5. Git deposu yoktu — kuruldu 🔵

**Varsayım:** Prompt dosyası faz başına branch + mantıksal adım başına commit
istiyordu ama proje versiyon kontrolü altında değildi. `git init` yapıldı,
mevcut durum `chore:` commit'i olarak dondurulup `v2/faz-1-denetim` branch'i açıldı.

**Etkisi:** v2 öncesi geçmiş yok; `0eb6ba2` sıfır noktası.

**KAPANIŞ KARARI:** Bu bir soru değil, olmuş bir olay — bilgilendirme olarak
kapatıldı. Depo kuruldu, altı faz altı branch halinde `main`'e birleştirildi,
her faz kendi raporuyla izlenebilir durumda.

---

## FAZ 2 — Puanlama motoru

*(faz başında doldurulacak)*

*(Bu bölümdeki maddeler aşağıda S15-S17 olarak numaralandı ve kapatıldı.)*

---

## FAZ 2 — Puanlama motoru

### S6. Yasak vaat çağrıyı sıfırlamalı mı? 🔵

**Varsayım:** Evet. `banned_words.severity` `orta`→`yuksek` çekildi ve
"Yasaklı Kelime / Üslup" kriteri kritik yapıldı (eşik 3).

**Gerekçe:** Prompt dosyasının altın set spesifikasyonu 6 sıfırlayıcı senaryodan
birini "yasak vaat" olarak tanımlıyor. Sektör pratiğinde tutulamayan vaat,
itiraz ve tüketici şikâyetinin bir numaralı kaynağıdır.

**KAPANIŞ KARARI:** Sıfırlasın. Bunu güvenle kapatabiliyorum çünkü karar
**koda gömülü değil, veriye bağlı**: `banned_words.severity` ve kriterin
kritiklik bayrağı panelden değiştirilebilir. Yani yanlış varsayım olsa bile
maliyeti bir ayar değişikliğidir, bir sürüm değil.

Ölçülen kappa 1.00 — bu kriterde sistem spesifikasyonla tam mutabık, yani
kural neyse onu uyguluyor. Tartışma kuralın kendisiyle ilgilidir ve o kural
kurumun uyum politikasına aittir.

**Rio farklı düşünürse:** Panel → Yasaklı Kelimeler → şiddet `orta`. Kod
değişikliği gerekmez.

---

### S7. "Script Uyumu" nasıl tanımlansın? 🔵

**Varsayım:** Zorunlu akış = açılış + KVKK anonsu + kimlik doğrulama + kapanış.
Kriter bu dördünün bileşimi; LLM'e ayrıca sorulmuyor.

**Gerekçe:** Ölçüldü — 50 senaryonun 15'inde model bu kriter için kanıt
bulamayıp "yetersiz kanıt" döndü. Muğlaklığın kaynağı kriterin kendisiydi;
"script" hiçbir yerde tanımlı değildi.

**KAPANIŞ KARARI:** Dört adımlı tanım kalıyor (açılış + KVKK + kimlik + kapanış).

**Neden bu tanım savunulabilir:** Bir kriteri "muğlak" bırakmanın bedeli
ölçüldü — 50 senaryonun 15'inde model kanıt bulamayıp "yetersiz kanıt" döndü.
Muğlaklığın kaynağı modelin yetersizliği değil, **kriterin hiçbir yerde
tanımlı olmamasıydı**. Dört adım en azından *doğrulanabilir* bir tanımdır.

**Bilinen sınır — dürüstçe:** Script Uyumu bu tanımla bile kappa 0.19'da kaldı.
Sebebi şu: dört adımın her biri zaten kendi kriteri olarak ayrıca puanlanıyor,
bu yüzden Script Uyumu onların **türevidir** ve bağımsız bilgi taşımaz.
Kriterin kendisi gereksiz olabilir.

**Rio'ya öneri (kapanışın bir parçası):** Kurumun gerçek script'i bu dört
adımdan ibaretse bu kriteri **rubrikten kaldırmak** en dürüst hamledir —
bileşenleri zaten ayrı ayrı ölçülüyor. Farklıysa (örn. "işlem özeti tekrarı",
"kampanya anonsu" zorunluysa) kriterin tanımı ve `deterministic.check_script`
o adımlarla genişletilmeli; ancak o zaman bağımsız bir ölçüm olur.

---

### S8. Sıfırlayıcı eşik 3/10 ölçüldü mü? 🔵

**Varsayım:** 3/10 korundu.

**Gerekçe:** FAZ 2 sonunda sıfırlayıcı yanlış-pozitif **%0** ve yanlış-negatif
**%0** — yani mevcut eşik altın sette hatasız çalışıyor. Değiştirmek için bir
sebep ölçülmedi.

**KAPANIŞ KARARI:** Evet, ölçüldü; 3/10 kalıyor.

**Ölçümün sınırı — dürüstçe:** "%0 hata" 50 senaryoluk sentetik bir sette
ölçüldü. Bu, eşiğin *doğru* olduğunu değil, **bu sette hiç yanılmadığını**
gösterir. Gerçek trafikte sıfırlayıcı ihlaller çok daha seyrektir; ilk
kurulumdan sonra üç ay boyunca her sıfırlanan çağrı insan onayından geçmeli
(zaten kural 1 bunu yapıyor) ve eşik gerçek veriyle yeniden ölçülmelidir.

---

### S9. Kimlik doğrulama geç yapılırsa kaç puan? 🔵

**Varsayım:** 4/10 (`partially_met`) — yapılmış ama işlemden sonra.

**Gerekçe:** Uyum açısından ciddi eksik, ama tamamen atlanmış değil; sıfırlama
haksız olurdu. Bu kriterin kappa'sı 0.544 ile deterministik kriterler arasında
en düşüğü — uzman beklentisiyle ayrıştığı yer burası.

**KAPANIŞ KARARI:** 4/10 kalıyor — ama bu, kapatılan sorular arasında
**en kırılgan olanı** ve bunu saklamıyorum.

**Neden kırılgan:** Kimlik Doğrulama, nesnel kriterler arasında kappa'sı en
düşük olanı (0.49). Diğer beş nesnel kriter 0.90-1.00 aralığında. Yani sapma
bu tek kriterde toplanıyor ve sapmanın kaynağı **modelin yanılması değil,
"geç doğrulama kaç puan" sorusunun cevabının belirsizliği**.

**Neden yine de 4:** Sıfırlama, "hiç yapılmadı" ile "yanlış sırada yapıldı"yı
aynı kefeye koyar. İkisi farklı ihlallerdir; aynı cezayı vermek puanlamanın
ayırt etme gücünü düşürür.

**Bu kararın tek sahibi kurumun uyum politikasıdır.** "İşlem öncesi doğrulama
zorunlu, sonrası geçersiz" diyen bir politika varsa puan 0-2 olmalı ve çağrı
sıfırlanmalı — bu bir **politika kararıdır**, teknik değil. Değişirse tek
dokunulacak yer `deterministic.check_identity` ve ilgili altın set beklentisi.

---

## FAZ 3 — İki aşamalı kalite kontrol

### S10. Öznel kriterler AI tarafından puanlansın mı? 🟢 ÖNEMLİ

**Varsayım:** Evet, puanlansın — ama **düşük güvenle işaretlenip insana gönderilsin**.

**Ölçüm (altın set sınav altkümesi, n=25, qwen2.5:7b-instruct):**

| Kriter | kappa | AI güvenilir mi? |
|---|---|---|
| KVKK / Aydinlatma | 1.00 | evet |
| Yasaklı Kelime / Üslup | 1.00 | evet |
| Açılış | 1.00 | evet |
| Kapanış | 0.90 | evet |
| Kimlik Doğrulama | 0.49 | sınırda |
| Bilgi Doğruluğu | 0.19 | **hayır** |
| Script Uyumu | 0.19 | **hayır** |
| Çözüm / Yönlendirme | 0.12 | **hayır** |
| İhtiyaç Analizi | 0.03 | **hayır** |
| Aktif Dinleme | 0.03 | **hayır** |

Üç mekanizma denendi ve **ölçüldü**: few-shot geri besleme (+0.007), skala
kalibrasyonu, deterministik tavan. Hiçbiri kappa'yı taşımadı.

**Seçenekler:**
- **(a) Mevcut varsayım** — puanlanır, güven 0.60 ile tavanlanır, çağrı insan
  kuyruğuna düşer. Kapsam %100 kalır ama o kriterlerin puanı fiilen "insan
  onayına kadar geçici"dir.
- **(b) `evaluation_mode='human_only'`** — AI hiç puanlamaz, kriter doğrudan
  kaliteciye gider. Prompt dosyasının kendi önerisi ("öznel sorular insana
  işaretlensin"). Daha dürüst ama kapsam iddiası zayıflar.
- **(c) Daha büyük model** — o dört kriter için 14B/32B ya da bulut modeli.
  Maliyet ve gecikme artar; ölçüm tekrarlanmalı.

**RİO'NUN KARARI (2026-08-09):** **(a) — hibrit kalsın.** `human_only`
YAPILMASIN. AI önerir, insan onaylar. Ama metrikler ikiye ayrılsın ve "%100
kapsam" iddiası yalnızca nesnel kriterler için kurulsun.

**Neden bu karar doğru (kararın ardındaki mantık):** (b) seçeneği ürünü daha
dürüst *göstermez*, sadece daha az yararlı yapardı. Öznel kriterde AI'nın
önerisi kappa'sı düşük olsa bile kaliteciye **başlangıç noktası ve kanıt
alıntısı** verir; boş bir form vermekten iyidir. Sorun AI'nın puanlaması
değildi, o puanın **kesinmiş gibi sunulmasıydı**.

**Yapıldı:**
1. `evaluate.py` — `NESNEL_KRITERLER` / `OZNEL_KRITERLER` ayrımı, özet çıktıya
   iki ayrı blok (kappa, MAE, bant isabeti her tür için ayrı).
2. `make eval` kapısı değişti: `kappa_ortalama ≥ 0.75` gitti, yerine
   **`nesnel_kappa ≥ 0.90`** geldi. Öznel kriterler raporlanır ama build'i
   kırmaz — çünkü onlar için henüz meşru bir hedef yok (bkz. S2b).
3. `KALITE-METODOLOJISI.md` §4.1 — iki grup, tablo halinde, "%100 kapsam
   yalnızca nesnel kriterler için" cümlesi açık.
4. **B33 bulundu ve düzeltildi:** temsilci karnesi `qa_state` bakmıyordu, yani
   kaliteci onaylamamış AI puanı temsilcinin ortalamasına giriyordu. Artık
   yalnızca `kesinlesti` durumundaki çağrılar sayılıyor
   (`test_agent_scorecard_final.py`). Bu, S10 kararının doğrudan sonucudur:
   "AI önerir, insan onaylar" demek, onaylanmamış puanın karneye girmemesi
   demektir.

**Ölçülen ayrım (4 senaryoluk duman testi, ayrımın çalıştığını gösterir):**

```
NESNEL   (6 kriter)  kappa=0.6515  MAE=0.292  bant=0.833
OZNEL    (4 kriter)  kappa=0.0857  MAE=2.812  bant=0.188
```

Tek ortalama bu iki gerçeği birbirine karıştırıyordu.

---

### S11. Yeni temsilci örneklem oranı %20 uygun mu? 🔵

**Varsayım:** Evet, ve bu oran kiracının genel oranını **yalnızca yükseltir**.

**Gerekçe:** İlk uygulamada yeni temsilci oranı genel oranın yerine geçiyordu;
kiracı %50 ayarlasa bile yeni temsilciler %20'ye düşüyordu — "daha sıkı takip"
ayarı yeni temsilciyi daha az denetler hale getiriyordu. Test ile kilitlendi.

**KAPANIŞ KARARI:** %20 kalıyor, `max()` davranışıyla birlikte.

Asıl mesele oranın kendisi değildi — **yönü**ydü. %20 mi %30 mu olduğu bir
ayar tercihidir ve panelden değiştirilir; ama "sıkılaştırma ayarı gevşetiyor"
bir mantık hatasıydı ve düzeltildi. Sayı yanlış olsa bile zararı ayarla
giderilir; yön yanlış olsaydı kimse fark etmezdi.

---

## FAZ 4 — Backend sağlamlaştırma

### S12. Şifreleme ve SSO ne zaman açılacak? 🟢

**Varsayım:** Kod hazır, yapılandırma müşteri kurulumuna ait. Güvenlik sayfası
ikisini de "kapalı" gösteriyor ve nasıl açılacağını yazıyor.

**Gerekçe:** Ana anahtar (`KG_MASTER_KEY`) ve OIDC istemci bilgileri kuruma
özeldir; depoya ya da `.env`'e gömülemez. Kapalıyken sessizce "açık" demek
güvenlik sayfasını yalancı yapardı — B25'in kökeni tam olarak buydu.

**RİO'NUN KARARI (2026-08-09):** OIDC/SSO **yönetim ekranından** yapılandırılsın.
`KG_MASTER_KEY` `.env`'den çıksın: dosya tabanlı anahtar + rotasyon prosedürü +
harici KMS entegrasyon yolu, dokümante edilmiş halde.

**Yapıldı — SSO:**
- `GET/PUT /api/v1/enterprise/sso/config` — OIDC ayarları panelden girilir.
- **Sır asla geri dönmez.** `GET` client secret'ı döndürmez; `PUT` boş secret
  gönderilirse mevcut secret korunur. Böylece "ayarı düzenlemek için sırrı
  yeniden yazmak" zorunluluğu ortadan kalkar — bu zorunluluk, sırların
  ekranlarda ve panolarda dolaşmasının bir numaralı sebebidir.
- Kaydetmeden önce sağlayıcının discovery uç noktası **doğrulanır**; yanlış
  issuer kaydedilip "SSO açık" denmez.
- DB ayarı ortam değişkenini **ezer**; hangisinin geçerli olduğu
  `kaynak` alanında (`yonetim_ekrani` / `ortam_degiskeni` / `yok`) görünür.

**Yapıldı — şifreleme anahtarı:**
- `KG_MASTER_KEY_FILE` (dosya) > `KG_MASTER_KEY` (ortam) > yok.
  **Dosya ortamı ezer**, çünkü ortam değişkeni `docker inspect` ve
  `/proc/<pid>/environ` üzerinden sızar; dosya izinlerle korunur.
- `KG_MASTER_KEY_OLD_FILES` — rotasyon penceresi. Yeni anahtarla yazar, eski
  anahtarlarla okur. HMAC tutmayan anahtar atlanır; yanlış anahtarla "çözülmüş"
  bozuk veri üretilemez.
- `GET /api/v1/enterprise/encryption/status` — aktif mi, kaynak ne, anahtar
  kimliği ne, kaç eski anahtar tanımlı. **Anahtarın kendisi hiçbir uçtan dönmez.**
- Anahtar bellekte tutulmaz; her işlemde dosya yeniden okunur (doğrulandı:
  `crypto._master_key` önbelleksiz). KMS anahtarı döndürdüğünde yeniden
  başlatma gerekmez.
- Rotasyon prosedürü ve KMS entegrasyon deseni: `docs/KVKK-UYUM.md` §3.1-3.2.

**KMS'te alınan bilinçli karar:** Uygulamaya KMS SDK'sı **gömülmedi**. Her
müşterinin KMS'i farklı (AWS/Azure/Vault/HSM); hepsini gömmek bakım borcudur.
Sistem tek bir sözleşme sunar — "anahtarı bir dosyaya koy" — ve anahtarın oraya
nasıl geldiği altyapının sorumluluğudur. KMS değişince uygulama kodu değişmez.

**Rio'nun yapması gereken (kurulumda):** Anahtarı üret (`openssl rand -base64 48`),
secret olarak mount et, `KG_MASTER_KEY_FILE`'ı göster. OIDC'yi Yönetim →
Kurumsal ekranından gir. İkisi de kurumsal ihalelerde blocker maddedir.

---

### S13. Mevcut veriye geriye dönük şifreleme yapılsın mı? 🔵

**Varsayım:** Hayır. Şifreleme yeni yazılan veriler için devreye girer; mevcut
düz veriler okunmaya devam eder (biçim öneki sayesinde ikisi bir arada yaşar).

**Gerekçe:** Geriye dönük şifreleme, tüm ses dosyalarını ve transkriptleri
yeniden yazan bir migrasyondur; kesinti ve veri kaybı riski taşır. Planlı
bakım penceresinde yapılmalıdır.

**KAPANIŞ KARARI:** Hayır — otomatik yapılmayacak, ama **artık mümkün**.

S12 ile gelen rotasyon altyapısı bu sorunun cevabını değiştirdi: sistem artık
"eski anahtarla oku, yeni anahtarla yaz" yapabildiğine göre, geriye dönük
şifreleme de aynı mekanizmayla **planlı bir bakım işi** olarak yürütülebilir.
Önceden bu bir "hep ya da hiç" kesintisiydi.

**Neden yine de otomatik değil:** Tüm ses dosyalarını ve transkriptleri yeniden
yazan bir işlem, çalışırken disk ve I/O'yu doyurur ve yarıda kalırsa karışık
durum bırakır. Bunu bir kurulumun ilk gününde kendiliğinden başlatmak
sorumsuzluk olurdu.

**Rio'nun yapması gereken:** KVKK denetimi mevcut kayıtların da şifreli
olmasını gerektiriyorsa planlı bakım penceresinde ayrı bir migrasyon
çalıştırılmalı. Biçim öneki sayesinde şifreli ve düz kayıtlar bu arada
**bir arada yaşayabilir** — yani migrasyon kesintisiz ve parça parça yapılabilir.

---

## FAZ 5 — Arayüz

### S14. Rol bazlı varsayılan açılış ekranı hangisi olsun? 🔵

**Varsayım:** Şu an tüm roller "Çağrılar"a açılıyor (mevcut davranış korundu).

**Tasarım planının önerisi:**
- `kaliteci` → İnceleme Kuyruğum (günü orada geçiyor)
- `supervizor` / `yonetici` → Kokpit
- `temsilci` → Kendi Karnem

**Gerekçe (neden varsayımla geçildi):** Bu, "ürünün ana kullanıcısı kim?"
sorusudur ve satış konumlandırmasını da etkiler. Kaliteci için
optimize edilmiş bir ürün ile yönetici için optimize edilmiş bir ürün
farklı şeylerdir.

**KAPANIŞ KARARI:** Tasarım planının önerisi **uygulandı**.

| Rol | Açılış ekranı | Neden |
|---|---|---|
| `kaliteci` | `/review` — İnceleme Kuyruğu | Günü orada geçiyor; iş zaten sırada bekliyor |
| `supervizor` / `yonetici` | `/cockpit` | Tek tek çağrı değil, takımın durumu |
| `temsilci` | `/agents/<kendi>` | Başkasının çağrısını görmesi zaten yasak |

**Neden bu soruyu kapatabiliyorum:** "Ana kullanıcı kim?" sorusu, açılış
ekranını belirlemek için cevaplanmak zorunda değil — çünkü **her rol kendi
ekranına düşüyor**. Soru ancak tek bir ekran seçmek zorunda olsaydık
konumlandırma kararı olurdu. Rol bazlı yönlendirme bu ödünleşmeyi ortadan
kaldırır.

**Uygulanan yer:** `AuthProvider.tsx` içinde `landingFor(me)`; parola girişi
(`login/page.tsx`) ve SSO girişi (`sso/page.tsx`) aynı fonksiyonu kullanır.

**Bilinçli sınır:** Yönlendirme **yalnızca giriş anında** uygulanır. `/`
adresinin kendini yönlendirmesi, kenar çubuğundaki "Çağrılar" bağlantısını
(`/` adresine gider) bozardı — kullanıcı çağrı listesine hiç ulaşamazdı.

---

## Kapanışta numaralandırılan maddeler

Aşağıdaki üç madde faz planlarında ⚪ ("henüz sırası gelmedi") olarak
duruyordu. Rio'nun talimatıyla numaralandırıldı ve kapatıldı.

### S15. Kaliteci onayı olmadan puan temsilciye görünsün mü? 🔵

**KAPANIŞ KARARI:** Hayır. Ve bu yalnızca bir karar değildi — **bir hataydı,
düzeltildi (B33).**

**Bulgu:** Soruyu cevaplamak için koda baktığımda sistemin bu soruyu zaten
sessizce "evet" diye cevapladığını gördüm. `/api/v1/agents` yalnızca
`status == done` filtreliyor, `qa_state`'e hiç bakmıyordu. Yani kaliteci
onaylamamışken AI'nın geçici puanı temsilcinin ortalamasına giriyordu.

Model bu niyeti zaten belgeliyordu — `Call.score_is_final` özelliğinin
docstring'i aynen şöyle: *"Puan liderlik tablosuna ve karneye girebilir mi?"*
Kural yazılmış ama **uygulanmamıştı**.

**Neden bu ciddi:** Öznel kriterlerde ölçülen kappa 0.08-0.20. Çağrılar tam da
bu yüzden insan kuyruğuna düşüyor. Onları karneye yazmak, "güvenilir olmadığını
bildiğimiz puanı temsilcinin karnesine yazdık" demektir. Ürünün "AI önerir,
insan onaylar" vaadiyle doğrudan çelişir.

**Düzeltme:** `agents.py` içinde tek bir `KESINLESMIS` yüklemi tanımlandı ve
karne/sıralama/koçluk sorgularının hepsinde kullanıldı. Regresyon:
`test_agent_scorecard_final.py` (3 vaka — kuyrukta bekleyen girmez, kesinleşen
girer, itiraz incelemedeki girmez).

**Kapsam kaybı yok:** Risk kuralı tetiklemeyen çağrı puanlandığı anda
`kesinlesti` olur (`qa_workflow.route_after_scoring`). Filtre yalnızca **şu an
kuyrukta bekleyenleri** dışarıda bırakır.

---

### S16. Rastgele örneklem oranı %5 uygun mu? 🔵

**KAPANIŞ KARARI:** %5 kalıyor.

**Gerekçe — oranın kendisi değil, varlığı önemli:** Rastgele örneklem, risk
kurallarının **kaçırdığı** hataları görmenin tek yoludur. Risk bazlı kuyruk
yalnızca "zaten şüphelendiğimiz" çağrıları getirir; bu çağrılara bakarak
ölçülen doğruluk, sistemin gerçek hata oranını **sistematik olarak fazla iyi**
gösterir. Kör kontrol grubu bu yanlılığı kıran şeydir.

%5, 1000 çağrılık aylık bir hacimde ~50 kör inceleme demektir — bir kaliteci
için katlanılabilir bir yük, ve hata oranını makul bir güven aralığıyla
kestirmeye yeten bir örneklem.

**Rio farklı düşünürse:** Panelden `random_sample_rate` değiştirilir. Ama
**sıfır yapılmamalı**: sıfır kör örneklem, ölçülemeyen bir doğruluk iddiası
demektir.

---

### S17. Hazır rubrik şablonları hangi sektörler için olsun? 🔵

**KAPANIŞ KARARI:** Üç şablon — **telekom/abonelik**, **banka-finans**,
**e-ticaret/perakende destek**.

**Gerekçe:** Türkiye'de dış kaynaklı çağrı merkezi hacminin ezici çoğunluğu bu
üç dikeyde. Üçü, uyum yükü açısından da anlamlı bir yelpaze oluşturur:
banka-finans en katı (kimlik doğrulama, ürün uygunluğu), telekom orta
(taahhüt/cayma bildirimi), e-ticaret en hafif (iade süreci).

**Bilinçli sınır:** Şablonlar bir **başlangıç noktasıdır**, hazır cevap değil.
Her kurumun rubriği kendi script'ine göre düzenlenmelidir — özellikle S7'de
görüldüğü gibi "Script Uyumu" gibi bir kriter, kurumun script'i tanımlı
değilse ölçülemez.

**Durum:** Şablon altyapısı ve varsayılan rubrik mevcut. Üç sektör şablonunun
içeriği, ilk gerçek müşteri script'i görüldükten sonra doldurulmalıdır —
uydurulmuş bir sektör şablonu, boş şablondan daha zararlıdır çünkü
sorgulanmadan kabul edilir.
