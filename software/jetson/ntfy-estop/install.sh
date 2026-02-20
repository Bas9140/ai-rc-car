#!/usr/bin/env bash
# install.sh – ntfy noodstop service installeren op de Jetson
set -euo pipefail

GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
info() { echo -e "${GREEN}[install]${NC} $*"; }
step() { echo -e "${CYAN}──── $* ────${NC}"; }

[[ $EUID -ne 0 ]] && { echo "Draai als root: sudo bash $0"; exit 1; }

NTFY_TOKEN="${1:-}"
[[ -z "$NTFY_TOKEN" ]] && { echo "Gebruik: sudo bash install.sh <ntfy-token>"; exit 1; }

step "Bestanden kopiëren"
mkdir -p /opt/rc-car/ntfy-estop
cp ntfy_estop.py /opt/rc-car/ntfy-estop/
chmod +x /opt/rc-car/ntfy-estop/ntfy_estop.py

step "Python dependency installeren"
pip3 install requests -q 2>/dev/null || pip3 install requests -q --break-system-packages

step "Config bestand aanmaken"
mkdir -p /etc/rc-car
cat > /etc/rc-car/ntfy-estop.conf << CONF
NTFY_URL=https://ntfy.basvenema.win
NTFY_TOPIC=rc-car
NTFY_TOKEN=${NTFY_TOKEN}
DASHBOARD_URL=http://localhost:8080
STATUS_TOPIC=Homelab
CONF
chmod 600 /etc/rc-car/ntfy-estop.conf
info "Config: /etc/rc-car/ntfy-estop.conf"

step "systemd service installeren"
# Token uit de service verwijderen (zit nu in conf bestand)
sed "s|NTFY_TOKEN=VERVANG_MET_JOUW_TOKEN|NTFY_TOKEN=${NTFY_TOKEN}|g" \
  ntfy-estop.service > /etc/systemd/system/ntfy-estop.service

systemctl daemon-reload
systemctl enable --now ntfy-estop.service

step "Testen"
sleep 2
systemctl is-active ntfy-estop && info "Service actief!" || echo "Service status: $(systemctl is-active ntfy-estop)"

info ""
info "Installatie klaar. Stuur een bericht naar ntfy topic 'rc-car' om te testen:"
info "  Commando's: STOP, PAUSE, RESUME, START, MANUAL, AUTO, STATUS"
info ""
info "Logboek bekijken: journalctl -u ntfy-estop -f"
