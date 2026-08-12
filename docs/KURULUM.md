# Kurulum — On-Prem

> Hedef: temiz bir makinede sistemi ayağa kaldırmak ve satışa hazır demo almak.
> Beş dakikada çalışır hâle gelir; yapay zekâ modellerinin indirilmesi ayrıca
> zaman alır.

---

## 1. Donanım gereksinimi

| Bileşen | Asgari | Önerilen | Neden |
|---|---|---|---|
| CPU | 8 çekirdek | 16 çekirdek | STT ve LLM paralel çalışır |
| RAM | 16 GB | 32 GB | 7B model ~6 GB, Whisper ~2 GB |
| GPU | — | NVIDIA 12 GB+ | LLM GPU'da 5-10× hızlı |
| Disk | 100 GB | 500 GB SSD | Ses kayıtları + modeller |

**GPU olmadan da çalışır** ama bir çağrının puanlanması ~40 sn yerine
3-5 dakika sürer.

## 2. Mimari — yapay zekâ Docker'da DEĞİL

```
        HOST (native)                    DOCKER
  ┌──────────────────────┐      ┌──────────────────────────┐
  │ Ollama :11434        │◀─────│ api · worker · beat      │
  │  (LLM + embedding)   │      │ watcher · frontend       │
  │ Whisper STT worker   │◀─────│ postgres · redis         │
  └──────────────────────┘      └──────────────────────────┘
```

Ollama Docker içinde GPU'ya erişemez (Windows/WSL2) ve CPU'da makineyi boğar.
Bu yüzden yapay zekâ **host'ta native** çalışır; Docker yalnız durum, kuyruk
ve web katmanını taşır.

## 3. Ön gereksinimler

