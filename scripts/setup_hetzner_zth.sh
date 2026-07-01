#!/bin/bash
# Setup script pour ZeroToHeroBTC sur Hetzner (Ubuntu 22.04)
# Usage : bash setup_hetzner_zth.sh
set -e

echo "=== ZeroToHeroBTC — Setup Hetzner ==="

# 1. Système
apt-get update -qq && apt-get install -y -qq git python3.11 python3.11-venv python3-pip screen

# 2. Cloner le repo
if [ ! -d "/opt/bottrading" ]; then
  git clone https://github.com/Cttdev7/BotTradingV2 /opt/bottrading
else
  cd /opt/bottrading && git pull
fi
cd /opt/bottrading

# 3. Virtualenv Python 3.11
python3.11 -m venv /opt/zth_venv
source /opt/zth_venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
pip install --quiet polymarket-client eth-account eth-utils eth-abi hexbytes pycryptodome

# 4. Fichier .env (à remplir manuellement)
if [ ! -f "/opt/bottrading/bot/.env" ]; then
  cat > /opt/bottrading/bot/.env << 'ENVEOF'
ZTH_WALLET_ADDRESS=REMPLACER
ZTH_PRIVATE_KEY=REMPLACER
ZTH_API_KEY=REMPLACER
ZTH_API_SECRET=REMPLACER
ZTH_API_PASSPHRASE=REMPLACER
ZTH_DRY_RUN=true
SUPABASE_URL=REMPLACER
SUPABASE_SERVICE_KEY=REMPLACER
ENVEOF
  echo ""
  echo "⚠️  IMPORTANT : remplis /opt/bottrading/bot/.env avec tes vraies clés !"
  echo "    nano /opt/bottrading/bot/.env"
  echo ""
fi

# 5. Service systemd (auto-restart)
cat > /etc/systemd/system/zerotoherobtc.service << 'SERVICEEOF'
[Unit]
Description=ZeroToHeroBTC Trading Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/bottrading/bot
EnvironmentFile=/opt/bottrading/bot/.env
ExecStart=/opt/zth_venv/bin/python3 /opt/bottrading/bot/zerotoherobtc.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SERVICEEOF

systemctl daemon-reload
systemctl enable zerotoherobtc

echo ""
echo "=== Installation terminée ==="
echo ""
echo "Étapes suivantes :"
echo "  1. Remplis les clés : nano /opt/bottrading/bot/.env"
echo "  2. Mets ZTH_DRY_RUN=true pour tester d'abord"
echo "  3. Lance : systemctl start zerotoherobtc"
echo "  4. Vérifie les logs : journalctl -u zerotoherobtc -f"
echo "  5. Si aucun geoblock → passe ZTH_DRY_RUN=false + systemctl restart zerotoherobtc"
