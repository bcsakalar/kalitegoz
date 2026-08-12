# =====================================================================
# KaliteGoz — TEMIZ BASLANGIC (uygulama veritabanini sifirlar)
# =====================================================================
# Uygulama DB'sini (kalitegoz_pgdata) siler ve stack'i yeniden kurar.
#
# NATIVE AI: Ollama ve Whisper artik HOST'ta calisir; modeller Docker volumunde
# DEGIL, Windows'ta (Ollama: %USERPROFILE%\.ollama, Whisper: HF cache) durur. Bu
# yuzden DB sifirlama modelleri HIC etkilemez — ayrica korumaya gerek yok.
# Sifirlama SONRASI sesli cagri isleme icin host worker'i tekrar baslatin:
#   powershell -ExecutionPolicy Bypass -File scripts\run-host-worker.ps1
#
# Kullanim:  powershell -ExecutionPolicy Bypass -File scripts\fresh-start.ps1
# =====================================================================

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "==> .env kontrol" -ForegroundColor Cyan
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env"; Write-Host "    .env olusturuldu (.env.example'dan)" }

Write-Host "==> Konteynerler durduruluyor (volumler KORUNUR)" -ForegroundColor Cyan
docker compose down

Write-Host "==> Uygulama veritabani sifirlaniyor (SADECE kalitegoz_pgdata)" -ForegroundColor Yellow
docker volume rm kalitegoz_pgdata 2>$null
Write-Host "    Not: AI modelleri host'ta (native Ollama + Whisper cache) — sifirlamadan etkilenmez." -ForegroundColor Green

Write-Host "==> Imajlar yeniden derleniyor + baslatiliyor" -ForegroundColor Cyan
docker compose up -d --build

Write-Host "==> API saglikli olana kadar bekleniyor..." -ForegroundColor Cyan
$ok = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 3
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:8000/api/health" -UseBasicParsing -TimeoutSec 3
        if ($r.StatusCode -eq 200) { $ok = $true; break }
    } catch {}
    Write-Host "    ...bekleniyor ($($i*3)s)"
}

if ($ok) {
    Write-Host ""
    Write-Host "HAZIR ✓  Arayuz: http://localhost:3000   API: http://localhost:8000/docs" -ForegroundColor Green
    Write-Host "Demo giris: landing'den rol sec (parolasiz) veya admin@demo.local; parola .env icindeki ADMIN_PASSWORD" -ForegroundColor Green
    Write-Host "Dashboard'u doldurmak icin: Yonetim > Demo > 'Demoyu sifirla & doldur'" -ForegroundColor Green
    Write-Host ""
    Write-Host "NATIVE AI: Ollama calisiyor mu? Sesli cagri icin host worker'i baslatin:" -ForegroundColor Yellow
    Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\run-host-worker.ps1" -ForegroundColor Yellow
} else {
    Write-Host "API 180s icinde saglikli olmadi — loglara bakin: docker compose logs -f api" -ForegroundColor Red
}
