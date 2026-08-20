# Değişiklik Günlüğü

## v2.4 — Yanlış alarm kapatıldı (2026-08-13)

### B45 — panel, sistem çalışırken "işçi çalışmıyor" diyordu

v2.3'te eklenen sesli işçi uyarısı **yanlış alarm veriyordu**. Kullanıcı
"İşlemeyi başlat"a bastı, 9 çağrı sorunsuz puanlandı, ama panel aynı anda
hem *"1 çağrı işleniyor"* hem *"Sesli çağrı işçisi çalışmıyor"* diyordu —
kendi kendini yalanlayan bir uyarı.

**Kök neden:** işçi `--pool=solo` ile çalışır; bir görevi işlerken **ana
döngüsü bloke olur** ve Celery'nin `inspect` yayınına cevap veremez. Kontrol
bunu "işçi yok" diye okudu.

Yanlış alarm veren bir uyarı, gerçek alarmı da değersizleştirir — B40'ta
denetimler için öğrenilen ders, bu kez ürünün kendisinde tekrarlandı.

**Düzeltme — kanıt sırası, kesinden zayıfa:**

1. Bir çağrı işleniyorsa işçi **kesinlikle** canlıdır (DB sayımı, ağ
   çağrısı gerektirmez).
2. `inspect` cevap verip `voice` kuyruğunu listeliyorsa canlı.
3. Son 15 dakikada görüldüyse canlı say — meşgul olabilir.
4. Hiçbiri yoksa: `inspect` cevap verdi ama `voice` yoksa gerçekten yok;
   hiç cevap vermediyse **"bilinmiyor"** de, "yok" deme.

Ölçülerek doğrulandı: bir çağrı işlenirken panel 4 ardışık sorguda
`voice_worker_active=true`, uyarı boş. 11 regresyon vakası.

Testi yazarken **ikinci bir kusur** çıktı: sahte `celery_app` bir
`MagicMock` olduğu için Redis `get` çağrısı truthy dönüyor ve "işçi hiç
görülmedi" demek isteyen testler kazara "görüldü" kuruyordu. Test çifti
gerçek Redis gibi `None` dönecek şekilde düzeltildi.

### TZ=Europe/Istanbul

Konteynerler UTC'de çalışıyordu, host UTC+3'te. İki sonucu vardı: Celery
"clocks are out of sync" uyarısı basıyordu ve **rapor tarihleri gece
yarısından sonra bir gün geri kayıyordu** (`datetime.now()` kullanan rapor
adları). Kalıcı veri her zaman UTC saklanıyor; bu ayar yalnızca görünen
saati hizalar. `.env` 76 → 77 anahtar.

### Ölçüm
Gerçek hız: **71 sn/çağrı** → 20 çağrı ≈ **24 dakika** (önceki mesajda
"1-1.5 saat" demiştim, yanlıştı). 525 backend + 83 betik testi, tüm
denetimler 0, 64 sayfa varyantı 0 çöken.

## v2.3 — Sesli işçi sessizliği kapatıldı (2026-08-13)

### B44 — "İşlemeyi başlat" sessizce hiçbir şey yapabiliyordu

Sesli çağrılar `voice` kuyruğuna gider ve o kuyruğu **yalnızca host'ta
çalışan native worker** tüketir (Whisper konteynerin bellek tavanına
sığmıyor). Worker çalışmıyorken "İşlemeyi başlat":

1. 20 çağrıyı kuyruğa atar, 2. Celery **başarıyla** döner, 3. panel
"kuyruğa alındı" der, 4. çağrılar **sonsuza kadar** bekler — hiçbir hata
görünmeden. Ürünün ana akışı, hata vermeden çalışmıyordu.

`/admin/processing` artık `voice_worker_active` + `voice_worker_hint`
döndürüyor; yönetim ekranı başlat butonunun **hemen üstünde** uyarıyor ve
çalıştırılacak komutu yazıyor. 7 regresyon vakası
(`test_voice_worker_uyarisi.py`), biri arayüzün uyarıyı gerçekten bastığını
kaynak düzeyinde kilitliyor.

### Uçtan uca doğrulama

Bir çağrı gerçek zincirle işlendi: host Whisper → 15 segment (zaman sırası
doğru, konuşmacılar ayrışmış) → Ollama puanlama → 10 kriter → kanıt
doğrulama **9 doğrulandı / 1 yetersiz kanıt / 0 doğrulanamayan** → 2 ihlal →
toplam puan 82.6 (kodda hesaplandı).

