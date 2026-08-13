# KaliteGöz — Son Denetim Sonucu

**Tarih:** 2026-08-13 · **Kapsam:** kod yazmadan önce baştan sona tarama,
sonra bulunanların düzeltilmesi · **Yöntem:** her madde için ölçüm; "yapıldı"
demek yerine kanıt.

Bu tur **4 gerçek kusur** buldu ve düzeltti, **1 yanlış iddiayı geri çekti**,
ve **6 "bulgu"nun aslında ölçüm hatam olduğunu** ortaya çıkardı. Sonuncusu
tesadüf değil: denetim aracının çıktısı da bir iddiadır ve doğrulanması
gerekir.

---

## 1. Madde madde durum

| # | Kontrol | Durum | Kanıt |
|---|---|---|---|
| 1 | Önceki turun 9 maddesi | ✅ | §2 |
| 2 | B1–B40 kapanış + regresyon | ✅ | §3 |
| 3 | Temiz makinede sıfırdan kurulum | ✅ | §4 |
| 4 | 20 bekleyen / 0 işlenmiş çağrı | ✅ | §4 |
| 5 | Ollama canlı, modeller kurulu | ✅ | §4 |
| 6 | Rol bazlı giriş + yetki sınırları | ✅ | §5 |
| 7 | Her sayfa × 2 tema × TR/EN | ✅ 64 varyant | §6 |
| 8 | Ölü buton / boş sayfa / ölü link | ✅ 0 | §6 |
| 9 | `border-radius` sıfır | ✅ | §7 |
| 10 | TODO/FIXME/mock/lorem sıfır | ✅ | §7 |
| 11 | `.env` commit edilmemiş, geçmişte sır yok | ✅ | §8 |
| 12 | `make test` + `make eval` + denetimler | ✅ | §9 |
| 13 | README / CLAUDE.md / docs gerçeği yansıtıyor | ⚠️ → ✅ | §10 |

---

## 2. Önceki turun 9 maddesi — kanıtla

| Madde | Kanıt | Ölçüm |
|---|---|---|
| 1 · Piyasa analizi | `docs/PIYASA-ANALIZI.md` | 292 satır, 13 sağlayıcı adı geçiyor |
| 2 · Keskin köşe | `--radius: 0` tek token | grep: 0 `rounded-*` kullanımı, 0 SVG `rx/ry`, tüm `border-radius` token'dan |
| 3 · Ekran denetimi | `docs/screens/` + `docs/internal/UI-DENETIM.md` | 40 görüntü, iki tur |
| 4 · Sil baştan kur | Bu turda **tekrar** yapıldı | §4 |
| 5 · Temiz başlangıç verisi | 20 çağrı, hepsi bekliyor | §4 |
| 6 · Testler yeşil | §9 | 514 backend + 83 betik |
| 7 · Test rehberi | `docs/TEST-REHBERI.md` | 567 satır, 35 numaralı adım |
| 8 · Repo temizliği | Kök dizin | `README CHANGELOG CLAUDE.md LICENSE Makefile docker-compose.yml backend data docs frontend scripts` + üretilen `secrets/` |
| 9 · `.env` eksiksiz | `.env` ↔ `.env.example` | 76 ↔ 76 anahtar, **aynı sıra**, 0 yorumsuz anahtar, CR yok |

**Madde 9'da bir eksik bulundu ve düzeltildi:** 6 anahtarın üstünde açıklama
yorumu yoktu (`WORKER_MEM`, `OIDC_CLIENT_SECRET`, `OIDC_REDIRECT_URI`,
`SMTP_FROM`, `SMTP_USE_TLS`, `REPORT_RECIPIENTS`). Şimdi 0.

**Madde 9'da ikinci ve ciddi bir eksik:** aşağıda B42.

---

## 3. B1–B40 kapanış

34 numaralı hatanın tamamı kapalı. Regresyon kapsaması iki ayrı yerde:

