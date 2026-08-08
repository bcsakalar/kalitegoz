# KaliteGöz — Çalıştırma Rehberi (Windows / PowerShell)

Bu dosya, sistemi **tek komutla** ayağa kaldırmanı sağlar. Tüm komutlar proje kök
dizininde (`KaliteGoz\`) PowerShell'de çalıştırılır.

> **Mimari not:** Uygulama servisleri (API, Frontend, Postgres, Redis, worker'lar)
> **Docker**'da çalışır. Yapay zekâ (Ollama LLM/embedding + Whisper STT) ise
> performans için **PC'de native** çalışır — Docker'da değil. Ayrıntı: `NATIVE-AI-KURULUM.md`.

---

## 1) Ön Gereksinimler (tek seferlik)

| Bileşen | Neden | Kontrol |
|---|---|---|
| **Docker Desktop** | API, DB, Redis, frontend | `docker info` |
| **Python 3.12 + `.venv`** | Backend testleri (pytest) | `.venv\Scripts\python.exe --version` |
| **Node.js 18+** | Frontend tip kontrolü (tsc) | `node --version` |
| **Ollama for Windows** | Yerel LLM/embedding (native) | `ollama list` |

**İlk kurulumda** (bir kere):
```powershell
# .env yoksa örnekten oluştur
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }

# Python 3.12 sanal ortamı + backend bağımlılıkları (test dahil)
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt   # pytest

# Frontend bağımlılıkları
cd frontend; npm install; cd ..

# Ollama modelleri (yerel AI)
ollama pull qwen2.5:7b-instruct
ollama pull nomic-embed-text
```

---

## 2) Temiz Veritabanı + Seed (sıfırdan başlat)

Postgres volume'ünü siler, şemayı sıfırdan kurar ve **otomatik seed** yapar
(demo tenant + rubrik + 12 temsilci + kullanıcılar). Şema migrasyonları
(`app/migrations.py`) boot'ta kendiliğinden uygulanır — **elle `psql` gerekmez**.

```powershell
docker compose down -v      # veritabanını (volume) sıfırla
docker compose up -d        # temiz başlat -> otomatik create_all + migrations + seed
```

Hazır script (aynı işi yapar, API sağlıklı olana kadar bekler):
```powershell
powershell -ExecutionPolicy Bypass -File scripts\fresh-start.ps1
```

> Temiz durumda **0 çağrı** gelir (clean state).

### 2a) Örnek çağrıları yükle (PENDING — sistem kendi işlesin) ⭐ önerilen
Hazır 24 örnek sesi işleme kuyruğuna **"pending"** olarak ekler. **Kendiliğinden
işlenmez** — panelden sen "İşlemeyi başlat" deyince sistemdeki AI (native Whisper
STT + Ollama) hepsini uçtan uca işler:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\load-examples.ps1
```
Sonra panelde: **Yönetim > İşleme > "İşlemeyi başlat"**. (Sesli çağrılar için
host worker açık olmalı — bkz. bölüm 3.)

> Alternatif demo verisi:
> - **Puanlanmış hazır örnekler** (anında, işleme beklemeden):
>   `docker exec kalitegoz-api-1 python scripts/seed_pro_calls.py`
> - **Sentetik puanlı geçmiş** (trend grafikleri için): `make seed-history`

---

## 3) Servisleri Başlatma

```powershell
docker compose up -d          # API + Frontend + Postgres + Redis + worker'lar
docker compose ps             # durum
```

**Sesli çağrı işleme** (native Whisper STT worker'ı — yalnızca ses işlemek için):
```powershell
powershell -ExecutionPolicy Bypass -File scripts\run-host-worker.ps1
```
> Bu pencere **açık kalmalı**; kapatırsan ses çağrıları işlenmez (chat/analiz etkilenmez).
> Ardından panelde: **Yönetim > İşleme > "İşlemeyi başlat"** (demo tenant duraklatılmış gelir).

### Erişim
- **Panel:** http://localhost:3000
- **API / Swagger:** http://localhost:8000/docs
- **Sağlık:** http://localhost:8000/api/health · **Readiness:** http://localhost:8000/api/health/ready

### Demo hesapları (parola: `demo1234`)
| E-posta | Rol |
|---|---|
| `admin@demo.local` | Yönetici |
| `sef.satis@demo.local` | Supervizör |
| `kalite@demo.local` | Kalite Uzmanı |
| `ayse.yilmaz@demo.local` | Temsilci |

---

## 4) Testleri Koşma (hızlı doğrulama)

**Backend (pytest):**
```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest -q
cd ..
```

**Frontend (TypeScript tip kontrolü):**
```powershell
cd frontend
npx tsc --noEmit
cd ..
```

İkisi de **0 hata** dönmelidir.

---

## 5) Sık Kullanılan Komutlar

```powershell
docker compose logs -f api          # API loglarını izle
docker compose restart api          # sadece API'yi yeniden başlat
docker compose build api frontend   # kod değişince imajları yeniden derle
docker compose up -d --force-recreate --no-deps api frontend   # yeni imajla değiştir
docker compose down                 # durdur (veri KORUNUR)
docker compose down -v              # durdur + veritabanını SİL (temiz reset)
```

---

## Sorun Giderme
- **`docker info` hata veriyor:** Docker Desktop'ı başlat, birkaç saniye bekle.
- **`No module named pytest`:** `.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt`
- **AI yanıtı gelmiyor / puanlama takılı:** `ollama list` ile modelleri kontrol et; Ollama çalışıyor olmalı.
- **Ses çağrısı işlenmiyor:** `scripts\run-host-worker.ps1` penceresi açık mı? Ardından Yönetim > İşleme > başlat.
- **Prod'a çıkış:** `.env`'de `ENVIRONMENT=production`, güçlü `JWT_SECRET` (32+), `DEMO_MODE=false`, gerçek `CORS_ORIGINS` ayarla (boot'ta uyarı verir).
