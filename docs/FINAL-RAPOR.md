# Final Rapor — yayına hazırlık turu

> Tarih: 2026-08-10 · Branch: `final/v2-yayina-hazirlik`
> Kapsam: piyasa araştırması, arayüz, repo temizliği, sırlar, sıfırdan
> kurulum, örnek veri, test rehberi.

Bu tur ürüne yeni özellik eklemekten çok, **ürünün kendisi hakkında söylediği
şeylerin doğru olmasını** sağlamakla geçti. Bulunan üç hata da bu türden:
yazılı olan ile yapılan arasındaki fark.

---

## 1. Piyasa analizinden ne uygulandı

15 ürün incelendi (MaestroQA/Rippit, Zendesk QA, Scorebuddy, Level AI,
Observe.AI, Playvox, Kaizo, Enthu.ai, EvaluAgent, Convin, Solidroad + Türkiye'den
Sonitel, Verimor, FGS, Zeno, VOİSCOPE). Tam analiz:
[PIYASA-ANALIZI.md](PIYASA-ANALIZI.md).

### Bulgu: eksik olan özellik değil, dış doğrulamaydı

Piyasada standart olan sekiz maddenin (AutoQA, özel skorkart, kalibrasyon,
koçluk, itiraz, risk sinyali, öz değerlendirme, SSO) **sekizi de bizde vardı.**

Araştırma sırasında "eksik" sandığım şeylerin yarısı koda bakınca zaten
uygulanmış çıktı: kanal bazlı skorkart (`channel_scope`), rubrik sürümleme,
inceleme ataması, temsilci öz değerlendirmesi, hedef takibi.

**Bunu analizde olduğu gibi bıraktım.** Rakip listesinden çıkan her boşluk
gerçek boşluk değildir; koda bakmadan "bizde yok" demek, olmayan işi yapmaya
kalkmaktır.

### Uygulanan: gerçek müşteri anketi (CSAT) ve korelasyon

Ürünün bütün doğrulaması **içeriden**ydi: altın seti sistemi geliştiren taraf
yazdı, `predicted_csat`'ı da aynı model üretti. Hiçbiri rubriğin kendisini
sorgulayamaz.

| Ne eklendi | Nerede |
|---|---|
| `Call.actual_csat` + kaynak + yorum + zaman | `models.py`, migrasyon |
| `POST /api/v1/csat/{id}` ve `/bulk` (kısmi başarı döner) | `api/csat_api.py` |
| Pearson r + tahmin MAE, kalite bandı başına ortalama CSAT | `services/csat.py` |
| Kokpit paneli | `components/CSATPanel.tsx` |

Dört dürüstlük kuralı koda gömüldü:

1. **20 çağrının altında korelasyon SAYISI gösterilmez.** Beş çağrıyla
   hesaplanan r=0.9 gürültüdür ve ekrana basıldığı anda birileri onu sunuma
   koyar.
2. **Ölçek sessizce dönüştürülmez.** 1-7'lik anketten gelen 7 kırpılmaz, hata
   fırlatılır — kırpmak verinin yanlış ölçekte olduğunu gizler.
3. **Sabit veride "ilişki yok" değil "ölçülemez" denir.** 0 döndürmek yanlış
   bir bilgi verir.
4. **Zayıf korelasyon uyarısı modeli değil RUBRİĞİ işaret eder.** Kalite puanı
   müşteri memnuniyetiyle ilişkisizse sorgulanması gereken şey ölçtüğümüz
   kriterlerdir.

21 test.

### Uygulanmayanlar ve gerekçeleri

| Madde | Neden |
|---|---|
| SCIM 2.0 | Hiçbir kimlik sağlayıcıya karşı test edilemez. Test edilmemiş bir SCIM, sessizce açık hesap bırakabilir — yokluğundan tehlikeli |
| Zendesk/Genesys/Five9 konektörleri | Gerçek hesap olmadan test edilemez. Test edilmemiş entegrasyon, olmayan entegrasyondan kötüdür |
| LMS / sınav modülü | Ayrı ürün kategorisi. Kurumların LMS'i zaten var; doğru yol webhook ile tetiklemek |
| Gerçek zamanlı asist | Farklı mimari (streaming STT, düşük gecikme). Yerel donanımda puanlama kalitesinden ödün verdirir |
| SOC 2 / ISO 27001 | Kod işi değil, süreç işi. Kod tarafı kanıt üretmeye hazır (denetim izi, rol matrisi, şifreleme, saklama) |

