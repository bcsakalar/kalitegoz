# CLAUDE.md — bu depoda çalışma rehberi

Bu dosya gelecekteki oturumlar içindir. Ürünün ne olduğu değil, **burada nasıl
çalışıldığı** yazılıdır.

---

## 1. Ürün tek cümlede

Çağrı merkezi görüşmelerini otomatik puanlayan, **her kararın kanıtını
transkriptten gösteren** ve güvenilir olmadığı kriteri insana yollayan bir
kalite yönetim platformu. Tamamen yerel çalışır.

---

## 2. Mimari özeti

```
HOST (Docker DIŞI)          Ollama :11434  ·  Whisper STT worker
        ↕ host.docker.internal
DOCKER COMPOSE              frontend :3000 · api :8000 · worker-fast
                            beat · watcher · postgres :5432 · redis :6379
```

**Yapay zekâ Docker'da DEĞİL.** GPU erişimi, model dosyası boyutu ve bellekte
kalma (`OLLAMA_KEEP_ALIVE`) sebebiyle. Bunu değiştirmeyi önerme.

Puanlama üç katmandır ve sırası önemlidir:

| Katman | Nerede | Ne yapar |
|---|---|---|
| **A** | `services/deterministic.py` | Kesin cevabı olan kriterler — **kodla**, LLM'e sorulmadan. LLM'i **ezer**. |
| **B** | `services/scoring_layers.py` | Öznel kriterler — LLM, 3'lü gruplar, sıcaklık 0, kanıt zorunlu |
| **C** | `services/scoring_layers.py` + `scoring.py` | Alıntı transkriptte **aranır**; toplam puan **kodda** hesaplanır |

Ayrıntı: [docs/MIMARI.md](docs/MIMARI.md)

---

## 3. Dizin haritası

```
backend/app/
  api/          FastAPI router'lari (HTTP yuzeyi)
  services/     Is mantigi — asil kod burada
  models.py     SQLAlchemy — TEK kaynak
  schemas.py    Pydantic giris/cikis
  migrations.py Hafif, idempotent kolon/indeks migrasyonlari
  seed.py       Baslangic verisi
backend/tests/  pytest — her hata icin regresyon vakasi

frontend/
  app/          Next.js App Router sayfalari
  components/   Paylasilan bilesenler
  lib/          api.ts (istemci) · types.ts · i18n.ts (TR+EN sozluk)
  tailwind.config.ts   Tasarim tokenlari

scripts/
  golden/       Altin set: build.py · evaluate.py · human_ref.py · compare.py
  tr_audit.py   Turkce karakter + jargon denetimi
  ui_audit.py   Keskin kose + tanimli renk denetimi
  shots.mjs     Arayuz ekran goruntusu (Playwright)

data/golden/    Altin set — SURUM KONTROLUNDE, asla silinmez
data/human_ref/ Insan referans sablonu — SURUM KONTROLUNDE
docs/internal/  Faz raporlari, karar defteri — .gitignore'da
```

---

## 4. Make komutları

| Komut | Ne yapar |
|---|---|
| `make up` / `make down` | Servisleri başlat / durdur |
| `make test` | Backend regresyon takımı (konteyner içinde) |
| `make eval` | **Altın set üzerinde gerçek puanlama motorunu koşar.** Eşikler sağlanmazsa çıkış kodu 1 |
| `make eval-baseline` | Aynı koşum, eşik kapısı kapalı (taban çizgisi için) |
| `make audit` | `tr-audit` + `ui-audit` |
| `make demo` | Satış demosu verisi |

`make eval` ~20 dakika sürer (50 senaryo × gerçek LLM). Arka planda koştur.

---

## 5. Çalışma kuralları

### Ölç, tahmin etme

Bu projedeki en pahalı hatalar hep aynı şekilde oldu: **ölçmeden iddia etmek.**
Somut örnekler (hepsi gerçekten yaşandı):

- `make eval` kapısı ölçülmeden `0.90` konuldu; gerçek `0.7639` çıktı ve kapı
  ilk günden kırmızı yandı.
- Bir kappa farkı (0.146→0.124) hata kanıtı diye gösterildi; sonra gürültü
  seviyesi ölçülünce farkın gürültü içinde kaldığı görüldü ve **kanıt geri
  çekildi**.
- Piyasa analizinde "kanal bazlı skorkart eksik" denildi; koda bakınca
  **zaten uygulanmış** olduğu görüldü.

Kural: bir sayı yazacaksan önce ölç. Ölçemiyorsan "ölçülmedi" yaz.

### Yazılı ama uygulanmayan kural arama

İki kez aynı hata çıktı: kural modelde/dokümanda **yazılıydı**, kodda
**uygulanmıyordu**.

- `Call.score_is_final` docstring'i "karneye girebilir mi?" diyordu; temsilci
  karnesi `qa_state`'e hiç bakmıyordu (B33).
- `hedefler()` fonksiyonu S2b kararını cisimleştiriyordu ama **hiç
  çağrılmıyordu**.

Bir kural gördüğünde "bu gerçekten uygulanıyor mu?" diye sor.

### Sessiz başarısızlıklara dikkat

Hata vermeyen, sadece çalışmayan şeyler:

