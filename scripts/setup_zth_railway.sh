#!/bin/bash
set -e
cd "$(dirname "$0")/.."
set -a
source bot/.env
set +a

SERVICE="blissful-integrity"

railway variable set ZTH_WALLET_ADDRESS="$ZTH_WALLET_ADDRESS" --service "$SERVICE" --skip-deploys --json >/dev/null
railway variable set ZTH_PRIVATE_KEY="$ZTH_PRIVATE_KEY" --service "$SERVICE" --skip-deploys --json >/dev/null
railway variable set ZTH_API_KEY="$ZTH_API_KEY" --service "$SERVICE" --skip-deploys --json >/dev/null
railway variable set ZTH_API_SECRET="$ZTH_API_SECRET" --service "$SERVICE" --skip-deploys --json >/dev/null
railway variable set ZTH_API_PASSPHRASE="$ZTH_API_PASSPHRASE" --service "$SERVICE" --skip-deploys --json >/dev/null
railway variable set ZTH_DRY_RUN="true" --service "$SERVICE" --skip-deploys --json >/dev/null

if [ -n "$SUPABASE_SERVICE_KEY" ]; then
  railway variable set SUPABASE_SERVICE_KEY="$SUPABASE_SERVICE_KEY" --service "$SERVICE" --skip-deploys --json >/dev/null
fi

railway variable delete PRIVATE_KEY --service "$SERVICE" --json >/dev/null || true
railway variable delete API_KEY --service "$SERVICE" --json >/dev/null || true
railway variable delete API_SECRET --service "$SERVICE" --json >/dev/null || true
railway variable delete API_PASSPHRASE --service "$SERVICE" --json >/dev/null || true
railway variable delete DRY_RUN --service "$SERVICE" --json >/dev/null || true

echo "OK — variables ZTH configurées, anciennes clés ProfitWeather supprimées de ce service"
