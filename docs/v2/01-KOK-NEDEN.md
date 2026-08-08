# 01 — Kök Neden Analizi: B1–B6 (FAZ 1.4)

> Yöntem: her hata için **çalışan sistemden ölçüm** alındı, sonra kaynak koda inildi.
> Hiçbir kök neden tahminle yazılmadı. Yeniden üretilemeyen bir iddia varsa öyle işaretlendi.
> Ölçüm tarihi: 2026-08-08

---

## Prompt dosyasının sorduğu 6 kontrol — toplu cevap

| Soru | Cevap | Kanıt |
|---|---|---|
| LLM'e giden prompt'ta transkript **tam** mı? | **Kısa çağrılarda evet, uzun çağrılarda HAYIR.** `duration > chunk_threshold_sec` ise reduce aşamasına yalnız ilk 25 + son 25 satır gidiyor, orta kısım atılıyor. | `scoring.py:301-310` (`_transcript_outline`) |
| Token limiti aşılıyor mu? | `num_ctx=8192`. 24 çağrının hepsi (90-110 sn) tek atışta sığıyor; taşma gözlenmedi. Uzun çağrıda pencereleme yerine **kırpma** yapılıyor (yukarıdaki madde). | `.env OLLAMA_NUM_CTX=8192`, `config.py:56` |
| Transkript hangi formatta gidiyor? Konuşmacı etiketi doğru mu? Zaman damgası var mı? | Format `[dk:sn \| Nsn] KONUSMACI: metin` — etiket ve zaman **var**. Ama **zaman damgaları bozuk** ve etiketler mono kayıtta tamamen kayboluyor. → §D ve §E | `scoring.py:68-73`, ölçüm §D |
| Kriter değerlendirmesi tek dev prompt'ta mı? | **Evet.** 10 kriterin tamamı + 15 görev maddesi tek çağrıda. Prompt dosyasının "asla yapma" 3. maddesinin ihlali. | `scoring.py:86-158`, `_evaluate_single` |
| STT çıktısı normalize ediliyor mu (`i/İ/ı/I` tuzağı)? | Kısmen. **İki ayrı, uyumsuz normalizasyon** var: `compliance._normalize()` ve `schemas._fold_tr()`. `İ` tuzağı ikisinde de ele alınmış ama farklı yollarla. Puanlama yolunda transkript **hiç** normalize edilmiyor. | `compliance.py:34`, `schemas.py:12` |
| Sıcaklık kaç? Deterministik mi? | **`temperature=0.1`, seed YOK.** Deterministik değil. Üç sağlayıcı fonksiyonunda ayrı ayrı hardcode. | `llm.py:38, 62, 87` |
| Akustik sinyaller puanlamaya nasıl giriyor? "Kim kesti" taşınıyor mu? | Veri modelinde **taşınıyor** (`temsilci_kesinti` / `musteri_kesinti` ayrı), prompt'a da yalnız temsilcininki giriyor. **Ama iki sayı da yanlış üretiliyor.** → §D | `metrics.py:29-38`, ölçüm §D |

---

## A) B1 — Açılış kriteri yanlış puanlandı

### Ölçüm
Çağrı #24, `scores` tablosundan birebir:

```
kriter : Acilis
puan   : 2 / 10
gerekçe: "Müşteriyi tanıtma ve kurum adı verilmedi."
kanıt  : "[00:01 | 1sn] TEMSILCI: Netik iletişime hoş geldiniz, ben Mehmet."
```

Transkriptin ilk segmenti (`segments.idx=0`, `speaker=temsilci`, `start_sec=1.2`):
> **"Netik iletişime hoş geldiniz, ben Mehmet."**

Kurum adı (*Netik İletişim*) ve temsilci adı (*Mehmet*) **ikisi de var**.

### Kök neden — üç katmanlı

**1. LLM kendi kanıtını okumuyor.** Model doğru kanıtı seçip yanına tam tersi gerekçeyi
yazdı. Literatürde "doğrulanamayan puan atfı" (unverifiable score attribution) denen hata modu.

