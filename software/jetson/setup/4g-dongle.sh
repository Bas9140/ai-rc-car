#!/usr/bin/env bash
# 4g-dongle.sh – USB 4G dongle instellen op de Jetson Orin Nano
#
# Ondersteunt:
#   - HiLink dongles (Huawei E3372h e.d.) → verschijnen als USB-ethernet, plug & play
#   - Modem-modus dongles via ModemManager + NetworkManager
#
# Gebruik:
#   sudo bash 4g-dongle.sh [--apn internet] [--sim-pin 1234]
#
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${GREEN}[4G]${NC} $*"; }
warn()  { echo -e "${YELLOW}[4G]${NC} $*"; }
error() { echo -e "${RED}[4G]${NC} $*"; exit 1; }
step()  { echo -e "${CYAN}──── $* ────${NC}"; }

[[ $EUID -ne 0 ]] && error "Draai dit script als root: sudo bash $0"

# ── Opties ────────────────────────────────────────────────────────────────
APN="internet"        # Odido / KPN / Vodafone NL = 'internet'
SIM_PIN=""
CONNECTION_NAME="rc-car-4g"

while [[ $# -gt 0 ]]; do
  case $1 in
    --apn)     APN="$2";     shift 2 ;;
    --sim-pin) SIM_PIN="$2"; shift 2 ;;
    *) warn "Onbekende optie: $1"; shift ;;
  esac
done

# ── Stap 1: Benodigde pakketten ───────────────────────────────────────────
step "Pakketten installeren"
apt-get update -qq
apt-get install -y -qq \
  usb-modeswitch usb-modeswitch-data \
  modemmanager \
  network-manager \
  network-manager-gnome 2>/dev/null || true

systemctl enable --now ModemManager NetworkManager

# ── Stap 2: Dongle detecteren ─────────────────────────────────────────────
step "USB dongle detecteren"
sleep 2  # wacht even na usb_modeswitch

# HiLink-modus: dongle als USB-ethernet (e.g. Huawei E3372h in HiLink mode)
HILINK_IF=$(ip -o link show | awk -F': ' '{print $2}' | grep -E '^(usb|enx|eth)[0-9]' | head -1 || true)

# Modem-modus: ModemManager
MODEM_PATH=$(mmcli -L 2>/dev/null | grep -oP '/org/freedesktop/ModemManager1/Modem/\d+' | head -1 || true)

if [[ -n "$HILINK_IF" ]]; then
  info "HiLink dongle gevonden op interface: $HILINK_IF"
  info "HiLink dongles werken als USB-ethernet – geen APN configuratie nodig."
  info "NetworkManager neemt automatisch DHCP over van de dongle."

  # Controleer of er al een verbinding is
  if nmcli -t -f DEVICE,STATE dev | grep -q "^${HILINK_IF}:connected"; then
    info "Dongle al verbonden!"
  else
    nmcli dev connect "$HILINK_IF" || warn "Verbinden mislukt, probeer handmatig."
  fi

  step "Netwerk prioriteit instellen (WiFi > 4G fallback)"
  _configure_routing "$HILINK_IF"

elif [[ -n "$MODEM_PATH" ]]; then
  info "Modem-modus dongle gevonden: $MODEM_PATH"
  _setup_modem "$MODEM_PATH"
else
  warn "Geen USB dongle gevonden. Controleer:"
  warn "  lsusb       → dongle zichtbaar?"
  warn "  dmesg | tail -20  → USB events?"
  warn "  mmcli -L    → modem gedetecteerd?"
  warn ""
  warn "Als de dongle in 'storage-modus' staat: usb_modeswitch schakelt automatisch."
  warn "Koppel de dongle los en opnieuw aan na dit script."
  exit 0
fi

# ── Stap 3: Modem-modus verbinding aanmaken ───────────────────────────────
_setup_modem() {
  local modem_path="$1"
  info "Modem configureren via NetworkManager..."

  # Verwijder oude verbinding als aanwezig
  nmcli con delete "$CONNECTION_NAME" 2>/dev/null || true

  # Maak GSM verbinding aan
  nmcli con add \
    type gsm \
    ifname "*" \
    con-name "$CONNECTION_NAME" \
    apn "$APN" \
    ${SIM_PIN:+pin "$SIM_PIN"}

  # Auto-connect inschakelen
  nmcli con modify "$CONNECTION_NAME" \
    connection.autoconnect yes \
    connection.autoconnect-priority 10

  nmcli con up "$CONNECTION_NAME"
  info "Verbinding '$CONNECTION_NAME' actief."
}

# ── Stap 4: Route prioriteit (WiFi primair, 4G als fallback) ──────────────
_configure_routing() {
  local mobile_if="${1:-}"

  # NetworkManager metric: lagere waarde = hogere prioriteit
  # WiFi: metric 100 (standaard), 4G: metric 200 (lagere prioriteit)
  if [[ -n "$mobile_if" ]]; then
    nmcli con modify "$CONNECTION_NAME" ipv4.route-metric 200 2>/dev/null || \
    nmcli dev modify "$mobile_if" ipv4.route-metric 200 2>/dev/null || true
  fi

  # WiFi verbindingen hogere prioriteit geven
  for WIFI_CON in $(nmcli -t -f NAME,TYPE con show | grep ':wifi' | cut -d: -f1); do
    nmcli con modify "$WIFI_CON" ipv4.route-metric 100 2>/dev/null || true
    info "WiFi '${WIFI_CON}' prioriteit: 100 (primair)"
  done

  info "4G interface prioriteit: 200 (fallback als WiFi wegvalt)"
}

# ── Stap 5: Verbinding testen ─────────────────────────────────────────────
step "Verbinding testen"
sleep 3
if ping -c 2 -W 3 8.8.8.8 &>/dev/null; then
  info "Internet bereikbaar via 4G!"
  PUBIP=$(curl -s --max-time 5 ifconfig.me || echo "onbekend")
  info "Publiek IP: $PUBIP"
else
  warn "Geen internet via 4G. Controleer SIM-kaart en APN (${APN})."
fi

# ── Stap 6: Auto-reconnect script ─────────────────────────────────────────
step "Auto-reconnect service installeren"
cat > /usr/local/bin/rc-car-net-watchdog.sh << 'WATCHDOG'
#!/usr/bin/env bash
# Watchdog: herverbind 4G als internet weg is
while true; do
  if ! ping -c 1 -W 5 8.8.8.8 &>/dev/null; then
    logger -t rc-car-net "Internet weg – 4G herverbinden..."
    nmcli con up rc-car-4g 2>/dev/null || \
    nmcli dev connect "$(ip -o link show | awk -F': ' '{print $2}' | grep -E '^(usb|enx)' | head -1)" 2>/dev/null || true
  fi
  sleep 30
done
WATCHDOG
chmod +x /usr/local/bin/rc-car-net-watchdog.sh

cat > /etc/systemd/system/rc-car-net-watchdog.service << 'SERVICE'
[Unit]
Description=RC Car 4G Network Watchdog
After=network.target NetworkManager.service
Wants=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/rc-car-net-watchdog.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable --now rc-car-net-watchdog.service
info "Watchdog actief: herverbindt 4G automatisch als internet wegvalt."

step "Klaar!"
info "4G dongle geconfigureerd."
info "  APN: $APN"
info "  Verbinding: $CONNECTION_NAME"
info "  Watchdog: rc-car-net-watchdog.service"
info ""
info "Volgende stap: bash cloudflare-tunnel.sh"