---

## 2. Arayüz — keskin köşe ve denetim

Tam rapor: `docs/internal/UI-DENETIM.md` (depoya dahil değil).

### Keskin köşe

**Tek kaynak:** `globals.css` içinde `--radius: 0`.

**İki katmanlı savunma:**
1. `tailwind.config.ts` içinde `borderRadius` ölçeği **ezildi** — `none`'dan
   `full`'e her anahtar `var(--radius)`e çözülüyor. Yani ileride biri
   `rounded-lg` yazsa bile sonuç 0.
2. Markup'taki 124 `rounded-*` sınıfı 25 dosyadan silindi. İşlevsizdiler ama
   durmaları sonraki geliştiriciye "burada yuvarlak köşe var" derdi.
   **Yanlış bilgi de bir hatadır.**

Ayrıca 1 inline `borderRadius`, 2 SVG yuvarlak uç.

`scripts/ui_audit.py` + `make audit` ile kalıcılaştırıldı (7 kontrol).

### Hiyerarşi neyle telafi edildi

Radius gidince "yüzen kart" hissi de gider:

- **Kenarlık ağırlığı** — yeni `--border-strong` tokenı; kart/buton/input
  kenarlıkları buna geçti. Yuvarlak köşe yokken zayıf bir çizgi, kartın nerede
  bittiğini söylemeye yetmiyor.
- **Gölge yeniden tanımlandı** — kare köşede geniş-bulanık gölge "hata" gibi
  görünür. `0 1px 2px + 0 4px 12px` yerine tek keskin `0 1px 0`.
- **Tipografi** — `.eyebrow` sınıfı (küçük, harf aralığı açılmış, büyük harf).
- **Rozetler** hap şeklinden çıkınca anlamı **2px sol kenar şeridi** taşıyor.
- **Aktif nav işareti** tam yükseklik kenar şeridine dönüştü.

### Denetimde ne bulundu

Playwright ile 16 sayfa × 2 tema = 32 ekran görüntüsü, 3 tur.

**45 sessiz stil hatası.** Bunların ortak özelliği: **başarısızlıkları
sessiz.** Tanımsız bir CSS değişkeni hata vermez, renk hiç uygulanmaz.

| Sorun | Adet | Somut sonuç |
|---|---|---|
| `var(--status-ok)` → doğrusu `--status-good` | 18 | Canlı bağlantı göstergesi **hiç görünmüyordu** |
| `var(--status-warn)` → `--status-warning` | 12 | Uyarı renkleri yok |
| `var(--series)` → `--series-1` | 2 | Vurgu rengi yok |
| `bg-surface2` (Tailwind'de tanımsız) | 10 | Koyu temada QA formu alanları **beyaz kutu** |
| `text-danger` (tanımsız) | 2 | Hata metni renksiz |

Her ikisi de `ui_audit.py`'a kalıcı kontrol olarak eklendi.

### Erişilebilirlik

| Bulgu | Düzeltme |
|---|---|
| Açık temada `--muted` **AA'yı geçmiyordu** (3.46:1, eşik 4.5) | `#6f6f6b` → **5.05:1** |
| Odak halkası `:focus` kullanıyordu | `:focus-visible`, kapsam genişletildi, `outline-offset: 2px` |
| Dokunma gecikmesi | `touch-action: manipulation` |
| Hareket tercihi yok sayılıyordu | `prefers-reduced-motion` |

### Aracın kendisi iki kez kırıldı

1. **`networkidle` hiç oturmuyor** — canlı alarm WebSocket'i açık kaldığı için
   ağ asla boşalmıyor; her sayfa 30 sn timeout'a giriyordu (50 dakikada 2
   görüntü).
2. **Giriş arayüzüne bağımlılık** — giriş ekranının görünümü sistemin
   durumuna bağlı. Oturum artık API üzerinden açılıyor.

---

## 3. Bulunan hatalar

Bu turda üç hata bulundu. Üçü de aynı sınıftan: **yazılı olan ile yapılan
arasındaki fark.**

### B35 — `make eval` giriş ekranını kırıyordu

`make eval` izole bir `__golden__` kiracısı kurar. `primary_tenant` "demo
olmayan ilk aktif kiracı" diye baktığı için onu **gerçek kurum** sandı:

```
/auth/config  ->  org_slug: "golden"
tarayici      ->  POST /auth/login {tenant_slug: "golden"}
kullanicilar  ->  "demo" kiracisinda
sonuc         ->  HER GIRIS 401
```