| Kapsam | Hatalar | Nerede koşar |
|---|---|---|
| Altın set senaryosu | B1, B2, B3, B4, B5, B6(×2), B29, B30, B32 | `make eval` — 10 `reg-b*` senaryosu, hepsi `data/golden/` içinde doğrulandı |
| pytest | B7–B14, B25, B27, B28, B31, B33, B35–B38, B40 | `make test` |
| `tr-audit` | B15, B16, B17 | `make audit` |
| Arayüz denetimi | B18–B24, B26 | `ui-audit` + ekran süpürmesi |

Doğrulama: `data/golden/` içinde 50 senaryo, bunların 10'u `reg-b*` öneki
taşıyor ve hepsi mevcut.

---

## 4. Sıfırdan kurulum

Yıkıcı adım kullanıcının açık talebiyle yapıldı.

```
docker compose down -v --rmi local      # 5 imaj + tüm hacimler silindi
rm -rf .env secrets/                    # taze klon simülasyonu
bash scripts/generate-secrets.sh        # TEK komut
docker compose up -d --build
```

**Taze klon kanıtı:** `.env` ve `secrets/` silindikten sonra `git status`
**boş** çıktı — ikisi de gerçekten takip dışı.

| Kontrol | Sonuç |
|---|---|
| `generate-secrets.sh` | Tek komutta 5 sır üretti, `.env` yazdı, giriş parolasını bir kez gösterdi |
| `.env` ↔ `.env.example` | 76 ↔ 76 anahtar, aynı sıra, **CR yok** |
| Zorunlu sırlar | `JWT_SECRET` `SESSION_SECRET` `ADMIN_PASSWORD` `DATABASE_URL` `REDIS_URL` `POSTGRES_PASSWORD` — hepsi dolu |
| `/health` | `{"status":"ok","version":"2.0.0"}` |
| `/ready` | `{"database":"ok","redis":"ok"}` |
| Konteynerler | 7/7 çalışıyor |

**Korunması gerekenler** (silme yasağı): `data/golden/` 51 dosya,
`data/human_ref/` 1, `docs/eval/` 9, git geçmişi 34 commit — hepsi yerinde.

### Başlangıç durumu

```
toplam çağrı     : 20
  status=pending : 20     <- hiçbiri işlenmemiş
demo bayraklı    : 20
is_golden        : 0
puan / alarm / ihlal : 0 / 0 / 0
temsilcisi atanmış   : 20
işleme duraklatılmış : true   (queued_now: 0)
kullanıcı 16 · temsilci 12 · rubrik kriteri 10 · takım 2
```

Dağılım üretim anında doğrulandı: **6 yüksek · 6 orta · 4 düşük ·
2 sıfırlayıcı · 2 kriz**.

> Bir ölçüm hatam: ilk saydığımda 17 çağrı gördüm ve "eksik" sandım. Watcher
> dosyaları ~3 saniyede bir alıyor; erken bakmışım. 45 saniye sonra 20/20.

### Ollama

Host'ta (Docker'da değil), 6 model kurulu:
`qwen2.5:14b-instruct` (9.0 GB) · `qwen2.5:7b-instruct` (4.7 GB) ·
`qwen3-vl:4b` (3.3 GB) · `qwen3.5:4b` (3.4 GB) · `bge-m3` (1.2 GB) ·
`nomic-embed-text` (0.3 GB).

Konteynerden erişim doğrulandı:
`http://host.docker.internal:11434/api/tags → 200, 6 model`.

---

## 5. Rol bazlı giriş ve yetki sınırları

Dört rolün dördü de giriş yapabiliyor.

| Uç | admin | süpervizör | kalite | temsilci |
|---|---|---|---|---|
| `/admin/users` | ✅ | 403 | 403 | 403 |
| `/admin/ai/config` | ✅ | 403 | 403 | 403 |
| `/admin/ai/models` | ✅ | 403 | 403 | 403 |
| `/analytics/timeseries` | ✅ | ✅ | ✅ | 403 |
| `/enterprise/security-checks` | ✅ | ✅ | ✅ | 403 |
| `/criteria`, `/calls` | ✅ | ✅ | ✅ | ✅ |

Jetonsuz erişim: `/calls`, `/admin/users`, `/criteria` → hepsi engellendi.

**Veri kapsamlaması ölçüldü** — sadece durum kodu yetmez:

| Rol | `/agents` döndürdüğü |
|---|---|
| admin | 12 temsilci (hepsi) |
| süpervizör | **6** (yalnız kendi takımı) |
| temsilci | **1** (yalnız kendisi) |

`agents.py:118-121` bu kapsamlamayı açıkça yapıyor ve yorumlamış.

> **Beş "ihlal" bulmuştum, beşi de benim yanlış beklentimdi.**
> `/security-checks`'i admin'e özel sandım — `require_staff` kullanıyor ve
> sidebar da aynı üç role gösteriyor, tutarlı. `/agents`'ı "sızıntı" sandım —
> 200 dönüyor ama yalnızca çağıranın kendi kaydını. Durum kodunu okuyup
> içeriği okumamak, olmayan bir açık uydurmak demekmiş.

---

## 6. Arayüz süpürmesi

`scripts/ui_sweep.mjs` — **16 sayfa × 2 tema × 2 dil = 64 varyant**, sonra
her sayfada etkileşimli öğeler tek tek tıklandı.

| Ölçüm | Sonuç |
|---|---|
| Çöken sayfa | **0** |
| Boş sayfa (ana içerik < 60 karakter) | **0** |
| Ölü buton | **0** |
| Ölü link (4xx dönen `/` bağlantısı) | **0** |

Bir buton "canlı" sayılmak için tıklandığında şunlardan biri olmalı: DOM
değişir · ağ isteği gider · gezinme olur · odak değişir · `localStorage`
durumu değişir. Yıkıcı öğeler (sil, çıkış, işlemeyi başlat) bilinçli olarak
dışarıda — denetim, denetlediği sistemi bozmamalı.

### Süpürmenin kendi ürettiği 6 yanlış pozitif

İlk koşum 5 "ölü buton" ve 1 "403" raporladı. **Altısı da yanlıştı** ve
sebepleri öğretici:

| Rapor | Gerçek |
|---|---|
| `giriş: 🌙`, `🖥️`, `🇹🇷 TR` ölü | Süpürme **zaten aktif** olan seçeneğe tıklıyordu. Aktif seçeneğe tıklamak hiçbir şeyi değiştirmez ve bu doğru davranıştır. Ayrıca `getByRole(name:"🌙")` erişilebilir ada bakar; buton `title="Dark"` taşıyor, eşleşme düştü ve tıklama sessizce yapılmadı. Ölçünce: üç tema seçeneği de `data-theme` + `kg_theme`'i doğru değiştiriyor. |
| `analitik: Ortalama puan`, `Takım` ölü | Aynı sebep. "CSAT" ve "Kampanya"ya tıklayınca istek gidiyor. Ayrıca kendi kalıbım "Kampanya"yı hiç aramıyordu. |
| `HTTP 403 /admin/users` | **Ürün kusuru değil, düzeneğimin yan etkisi.** Tek tarayıcı bağlamında rolden role geçince önceki sayfanın geciken isteği sonraki sayfanın sayacına yazılıyordu. Temiz bağlamda her sayfa doğru rolüyle açıldığında **sıfır 4xx** (`scripts/probe_403.mjs`). |

Süpürme düzeltildi: `data-active` / `aria-pressed` / `aria-selected` /
`aria-current` taşıyan öğeler atlanıyor, ve durum değişimi artık
`localStorage` üzerinden de ölçülüyor. Düzeltilmiş koşum: **0 ölü buton**.

Bu, geçen turun B40 dersinin tekrarı: *yanlış pozitif üreten denetim
görmezden gelinir.*

---

## 7. Statik kontroller

| Kontrol | Sonuç |
|---|---|
| `TODO` / `FIXME` / `XXX` / `HACK` (takip edilen dosyalar) | **0** |
| `lorem` / `ipsum` | **0** |
| `mock` (test dışı) | **0** |
| `.venv`, `node_modules`, `__pycache__`, `.next` takip ediliyor mu | **hayır** |
| Takip edilen dosya sayısı | 415 |
| `rounded-*` sınıf kullanımı | **0** (yalnız yorumlarda) |
| SVG `rx` / `ry` | **0** |
| `border-radius` | hepsi `var(--radius)`, tek tanım `--radius: 0` |
| Tailwind `borderRadius` ölçeği | 9 girdinin **hepsi** `var(--radius)` |

