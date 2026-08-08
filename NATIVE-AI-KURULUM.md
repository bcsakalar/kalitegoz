# KaliteGöz — Native (Docker'sız) Yapay Zekâ Kurulumu

> **Amaç:** Ollama (LLM + embedding + vision) ve Whisper STT'yi **Docker içinde
> değil, PC'de (host) native** çalıştırmak. Böylece ağır CPU/RAM yükü Docker'ın
> Linux VM'inden çıkar, **GPU'nuz varsa doğrudan kullanılır** ve makine çok daha
> az yorulur.

## Neden?

Docker Desktop Windows'ta container'lar bir **WSL2 Linux VM** içinde çalışır. Ollama
o VM'de:
- **GPU'ya kolay erişemez** → 7B model CPU'da çalışır (çok ağır: ~%400-550 CPU + ~6 GB RAM).
- VM katmanı ek yük getirir.

Ollama'yı **Windows'a native** kurunca aynı model:
- **GPU'nu (NVIDIA/AMD) otomatik kullanır** → kat kat hızlı, CPU'yu boğmaz.
- VM katmanı yok.

Whisper STT de aynı mantıkla host'ta çalışır.

## Yeni mimari

```
  ┌─────────────────── PC (HOST, native) ───────────────────┐
  │  Ollama (qwen2.5:7b + nomic-embed-text + llava:7b)       │  ← GPU kullanır
  │       ▲ 127.0.0.1:11434                                  │
  │  Whisper STT worker  (scripts/run-host-worker.ps1)       │  ← Celery -Q voice
  └───────▲──────────────────────▲──────────────────────────┘
          │ localhost:5432/6379   │ host.docker.internal:11434
  ┌───────┴──────────────────────┴──────── Docker ──────────┐
  │  postgres · redis · api · worker-fast (chat/rescore) ·   │
  │  beat · watcher · frontend                               │
  └──────────────────────────────────────────────────────────┘
```

- **Docker container'ları → host Ollama:** `http://host.docker.internal:11434` (`.env`).
- **Host worker → Docker Postgres/Redis:** `localhost:5432` / `localhost:6379` (portlar açıldı).
- **Host worker → host Ollama:** `http://127.0.0.1:11434` (script override eder).
- **Ses dosyası yolu:** api (Docker) `/data/storage/audio/x.wav` yazar; host worker
  bunu `HOST_DATA_DIR` ile Windows yoluna çevirir (kod: `settings.resolve_path`).

---

## Kurulum (tek sefer)

### 1. Ollama'yı Windows'a kur
- İndir: https://ollama.com/download → **OllamaSetup.exe** → kur.
- Kurulunca arka planda `11434` portunda çalışır (sistem tepsisinde). Doğrula:
  ```powershell
  ollama --version
  Invoke-RestMethod http://127.0.0.1:11434/api/tags   # boş liste dönebilir, önemli olan cevap vermesi
  ```
- **Modelleri çek** (tek sefer, ~4.7 + 0.27 + 4.7 GB):
  ```powershell
  ollama pull qwen2.5:7b          # puanlama LLM'i
  ollama pull nomic-embed-text    # RAG embedding
  ollama pull llava:7b            # vision (istege bağlı — VISION_ENABLED=true ise)
  ```