| Bileşen | Kontrol |
|---|---|
| Docker Desktop | `docker info` |
| Python 3.12 | `py -3.12 --version` (3.14 KULLANMAYIN — faster-whisper wheel'i yok) |
| Node.js 18+ | `node --version` |
| Ollama | `ollama list` |

## 4. Kurulum

```bash
# 1) Yapılandırma
cp .env.example .env

# 2) Yapay zekâ modelleri (host'ta)
ollama pull qwen2.5:7b-instruct     # puanlama
ollama pull nomic-embed-text        # bilgi bankası / benzer çağrı
ollama pull qwen3-vl:4b             # görsel analiz (opsiyonel)

# 3) Servisler
docker compose up -d

# 4) Satış demosu (220 çağrı, saniyeler içinde)
make demo
```

Panel: <http://localhost:3000>

Giriş: `admin@demo.local` · parola `.env` dosyanızdaki **`ADMIN_PASSWORD`**
(`./scripts/generate-secrets.sh` çalıştırıldığında ekrana bir kez basılır).

### Sesli çağrı işleme (opsiyonel)
Gerçek ses dosyalarını uçtan uca işlemek için host worker'ı açın:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\run-host-worker.ps1
```
Bu pencere açık kalmalıdır.

## 5. Ollama model seçimi

| Model | Boyut | Puanlama kalitesi | Hız (RTX 3060) |
|---|---|---|---|
| `qwen2.5:7b-instruct` | 4.7 GB | **Ölçüldü** — uyum kriterlerinde kappa 0.90-1.00 | ~40 sn/çağrı |
| `qwen2.5:14b-instruct` | 9 GB | Ölçülmedi; öznel kriterlerde daha iyi beklenir | ~90 sn/çağrı |
| `qwen3.5:4b` | 3.4 GB | Ölçülmedi; daha hızlı, kalite düşebilir | ~20 sn/çağrı |

Model değiştirdikten sonra **`make eval` ile ölçün.** Doğruluk iddiası
ölçülmeden yapılmaz — `docs/KALITE-METODOLOJISI.md` bu ilkeye dayanır.

Model seçimi panelden yapılır: **Yönetim → Yapay Zekâ**. `.env`'i düzeltmek
yetmez; veritabanındaki ayar `.env`'i ezer.

## 6. Üretim sertleştirmesi

`.env` içinde:
```
ENVIRONMENT=production
JWT_SECRET=<32+ karakter rastgele>
DEMO_MODE=false
CORS_ORIGINS=https://kalitegoz.sirketiniz.com
```

Ortam değişkeni olarak (`.env` DIŞINDA — Docker secret / systemd):
```
KG_MASTER_KEY=<32+ karakter>          # diskte şifreleme
OIDC_ISSUER=https://keycloak.../realms/kalitegoz
OIDC_CLIENT_ID=kalitegoz
OIDC_CLIENT_SECRET=...
```

Kurulumdan sonra **Güvenlik sayfasını açın**: dokuz kontrol canlı çalışır ve
eksik olanı nasıl açacağınızı yazar.

## 7. Ölçekleme

| Yük | Öneri |
|---|---|
| < 500 çağrı/gün | Tek makine yeterli |
| 500-2000 | `worker-fast` replika sayısını artırın; ayrı Ollama sunucusu |
| 2000+ | Postgres'i ayrı sunucuya alın; Ollama'yı GPU kümesine taşıyın |

Kokpit sorguları 1000 çağrıda **11 ms** ölçüldü (`make perf`); darboğaz
veritabanı değil, yapay zekâ işleme kapasitesidir.

## 8. Doğrulama komutları

```bash
make test        # backend testleri
make eval        # puanlama doğruluğu (altın set)
make perf        # kokpit performansı
make tr-audit    # Türkçe karakter ve jargon denetimi
```

---

## 9. Windows (PowerShell) hızlı yol

Depoyu klonlayan biri için tek akış:

```powershell
# 1) Sırları üret ve .env'i oluştur (tek komut, elle doldurulacak alan yok)
bash scripts/generate-secrets.sh          # Git Bash
#   veya WSL / Linux / macOS'ta: ./scripts/generate-secrets.sh

# 2) Yapay zekâ modelleri — Ollama HOST'ta çalışır, Docker'da DEĞİL
ollama pull qwen2.5:7b-instruct
ollama pull nomic-embed-text

# 3) Servisler
docker compose up -d --build

# 4) Doğrula
curl http://localhost:8000/health      # {"status":"ok"}
curl http://localhost:8000/ready       # {"status":"ready", checks: db+redis}
```

### Erişim adresleri

| Ne | Adres |
|---|---|
| Panel | http://localhost:3000 |
| API / Swagger | http://localhost:8000/docs |
| Sağlık (liveness) | http://localhost:8000/health |
| Hazırlık (readiness) | http://localhost:8000/ready |

### Sık kullanılan komutlar

```powershell
docker compose logs -f api                       # API loglarini izle
docker compose build api worker-fast             # kod degisince imajlari yeniden kur
docker compose up -d --force-recreate api        # yeni imajla degistir
docker compose down                              # durdur (VERI KORUNUR)
docker compose down -v                           # durdur + veritabanini SIL
make audit                                       # Turkce + arayuz denetimi
make test                                        # backend testleri
make eval                                        # altin set regresyonu
```

### Sorun giderme

| Belirti | Sebep ve çözüm |
|---|---|
| `docker info` hata veriyor | Docker Desktop çalışmıyor; başlatıp birkaç saniye bekleyin |
| Panelde giriş 401 dönüyor | `make eval` koşulmuşsa eskiden iç kiracı giriş hedefi oluyordu (B35). Güncel sürümde düzeltildi; eski sürümdeyseniz güncelleyin |
| AI yanıtı gelmiyor, puanlama takılı | `ollama list` ile modelleri kontrol edin; Ollama **host'ta** çalışıyor olmalı |
| Sesli çağrı işlenmiyor | Yönetim → İşleme ekranından işlemeyi başlatın; kuyruk duraklatılmış olabilir |
| `No module named pytest` | `.venv\Scripts\python.exe -m pip install -r backend
equirements-dev.txt` |
| Üretime çıkış | `.env`'de `ENVIRONMENT=production`, `DEMO_MODE=false`, gerçek `CORS_ORIGINS`. Eksikse uygulama açık Türkçe hatayla durur |
