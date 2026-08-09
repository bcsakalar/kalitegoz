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

Panel: <http://localhost:3000> · `admin@demo.local` / `demo1234`

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
