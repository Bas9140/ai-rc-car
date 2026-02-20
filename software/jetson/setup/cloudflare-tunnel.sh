#!/usr/bin/env bash
# cloudflare-tunnel.sh – Cloudflare Tunnel instellen op de Jetson
#
# Maakt een tunnel aan voor rc-car.basvenema.win → localhost:8080
# Gebruikt de Cloudflare API (geen browser-login nodig).
#
# Gebruik:
#   sudo bash cloudflare-tunnel.sh \
#     --token  <CF_API_TOKEN> \
#     --zone   <ZONE_ID>
#
# Beide waarden staan in MEMORY.md / je password manager.
#
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${GREEN}[CF]${NC} $*"; }
warn()  { echo -e "${YELLOW}[CF]${NC} $*"; }
error() { echo -e "${RED}[CF]${NC} $*"; exit 1; }
step()  { echo -e "${CYAN}──── $* ────${NC}"; }

[[ $EUID -ne 0 ]] && error "Draai dit script als root: sudo bash $0"

# ── Opties ────────────────────────────────────────────────────────────────
CF_TOKEN=""
CF_ZONE_ID=""
TUNNEL_NAME="rc-car"
HOSTNAME="rc-car.basvenema.win"
DASHBOARD_PORT=8080
CRED_DIR="/etc/cloudflared"

while [[ $# -gt 0 ]]; do
  case $1 in
    --token)  CF_TOKEN="$2";   shift 2 ;;
    --zone)   CF_ZONE_ID="$2"; shift 2 ;;
    --name)   TUNNEL_NAME="$2"; shift 2 ;;
    --host)   HOSTNAME="$2";   shift 2 ;;
    --port)   DASHBOARD_PORT="$2"; shift 2 ;;
    *) warn "Onbekende optie: $1"; shift ;;
  esac
done

[[ -z "$CF_TOKEN"   ]] && error "--token vereist (Cloudflare API token)"
[[ -z "$CF_ZONE_ID" ]] && error "--zone vereist (Cloudflare Zone ID)"

# ── Stap 1: cloudflared installeren (ARM64 voor Jetson) ───────────────────
step "cloudflared installeren"

ARCH=$(uname -m)
case $ARCH in
  aarch64|arm64) CF_ARCH="arm64" ;;
  x86_64)        CF_ARCH="amd64" ;;
  *) error "Onbekende architectuur: $ARCH" ;;
esac

if ! command -v cloudflared &>/dev/null; then
  info "cloudflared downloaden voor ${CF_ARCH}..."
  CF_VERSION=$(curl -s https://api.github.com/repos/cloudflare/cloudflared/releases/latest \
    | grep '"tag_name"' | cut -d'"' -f4)
  info "Versie: $CF_VERSION"

  curl -fsSL \
    "https://github.com/cloudflare/cloudflared/releases/download/${CF_VERSION}/cloudflared-linux-${CF_ARCH}" \
    -o /usr/local/bin/cloudflared

  chmod +x /usr/local/bin/cloudflared
  info "cloudflared geïnstalleerd: $(cloudflared --version)"
else
  info "cloudflared al aanwezig: $(cloudflared --version)"
fi

# ── Stap 2: Account ID ophalen via API ────────────────────────────────────
step "Account ID ophalen"
ACCOUNT_ID=$(curl -s \
  -H "Authorization: Bearer ${CF_TOKEN}" \
  -H "Content-Type: application/json" \
  "https://api.cloudflare.com/client/v4/accounts?per_page=1" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['result'][0]['id'])")

[[ -z "$ACCOUNT_ID" ]] && error "Account ID ophalen mislukt. Controleer je API token."
info "Account ID: ${ACCOUNT_ID:0:8}..."

# ── Stap 3: Tunnel aanmaken (of bestaande hergebruiken) ───────────────────
step "Tunnel aanmaken: $TUNNEL_NAME"
mkdir -p "$CRED_DIR"

# Controleer of tunnel al bestaat
EXISTING=$(curl -s \
  -H "Authorization: Bearer ${CF_TOKEN}" \
  "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/cfd_tunnel?name=${TUNNEL_NAME}&is_deleted=false" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); \
    t=d.get('result',[]); print(t[0]['id'] if t else '')" 2>/dev/null || true)

if [[ -n "$EXISTING" ]]; then
  TUNNEL_ID="$EXISTING"
  info "Bestaande tunnel hergebruikt: $TUNNEL_ID"

  # Token ophalen van bestaande tunnel
  TUNNEL_TOKEN=$(curl -s \
    -H "Authorization: Bearer ${CF_TOKEN}" \
    "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/cfd_tunnel/${TUNNEL_ID}/token" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['result'])")
