<#
  KaliteGoz - Docker DISI (native) sesli cagri STT worker'i.

  Ne yapar: Celery 'voice' kuyrugunu host'ta calistirir. Sesli cagrilarin
  Whisper (STT) + Ollama (LLM) puanlamasi burada, PC'de yapilir; Docker VM'i
  yorulmaz, GPU'nuz varsa dogrudan kullanilir.

  Mimari: Ollama + bu worker HOST'ta; Postgres/Redis/api/worker-fast/beat/
  watcher/frontend Docker'da. Bu script host-ozel adresleri (localhost) enjekte
  eder ve DB'deki container yolunu (/data/...) host yoluna cevirir (HOST_DATA_DIR).

  ON KOSULLAR (bir kez kurun; ayrinti: NATIVE-AI-KURULUM.md):
    1) Ollama for Windows kurulu + calisiyor. Modeller cekili.
    2) Python 3.10-3.12 venv + backend bagimliliklari:
         py -3.12 -m venv .venv
         .\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
    3) ffmpeg PATH'te ('ffmpeg -version' calismali)
    4) Docker stack ayakta:  docker compose up -d

  KULLANIM:
    powershell -ExecutionPolicy Bypass -File scripts\run-host-worker.ps1

  NOT: Bu dosya SAF ASCII tutulmalidir. PowerShell 5.1 BOM'suz dosyalari ANSI
  okur; Turkce ozel karakter/em-dash parser'i bozar.
#>
$ErrorActionPreference = "Stop"

# Proje kok dizini (bu script scripts/ altinda)
$proj = Split-Path -Parent $PSScriptRoot
$data = Join-Path $proj "data"

# --- Host-ozel override'lar (pydantic: gercek ortam degiskeni > .env dosyasi) ---
# Docker servislerine host uzerinden localhost ile baglaniriz:
$env:DATABASE_URL    = "postgresql+psycopg://kalitegoz:kalitegoz@localhost:5432/kalitegoz"
$env:REDIS_URL       = "redis://localhost:6379/0"
$env:OLLAMA_BASE_URL = "http://127.0.0.1:11434"          # PC'deki native Ollama
$env:STORAGE_DIR     = (Join-Path $data "storage")
$env:WATCH_DIR       = (Join-Path $data "inbox")
$env:HOST_DATA_DIR   = $data                              # /data -> bu klasore cevrilir
# WHISPER_DEVICE'i .env belirler (cpu/cuda). Burada override ETMIYORUZ; yoksa
# OS env, .env'i ezerdi. GPU STT icin .env'de WHISPER_DEVICE=cuda + cublas/cudnn.

# 'app' paketi backend/ altinda; kok .env (OLLAMA_MODEL/WHISPER_MODEL vb.) okunabilsin
# diye proje kokunden calistiriyoruz, backend'i PYTHONPATH'e ekliyoruz.
$env:PYTHONPATH = Join-Path $proj "backend"
Set-Location $proj

# On kontrol: ffmpeg ve Ollama erisimi
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
  Write-Warning "ffmpeg PATH'te bulunamadi. STT ses cozumleme BASARISIZ olur. Bkz: NATIVE-AI-KURULUM.md"
}
try {
  Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 5 | Out-Null
} catch {
  Write-Warning "Ollama'ya (127.0.0.1:11434) ulasilamadi. Once Ollama'yi baslatin (ollama serve / uygulama)."
}

# venv varsa onun python'unu kullan (backend bagimliliklari orada). Yoksa PATH'teki python.
$py = if (Test-Path (Join-Path $proj ".venv\Scripts\python.exe")) {
        Join-Path $proj ".venv\Scripts\python.exe"
      } else { "python" }

# Banner icin WHISPER_DEVICE'i .env'den oku (script OS env set etmiyor).
$whDev = "auto (varsayilan)"
$envFile = Join-Path $proj ".env"
if (Test-Path $envFile) {
  $m = Select-String -Path $envFile -Pattern '^\s*WHISPER_DEVICE\s*=\s*(\S+)'
  if ($m) { $whDev = "$($m.Matches[0].Groups[1].Value) (.env)" }
}

Write-Host "KaliteGoz native STT worker baslatiliyor..." -ForegroundColor Cyan
Write-Host "  Ollama    : $($env:OLLAMA_BASE_URL)"
Write-Host "  Postgres  : localhost:5432    Redis: localhost:6379"
Write-Host "  Veri kok  : $data"
Write-Host "  Whisper   : device=$whDev"
Write-Host "  Python    : $py"
Write-Host "  Durdurmak : Ctrl+C" -ForegroundColor DarkGray
Write-Host ""

# Windows'ta Celery prefork (fork) pool'u YOK -> '--pool=solo' zorunlu.
# 'python -m celery' PATH sorunlarindan kacinir (celery.exe aramaya gerek yok).
& $py -m celery -A app.tasks.celery_app worker -Q voice --pool=solo --loglevel=INFO -n voice-host@%h
