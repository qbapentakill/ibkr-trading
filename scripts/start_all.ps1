# IBKR Trading System — uruchamia wszystko naraz
# Backend + Panel + ngrok

$dir = "C:\Users\kubak\Documents\kiro\ibkr_trading_system"

# Okno 1 — Backend
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$dir'; .\.venv\Scripts\Activate.ps1; py -3.11 main.py"

# Poczekaj 15 sekund aż backend wstanie
Start-Sleep -Seconds 15

# Okno 2 — Streamlit panel
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$dir'; .\.venv\Scripts\Activate.ps1; streamlit run panel/frontend/dashboard.py"

# Poczekaj 8 sekund aż streamlit wstanie
Start-Sleep -Seconds 8

# Okno 3 — ngrok tunel
Start-Process powershell -ArgumentList "-NoExit", "-Command", "ngrok http --domain=five-party-outshoot.ngrok-free.dev 8501"

# Poczekaj 3 sekundy i otwórz publiczny URL
Start-Sleep -Seconds 3
Start-Process "https://five-party-outshoot.ngrok-free.dev"