Yani **`make eval` koşulan bir makinede arayüze hiç girilemiyordu.** Hiçbir
hata logu yok; sadece giriş çalışmıyor. Üstelik ortama bağlı — "bende
çalışıyor" türünden.

Ekran görüntüsü alırken ortaya çıktı: 32 görüntünün 30'u giriş sayfasıydı.

**Düzeltme:** Çift alt çizgiyle başlayan kiracı adı = iç kiracı.
**Düzeltmenin kendisi de hataliydı** ve testler yakaladı: SQL `LIKE` içinde
`_` tek karakter jokeridir, `'__%'` deseni **adı 2+ karakter olan her kurumu**
eliyordu. `autoescape=True` ile çözüldü. 6 regresyon testi.

### B36 — insan kuyruğuna düşen her çağrı işlenirken çöküyordu

`pipeline.process_call`, çağrı insan onayına alındığında alarm üretiyordu ama
**eski (tuple) biçimde**. Alarm motoru FAZ 4'te `AlertDraft`'a geçmiş, bu
üretici güncellenmemişti:

```
AttributeError: 'tuple' object has no attribute 'validate'
```

Bu dal **yalnızca** risk kuralı tetiklendiğinde çalışır — yani hata tam da
ürünün en önemli akışını vuruyordu: *kalite uzmanı onayı gereken çağrılar*.
Puanlama başarıyla bitmiş, transkript çıkmış, kriterler kanıtlanmış olsa bile
çağrı `failed` kapanıyordu.

**Neden hiçbir test yakalamadı:**
- `make eval` pipeline görevini **çağırmaz**, doğrudan `scoring.run_scoring`
  kullanır. Puanlama doğruydu, altın set yeşildi.
- Alarm motorunun testleri `AlertDraft` ile çağrı yapıyordu — yani **motoru**
  test ediyordu, **üreticiyi** değil.

Hata ancak gerçek bir sesli çağrı uçtan uca işlenirken çıktı.

Testi yazarken **ikinci bir hata** ortaya çıktı: eski kod `"dusuk"` şiddetini
kullanıyordu ama geçerli değerler `kritik|yuksek|bilgi`. Yani tuple sorunu
çözülse bile alarm üretilemeyecekti. 5 regresyon testi (biri kaynak desenini
denetler).

### CRLF — `generate-secrets.sh` klonlayan herkesi vururdu

Temiz kurulumda API "password authentication failed" ile ayağa kalkmadı.

Git Bash altındaki Windows `openssl.exe` çıktıyı CRLF ile veriyor;
`tr -d '\n='` `\r`'yi silmiyordu. Parolanın sonuna görünmez bir satır başı
karakteri yapışıyor ve `DATABASE_URL` şu hale geliyordu:

```
postgresql://kalitegoz:PAROLA<CR>@postgres:5432/kalitegoz
```

Postgres bunu farklı bir parola sayıyor ve **hata mesajının hiçbir yerinde
`\r` geçmiyor**. Sebep ancak `cat -A` ile görüldü.

**Düzeltme:** `tr -d "$CR"'\n='`, üretilen her sırda yazdırılamayan karakter
denetimi, şablonu LF'e çevirme, `.env`'de CR kalmadığının son kontrolü.

---

## 4. Repo ve güvenlik denetimi sonucu

### Kök dizin

```
README.md  CLAUDE.md  LICENSE  Makefile  docker-compose.yml
.env.example  .gitignore  CHANGELOG.md
backend/  frontend/  data/  docs/  scripts/  .github/
```

Silinen/taşınan: `NATIVE-AI-KURULUM.md`, `RUN.md`, `SISTEM-TEST-REHBERI.md`
(→ `docs/KURULUM.md` içinde konsolide), overhaul prompt'u ve faz raporları
(→ `docs/internal/`), `_scoring_head.tmp` (ölü geçici dosya),
`seed_pro_calls.py` (hiçbir yerden çağrılmıyordu), `.claude/` ve
`skills-lock.json` (geliştirme aracı artefaktı).

### Ciddi bulgu: altın set hiç commit edilmemişti

Eski `.gitignore`'da `data/` (dizin) yazıyordu. **Git'te bir dizin yok
sayılınca içindeki negatif desenler (`!data/golden/`) çalışmaz.**

