# IBKR Trading System - Start
$dir    = "C:\Users\kubak\Documents\kiro\ibkr_trading_system"
$python = "$dir\.venv\Scripts\python.exe"
$stream = "$dir\.venv\Scripts\streamlit.exe"

# Zabij stare procesy jesli dzialaja
Get-Process -Name python -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process -Name ngrok  -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  IBKR Trading System - Uruchamianie..." -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# [1/3] Backend w widocznym oknie żeby zobaczyć błędy
Write-Host "  [1/3] Backend..." -NoNewline
$bot = Start-Process $python -ArgumentList "-c `"import traceback; exec(open('main.py').read())`"" -WorkingDirectory $dir -PassThru -WindowStyle Normal
Start-Sleep -Seconds 2
Write-Host " OK (PID $($bot.Id))" -ForegroundColor Green

# Czekaj az API wstanie (max 60s)
Write-Host "  [1/3] Czekam na API" -NoNewline
$ready = $false
for ($i = 0; $i -lt 120; $i++) {
    Start-Sleep -Seconds 1
    Write-Host "." -NoNewline
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:8000/health" -TimeoutSec 1 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch {}
    # Co 20s pokaż że nadal czekamy
    if ($i -gt 0 -and $i % 20 -eq 0) {
        Write-Host "" 
        Write-Host "  (backend ładuje dane rynkowe, czekaj...)" -ForegroundColor DarkGray -NoNewline
    }
}
if ($ready) {
    Write-Host " gotowy!" -ForegroundColor Green
} else {
    Write-Host " timeout" -ForegroundColor Yellow
}

# [2/3] Panel w tle
Write-Host "  [2/3] Panel..." -NoNewline
$panel = Start-Process $stream -ArgumentList "run panel/frontend/dashboard.py --server.headless true" -WorkingDirectory $dir -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 6
Write-Host " OK (PID $($panel.Id))" -ForegroundColor Green

# [3/3] ngrok
Write-Host "  [3/3] ngrok..." -NoNewline
$ngrok = Start-Process "ngrok" -ArgumentList "http --domain=five-party-outshoot.ngrok-free.dev 8501" -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 4
Write-Host " OK (PID $($ngrok.Id))" -ForegroundColor Green

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  SYSTEM GOTOWY" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  URL: https://five-party-outshoot.ngrok-free.dev" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Nie zamykaj tego okna!" -ForegroundColor Yellow
Write-Host ""

Start-Process "https://five-party-outshoot.ngrok-free.dev"

# Status co 30s + auto-restart
while ($true) {
    Start-Sleep -Seconds 30
    $now = Get-Date -Format "HH:mm:ss"
    $b = if (-not $bot.HasExited)   { "Bot:OK" }   else { "Bot:PADL" }
    $p = if (-not $panel.HasExited) { "Panel:OK" } else { "Panel:PADL" }
    $n = if (-not $ngrok.HasExited) { "ngrok:OK" } else { "ngrok:PADL" }
    Write-Host "  $now  $b  $p  $n" -ForegroundColor DarkGray

    if ($bot.HasExited) {
        Write-Host "  Restarting bot..." -ForegroundColor Yellow
        $bot = Start-Process $python -ArgumentList "main.py" -WorkingDirectory $dir -PassThru -WindowStyle Hidden
    }
    if ($ngrok.HasExited) {
        Write-Host "  Restarting ngrok..." -ForegroundColor Yellow
        $ngrok = Start-Process "ngrok" -ArgumentList "http --domain=five-party-outshoot.ngrok-free.dev 8501" -PassThru -WindowStyle Hidden
    }
}