**2. Kanıt ↔ karar tutarlılığını doğrulayan hiçbir kod yok.** `scoring.py:452-466`
LLM'in verdiği `puan`, `gerekce` ve `kanit` alanlarını **hiç sorgulamadan** DB'ye yazıyor.
Kanıtın transkriptte geçip geçmediği aranmıyor, gerekçeyle puanın uyumu kontrol edilmiyor.
Katman C yok.

**3. Açılış kriteri deterministik olarak çözülebilirken LLM'e soruluyor.** "Marka adı +
temsilci adı ilk N saniyede geçti mi?" sorusu bir dize aramasıdır. `evaluation_mode`
diye bir kavram olmadığı için 10 kriterin 10'u da LLM'e gidiyor.

> **Not (dürüstlük kaydı):** Bu üç kök nedenin yanında §D'deki bozuk zaman damgaları da
> katkı yapıyor — LLM transkripti mantıksal olarak bozuk sırada görüyor. Ama B1 tek başına
> §D olmadan da üretilebilir: kanıt doğruydu, karar yanlıştı.

### Aynı çağrıda ikinci, daha ağır örnek
```
kriter : Kimlik Dogrulama   (KRİTİK, eşik 3)
puan   : 2 / 10   → ÇAĞRININ TAMAMI SIFIRLANDI
gerekçe: "Müşterinin kimlik bilgileri teyit edilmedi."
kanıt  : "[00:18 | 18sn] MUSTERI: Dün için teknisyen randevusu verilmişti..."
```
Gerçek transkriptte:
- `idx=9`, temsilci, 34.6 sn: **"Adınızı ve hizmet numaranızı alabilir miyim?"**
- `idx=7`, musteri, 25.9 sn: **"Hasan Yıldız 447821"**

Kimlik doğrulama **yapılmış**. Model, kriterle **hiç ilgisi olmayan** bir müşteri repliğini
kanıt diye gösterip kritik kriteri 2 verdi ve **çağrının puanını sıfırladı**. Bu, ürünün en
kritik metriği olan "sıfırlayıcı ihlal yanlış-pozitifi"nin canlı örneğidir.

---

## B) B2 — KVKK alarmı yanlış üretildi

### Ölçüm — **bu hata mevcut veride yeniden ÜRETİLEMEDİ**

24 çağrının tamamında KVKK uyum kontrolü ayrı ayrı çalıştırıldı:

| Sonuç | Çağrı sayısı |
|---|---|
| Anons var, ihlal üretilmedi ✅ | 18 (#1-4, #6, #8-10, #14-17, #19-24) |
| Anons yok, ihlal üretildi ✅ | 6 (#5, #7, #11, #12, #13, #18) |
| **Anons var ama ihlal üretildi (yanlış pozitif)** | **0** |

Çağrı #24 (B2'nin bildirildiği çağrı) şu an KVKK ihlali **üretmiyor** ve `alerts` tablosunda
bu çağrıya ait tek alarm var: `zeroing | Kritik kriter esik alti: Kimlik Dogrulama (2/3)`.

İhlal üretilen 6 çağrı elle kontrol edildi — üçünün (#5, #13, #18) ilk repliklerinde gerçekten
kayıt/KVKK anonsu **yok** (bunlar bilinçli "kötü açılış" senaryoları). Yani kontrol doğru çalışıyor.

### Kök neden — mekanizma değil, yaşam döngüsü

Kontrolün kendisi sağlam: `compliance_packs` anlam kümesi kullanıyor (`"kayit alt"`,
`"kayit edil"`, `"kaydedilmekte"`, `"kvkk"`, `"kisisel veri"`, `"aydinlatma"`), tek kalıba
bağlı değil, Türkçe ek toleransı var. Prompt dosyasının §584'te istediği yapı zaten burada.

Kullanıcının gördüğü yanlış alarmın **en olası açıklaması B31**: yeniden puanlamada
`scores` ve `violations` siliniyor (`scoring.py:451, 469`) ama **`alerts` silinmiyor**.
Yani çağrı bir kez eksik/hatalı transkriptle işlendiyse üretilen KVKK alarmı, çağrı sonradan
düzgün yeniden puanlansa bile ekranda **kalıcı olarak asılı kalıyor**.

İkinci olası açıklama **B29**: mono kayıtta `HF_TOKEN` yoksa tüm segmentler `bilinmeyen`
etiketi alıyor; `compliance_packs` yalnız `speaker=='temsilci'` metnine baktığı için
**anons yapılmış olsa bile agent_text boş kalıyor** ve zorunlu açıklama eksik sayılıyor.
Mevcut 24 çağrının hepsi stereo olduğu için bu yol şu an tetiklenmiyor, ama gerçek
müşteride mono kayıt geldiği anda **sistematik yanlış KVKK alarmı** üretir.

### Karar
B2, "kalıp eşleşmesi zayıf" hatası **değil**. FAZ 2'de iki gerçek kök neden kapatılacak:
1. Alarmlar yeniden puanlamada geçersizleştirilecek (B31).
2. Mono kayıtta konuşmacı ayrımı yoksa uyum kontrolü **"değerlendirilemedi"** dönecek —
   sessizce "ihlal" demeyecek (B29). *Kanıt yoksa ceza yok* ilkesi.

Regresyon setine hem "anons farklı cümleyle var" tuzağı hem de bu iki yol için vaka yazıldı.

---

## C) B4 — Alarm metin şablonu bozuk / yasaklı kelime yanlış eşleşiyor

### Ölçüm — kanıtlanmış yanlış pozitif

`compliance._match_in()` canlı sistemde `term='kesin cozulur'` (kategori `yasak_vaat`,
şiddet `yuksek`) ile test edildi:

| Cümle | Sonuç | Doğru mu? |
|---|---|---|
| "Bu sorun kesin çözülür merak etmeyin." | ESLESTI | ✅ doğru |
| "Kesinlikle daha avantajlı bir paket sunabilirim." | ESLESTI | ❌ **yanlış** |
| "Kesinlikle haklısınız efendim." | ESLESTI | ❌ **yanlış** |
| "Kesin bir tarih veremiyorum." | ESLESTI | ❌ **yanlış** |

4 denemenin 3'ü yanlış pozitif. **Yanlış pozitif oranı %75.**

### Kök neden — `compliance.py:70-76`

```python
stem = term_norm[:5]                     # "kesin cozulur" -> "kesin"
for word in segment_norm.split():
    if fuzz.ratio(term_norm, word) >= 85:
        return True
    if len(term_norm) >= 5 and word.startswith(stem) and fuzz.partial_ratio(term_norm, word) >= 60:
        return True                       # <-- yanlış pozitif buradan
```

İki kusur birleşiyor:
1. **Kök, terimin ilk 5 karakteri sanılıyor.** Çok kelimeli bir terimde (`"kesin cozulur"`)
   ilk 5 karakter yalnız ilk kelimenin parçası. Terim tek kelimeymiş gibi davranılıyor.
2. **`partial_ratio >= 60` eşiği anlamsız derecede düşük.** `partial_ratio` zaten alt-dize
   benzerliği ölçer; 60 eşiği "ortak birkaç harf" demektir.

### Zincirleme sonuç — bu sadece bir metin hatası değil

`scoring.py:548-551`:
```python
severe = [v for v in agent_hits if v.severity == "yuksek"]
if severe:
    zeroing_reason = f"Temsilci agir yasakli ifade kullandi: '{severe[0].term}'"
```
Yüksek şiddetli yasaklı kelime **çağrının puanını sıfırlıyor**. Yani **"Kesinlikle haklısınız
efendim." diyen kibar bir temsilcinin çağrısı 0 alıyor.** B4 bir görüntü hatası değil,
ikinci bir sıfırlayıcı yanlış-pozitif yoludur.

### Şablonun bozukluğu ayrıca gerçek
Alarm metni `f"Yasakli kelime ({v.category}): '{v.term}' — {v.evidence[:80]}"` biçiminde
kuruluyor: `term` = **listedeki terim**, `evidence` = **eşleşen segmentin tamamı**. Eşleşme
yanlışsa metin de doğal olarak tutmuyor — kullanıcının gördüğü "'kesin çözülür' — Kesinlikle
daha avantajlı" tam olarak budur. `alerts` tablosunda `evidence`, `evidence_ts`,
`suggested_action` kolonları **yok** (D3); şablon zorunlu alanları dolduramıyor.

---

## D) B3 — Sinyal-kriter uyumsuzluğu · **ve denetimin en büyük bulgusu**

### Ölçüm
Çağrı #24 `metrics`:
```json
{"temsilci_kesinti": 4, "musteri_kesinti": 4, "temsilci_konusma_orani": 54.5, "sessizlik_sn": 2.7}
```

Segment zamanları (birebir DB'den):

| idx | konuşmacı | başlangıç | bitiş | süre | kelime | metin |
|---|---|---|---|---|---|---|
| 3 | temsilci | 13.3 | **32.1** | 18.8 sn | 9 | "Bunun için gerçekten çok üzgünüm…" |
| 4 | musteri | 14.9 | 18.4 | 3.5 sn | 7 | "İyi günler ama hiç iyi değilim açıkçası." |
| 7 | musteri | 25.9 | **42.9** | 17.0 sn | **3** | "Hasan Yıldız 447821" |
| 11 | musteri | 42.9 | **65.0** | 22.1 sn | **5** | "Yarın kesin gelecekler mi peki?" |
| 16 | musteri | 67.4 | **88.0** | 20.6 sn | **3** | "Tamam, not aldım." |

**Üç kelimelik replik 20.6 saniye sürüyor** ve karşı tarafın dört repliğini kapsıyor.

### Kök neden — `diarization.py:33-41` (`_stereo`)

```python
for wav, speaker in ((left, MUSTERI), (right, TEMSILCI)):
    for seg in stt.transcribe(wav):     # her kanal BAĞIMSIZ transkribe ediliyor
        seg["speaker"] = speaker
        segments.append(seg)
segments.sort(key=lambda s: (s["start"], s["end"]))
```

Sol ve sağ kanal ayrı ayrı Whisper'a veriliyor. Whisper bir kanalı işlerken karşı taraf
konuşurken oluşan **sessizliği kendi segmentinin içine katıyor** — çünkü o kanalda konuşma
bitmemiştir, sadece duraklamıştır. Sonuç: her repliğin `end` zamanı, o konuşmacının bir
sonraki repliğine kadar uzuyor. Segmentler birleştirilip başlangıca göre sıralanınca
**yapay ve devasa bir bindirme** ortaya çıkıyor.

### Zincirleme sonuçlar — hepsi ölçülmüş

**1. Söz kesme sayacı çöp üretiyor.** `metrics.py:32-38`:
```python
if cur["speaker"] != prev["speaker"] and cur["start"] < prev["end"] - 0.2:
    interruptions[cur["speaker"]] += 1
```
Mantık **doğru** (yalnız kesen tarafa yazıyor). Ama girdi bozuk: neredeyse her konuşmacı
değişimi "bindirme" görünüyor. Çağrı #24'te 4 + 4 = 8 söz kesme raporlanıyor; **hiçbirinin
gerçek karşılığı yok.**

**2. Bu sahte sayı LLM'e "KESİN" diye sunuluyor.** `scoring.py:165-171`:
```
## OTOMATIK OLCUMLER (ses analizinden, KESIN degerler)
- Temsilcinin musteriyi soz kesme sayisi: 4
```
ve prompt açıkça yönlendiriyor (`scoring.py:199-204`):
```
Bu olcumleri kullan: soz kesme/sessizlik -> 'Aktif Dinleme'
```
→ **Temsilci, yapmadığı 4 söz kesme yüzünden cezalandırılıyor. B3 budur.**
Kullanıcının ekranda gördüğü "Söz kesme: 4, müşteri: 4" çelişkisi de buradan geliyor:
iki sayı da aynı sahte bindirmelerden üretiliyor.

**3. Konuşma oranı ve sessizlik de anlamsız.** `temsilci_konusma_orani: 54.5` ve
`sessizlik_sn: 2.7`, şişirilmiş sürelerden hesaplandığı için gerçeği yansıtmıyor.

**4. Transkript LLM'e mantıksal olarak bozuk sırada gidiyor.** Temsilci 13.3 sn'de
"özür dilerim" diyor, müşteri şikâyetini 18.4 sn'de anlatıyor. Model, sonucu sebebinden
önce görüyor. Bu, B1'e katkı yapıyor ve **B6'nın (aynı senaryo, farklı puan) en güçlü
açıklaması**: girdi tutarsızsa çıktı da kararsız olur.

### Değerlendirme
B3 bir "kriter eşleme" hatası değil. Puanlama motoruna giden **deterministik ölçüm katmanının
girdisi bozuk.** Motor düzeltilse bile bu veriyle doğru puan üretilemez. FAZ 2'de stereo
hizalama (kanal başına VAD + karşı kanal sessizliğinin segmentten çıkarılması) yapılmadan
Katman A'nın akustik kısmı güvenilir olmayacak.

---

## E) B5 — Kanıtsız sıfırlayıcı ihlal

### Ölçüm
```
id | dosya                           | puan | zeroed
 5 | mehmet.kaya_fatura_07.wav       |  0   | t
 7 | pelin.acar_sikayet_09_v2.wav    |  0   | t
18 | zeynep.demir_sikayet_09.wav     |  0   | t
23 | gizem.celik_fatura_06_v2.wav    |  0   | t
24 | deniz.yildiz_sikayet_05_v2.wav  |  0   | t
```
Beş çağrı sıfırlanmış. `calls` tablosunda sıfırlama gerekçesini tutan **hiçbir kolon yok.**

### Kök neden — veri modeli eksiği (D1)

`scoring.py:541-557`:
```python
zeroing_reason = None
for c in criteria:
    if c.is_critical and score_by_crit.get(c.id, 10) < c.critical_threshold:
        zeroing_reason = f"Kritik kriter esik alti: {c.name} (...)"
        break
...
if zeroing_reason:
    call.total_score = 0.0
    call.zeroed = True                                  # <- yalnız bayrak kalıcı
    alerts.append((AlertType.zeroing, "yuksek", zeroing_reason))   # <- gerekçe SADECE alarm metninde
```

`zeroing_reason` bir **yerel değişken**. `calls` tablosuna yazılmıyor. Gerekçe yalnızca
`alerts.message` içinde serbest metin olarak yaşıyor:
- Alarm silinirse/okundu işaretlenirse gerekçe kaybolur.
- Çağrılar listesi `alerts` tablosuna join atmadığı için "neden 0?" sorusunu cevaplayamaz.
- Temsilci karnesinde 0.0 görünüyor, sebebi hiçbir yerde yok.

Ayrıca **kanıt hiç saklanmıyor**: prompt dosyasının FAZ 2'de istediği `zeroing_evidence`
alanının veri modelinde karşılığı yok. Şu an sistem, kanıtsız sıfırlamayı hata olarak
fırlatmak bir yana, **kanıtı kaydedecek yere sahip değil.**

### Not
Sıfırlanan 5 çağrının en az 1'i (#24) §A'da gösterildiği gibi **yanlış** sıfırlanmış.
Yani B5 yalnız "gerekçe görünmüyor" değil; görünmeyen gerekçelerin bir kısmı **hatalı**.

---

## F) B6 — Aynı senaryo, farklı puan (judge instability)

### Ölçüm durumu — **taban çizgisi FAZ 1.3'te ölçülecek**

Dürüstlük kaydı: elimdeki iki gözlem temiz bir tekrarlanabilirlik ölçümü **değil**.
Çağrı #24 daha önce 89.6 iken bu denetimde yeniden puanlandığında 0.0 (sıfırlanmış) geldi;
ancak iki koşum arasında **model konfigürasyonu değişti** (DB'de `qwen2.5:14b` yazılıydı ve
o model kurulu değildi). Bu yüzden farkı doğrudan judge instability'ye yazamam.

Gerçek tekrarlanabilirlik sayısı `make eval`in **tekrarlanabilirlik** metriğinden gelecek:
aynı çağrı 3 kez puanlanır, toplam puanın standart sapması raporlanır (hedef ≤ 1.5).

### Kök nedenler — koddan okunabilen, ölçüm beklemeyenler

| # | Neden | Yer |
|---|---|---|
| 1 | **`temperature=0.1`, seed yok.** Sıfır değil; her koşumda örnekleme farklı. | `llm.py:38, 62, 87` |
| 2 | **Tek dev prompt.** 10 kriter + 15 görev maddesi tek çağrıda; modelin dikkati kriterler arasında bölünüyor, sıralama ve uzunluk bias'ı devreye giriyor. | `scoring.py:86-158` |
| 3 | **Kriterler artan `id` sırasında sunuluyor** (`_load_criteria` → `order_by(Criterion.id)`), harf/roma rakamı ID yok. Literatürdeki pozisyon bias'ı azaltıcıları uygulanmamış. | `scoring.py:403`, `_criteria_block` |
| 4 | **`_ensure_coverage` kanıtsız 5 uyduruyor.** LLM bir kriteri atladığında sistem 5 yazıyor; bu tamamen rastlantısal bir kaynak (B28). | `scoring.py:341-349` |
| 5 | **Aynı kriter iki kez puanlanabiliyor** ve ağırlığı iki kez sayılıyor (B27) — koşumdan koşuma toplamı oynatır. | `scoring.py:317-321`, `compute_total` |
| 6 | **Self-consistency yok.** Sıfırlayıcı ve kriz kararları tek atışta veriliyor; çoğunluk oylaması yok. | `scoring.py` geneli |
| 7 | **Girdi bozuk** (§D). Aynı senaryonun iki kaydı farklı bindirme desenleri üretiyorsa metrikler de farklı oluyor; model farklı "KESIN" sayılar görüyor. | `diarization.py:33-41` |

### Ek ölçüm — kanıt kapsaması
```
kanıtsız puan satırı : 44
toplam puan satırı   : 241
                     → %18.3'ünün kanıtı YOK
```
Kanıtsız 44 puanın hiçbiri "yetersiz kanıt" olarak işaretlenmiyor; hepsi **gerçek puan
gibi** ortalamaya giriyor. Prompt dosyasının 1. "asla yapma" maddesinin (kanıtsız ceza verme)
sistematik ihlali.

---

## G) Kök nedenlerin FAZ 2 tasarımına haritası

| Kök neden | FAZ 2 karşılığı |
|---|---|
| Deterministik kriter LLM'e soruluyor (B1) | **Katman A** — Açılış/KVKK/Kimlik/Kapanış/Yasaklı kelime kodda; LLM'i **ezer** |
| Kanıt doğrulanmıyor (B1, B5) | **Katman C** — her `quote` normalize transkriptte aranır; bulunamazsa `insufficient_evidence` |
| Kanıtsız ceza (B1, B28, %18.3 kanıtsız) | **Altın kural** — kanıt yoksa düşük puan yok, insan kuyruğuna |
| Fuzzy eşleşme gevşek (B4) | Kelime sınırı + Türkçe ek toleransı; `partial_ratio>=60` kısayolu kaldırılacak; çok kelimeli terim ifade olarak aranacak |
| Sıfırlama gerekçesi kalıcı değil (B5) | `calls.zeroing_reason` + `zeroing_evidence` **NOT NULL when zeroed**; kanıtsız sıfırlama sistem hatası |
| Tek dev prompt (B6) | Kriterler 3-4'lük gruplara bölünür, ayrı çağrılar |
| `temperature=0.1`, seed yok (B6) | `temperature=0`, sabit seed, sürümlenmiş prompt |
| Kriter tekrarı / uydurma 5 (B27, B28) | `(call_id, criterion_id)` tekillik kısıtı; `decision=insufficient_evidence` |
| **Stereo zaman damgaları bozuk (B3, B1, B6)** | **Kanal başına VAD hizalama** — segment `end` zamanı gerçek konuşma bitişine çekilir; söz kesme yeniden hesaplanır |
| Mono'da konuşmacı kaybı (B29) | Konuşmacı bilinmiyorsa uyum kriteri `insufficient_evidence` döner, "ihlal" demez |
| Uzun çağrıda orta kısım atlanıyor (B30) | Kırpma yerine pencereleme + kriter bazlı ilgili pencere seçimi |
| Alarmlar geçersizleşmiyor (B31, B2) | Yeniden puanlamada alarmlar geçersizleştirilir; `(call_id, rule_id, evidence_hash)` tekil |