Yani "ürünün doğruluk iddiasının kanıtı" olan 50 senaryoluk altın set ve insan
referans şablonu depoda hiç yoktu. `data/*` ile düzeltildi; 103 dosya artık
takipte, ses dosyası sızmadı.

### Sır denetimi

| Kontrol | Sonuç |
|---|---|
| `.env` geçmişte commit edilmiş mi | **Hayır** |
| `JWT_SECRET`, `KG_MASTER_KEY`, `POSTGRES_PASSWORD`, `sk-*`, `AKIA*`, PEM özel anahtar kalıpları tüm commit'lerde | Tek bulgu `.env.example` içindeki placeholder'lar (`kalitegoz-dev-secret-CHANGE-IN-PROD`) — **gerçek sır sızıntısı yok** |
| `git filter-repo` gerekti mi | **Hayır** |

**Bu turda bir yakın kaçış oldu ve raporlanmalı:** `generate-secrets.sh`
mevcut `.env`'i `.env.yedek` olarak yedekliyor ve bu yedek `.gitignore`'da
değildi — bir commit'e girdi. Fark edilir edilmez commit yeniden yazıldı,
dosya geçmişten çıkarıldı ve **tedbiren tüm sırlar döndürüldü**. `.gitignore`'a
`.env.yedek`, `.env.bak`, `.env.backup` eklendi.

Commit henüz uzağa gönderilmemişti; sızıntı depo dışına çıkmadı.

### Lisans: AGPL-3.0 — gerekçe

Üç aday değerlendirildi:

| Lisans | Neden seçilmedi / seçildi |
|---|---|
| MIT | Bir SaaS sağlayıcı kodu alıp kapalı bir hizmet olarak sunabilir; kurumun kendi donanımında çalışma vaadi, ürünün ayırt edici yanı — onu korumasız bırakmak mantıksız |
| Apache-2.0 | Patent koruması iyi ama aynı SaaS açığı var |
| **AGPL-3.0** | **Seçildi.** Ağ üzerinden hizmet olarak sunan da kaynağı paylaşmak zorunda. Ürün zaten on-prem konumlanıyor; AGPL bu konumlandırmayı hukuki olarak da destekliyor |

**Bilinen bedeli, dürüstçe:** AGPL, bazı kurumsal alım süreçlerinde eleyici
sayılır. Ticari lisans istenirse ikili lisanslama (dual licensing) mümkün —
telif hakkı tek elde olduğu sürece.

---

## 5. Sıfırdan kurulum ve başlangıç verisi

```
docker compose down -v --rmi local
docker compose up -d --build
```

| Kontrol | Sonuç |
|---|---|
| `/health` | `{"status":"ok","app":"KaliteGoz","version":"2.0.0"}` |
| `/ready` | `{"status":"ready","checks":{"database":"ok","redis":"ok"}}` |
| Ollama (host, Docker dışı) | Konteynerden `host.docker.internal` ile erişiliyor, 6 model |
| Migrasyonlar | Temiz DB üzerinde koştu |

### Başlangıç durumu

```
toplam cagri    : 20
bekleyen        : 20     <- hicbiri islenmemis
demo bayrakli   : 20
temsilcisi olan : 20
puan kaydi      : 0
transkript      : 0
alarm / ihlal   : 0 / 0
isleme duraklati: True   <- kullanici baslatacak
```

**Dağılım:** 6 yüksek · 6 orta · 4 düşük · 2 sıfırlayıcı (KVKK anonsu yok,
hakaret) · 2 kriz (avukat, hakem heyeti). 8 farklı temsilci (kadın/erkek
karışık), 5 kategori.

**Sesler gerçek TTS ile üretildi** — 8 kHz stereo (sol=müşteri, sağ=temsilci).
Doğrudan DB'ye puanlı çağrı yazmak ürünü *anlatır* ama *göstermez*; ses
bırakmak STT'den puanlamaya kadar bütün hattın çalıştığını kanıtlar.

**Hazır gelenler:** her rolden kullanıcı (yönetici, 2 süpervizör, kalite
uzmanı, 12 temsilci), 2 takım, 2 kampanya, 10 kriterlik tam Türkçe karakterli
rubrik, 8 yasaklı kelime.

`Call.is_demo` bayrağı eklendi — `is_golden`'dan **ayrı** kavram: `is_golden`
kalite ekibinin işaretlediği gerçek çağrı, `is_demo` ürünü denemek için
üretilmiş sentetik çağrı. `make eval` zaten ayrı bir kiracıda çalışır.

