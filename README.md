# KaliteGöz — Çağrı Merkezi Kalite Yönetim Platformu

> 🖥️ **NATIVE AI:** Ollama (LLM+embedding+vision) ve Whisper STT artık **PC'de (host)
> native** çalışır, Docker'da değil — makine daha az yorulur, GPU doğrudan kullanılır.
> Kurulum: **[NATIVE-AI-KURULUM.md](NATIVE-AI-KURULUM.md)** · Test/sistem: **[SISTEM-TEST-REHBERI.md](SISTEM-TEST-REHBERI.md)**.
> (Aşağıdaki bazı `docker compose exec ollama …` komutları bu değişiklikle güncelliğini yitirdi → `ollama pull …`.)

> **Tek komutla demo:** `make demo` → http://localhost:3000 → rol seçip tek tıkla girin.
> **Diğer dokümanlar:** [Satış özeti](docs/SALES-ONEPAGER.md) · [Demo senaryosu](docs/DEMO-SCRIPT.md) · [API rehberi](docs/API.md) · [Yol haritası](docs/ROADMAP.md) · [Çalıştırma/test](run.md)

Çağrı merkezleri çağrıların **%2–3'ünü** elle dinler. KaliteGöz **%100'ünü**
otomatik dinler, puanlar ve raporlar — sesli çağrı ve chat kanalı, aynı rubrikle.
Multi-tenant, RBAC'lı, KVKK uyumlu, kendi sunucunuzda çalışan kurumsal bir platform.

```
 ses (wav/mp3)  ·  chat (JSON)
   │  REST API (/api/v1)  ·  watch-folder (data/inbox)
   ▼
┌──────────┐  Celery/Redis   ┌───────────────────────────────────────────────┐
│ FastAPI  │ ──────────────► │ worker (kuyruk: voice) — ağır STT             │
│  api     │   2 kuyruk      │ 1. STT (faster-whisper medium int8)           │
│ JWT+RBAC │                 │    • stereo: sol=müşteri sağ=temsilci         │
│ tenant   │                 │      (bedava diarization) · mono: pyannote    │
└────┬─────┘                 │ 2. Konuşma metrikleri (oran/söz kesme/        │
     │                       │    sessizlik/hız) — LLM'e nesnel dayanak      │
     │                       ├───────────────────────────────────────────────┤
     │  PostgreSQL(+pgvector)│ worker-fast (kuyruk: fast) — chat/rescore     │
     │  tenant · rubrik ·    │ 3. Uyum motoru: yasaklı kelime (fuzzy, kim    │
     │  puan · ihlal · alarm │    söyledi) + kriz tespiti                    │
     │  itiraz · audit log   │ 4. RAG: bilgi bankasından ilgili pasajlar     │
     │  bilgi bankası (RAG)  │ 5. LLM rubrik puanlama (Ollama qwen2.5:7b     │
     ▼                       │    veya Gemini) — JSON şema + repair          │
┌──────────┐                 │ 6. Sıfırlayıcı ihlal → puan 0 + alarm+webhook │
│ Next.js  │                 ├───────────────────────────────────────────────┤
│ dashboard│                 │ beat — KVKK retention (her gece 03:15)        │
└──────────┘                 └───────────────────────────────────────────────┘
```

## Hızlı başlangıç

```bash
make demo        # .env oluşturur, stack'i kurar, LLM modelini indirir, demo veriyi üretir
```

> ⚠️ **Ağır işi siz başlatırsınız.** Demo tenant'ta **işleme duraklatılmış** gelir:
> çağrılar yüklenir ama STT/LLM çalışmaz (makineniz boşta, ~%1 CPU). Hazır
> olduğunuzda **Yönetim → İşleme → "▶ İşlemeyi başlat"**. Böylece 7B LLM + Whisper
> bilgisayarınızı siz istemeden meşgul etmez.