### Testler
521 backend + 83 betik · tr/ui/api denetimi 0 · tsc 0 · 64 sayfa varyantı,
0 çöken.

## v2.2 — Son denetim (2026-08-13)

Kod yazmadan önce baştan sona tarama, sonra bulunanların düzeltilmesi.
Ölçüm çıktıları: [`docs/eval/`](docs/eval/).

### Düzeltildi
- **B41** — İngilizce arayüzde Türkçe metin kalıyordu. `api.ts` altı etiket
  haritasını sabit Türkçe tutuyordu; ölçüldü: çağrı listesinde "Kuyrukta",
  aramada "Sesli". Roller için aynı sorun daha önce çözülmüş, kalan beşi
  bırakılmıştı. 34 anahtar TR+EN eklendi.
  Yan fayda: `pending` etiketi "Kuyrukta" → **"Bekliyor"**; işleme
  duraklatılmışken çağrı bir kuyrukta değil, kullanıcıyı bekliyor.
- **B42** — "Zorunlu env eksikse dur" kuralı üç alan için hiç çalışamıyordu.
  `jwt_secret`, `database_url`, `redis_url` **dolu varsayılan** taşıyordu ve
  "boş mu?" kontrolü erişilemez kalıyordu. `JWT_SECRET` tanımsızsa uygulama
  bilinen bir imza anahtarıyla ayağa kalkıyordu.
- **B43** — o korumanın hiç testi yoktu; 18 regresyon vakası eklendi.
- `.env.example`'da 6 anahtarın üstünde açıklama yoktu.

### Geri çekildi
- Denetimde açılan "süpervizör `/admin/users` 403 alıyor" maddesi.
  Ölçüldü: temiz tarayıcı bağlamında her sayfa doğru rolüyle sıfır 4xx
  üretiyor. 403, ekran denetiminin kendi düzeneğinden geliyordu.

### Denetim araçları
- `scripts/ui_sweep.mjs` — 16 sayfa × 2 tema × 2 dil, sonra her etkileşimli
  öğe tıklanır. İlk sürümü 5 yanlış pozitif üretti (zaten aktif olan
  seçeneğe tıklıyordu); `data-active`/`aria-pressed` taşıyanlar atlanıyor.
- `tr-audit` yeni kontrol: **istemci sabitleri** — `frontend/lib/` altındaki
  sabit Türkçe metinleri yakalar. Eklenir eklenmez 5 sızıntı daha buldu.

### Ölçüm
`make eval` tüm eşikleri geçti (çıkış 0). Nesnel kappa **0.7639** — altıncı
kez birebir aynı. Öznel kappa üç ardışık koşumda 0.1637 → 0.1078 → 0.0931;
aradaki değişiklikler puanlama koduna dokunmadı, yani **koşum-arası varyans
belgelerde yazan 0.05'lik bandan geniş**. Öznel kappa artık tek sayı değil
**0.09–0.18 aralığı** olarak yazılıyor.

## v2.1 — Çoklu sağlayıcı gerçekten çalışır (2026-08-13)

Soru şuydu: *"Gemini seçersem sistemdeki her şey Gemini ile mi çalışıyor?"*
Cevap ölçülerek verildi.

### Doğrulandı
- Puanlama, gömme ve görsel **bağımsız** sağlayıcı seçiyor; anahtarlar
  karışmıyor, kiracı bağlamı kapanınca sızmıyor (12 test).
- Kaynak taraması: hiçbir serviste sabit kodlanmış sağlayıcı adresi yok —
  olsaydı seçim sessizce atlanırdı.

### Eklendi
- **Canlı model listesi.** Sağlayıcının kendi API'sinden çekilir, 15 dk
  önbelleklenir, erişilemezse statik yedeğe düşer ve *hangi kaynaktan
  geldiğini söyler*. Ölçüldü: OpenRouter'da 410 model (önceki sabit liste: 4).
- Aranabilir model seçici; her modelin boyut / bağlam / fiyat bilgisiyle,
  Ollama'da kurulu olanlar işaretli. Listede olmayan ad da yazılabilir.
- **Etkin model göstergesi.** Panel yalnızca *seçimi* gösterdiği için hiç
  seçim yapılmamış kurulumda model alanı boş görünüyor ve kullanıcı "hiçbir
  şey ayarlı değil" sanıyordu; artık fiilen kullanılan model yazıyor.
