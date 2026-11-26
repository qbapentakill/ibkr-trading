#!/bin/bash
# ============================================================
# IBKR Trading Bot - Auto Setup Script dla Ubuntu VPS
# Uruchom: bash setup_vps.sh
# ============================================================

set -e
echo "🚀 Instalacja IBKR Trading Bot..."

# 1. System update
apt-get update -qq
apt-get install -y git python3 python3-pip python3-venv screen curl

# 2. Klonuj repo
cd /opt
git clone https://github.com/qbapentakill/ibkr-trading.git trading-bot
cd trading-bot

# 3. Virtualenv
python3 -m venv .venv
source .venv/bin/activate

# 4. Instaluj zależności
pip install -q --upgrade pip
pip install -q -r requirements.txt
pip install -q psutil

# 5. Utwórz katalogi
mkdir -p logs data

# 6. Utwórz plik .env
cat > .env << 'EOF'
REAL_MODE=false
DATABASE_URL=sqlite+aiosqlite:///./data/trading.db
PANEL_USERNAME=admin
PANEL_PASSWORD_HASH=$2b$12$F.f.BvuULaa/5Z.1ahJICeFE1NelWnuQ2cu6vY1z2cLsUeSdQCrpK
SECRET_KEY=ibkr-trading-secret-key-256bit-secure
POLYGON_API_KEY=AcPTTko_iZlputYsD7bTuSEQSIbHh6ws
GROQ_API_KEY=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
ALPACA_API_KEY=PKBNZRZJLZPM7H3VEBPBGZ3GHY
ALPACA_SECRET_KEY=9XNSFZA9r3L7bHV7eF9cz8n1CwiEqPEuriw7PAXXAEtP
ALPACA_PAPER=true
ALPACA_BASE_URL=https://paper-api.alpaca.markets
ALPACA_DATA_URL=https://data.alpaca.markets
REDIS_URL=redis://localhost:6379/0
EMERGENCY_STOP_PASSWORD=stop123
EOF

# 7. Utwórz serwisy systemd

# Backend API
cat > /etc/systemd/system/trading-api.service << 'EOF'
[Unit]
Description=Trading Bot API
After=network.target

[Service]
WorkingDirectory=/opt/trading-bot
ExecStart=/opt/trading-bot/.venv/bin/uvicorn panel.api.app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Dashboard
cat > /etc/systemd/system/trading-dashboard.service << 'EOF'
[Unit]
Description=Trading Bot Dashboard
After=trading-api.service

[Service]
WorkingDirectory=/opt/trading-bot
ExecStart=/opt/trading-bot/.venv/bin/streamlit run panel/frontend/dashboard.py --server.port 8501 --server.address 0.0.0.0 --server.headless true
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 8. Uruchom serwisy
systemctl daemon-reload
systemctl enable trading-api trading-dashboard
systemctl start trading-api trading-dashboard

echo ""
echo "✅ INSTALACJA ZAKOŃCZONA!"
echo ""
echo "Dashboard: http://2.29.118.173:8501"
echo "API:       http://2.29.118.173:8000"
echo "API docs:  http://2.29.118.173:8000/docs"
echo ""
echo "Login: admin"
echo "Hasło: jakie ustawiłeś w .env"
echo ""
echo "Logi: journalctl -u trading-api -f"