`make` yoksa:
```bash
cp .env.example .env
docker compose up -d --build
pip install -r scripts/requirements.txt
python scripts/generate_demo.py --upload http://localhost:8000
```

| Adres | Ne |
|---|---|
| http://localhost:3000 | Dashboard (rol seçimli demo girişi) |
| http://localhost:8000/docs | API (OpenAPI/Swagger) |
| http://localhost:8000/metrics | Prometheus metrikleri |

**Demo hesapları** (parola `demo1234`): `admin@demo.local` ·
`sef.satis@demo.local` · `kalite@demo.local` · `ayse.yilmaz@demo.local`

İlk açılışta qwen2.5:7b (~4.7 GB) ve Whisper medium (~1.5 GB) indirilir (tek sefer).

## Arayüz

- **Sol sidebar** — rol bazlı menü (temsilci yönetim sayfalarını görmez), katlanabilir,
  mobilde drawer. Alarm sayısı nav üzerinde canlı görünür.
- **Açık / koyu / sistem teması** — sağ alttan seçilir, tercih tarayıcıda saklanır.
- **Türkçe / English** — 🇹🇷/🇬🇧 ile anlık değişir; ilk girişte tarayıcı dilinden tahmin edilir.
- **Sayfalar** — Çağrılar · Arama · Kokpit · **Analitik** (zaman serisi + VoC trend + kohort) ·
  **Asistan** (canlı sufle + görsel denetim) · Temsilciler · Lig (+ "Performansım" gamification) ·
  Görevler · Kalibrasyon · Rubrik · Yönetim (+ uyum paketleri).
- **Çağrı detayı** — 🧠 Yapay Zekâ Analizi kartı: baskın duygu, duygu seyri, churn riski,
  müşteri efor skoru, sonraki-en-iyi-aksiyon, niyet etiketleri, duygu-sonuç uyumsuzluk uyarısı.

## Roller (RBAC)

| Rol | Yetki |
|---|---|
| **Yönetici** | Her şey + kullanıcı/kampanya/yasaklı kelime yönetimi |
| **Süpervizör** | Ekip kokpiti, alarmlar, koçluk görevi atama |
| **Kalite Uzmanı** | Puan override, kalibrasyon, itiraz kararı |
| **Temsilci** | **Yalnızca kendi** çağrıları, karnesi, itiraz hakkı |

## Öne çıkan yetenekler

- **Sıfırlayıcı ihlal** — kritik kriter (KVKK, kimlik doğrulama) eşik altındaysa
  veya temsilci ağır yasaklı ifade kullandıysa çağrı puanı otomatik **0** + alarm.
- **Bilgi bankası (RAG)** — şirket prosedür/SSS dokümanlarınızı (PDF/DOCX/MD/TXT)
  yükleyin; temsilcinin verdiği bilgi bu dokümanlarla karşılaştırılır. *"İade süresini
  30 gün dedi, prosedürde 14 gün yazıyor"* → **Bilgi Doğruluğu** kriterinde düşük puan
  + gerekçede doğru bilgi ve kaynak doküman.
- **Konuşma araması** — tüm transkriptlerde ifade arayın: *"avukat"*, *"garanti ederim"*,
  *"iptal ediyorum"*. Konuşmacı/kanal filtresi, sonuca tıklayınca **sesin tam o anına**
  atlar. Temsilci yalnızca kendi çağrılarında arar.
- **Yönetilebilir rubrik** — kriter/ağırlık/grup/puan aralığı; **kampanya ve kanal
  bazlı** rubrik; yeni kriter LLM prompt'una otomatik girer (kod değişikliği yok).
- **Yasaklı kelime motoru** — exact/fuzzy/regex, TR çekim varyasyonları, ve
  **kim söyledi** (müşteri küfrederse temsilci cezalandırılmaz).