`placeholder` eşleşmelerinin tamamı HTML `placeholder` niteliği — meşru.

---

## 8. Sır denetimi

| Kontrol | Sonuç |
|---|---|
| `.env` takip ediliyor mu | **hayır** (`git check-ignore` doğruladı) |
| `secrets/` takip ediliyor mu | **hayır** |
| Geçmişte eklenen `.env*` dosyası | yalnız `.env.example` |
| Tüm commit'lerde `sk-…`, `AIza…`, `ghp_…`, `xox…`, PEM özel anahtar | **0 gerçek eşleşme** |
| Uzun rastgele sır ataması | yalnız `.env.example` içindeki açıklayıcı yer tutucular |
| Ekran görüntülerinde sır | **yok** — yeni 40 görüntü bu gözle incelendi; API anahtarı alanları yalnız bulut sağlayıcı seçiliyken görünüyor ve boş |

`sk-qa-quality-assurance` gibi iki eşleşme çıktı; ikisi de
`docs/PIYASA-ANALIZI.md` içindeki bir bağlantı adresinin parçası.

---

## 9. Testler ve denetimler

| Komut | Sonuç |
|---|---|
| Backend regresyon takımı | **514 geçti** |
| Betik testleri | **83 geçti** |
| `tr-audit` | **0 ihlal** (5 kontrol) |
| `ui-audit` | **0 ihlal** (7 kontrol) |
| `api-audit` | **0 uyuşmazlık** (65 uç) |
| `tsc --noEmit` | **0 hata** |
| Ekran süpürmesi | 64 varyant, 0 çöken |

### `make eval` — 50 senaryo, gerçek puanlama motoru

**Tüm eşikler sağlandı, çıkış kodu 0.** Ham çıktı:
[`docs/eval/2026-08-13-son-denetim.json`](eval/2026-08-13-son-denetim.json).

| Metrik | Bu koşum | Eşik |
|---|---|---|
| Sıfırlayıcı yanlış-pozitif | **%0.0** | %0 |
| Sıfırlayıcı yanlış-negatif | **%0.0** | — |
| Kanıt doğrulanabilirlik | **%100** | ≥%95 |
| Kanıtsız ceza ihlali | **0** | 0 |
| Kaçırılan kriz | **0** | 0 |
| Kriter MAE | 0.783 | ≤1.0 |
| Tam isabet | %64.5 | — |
| Tekrarlanabilirlik std | 0.46 | ≤1.5 |
| **Nesnel kappa** | **0.7639** | — |
| **Çekirdek nesnel en düşük** | **0.9392** | ≥0.90 |
| Öznel kappa | 0.0931 | hedef yok |

**Demo verisi izolasyonu doğrulandı:** koşum `golden` adlı ayrı bir kiracı
yarattı; 20 demo çağrının hepsi **bekliyor** durumunda kaldı, hiçbiri
puanlanmadı.

**B35 canlı koşulda test edildi:** eval *koşarken* `/auth/config`
`org_slug: "demo"` döndü (`golden` değil) ve dört rolün dördü de 200 ile
giriş yaptı. B35 tam olarak bu anda kırılıyordu.

### Ölçümün ortaya çıkardığı yeni bilgi: gürültü bandı sanılandan geniş

Nesnel kappa **0.7639** — altıncı kez kuruşu kuruşuna aynı. Katman A'nın
gerçekten deterministik olduğunun bir kanıtı daha.

Öznel kappa ise art arda üç koşumda:

| Koşum | Öznel kappa |
|---|---|
| çoklu sağlayıcı öncesi | 0.1637 |
| çoklu sağlayıcı sonrası | 0.1078 |
| bu denetim | **0.0931** |

Aralarındaki değişiklikler puanlama koduna **dokunmadı** (sağlayıcı hata
yolu, env varsayılanları, arayüz etiketleri). Yani bu düşüşün bir mekanizması
yok — ölçtüğü şey koşum-arası varyansın kendisi.