- **(Opsiyonel) Kaynak ayarı** — native Ollama, Windows ortam değişkenlerini okur:
  ```powershell
  setx OLLAMA_NUM_THREAD 4        # LLM çekirdek sayısı (ana CPU tüketici)
  setx OLLAMA_KEEP_ALIVE 5m       # model boşta bellekte kalma; kısa=RAM erken serbest
  ```
  (Değişiklik için Ollama'yı yeniden başlatın. GPU varsa NUM_THREAD daha az önemli.)

### 2. Python + backend bağımlılıkları (host worker için)
```powershell
# Proje kökünde:
python --version                        # 3.10+ olmalı
python -m venv .venv
.\.venv\Scripts\Activate.ps1            # venv aktif (her yeni terminalde tekrar)
pip install -r backend/requirements.txt
```
> Bu paket seti `faster-whisper`, `celery`, `psycopg`, `numpy` vb. içerir. İlk STT
> çağrısında Whisper `medium` modeli Windows kullanıcı önbelleğine iner (~1.5 GB, tek sefer).

### 3. ffmpeg (ses çözümleme için şart)
```powershell
winget install Gyan.FFmpeg           # veya: choco install ffmpeg
# Yeni terminal aç, doğrula:
ffmpeg -version
```

### 4. Docker stack'i başlat (AI'sız katman)
```powershell
docker compose up -d --build
```
Bu artık **ollama** ve **voice worker** içermez — sadece postgres, redis, api,
worker-fast, beat, watcher, frontend. Postgres (5432) ve Redis (6379) host'a açıktır.

---

## Çalıştırma (her seferinde)

**3 terminal / adım:**

1. **Ollama** — zaten arka planda çalışıyor (sistem tepsisi). Değilse: `ollama serve`.

2. **Docker stack:**
   ```powershell
   docker compose up -d
   ```

3. **Native STT worker** (sesli çağrıları işler):
   ```powershell
   .\.venv\Scripts\Activate.ps1        # venv kullandıysanız
   powershell -ExecutionPolicy Bypass -File scripts\run-host-worker.ps1
   ```
   Bu terminal açık kalır ve sesli çağrıları işler (Ctrl+C ile durur).

4. **Dashboard:** http://localhost:3000 → Yönetici → **Yönetim → İşleme → "▶ İşlemeyi başlat"**
   (demo tenant duraklatılmış gelir). Chat'ler Docker'daki worker-fast'te, sesli
   çağrılar host worker'da işlenir.

---

## Doğrulama / sağlık kontrolü

```powershell
# Ollama host'ta cevap veriyor mu?
Invoke-RestMethod http://127.0.0.1:11434/api/tags

# Docker api, host Ollama'yı görebiliyor mu? (container içinden)
docker compose exec api curl -s http://host.docker.internal:11434/api/tags

# Native worker Redis'e bağlandı mı? (worker başlarken "voice@..." log'u + "ready")
# Bir sesli çağrıyı işleyince host worker terminalinde STT + puanlama log'u akar.
```

Beklenen: Sesli bir çağrıyı "İşlemeyi başlat" ile tetiklediğinde **host worker
terminalinde** Whisper yükleme + segment log'ları görünür, çağrı `done` olur.

---

## Sorun giderme

| Belirti | Çözüm |
|---|---|
| Worker `connection refused` (11434) | Ollama çalışmıyor → başlat (`ollama serve` / uygulama). |
| api/worker-fast LLM'e ulaşamıyor | `host.docker.internal` çözülmüyor: Docker Desktop güncel mi? `.env → OLLAMA_BASE_URL=http://host.docker.internal:11434` |
| Worker `could not connect` (5432/6379) | Docker up mı? Portlar açık mı? Host'ta 5432'de başka Postgres varsa compose'da `5433:5432` yapıp script'teki `DATABASE_URL`'i güncelleyin. |
| STT `ffmpeg hatasi` / `ffmpeg cozemedi` | ffmpeg PATH'te değil → kur (adım 3), yeni terminal aç. |
| Ses dosyası bulunamadı (host worker) | `HOST_DATA_DIR` yanlış. Script proje kökünden `data` klasörünü kullanır; scripti `scripts\` içinden değil proje kökünden tetikleyin (script kendi konumundan kökü bulur). |
| `celery` prefork hatası / takılma | Windows'ta `--pool=solo` şart (script'te var). Elle çalıştırıyorsanız ekleyin. |
| Whisper GPU kullanmıyor | `WHISPER_DEVICE=cuda` + CUDA/cuDNN kütüphaneleri gerekir; yoksa `auto` CPU'ya düşer (çalışır, yavaş). |
| Model çok yavaş (CPU) | GPU yoksa `.env → OLLAMA_MODEL=qwen2.5:3b` + `WHISPER_MODEL=small` (host worker'ı yeniden başlat). |

---

## Docker'a geri dönmek istersen (revert)

Native kurulumu geri almak için:
1. `docker-compose.yml`'e `ollama` + `ollama-pull` + `worker` (voice) servislerini geri ekle
   (git yoksa bu dosyanın eski hâli README/ROADMAP mimarisinde tarif edilir).
2. `.env → OLLAMA_BASE_URL=http://ollama:11434`.
3. `api`/`worker-fast`'ten `extra_hosts`'u kaldır (zararı yok, kalabilir de).
4. `docker compose up -d --build` ve `make pull-model` (Docker exec sürümü).

> Not: Bu proje git deposu değil; değişiklikler manuel. İstersen bu dosyayı referans
> alarak eski compose'u yeniden üretebilirim — söylemen yeter.