- Sağlayıcının o yüzeyi hiç sunmadığı durum (OpenRouter'da gömme yok) boş
  liste yerine sebebiyle dönüyor.

### Düzeltildi
- **B38** — bulut sağlayıcı düşünce sistem sessizce yerel modele kaçıyordu ve
  bunun tek izi konteyner loguydu. Davranış korundu (kesinti puanlamayı
  durdurmaz) ama artık `LLM_FALLBACK_OLLAMA` ile kapatılabiliyor ve düşme
  sayısı panelde uyarı olarak görünüyor.
- **B39** — dört güvenlik testi ana anahtarı hiç kaldırmadan geçiyordu:
  anahtar iki kaynaktan okunuyor, testler yalnızca birini siliyordu.
- Model türü artık sağlayıcının `capabilities` alanından okunuyor, ad
  kalıbından değil — `bge-m3` LLM sanılmıştı.
- Model seçicinin tüm metinleri i18n'e taşındı; İngilizce arayüzde satırlar
  karma dilde görünüyordu.

## v2.0 — Uçtan uca overhaul (2026-08-09)

Altı fazda yapıldı; her fazın raporu `docs/internal/FAZ-N-RAPOR.md` altında.
Ölçüm çıktıları `docs/eval/`, ekran görüntüleri `docs/screens/`.

### Ölçülen sonuç

| Metrik | v1 | v2 |
|---|---|---|
| Sıfırlayıcı ihlal yanlış-pozitif | %38.5 | **%0.0** |
| Sıfırlayıcı ihlal yanlış-negatif | %18.2 | **%0.0** |
| Kriter bazlı MAE (0-10) | 2.16 | **0.82** |
| Kanıt doğrulanabilirlik | %56.1 | **%100** |
| Tekrarlanabilirlik (std) | 1.95 | **0.46** |
| Cohen's kappa (ortalama) | 0.32 | 0.51 |
| Çekirdek uyum kriterlerinde kappa* | 0.32 | **0.94–1.00** |
| Backend testi | 221 | **496** |

\* Açılış, KVKK / Aydınlatma, Kapanış, Yasaklı Kelime / Üslup. Diğer iki
deterministik kriter (Kimlik Doğrulama 0.54, Script Uyumu 0.10) **tanım
sorunu** taşıyor — kural %100 tekrarlanabilir, tartışma kuralın ne olması
gerektiğinde. Öznel dört kriterde kappa 0.08–0.20 (14B ile 0.33).
Ayrıntı: `docs/KALITE-METODOLOJISI.md` §4.

### FAZ 1 — Denetim ve doğruluk temeli
- 50 senaryoluk altın set (**sentetik referans** — kaynağı §4.0'da açık), sürüm kontrolünde
- `make eval` regresyon takımı: MAE, kappa, sıfırlayıcı FP/FN, kanıt
  doğrulanabilirlik, tekrarlanabilirlik
- B1–B6 kök neden analizi **ölçümle**; 6 yeni hata bulundu (B27–B32)
- Proje git altına alındı

### FAZ 2 — Puanlama motorunun yeniden yazımı
- Üç katmanlı hibrit motor: deterministik ön kontrol → kanıt zorunlu LLM →
  sunucu doğrulaması
- **Kanıt yoksa ceza yok** kuralı; kanıtsız sıfırlama istisna fırlatır
- `normalize_tr()` tek Türkçe normalizasyon kaynağı
- STT `word_timestamps` düzeltmesi — şişik segment süreleri (B3'ün kök nedeni)
- Eski tek-dev-prompt implementasyonu kaldırıldı (265 satır ölü kod)

### FAZ 3 — İki aşamalı kalite kontrol
- QA durum makinesi: yapay zekâ puanladı → insan kuyruğunda → kesinleşti
- Yedi insan-kuyruğu kuralı, hepsi yapılandırılabilir
- Kaliteci inceleme kuyruğu: tek istekte tam bağlam, tek istekte tam karar
- Kalibrasyon geri besleme döngüsü (ölçüldü: anlamlı fark yok — dürüst kayıt)
- Ölçülen güvenilirlik kapısı: güvenilmez kriter insana **garantili** düşer
- Kesinleşmemiş puan lig tablosuna sayılmaz

### FAZ 4 — Backend sağlamlaştırma
- İstatistiksel dürüstlük: n<30'da korelasyon yok, önceki dönem boşsa yüzde yok,
  tek noktayla grafik yok, az örneklemli temsilci üst sıraya çıkamaz
- Alarm motoru: zorunlu alanlı şablon + `(call_id, rule_id, evidence_hash)`
  tekilliği; rozet yalnız kritik+yüksek sayar
- Güvenlik sayfası **9 gerçek kontrolden** okur; diskte şifreleme ve OIDC SSO
  uygulandı
- Standart hata zarfı `{error: {code, message_tr, details}}`
- Ölçüldü: kokpit 1000 çağrıyla **0.011 sn**

### FAZ 5 — Arayüz yeniden tasarımı
- Dört skill kuruldu ve okundu; `docs/internal/05-TASARIM-PLANI.md` kod öncesi üretildi
- 14 düz menü → 5 rol bazlı grup; 13 emoji ikon → 17 inline SVG
- İmza öğesi: **kanıt-transkript bağı** — alıntıya tıklayınca ses o saniyeye atlar
- Dört durum bileşenleri (yükleniyor/boş/hata/dolu)
- Klavyeyle tamamlanabilen inceleme akışı (J/K/A/Space/Ctrl+Enter)
- 13 ekran görüntüsü, her ekran iki temada

### FAZ 6 — Dil, demo, satışa hazırlık
- Rubrik kriter adları **tam Türkçe** (migration ile mevcut veri dahil)
- `scripts/tr_audit.py` — Türkçe karakter ve jargon denetimi, CI'da
- AI çıktısı Türkçe kalite kapısı: ASCII Türkçe tespit edilirse düzeltme istenir
- `docs/SOZLUK.md` — terim sözlüğü; aynı kavrama iki isim verilmez
- `make demo` — 220 çağrılık satış demosu, zaman içinde iyileşme hikâyesiyle
- `docs/KALITE-METODOLOJISI.md` — satış dokümanı, ölçülmüş metriklerle
- `docs/KVKK-UYUM.md` — veri yerleşimi, maskeleme, rol matrisi

### FAZ 7 — ürün kararları ve dürüstlük düzeltmeleri
- **Altın setin kaynağı açıkça yazıldı**: "uzman referansı" değil
  **sentetik referans**; nesnel kriterlerde *spesifikasyon*, öznel
  kriterlerde **döngüsel** ve bağımsız doğruluk kanıtı sayılmaz
- Metrikler **nesnel/öznel ayrı** raporlanıyor; "%100 kapsam" iddiası
  yalnızca nesnel kriterler için kuruluyor
- Öznel kriterlerde hedef **sabit değil**: insan-insan kappa × 0.85.
  IRR ölçülmediği için şu an hedef **konulmuyor** — hedef uydurulmuyor
- İnsan referansı altyapısı: 20 senaryoluk şablon + IRR karşılaştırması
  (`scripts/golden/human_ref.py`)
- **Kriter bazlı model yönlendirmesi** (ölçüldü): `qwen2.5:14b-instruct` ile
  dört öznel kriterin **üçünde** gürültüyü aşan kazanç — İhtiyaç Analizi
  0.11→0.46, Çözüm 0.20→0.45, Aktif Dinleme 0.08→0.23. Bilgi Doğruluğu'nda
  ölçüm sonuçsuz. Varsayılan kapalı (9 GB, 3× yavaş)
- OIDC/SSO **yönetim ekranından** yapılandırılıyor; sır asla geri dönmüyor
- Şifreleme anahtarı **dosyadan** (ortam değişkenini ezer) + rotasyon
  penceresi + KMS/Vault entegrasyon yolu (`docs/KVKK-UYUM.md` §3.1–3.2)
- Rol bazlı açılış ekranı: kaliteci → inceleme kuyruğu, yönetici → kokpit,
  temsilci → kendi karnesi
- `docs/internal/SORULAR.md`: **17 sorunun tamamı kapatıldı**, açık soru yok

### Kapatılan hatalar
B1–B26 (prompt dosyasında listelenen) + B27–B32 (denetimde bulunan)
+ B33–B34 (kapanış turunda bulunan) = **34 hata**.
Her biri için regresyon testi veya altın set senaryosu var.

- **B33** — Temsilci karnesi, kaliteci onaylamamış AI puanını sayıyordu.
- **B34** — Opt-in model yönlendirmesi, kapalıyken bile kriter gruplamasını
  değiştiriyordu. Kusur birim testle kanıtlandı; ilk gösterdiğim kappa farkı
  ise sonradan **gürültü aralığında** çıktı ve kanıt olarak geri çekildi.