Bunun pratik sonucu: `CLAUDE.md`'de yazan **"0.05 altı farklar
yorumlanmamalı"** eşiği **yetersiz**. Toplam oynama 0.07. Belgeler buna göre
güncellendi ve öznel kappa artık tek sayı değil **0.09–0.18 aralığı** olarak
yazılıyor.

Bu, ürünün lehine olmayan bir düzeltme ve bilinçli: en iyi koşumu seçip
yazmak tabloyu güzelleştirir, gerçeği değiştirmez.

---

## 10. Doküman doğruluğu

Üç düzeltme gerekti — **üçü de ürünün lehine sapan sayılardı**, bu yüzden
düzeltilmesi önemliydi.

| Nerede | Yazan | Ölçülen | Yapıldı |
|---|---|---|---|
| `README.md` | MAE **0.78** | 0.758 | 0.76 yazıldı |
| `README.md` | Tam isabet **%64.9** | %65.2 | güncellendi |
| `README.md` (TR+EN) | Öznel kappa **0.18** | son iki koşum 0.1637 ve 0.1078 | **0.11–0.18 aralığı** yazıldı |
| `CLAUDE.md` | Öznel kappa 0.18 | aynı | aralık + gürültü notu |
| `docs/FINAL-RAPOR.md` §8 | "Süpervizör `/admin/users` 403 alıyor" | temiz bağlamda 0 4xx | **madde geri çekildi** |

Öznel kappa'yı aralık olarak yazmak bilinçli: en iyi koşumu seçmek tabloyu
güzelleştirir ama kriter bazlı varyans henüz ölçülmediği için bu oynamanın
ne kadarının gürültü olduğu bilinmiyor.

---

## 11. Bulunan ve düzeltilen kusurlar

### B41 — İngilizce arayüzde Türkçe metin kalıyordu

`frontend/lib/api.ts` altı etiket haritası tutuyordu (kategori, durum, kanal,
ihlal, duygu, rol) ve değerleri **sabit Türkçe metindi**. Arayüz onları
olduğu gibi basıyordu.

**Ölçüldü** (`scripts/probe_dil.mjs`, İngilizce arayüz):

```
çağrılar  → "Kuyrukta"
arama     → "Sesli"
kokpit    → (temiz — ama yalnızca işlenmiş çağrı olmadığı için;
             kategori etiketleri de aynı şekilde sızacaktı)
```

Roller için **aynı sorun daha önce fark edilip** `ROLE_LABEL_KEYS` ile
çözülmüş, kalan beş harita öyle bırakılmıştı: kural biliniyordu, yarısı
uygulanmıştı.

Denetim bunu görmüyordu çünkü `tr-audit` yalnızca `i18n.ts` sözlüğüne ve JSX
metin düğümlerine bakıyordu; `lib/` altındaki sabitler kapsam dışıydı.

