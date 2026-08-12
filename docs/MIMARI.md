# Mimari

KaliteGöz **tamamen yerel** çalışır: ses, transkript ve puanlar kurumun
donanımından hiç çıkmaz. Bunun mimariye yansıması, yapay zekânın Docker'ın
**dışında** durmasıdır.

---

## 1. Servis topolojisi

```
┌──────────────── HOST MAKİNE (Docker DIŞI) ─────────────────┐
│                                                             │
│   Ollama          :11434    LLM + gömme (embedding)         │
│   Host STT worker           Whisper — GPU/CPU'ya doğrudan   │
│                                                             │
└──────────────────────────┬──────────────────────────────────┘
                           │ host.docker.internal:11434
┌──────────────────────────┴──────────────────────────────────┐
│                       DOCKER COMPOSE                         │
│                                                              │
│   frontend  :3000   Next.js 15 (App Router)                  │
│   api       :8000   FastAPI — REST + WebSocket               │
│   worker-fast       Celery: chat, yeniden puanlama, bakım    │
│   beat              Celery beat: saklama süresi, raporlar    │
│   watcher           data/inbox klasörünü izler               │
│   postgres  :5432   Ana veri deposu                          │
│   redis     :6379   Kuyruk + önbellek                        │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Postgres ve Redis portları host'a açılır.** Sebep: Docker dışında çalışan
STT worker'ın onlara `localhost` üzerinden bağlanabilmesi.

### Yapay zekâ neden Docker'da değil?

Üç somut sebep:

1. **GPU erişimi.** Docker içinden GPU'ya erişim, sürücü/araç zinciri
   uyumuna bağlıdır ve Windows'ta kırılgandır. Host'ta Ollama doğrudan
   donanımı kullanır.
2. **Model dosyaları.** 5–9 GB'lık modelleri imaj katmanına koymak imajı
   taşınamaz yapar; volume'a koymak da Docker'ı gereksiz bir dosya
   yöneticisine çevirir.
3. **Bellek.** Model bellekte kalır (`OLLAMA_KEEP_ALIVE`); konteyner
   yeniden başlatmaları bu belleği boşa harcar.

---

## 2. Puanlama hattı — üç katman

Bu, ürünün özüdür. Ayrıntı ve ölçümler: [KALITE-METODOLOJISI.md](KALITE-METODOLOJISI.md).

```
ses/chat
   │
   ├─ STT (Whisper) + konuşmacı ayrımı        [host worker]
   │
   ├─ KATMAN A — DETERMİNİSTİK ÖN KONTROL     [kod, LLM yok]
   │     açılış · KVKK anonsu · kimlik doğrulama · kapanış
   │     yasaklı kelime · script uyumu
   │     → kesin cevabı olan her şey burada biter ve LLM'i EZER
   │
   ├─ KATMAN B — KANIT ZORUNLU LLM            [3'lü kriter grupları]
   │     her kararın yanında transkriptten birebir alıntı
   │     sıcaklık 0, sabit prompt sürümü, harf kimlikli kriterler
   │
   ├─ KATMAN C — SUNUCU DOĞRULAMASI           [kod]
   │     alıntı transkriptte gerçekten var mı?
   │     yoksa → "yetersiz kanıt", puan YOK, insana gider
   │     toplam puan aritmetiği KODDA hesaplanır
   │
   └─ QA DURUM MAKİNESİ
         risk kuralı tetiklendi mi?
           evet → insan kuyruğu → kaliteci onayı → kesinleşti
           hayır → doğrudan kesinleşti
```

### Üç mutlak kural

1. **Kanıt yoksa ceza yok.** Doğrulanamayan alıntıyla düşük puan verilmez.
2. **Toplam puan kodda hesaplanır.** Dil modeline toplam sordurulmaz.
3. **Kanıtsız sıfırlama sistem hatasıdır** ve istisna fırlatır.

---

## 3. Veri modeli — ana varlıklar

```
Tenant ──┬── User (4 rol: admin, supervisor, quality, agent)
         ├── Team ── Agent
         ├── Criterion (rubrik) ── RubricVersion
         ├── BannedWord
         └── Call ──┬── Segment      (transkript, zaman damgalı)
                    ├── Score        (kriter başına puan + kanıt)
                    ├── Violation
                    ├── Alert
                    ├── ManualEvaluation / ReviewAssignment
                    ├── Appeal
                    └── SelfAssessment
```

**Kiracı izolasyonu** her sorguda `tenant_id` ile uygulanır ve testle
kilitlenmiştir (`test_rbac_tenant.py`).

### Çağrının iki ayrı durumu

Karıştırılmaması gereken iki alan var:

| Alan | Neyi anlatır |
|---|---|
| `Call.status` | **İşleme** durumu: pending → processing → done / failed |
| `Call.qa_state` | **Kalite** durumu: ai_puanlandi → insan_kuyrugunda → kesinlesti |

Bir çağrı `status=done` olabilir ama `qa_state=insan_kuyrugunda` olduğu için
puanı henüz **geçerli değildir**. Temsilci karnesi yalnızca `kesinlesti`
durumundakileri sayar.

---

## 4. Dizin haritası

```
backend/
  app/
    api/          FastAPI router'lari — HTTP yuzeyi
    services/     Is mantigi (puanlama, uyum, analitik, kripto…)
    models.py     SQLAlchemy modelleri — TEK kaynak
    schemas.py    Pydantic giris/cikis semalari
    migrations.py Hafif, idempotent kolon/indeks migrasyonlari
    seed.py       Baslangic verisi
  tests/          pytest — her hata icin regresyon vakasi

frontend/
  app/            Next.js App Router sayfalari
  components/     Paylasilan bilesenler
  lib/            API istemcisi, tipler, i18n sozlugu
  tailwind.config.ts   Tasarim tokenlari (radius, renkler)

scripts/
  golden/         Altin set: uretim, degerlendirme, insan referansi
  tr_audit.py     Turkce karakter + jargon denetimi
  ui_audit.py     Keskin kose + tanimli renk denetimi
  shots.mjs       Arayuz ekran goruntusu alici (Playwright)

data/
  golden/         Altin set senaryolari — SURUM KONTROLUNDE
  human_ref/      Insan referans sablonu — SURUM KONTROLUNDE
  inbox/          Izlenen klasor (ses dusurulur)
  storage/        Ses ve uretilen dosyalar — surum kontrolunde DEGIL
```

---

## 5. Yapay zekâ yapılandırması

Sağlayıcı ve model seçimi **veritabanından** gelir, `.env`'den değil.
Kurum panelden değiştirebilir; `.env` yalnızca ilk varsayılanı belirler.

| Rol | Varsayılan | Nerede kullanılır |
|---|---|---|
| LLM | `qwen2.5:7b-instruct` | Kriter değerlendirme, özet, analitik |
| Gömme (embedding) | `nomic-embed-text` | Bilgi bankası araması (RAG) |
| Görsel | `qwen3-vl:4b` | Ek dosya denetimi (opsiyonel) |

**Kriter bazlı yönlendirme:** Öznel kriterler daha büyük bir modele
gönderilebilir (`subjective_model`). Ölçüm ve gerekçe:
[KALITE-METODOLOJISI.md §4.4](KALITE-METODOLOJISI.md). Varsayılan kapalı.

Bulut sağlayıcı (Gemini/OpenAI/OpenRouter) da desteklenir ama **veri kurum
dışına çıkar** — güvenlik sayfası bunu açıkça söyler.

### Üç yüzey bağımsızdır

Puanlama, gömme ve görsel ayrı ayrı sağlayıcı seçer. Puanlama Gemini,
gömme yerel Ollama, görsel OpenAI olabilir; anahtarlar birbirine karışmaz.
Bunu `backend/tests/test_provider_routing.py` kilitler — testlerden biri
kaynak taraması yapar ve servislerde **sabit kodlanmış sağlayıcı adresi**
bulunursa kırılır. Sabit adres, kullanıcı Gemini seçtiğini sanırken çağrının
sessizce Ollama'ya gitmesi demektir.

### Model listesi canlıdır

`GET /api/v1/admin/ai/models?provider=…&kind=…` sağlayıcının **kendi
API'sinden** çeker (`services/model_catalog.py`), 15 dakika önbellekler ve
erişilemezse statik yedeğe düşer. Yanıt hangi kaynaktan geldiğini söyler
(`canli` / `onbellek` / `yedek`) ve panel bunu kullanıcıya yazar.

| Sağlayıcı | Uç | Anahtar | Ölçülen |
|---|---|---|---|
| Ollama | `/api/tags` | gerekmez | kurulu modeller, `capabilities` ile tür |
| OpenRouter | `/api/v1/models` | gerekmez | 410 model, bağlam + fiyat |
| OpenAI | `/v1/models` | gerekir | anahtarsız yedek liste + neden |
| Gemini | `/v1beta/models` | gerekir | anahtarsız yedek liste + neden |

Model türü (llm/embed/vision) **sağlayıcının kendi meta verisinden** okunur,
ad kalıbından değil — `bge-m3` ad kalıbıyla LLM sanılmıştı.

Sağlayıcının o yüzeyi hiç sunmadığı durumlar (OpenRouter'da gömme yok)
boş liste yerine **sebebiyle** döner; boş liste kullanıcıya "anahtarım mı
yanlış?" dedirtiyordu.

### Bulut düşerse ne olur

`LLM_FALLBACK_OLLAMA=true` (varsayılan) iken bulut sağlayıcı hata verirse
çağrı yerel Ollama ile puanlanır — kesinti puanlamayı durdurmaz. Ama o çağrı
**seçilenden başka bir modelle** puanlanmıştır. Bu yüzden:

- düşme `AiUsage`'a **gerçek** sağlayıcı adıyla yazılır,
- panel son 24 saatin düşme sayısını uyarı bandında gösterir,
- `false` yapılırsa çağrı hatayla durur ve kuyrukta bekler.

Anahtarın kendisi yoksa yedeğe düşülmeden önce açık hata verilir — sorun
yapılandırmadadır ve yerele kaçmak onu gizlerdi.

---

## 6. Güvenlik yüzeyi

| Konu | Uygulama |
|---|---|
| Kimlik | JWT (erişim + yenileme), OIDC/SSO opsiyonel — panelden yapılandırılır |
| Yetki | 4 rol, kiracı izolasyonu, takım kapsamı |
| Diskte şifreleme | Zarf şifreleme + HMAC bütünlük; anahtar **dosyadan**, rotasyon penceresi ile |
| PII | Maskeleme; ham PII görüntüleme denetim günlüğüne yazılır |
| Denetim izi | Giriş, PII görüntüleme, rol değişimi, ses indirme, ayar değişikliği |
| Saklama | Kurum bazında süre; süresi dolan ses otomatik silinir |

Ayrıntı: [KVKK-UYUM.md](KVKK-UYUM.md).

---

## 7. Ölçüm altyapısı

Ürünün doğruluk iddiaları **yeniden üretilebilir**:

```
make eval     50 senaryoluk altin set uzerinde gercek puanlama motorunu kosar
make audit    Turkce + arayuz statik denetimleri
make test     backend regresyon takimi
```

`make eval` eşikleri sağlamazsa **çıkış kodu 1** döner ve CI kırılır.
Eşiklerin neden o değerde olduğu `scripts/golden/evaluate.py` içinde yazılı.