- **Kriz tespiti** — hukuki/eskalasyon söylemi ("avukatıma gideceğim") → etiket + alarm.
- **Konuşma metrikleri** — konuşma oranı, söz kesme, sessizlik, kelime/dk;
  chat'te ilk/ortalama yanıt süresi. LLM'e ipucu olarak verilir.
- **Duygu değişimi + tahmini CSAT** + otomatik **koçluk önerisi**.
- **Kalibrasyon & itiraz** — insan override + AI/insan sapma raporu; temsilci itirazı.
- **Gamification** — liderlik tablosu, rozetler, temsilci karnesi (PDF).
- **KVKK** — PII maskeleme (harici LLM'e maskeli gider — **testle garanti**),
  append-only audit log, **otomatik saklama süresi (retention)**: süresi dolan
  kayıtlar her gece silinir, silme denetim kaydına yazılır.
- **Toplu yeniden puanlama** — rubrik değişince tüm çağrılar tek tuşla güncel
  rubrikle yeniden puanlanır (STT tekrar çalışmaz).
- **Entegrasyon** — REST API, webhook, watch-folder, CSV/Excel/PDF export.

## Yapılandırma

Tüm ayarlar `.env` ([.env.example](.env.example) eksiksiz şablondur):

| Değişken | Açıklama |
|---|---|
| `JWT_SECRET` | **Production'da mutlaka değiştirin** |
| `DEMO_MODE` | Rol seçimli parolasız giriş — **production'da `false`** |
| `LLM_PROVIDER` | `ollama` (varsayılan, offline) veya `gemini` |
| `WHISPER_DEVICE` | `auto` / `cuda` / `cpu` |
| `HF_TOKEN` | mono kayıtlarda pyannote diarization için |
| `WEBHOOK_URLS` | ihlal/kriz olaylarının POST edileceği adresler |
| `MASK_LOCAL_LLM` | yerel LLM'e giden metni de maskele |
| `RATE_LIMIT_PER_MIN` | IP başına dakikalık istek limiti |

## Kaynak kullanımı (CPU / RAM)

Yerel LLM + STT çalıştırdığınız için işleme **ağırdır**. Üç katmanlı koruma var:

1. **İşleme duraklatılabilir** — Yönetim → İşleme. Duraklatılmışken çağrılar
   birikir, makine **boşta kalır (~%1 CPU)**. Ağır işi siz başlatırsınız.
2. **Ollama boştayken modeli bırakır** (`OLLAMA_KEEP_ALIVE=5m`) → RAM serbest.
3. **Her servisin CPU/RAM tavanı var** (`.env`'den ayarlanır).

Ölçülen değerler (12 çekirdek / 11.7 GB Docker VM, varsayılan ayarlar):

| Servis | CPU tavanı | RAM tavanı | Boşta | Puanlama sırasında |
|---|---|---|---|---|
| `ollama` (LLM) | 4 çekirdek | 8 GB | **~20 MB** | ~6 GB, ~%400 CPU |
| `worker` (Whisper STT) | 4 çekirdek | 3 GB | ~90 MB | ~1.6 GB, ~%400 CPU |
| `worker-fast`, `api`, `frontend` | 1-2 çekirdek | 0.5-1 GB | ~100 MB | ~100 MB |
| `beat`, `watcher` | 0.5 çekirdek | 256 MB | ~50 MB | ~50 MB |
| **Toplam** | | | **~%1 CPU** | ~%400-800 CPU |

**Ayar düğmeleri** (`.env`):

| Değişken | Etki |
|---|---|
| `OLLAMA_NUM_THREAD=4` | LLM çıkarım thread'i — **ana CPU tüketicisi**. Ayarlanmazsa llama.cpp tüm çekirdekleri kapar (12 çekirdekte ~550% CPU). Düşürmek CPU'yu rahatlatır, puanlamayı yavaşlatır. |
| `OLLAMA_KEEP_ALIVE=5m` | Model bellekte kalma süresi. Uzun = hızlı ama **boşta da ~6 GB tutar**; kısa = RAM serbest ama sonraki istekte ~70 sn yeniden yükleme. |
| `OLLAMA_NUM_CTX=8192` | Bağlam penceresi. Büyütmek KV cache'i (RAM) şişirir. Büyütürseniz `CHUNK_THRESHOLD_SEC`'i de gözden geçirin. |
| `OLLAMA_CPUS` / `OLLAMA_MEM` | Container tavanları |
| `WORKER_CPUS` / `WORKER_MEM` | STT worker tavanları |

**Makineniz zorlanıyorsa** (hafif mod):
```bash
# .env
OLLAMA_MODEL=qwen2.5:3b      # 4.7 GB → ~2 GB, belirgin hızlı (kalite biraz düşer)
OLLAMA_NUM_THREAD=4
WHISPER_MODEL=small          # 1.5 GB → ~500 MB, ~3x hızlı
OLLAMA_KEEP_ALIVE=2m
```
Sonra: `docker compose up -d` + `docker compose exec ollama ollama pull qwen2.5:3b`

**GPU'nuz varsa** (çok daha hızlı): NVIDIA Container Toolkit kurun →
`docker-compose.yml`'de `ollama` ve `worker` servislerinin `deploy.resources`
altındaki GPU bloklarını açın → `.env` → `WHISPER_DEVICE=cuda`. GPU'da
`worker-fast` concurrency'sini 2-4 yapabilirsiniz.

### Mono kayıtlarda pyannote
```bash
docker compose build --build-arg WITH_DIARIZATION=1 worker
# .env → HF_TOKEN=hf_...
```

## Test

```bash
make test     # pytest: PII maskeleme, yasaklı kelime, RBAC, tenant izolasyonu
```
CI (GitHub Actions): backend test + frontend lint/build + docker build.

## Proje yapısı

```
backend/app/
  api/        auth, calls, chats, criteria, agents, stats, admin, workflow, supervisor, reports
  services/   audio, stt, diarization, metrics, compliance, masking, llm, scoring, ingest, audit, webhooks, events
  tasks/      celery_app + pipeline (process_call, process_chat, rescore_call)
  models.py   multi-tenant şema · security.py JWT/bcrypt · deps.py RBAC · seed.py demo tohum
  watcher.py  watch-folder servisi
backend/tests/  pytest (maskeleme, uyum, RBAC/tenant, canlı alarm)
frontend/app/   login · / (çağrılar) · calls/[id] · cockpit · agents · agents/[id] · leaderboard · workflow · rubric · admin
scripts/generate_demo.py   sentetik demo (TTS sesli + chat + 8 haftalık geçmiş)
scripts/tts_engines.py     TTS motorları (edge-tts gerçek kadın/erkek · Piper çevrimdışı yedek)
scripts/tr_gender.py       Türkçe ad/hitap → cinsiyet (yalnız demo seslendirmesi)
scripts/tests/             pytest (cinsiyet çıkarımı, konuşmacı ayrımı)
docs/       AUDIT · ROADMAP · SALES-ONEPAGER · DEMO-SCRIPT · API
```

## Sorun giderme

| Belirti | Çözüm |
|---|---|
| Puanlama `LLM erisim hatasi` | Model inmesi bitmemiş: `docker compose logs ollama-pull`; sonra çağrıda "Yeniden puanla" |
| İlk çağrı çok yavaş | Whisper medium iniyor (tek sefer). Hız için `.env` → `WHISPER_MODEL=small` |
| Frontend "Oturum gerekli" | Token süresi doldu; çıkış yapıp tekrar girin |
| Frontend API'ye erişemiyor | `NEXT_PUBLIC_API_URL` build'e gömülür → `docker compose build frontend` |
| Şema hatası (`column does not exist`) | `make clean && make demo` (eski DB'yi temizler) |

Ayrıntılı çalıştırma/test rehberi: **[run.md](run.md)**