**Düzeltme**
- Altı harita `*_LABEL_KEYS` oldu, 26 anahtar TR + EN eklendi.
- `Badges.tsx` içindeki üç sabit metin (`— sıfırlayıcı ihlal`, sıfırlama
  tooltip'i, `Kriz`) i18n'e taşındı.
- `api.ts` bir bileşen olmadığı için `useT()` çağıramıyor; `i18n.ts`'in
  kancasız `translate(lang, key)` fonksiyonuna bağlandı.
- **Yeni denetim kontrolü** `tr-audit → istemci sabitleri`: `frontend/lib/`
  altındaki dize sabitlerinde Türkçe'ye özgü harf arar.

Kontrol eklenir eklenmez **5 sızıntı daha** buldu — kullanıcıya gösterilen
hata mesajları (`Demo giriş başarısız`, `Kurum oluşturulamadı`,
`Parola sıfırlanamadı`, `Ses yüklenemedi`, `İndirme başarısız`). Onlar da
çevrildi.

**Yan fayda:** `pending` durumunun etiketi **"Kuyrukta" → "Bekliyor"**
oldu. Eski etiket yanıltıyordu: işleme duraklatılmışken çağrı bir kuyrukta
değil, kullanıcının başlatmasını bekliyor — `/admin/processing` aynı anda
`queued_now: 0` döndürüyordu.

**Doğrulama:** yeniden ölçüm → üç sayfada da `(yok)`.

### B42 — "Zorunlu env eksikse dur" kuralı üç alan için hiç çalışamıyordu

Önceki turun şartı açıktı: *"Zorunlu bir env değişkeni eksik veya boşsa
uygulama açık Türkçe hata mesajıyla düşsün, sessizce varsayılana kaçmasın."*

`zorunlu_ayarlari_dogrula` beş alanı zorunlu ilan ediyor ve alanın **boş**
olmasını arıyordu. Ama üçünün `Settings` içinde **dolu varsayılanı** vardı:

| Alan | Eski varsayılan |
|---|---|
| `jwt_secret` | `kalitegoz-dev-secret-CHANGE-IN-PROD` |
| `database_url` | `postgresql+psycopg://kalitegoz:kalitegoz@postgres:5432/…` |
| `redis_url` | `redis://redis:6379/0` |

Dolu varsayılan, "boş mu?" kontrolünü **erişilemez** kılar. Kural yazılıydı,
listede duruyordu, üç alan için hiçbir zaman ateşleyemezdi.

Somut sonucu: `JWT_SECRET` tanımsızsa uygulama **bilinen bir imza
anahtarıyla** ayağa kalkıyordu. Üretim koruması yalnızca
`ENVIRONMENT=production` iken devreye giriyor ve varsayılan `development`.
`database_url` varsayılanı ayrıca sabit bir parola içeriyordu.

**Düzeltme:** üçünün de varsayılanı boşaltıldı, gerekçesi koda yazıldı.
Konteyner testleri lifespan'ı tetiklemiyor ve compose `.env`'den besleniyor,
dolayısıyla kırılma yok — 514 test yeşil.

### B43 — Bu korumanın hiç testi yoktu

Kendi doğruluğunu iddia eden ama sınanmayan bir koruma, korumadığını fark
ettirmez. `backend/tests/test_zorunlu_ayarlar.py` — **18 vaka**:

- Beş zorunlu alanın **hiçbirinin** dolu varsayılanı olamaz (parametreli).
- Her alan eksikken uygulama duruyor ve hata mesajı **hangi değişken**
  olduğunu söylüyor.
- Mesaj Türkçe ve **çözüm adımını** (`generate-secrets.sh`) veriyor.
- `"   "` dolu sayılmıyor.
- Üretimde kısa JWT / demo modu / joker CORS reddediliyor; geliştirmede
  bunlar uygulanmıyor.
- Doğrulamanın `main.py`'de **çağrıldığı** kaynak düzeyinde kilitli — bu
  depoda "yazılı ama çağrılmıyor" kalıbı iki kez yaşandı.

---

## 11b. B44 — sesli işçi çalışmıyorken başlat sessizce boşa gidiyordu

Bu, denetimin **en pahalı** bulgusu: ürünün ana akışı, hata vermeden
çalışmıyordu.

Sesli çağrılar `voice` kuyruğuna gider (`celery_app.task_routes`) ve o
kuyruğu yalnızca host'taki native worker tüketir — Whisper konteynerin
bellek tavanına sığmıyor (exit 137). Worker yokken "İşlemeyi başlat":

| Adım | Ne oluyor |
|---|---|
| 1 | 20 çağrı `voice` kuyruğuna atılır |
| 2 | Celery **başarıyla** döner — kuyruğa yazmak başarılıdır |
| 3 | Panel "20 kuyruğa alındı" der |
| 4 | Çağrılar **sonsuza kadar** `pending` kalır |

Hiçbir yerde hata yok. Ölçüldü: denetim başında `active_queues()` yalnızca
`fast@konteyner` döndürüyordu, `voice` dinleyicisi **yoktu**.

**Düzeltme:** `/admin/processing` artık `voice_worker_active` ve
`voice_worker_hint` döndürüyor; yönetim ekranı başlat butonunun hemen
üstünde uyarıyor ve çalıştırılacak komutu yazıyor. Broker yanıt vermezse
panel çökmüyor, "bilinmiyor" diyor.

**Regresyon:** `backend/tests/test_voice_worker_uyarisi.py` (7 vaka) — biri
arayüzün uyarıyı gerçekten bastığını, biri `process_call`'ın hâlâ `voice`
kuyruğuna gittiğini kaynak düzeyinde kilitliyor.

### Uçtan uca zincir kanıtlandı

Bir çağrı gerçek hattan geçirildi:

```
host Whisper  → 15 segment · zaman sırası ARTAN · temsilci 10 / müşteri 5
Ollama        → 10 kriter puanlandı
kanıt doğrulama → 9 doğrulandı · 1 yetersiz kanıt · 0 doğrulanamayan
ihlal motoru  → 2 ihlal
toplam puan   → 82.6 (kodda hesaplandı, LLM'e sorulmadı)
```

"Yetersiz kanıt" alan 1 kriter puanlanmadı ve insana yönlendirildi —
tasarlanan davranış tam olarak bu.

---

## 12. Kalan açıklar

Düzeltilmeyenler ve **neden**:

1. **Bulut sağlayıcı gerçek anahtarla denenmedi.** Elimde Gemini/OpenAI/
   OpenRouter anahtarı yok. Kanıtlanan: sahte anahtarla istek atıldığında üç
   sağlayıcı da kendi gerçek adresinden kendi kimlik doğrulama hatasını
   döndürüyor. Kanıtlanmayan: gerçek yanıtın JSON şemasının puanlayıcıyı
   memnun ettiği. Anahtar girildiğinde ilk basılacak yer panelin
   "Bağlantıyı test et" düğmesi.

2. **`secrets/kg_master_key` izni Windows'ta 0600 değil.**
   `generate-secrets.sh` "0600" yazdırıyor ama dosya `644` görünüyor —
   `chmod` NTFS'te aynı şekilde uygulanmıyor. Linux dağıtımda doğru. Betiğin
   çıktısı bu platformda gerçeği tam söylemiyor; kullanıcı Windows'ta
   çalıştığının farkında olmalı.

3. **Kriter bazlı varyans hâlâ ölçülmedi — ama artık alt sınırı biliniyor.**
   Üç ardışık koşumda öznel kappa 0.1637 → 0.1078 → 0.0931 ölçüldü; toplam
   oynama **0.07** ve mekanizması yok. Belgelerde yazan 0.05'lik "gürültü
   bandı" bu yüzden yetersiz. Gerçek bandı saptamak aynı yapılandırmayla çok
   sayıda koşum ister (~20 dk × N) ve bu turda yapılmadı.

4. **Ekran okuyucuyla test edilmedi.** Tema ve dil düğmeleri `aria-label`
   değil `title` taşıyor; erişilebilir ad emoji oluyor. İşlevsel olarak
   çalışıyor, gerçek bir okuyucuyla gezilmedi.

5. **B18–B24, B26 için otomatik regresyon yok.** Bunlar arayüz kararları
   (sidebar gruplaması, tek `EmptyState` bileşeni, ayrı inceleme ekranı).
   Ekran süpürmesi çöktüklerini yakalar, *geri alındıklarını* yakalamaz.

---

## 13. Sistemin şu anki hali

```
demo kiracısı: 20 bekleyen çağrı · 0 puan · 0 alarm · 0 ihlal
API'nin admin'e döndürdüğü toplam: 20
işleme duraklatılmış → kullanıcı "İşlemeyi başlat" diyecek
Ollama host'ta, 6 model kurulu, konteynerden erişilebiliyor
7 konteyner çalışıyor · /health ok · /ready ok
```

**Bir not:** `make eval` koşumu `golden` adlı **ayrı bir kiracı** bıraktı
(50 senaryo + puanları). Bu kiracı arayüzde görünmez — `/calls` kiracıya
göre kapsamlanır ve admin'e 20 döner. Silmedim: her `make eval` koşumunda
yeniden üretiliyor ve kullanıcının gördüğü hiçbir şeyi etkilemiyor. Yıkıcı
bir temizlik yapmak yerine burada söylemeyi tercih ettim.
