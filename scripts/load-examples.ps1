# =====================================================================
# KaliteGoz — ORNEK CAGRILARI YUKLE (PENDING)
# =====================================================================
# data/demo_out'taki hazir ornek sesleri data/inbox'a kopyalar. Docker'daki
# watcher bunlari otomatik alir ve "pending" (islenmeyi bekleyen) cagri olarak
# olusturur. Demo kiracisi duraklatilmis geldigi icin cagrilar KENDILIGINDEN
# ISLENMEZ — panelde "Yonetim > Isleme > Islemeyi baslat" deyince sistemdeki AI
# (native Whisper STT + Ollama) hepsini uctan uca isler.
#
# Kullanim:  powershell -ExecutionPolicy Bypass -File scripts\load-examples.ps1
# =====================================================================

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$src = Join-Path $root "data\demo_out"
$dst = Join-Path $root "data\inbox"
if (-not (Test-Path $src)) { Write-Error "Ornek ses klasoru yok: $src"; exit 1 }
New-Item -ItemType Directory -Force -Path $dst | Out-Null

$files = Get-ChildItem -Path $src -Filter *.wav | Sort-Object Name
if ($files.Count -eq 0) { Write-Error "data\demo_out icinde .wav yok"; exit 1 }

# Temsilci kadrosu (kopyalari farkli temsilcilere dagitmak icin)
$agents = @("ayse.yilmaz","mehmet.kaya","zeynep.demir","emre.sahin","elif.arslan",
            "burak.ozturk","selin.koc","caner.aydin","deniz.yildiz","gizem.celik",
            "okan.dogan","pelin.acar")

$n = 0
# 1) Orijinaller (temsilci = dosya adindaki ilk '_' oncesi)
foreach ($f in $files) {
    Copy-Item $f.FullName (Join-Path $dst $f.Name) -Force
    $n++
}
# 2) Kopyalar — farkli temsilcilere yeniden atanmis (kategori korunur, daha bol veri)
for ($i = 0; $i -lt $files.Count; $i++) {
    $f = $files[$i]
    $rest = ($f.Name -split "_", 2)[1]            # "kategori_NN.wav"
    $rest = $rest -replace "\.wav$", ""
    $agent = $agents[$i % $agents.Count]
    $new = "{0}_{1}_v2.wav" -f $agent, $rest
    Copy-Item $f.FullName (Join-Path $dst $new) -Force
    $n++
}

Write-Host ""
Write-Host "==> $n ornek cagri data\inbox'a kopyalandi (watcher PENDING olarak alacak)." -ForegroundColor Green
Write-Host "    Simdi panelde: Yonetim > Isleme > 'Islemeyi baslat' deyin." -ForegroundColor Cyan
Write-Host "    (Sesli cagrilar icin host worker acik olmali: scripts\run-host-worker.ps1)" -ForegroundColor Yellow