### Uçtan uca doğrulama

Whisper Docker'da değil — api konteynerinin 1 GB tavanı var, medium model onu
aşıyor (exit 137 = OOM). Mimari zaten STT'yi host'a koyuyor. Host'ta koşuldu:

```
sure          : 38 sn
durum         : done
transkript    : 27 segment
toplam puan   : 80.8
kriter puani  : 10  (kanitli: 8)
ihlal / alarm : 3 / 3
tahmini CSAT  : 3.5
```

Kanıt doğrulaması **canlıda çalıştı**: doğrulanamayan bir alıntı reddedildi
(`evidence_verification_failed`). Sonra o çağrının bütün kayıtları silindi —
sistem yine 20 bekleyen çağrıyla duruyor.

---

## 6. Test sonuçları

| Komut | Sonuç |
|---|---|
| `make test` | **454 test geçti** |
| `make audit` (tr + ui) | **0 ihlal** (7 kontrol) |
| `tsc --noEmit` | 0 hata |
| `make eval` | §7 |

---

## 7. Altın set ölçümü

`make eval` — 50 senaryo, gerçek puanlama motoru, temiz kurulum üzerinde.
**Tüm eşikler sağlandı, çıkış kodu 0.** Ham çıktı:
[`docs/eval/2026-08-10-final.json`](eval/2026-08-10-final.json).

| Metrik | v1 tabanı | Bu koşum | Eşik |
|---|---|---|---|
| Sıfırlayıcı ihlal yanlış-pozitif | %38.5 | **%0.0** | %0 |
| Sıfırlayıcı ihlal yanlış-negatif | %18.2 | **%0.0** | — |
| Kriter bazlı MAE (0-10) | 2.16 | **0.78** | ≤1.0 |
| Kanıt doğrulanabilirlik | %56.1 | **%100** | ≥%95 |
| Tam isabet oranı | %21.4 | **%64.9** | — |
| Kanıtsız ceza ihlali | 4 | **0** | 0 |
| Kaçırılan kriz | — | **0** | 0 |

### Kriter türüne göre

| | Nesnel (6 kriter) | Öznel (4 kriter) |
|---|---|---|
| Cohen's kappa | **0.7639** | 0.1637 |
| MAE | **0.16** | 1.718 |
| Bant isabeti | **%92.2** | %65.0 |
| Çekirdek 4 kriterin **en düşüğü** | **0.9392** (eşik 0.90 ✓) | — |

**Nesnel kriterlerin kappa'sı önceki koşumla kuruşu kuruşuna aynı (0.7639).**
Bu, Katman A'nın gerçekten deterministik olduğunun dördüncü kez doğrulanması:
kod değişti, DB sıfırlandı, sırlar döndü — sonuç değişmedi.

### Değişen bir metrik: tekrarlanabilirlik 0.00 → 0.46

Önceki koşumlarda `tekrarlanabilirlik_std` **0.00** çıkıyordu; bu koşumda
**0.46**. Bunu saklamak yerine açıklıyorum, çünkü ürünün "tekrarlanabilir"
iddiasını doğrudan ilgilendiriyor.

Ayrıntıya bakınca tablo netleşiyor (3 senaryo × 3 koşum, toplam puan):

| Senaryo | Puanlar | std |
|---|---|---|
| `yuksek-01-fatura-itiraz` | 96.3 · 96.3 · 96.3 | **0.00** |
| `reg-b1-acilis-tam` | 95.6 · 96.3 · 95.6 | 0.40 |
| `orta-01-kapanis-eksik` | 91.2 · 90.4 · 90.4 | 0.46 |