else
  # Nieuwe tunnel aanmaken
  RESULT=$(curl -s -X POST \
    -H "Authorization: Bearer ${CF_TOKEN}" \
    -H "Content-Type: application/json" \
    "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/cfd_tunnel" \
    -d "{\"name\":\"${TUNNEL_NAME}\",\"config_src\":\"cloudflare\"}")

  TUNNEL_ID=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['id'])")
  info "Nieuwe tunnel aangemaakt: $TUNNEL_ID"

  TUNNEL_TOKEN=$(curl -s \
    -H "Authorization: Bearer ${CF_TOKEN}" \
    "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/cfd_tunnel/${TUNNEL_ID}/token" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['result'])")
fi

# Token opslaan
echo "$TUNNEL_TOKEN" > "${CRED_DIR}/tunnel-token"
chmod 600 "${CRED_DIR}/tunnel-token"
info "Tunnel token opgeslagen in ${CRED_DIR}/tunnel-token"

# ── Stap 4: Tunnel configuratie aanmaken via API ──────────────────────────
step "Route configureren: $HOSTNAME → localhost:${DASHBOARD_PORT}"
curl -s -X PUT \
  -H "Authorization: Bearer ${CF_TOKEN}" \
  -H "Content-Type: application/json" \
  "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/cfd_tunnel/${TUNNEL_ID}/configurations" \
  -d "{
    \"config\": {
      \"ingress\": [
        {
          \"hostname\": \"${HOSTNAME}\",
          \"service\": \"http://localhost:${DASHBOARD_PORT}\"
        },
        {
          \"service\": \"http_status:404\"
        }
      ]
    }
  }" | python3 -c "
import sys,json
d=json.load(sys.stdin)
if d.get('success'):
    print('  Route geconfigureerd OK')
else:
    print('  Fout:', d.get('errors'))
"

# ── Stap 5: DNS record aanmaken ───────────────────────────────────────────
step "DNS CNAME aanmaken: $HOSTNAME"
SUBDOMAIN=$(echo "$HOSTNAME" | cut -d. -f1)

# Controleer of record al bestaat
EXISTING_DNS=$(curl -s \
  -H "Authorization: Bearer ${CF_TOKEN}" \
  "https://api.cloudflare.com/client/v4/zones/${CF_ZONE_ID}/dns_records?name=${HOSTNAME}&type=CNAME" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); \
    r=d.get('result',[]); print(r[0]['id'] if r else '')" 2>/dev/null || true)

DNS_RECORD="{
  \"type\": \"CNAME\",
  \"name\": \"${SUBDOMAIN}\",
  \"content\": \"${TUNNEL_ID}.cfargotunnel.com\",
  \"proxied\": true,
  \"ttl\": 1
}"

if [[ -n "$EXISTING_DNS" ]]; then
  curl -s -X PUT \
    -H "Authorization: Bearer ${CF_TOKEN}" \
    -H "Content-Type: application/json" \
    "https://api.cloudflare.com/client/v4/zones/${CF_ZONE_ID}/dns_records/${EXISTING_DNS}" \
    -d "$DNS_RECORD" > /dev/null
  info "DNS record bijgewerkt"
else
  curl -s -X POST \
    -H "Authorization: Bearer ${CF_TOKEN}" \
    -H "Content-Type: application/json" \
    "https://api.cloudflare.com/client/v4/zones/${CF_ZONE_ID}/dns_records" \
    -d "$DNS_RECORD" > /dev/null
  info "DNS record aangemaakt"
fi

info "${HOSTNAME} → tunnel (Cloudflare proxied)"

# ── Stap 6: systemd service ───────────────────────────────────────────────
step "systemd service installeren"
cat > /etc/systemd/system/rc-car-tunnel.service << SERVICE
[Unit]
Description=RC Car Cloudflare Tunnel
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=nobody
ExecStart=/usr/local/bin/cloudflared tunnel --no-autoupdate run --token $(cat ${CRED_DIR}/tunnel-token)
Restart=always
RestartSec=15
# Wacht op internet voordat tunnel start
ExecStartPre=/bin/sh -c 'until ping -c1 8.8.8.8 >/dev/null 2>&1; do sleep 2; done'

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable rc-car-tunnel.service
info "Service geïnstalleerd: rc-car-tunnel.service"
info "Start handmatig met: systemctl start rc-car-tunnel"
info "(auto-start bij volgende reboot)"

# ── Stap 7: Test ─────────────────────────────────────────────────────────
step "Tunnel starten en testen"
systemctl start rc-car-tunnel.service
sleep 5

STATUS=$(systemctl is-active rc-car-tunnel.service)
if [[ "$STATUS" == "active" ]]; then
  info "Tunnel actief!"
  info ""
  info "Dashboard bereikbaar op: https://${HOSTNAME}"
  info ""
  info "Let op: het kan 1-2 minuten duren voor DNS propagatie."
else
  warn "Tunnel status: $STATUS"
  warn "Bekijk logs: journalctl -u rc-car-tunnel -n 20"
fi

step "Klaar!"
info "Tunnel ID:  $TUNNEL_ID"
info "Hostname:   https://${HOSTNAME}"
info "Lokale URL: http://localhost:${DASHBOARD_PORT}"