- Tanımsız CSS değişkeni → renk uygulanmaz, konsol sessiz (33 vaka bulundu)
- Tanımsız Tailwind sınıfı → stil atlanır (12 vaka)
- SQL `LIKE` içinde `_` tek karakter jokeri → filtre her şeyi eler
- Fonksiyon-yerel `from . import x` → modül gölgelenir, `UnboundLocalError`
  try/except'e yutulur

`make audit` bunların bir kısmını yakalar; kalanı için dikkat.

### Her hata bir regresyon vakası

Düzeltilen her hata için test veya altın set senaryosu yazılır. Henüz
düzeltilmemişse `xfail(strict=True)` kullanılır — düzeltilince test
"beklenmedik şekilde geçti" diye takımı kırar ve işaretçiyi kaldırmaya zorlar.

### Dürüstlük ürünün özelliği

`docs/KALITE-METODOLOJISI.md` satışta kullanılır ve **zayıf tarafları da
yazar**. "%100 doğru" iddiası ürünü satmaz, batırır. Bir metriği iyileştiremiyorsan
gizleme — ölç, yaz, ürün davranışına çevir (güven tavanlama gibi).

---

## 6. Asla yapma

| Yapma | Neden |
|---|---|
| **Yapay zekâyı Docker'a koyma** | GPU, model boyutu, bellekte kalma |
| **LLM'e toplam puan hesaplatma** | Aritmetik kodda; model sadece kriter kararı verir |
| **Kanıtsız ceza verme** | Doğrulanamayan alıntı → `insufficient_evidence`, puan yok |
| **`data/golden/` veya `data/human_ref/` silme** | Ürünün doğruluk iddiasının kanıtı |
| **`.env` commit etme** | `.gitignore`'da; sır sızarsa yenisi üretilmeli |
| **Ölçmeden eşik/hedef koyma** | İlk günden kırmızı yanan kapı işe yaramaz |
| **`docker compose down -v` çalıştırma** | Kullanıcı açıkça istemedikçe — veri siler |
| **Türkçe metinde ASCII kullanma** | `make audit` build'i kırar |
| **`border-radius` ekleme** | Tasarım kuralı: her yerde 0, tek token |

---

## 7. Kod stili

**Python**
- Türkçe docstring ve yorum. Yorum *ne yaptığını* değil **neden öyle
  olduğunu** anlatır; tercihin gerekçesi ve alternatifin neden seçilmediği.
- Değişken/fonksiyon adları Türkçe olabilir (`kaydet`, `dogrula`, `hedefler`)
  ama mevcut dosyanın diline uy.
- Tip ipuçları zorunlu. `from __future__ import annotations` kullanılıyor.
- Geniş `except Exception` yalnızca "bu hata ana akışı düşürmemeli" olduğunda
  ve `# noqa: BLE001` + gerekçe yorumuyla.

**TypeScript / React**
- `"use client"` gerektiğinde. Bileşen başında amacı ve **neden var olduğunu**
  anlatan blok yorum.
- Renk ve boşluk **token** üzerinden: `bg-surface`, `text-ink2`,
  `border-hairline`. Ham hex kullanma.
- Kullanıcıya görünen her metin `i18n.ts` üzerinden (TR + EN).

**Genel**
- Satır uzunluğu ~90.
- Commit mesajı Türkçe, ne değiştiğini **ve neden** anlatır. ASCII yeterli
  (Windows konsol uyumu için commit mesajlarında diakritik kullanılmıyor).

---

## 8. Test beklentisi

| Ne | Beklenen |
|---|---|
| `make test` | Tamamı yeşil. Yeni kod = yeni test. |
| `make eval` | Tüm eşikler sağlanmalı; çıkış kodu 0 |
| `make audit` | 0 ihlal |
| `tsc --noEmit` | 0 hata |

Yeni bir servis eklediğinde testi de yaz. Test yazmadan "çalışıyor" deme.

---

## 9. Bilinen sınırlar (uydurma, bunları tekrar keşfetme)

- **Öznel kriterlerde kappa düşük** (koşumlara göre 0.09–0.18) ve bu bilinçli
  olarak raporlanıyor. Tek sayı değil aralık yazılıyor: en iyi koşumu seçmek
  tabloyu güzelleştirir, gerçeği değiştirmez.
  Üç iyileştirme denendi ve **ölçülerek başarısız oldu** (few-shot, skala
  kalibrasyonu, deterministik tavan). Dördüncüsü (14B model) üç kriterde
  işe yaradı, biri sonuçsuz.
- **Öznel kriterlerde hedef yok** — insan-insan uyumu (IRR) ölçülmediği için.
  Hedef uydurulmuyor.
- **Kriter bazlı varyans ölçülmedi.** Aynı yapılandırmanın iki koşumu arasında
  öznel kappa 0.05'e kadar oynayabiliyor; 0.05 altı farklar yorumlanmamalı.
  Art arda **üç** koşumda 0.1637 → 0.1078 → 0.0931 ölçüldü; toplam oynama
  0.07, yani varsayılan banttan geniş. Hiçbiri arasında puanlama koduna
  dokunulmadı — bu oynamanın mekanizması yok. Varyans ölçülene kadar bu
  aralıktaki hareketten sonuç çıkarma, ve tek koşumu "sonuç" diye yazma.
- **Altın set sentetik.** Referans puanları sistemi geliştiren yapay zekâ
  yazdı; nesnel kriterlerde spesifikasyon, öznel kriterlerde **döngüsel**.
  `docs/KALITE-METODOLOJISI.md` §4.0 bunu açıkça söyler.