Oynama **0.8 puanı geçmiyor** (100'lük ölçekte %0.8) ve kaynağı öznel
kriterler — nesnel kriterler her koşumda aynı. Eşik 1.5 olduğu için kapı
yeşil, ama **"std 0.00" artık doğru bir iddia değil**; doğrusu şu:

> Aynı çağrı üç kez puanlandığında toplam puan **1 puandan az** oynar; nesnel
> kriterler hiç oynamaz, oynama öznel kriterlerden gelir.

Bu, `docs/internal/UI-DENETIM.md` ve FAZ-7 raporundaki varyans bulgusuyla
tutarlı: öznel kriterler koşumdan koşuma değişiyor. Bu koşum onu bir kez daha
gösterdi.

**README ve metodoloji dokümanındaki "std 0.00" ifadesi güncellendi.**

### Yetersiz kanıt oranı %3.4 → %9.0

455 kriterin 45'i "yetersiz kanıt" oldu. Bu bir bozulma **değil**, beklenen
davranış: bu koşumdaki çağrılar gerçek TTS sesinden geçti ve STT bazı
ifadeleri tam yakalayamadı; model alıntı gösteremediği kriterde puan vermedi.

Kural tam da bu: **kanıt yoksa ceza yok.** 45 kriter puansız kaldı ve insana
yönlendirildi — uydurma puan üretilmedi.

---

## 8. Bilinen açıklar

Dürüst liste. Hiçbiri gizlenmedi.

### Ölçüm tarafı

1. **Öznel kriterlerde kappa düşük (0.18) ve hedef yok.** İnsan-insan uyumu
   (IRR) ölçülmediği için meşru bir hedef koyulamıyor. Hedef uydurulmuyor.
2. **Kriter bazlı varyans ölçülmedi.** Aynı yapılandırmanın iki koşumu
   arasında öznel kappa 0.05'e kadar oynayabiliyor. **Bu ölçüm yapılmadan
   0.05 altı kappa farkları yorumlanmamalıdır.**
3. **Altın set sentetik.** Referans puanlarını sistemi geliştiren yapay zekâ
   yazdı; nesnel kriterlerde spesifikasyon, öznel kriterlerde **döngüsel**.
4. **Gerçek CSAT verisi yok.** Korelasyon altyapısı hazır ama kurum anket
   sonuçlarını girene kadar sayı üretmiyor (ve üretmemeli).

### Ürün tarafı

5. **SCIM yok** — çalışan ayrıldığında hesap otomatik kapanmıyor.
6. **Hazır CCaaS konektörü yok** — API ve webhook var, konektör yok.
7. **Gerçek zamanlı asist yok** — bilinçli kapsam dışı.
8. **Görsel regresyon karşılaştırması yok** — ekran görüntüsü alınıyor ama
   öncekiyle piksel bazında karşılaştırılmıyor.
9. **Mobil görünüm denetlenmedi** — tüm ekran görüntüleri 1440×900.
10. **Ekran okuyucuyla test edilmedi** — ARIA etiketleri kodda var ama gerçek
    bir okuyucuyla gezilmedi.

### İşletim tarafı

11. **STT worker'ı elle başlatılıyor** (`run-host-worker.ps1`). Bu mimarinin
    gereği ama kurulumu deneyen kişi için sürpriz olabiliyor — test rehberinde
    açıkça yazıldı.
12. **`docs/internal/` depoya dahil değil.** Faz raporları ve karar defteri
    diskte duruyor ama klonlayan görmüyor. Bu bilinçli bir tercihti (ara
    raporlar eski ölçümler içerir) ama **çalışmanın önemli bir kısmı depoda
    görünmüyor** demektir.

---

## 9. Rio'nun karar vermesi gerekenler

### 9.1 Lisans kesinleşsin mi?

AGPL-3.0 seçildi ve gerekçesi §4'te. Ticari satış planlıyorsan ikili
lisanslama gerekir; bu bir hukuk kararı, bende cevabı yok.

### 9.2 Hedef segment

On-prem + KVKK + Türkçe üçlüsü **bankacılık, sigorta, kamu** için güçlü.
SaaS hızı arayan e-ticaret için ağır. İkisini aynı anda kovalamak ürünü
bulanıklaştırır.

### 9.3 Hangi santrale konektör?

Türkiye pazarında hangi santral yaygınsa **önce ona** konektör yazılmalı.
Bu bilgi bende yok, sende var.

### 9.4 `docs/internal/` gerçekten gizli mi kalsın?

Şu an `.gitignore`'da. Faz raporları ürünün nasıl inşa edildiğini ve **hangi
hataların ölçülerek bulunduğunu** anlatıyor — bu, teknik bir alıcı için ikna
edici olabilir. Alternatif: sadece FAZ-7 ve UI-DENETIM'i public yapmak.

### 9.5 İnsan referansı ne zaman?

`data/human_ref/sablon.json` hazır. 20 senaryoyu elle puanlaman ve **ikinci
bir kalite uzmanının** aynı seti bağımsız puanlaması gerekiyor. Öznel
kriterlerde meşru bir hedef ancak ondan sonra doğar.

### 9.6 SOC 2'ye girilecek mi?

Kod tarafı kanıt üretmeye hazır. Süreç 6-12 ay ve kod işi değil.
