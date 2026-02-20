#!/usr/bin/env python3
"""
ntfy_estop.py – Noodstop luisteraar via ntfy SSE stream

Luistert naar het ntfy topic 'rc-car'.
Ondersteunde commando's (hoofdletter-onafhankelijk):

  STOP / NOODSTOP / E-STOP → emergency stop + modus idle
  PAUSE                     → navigatie pauzeren
  RESUME                    → navigatie hervatten
  START                     → navigatie starten
  MANUAL                    → wisselen naar handmatige modus
  AUTO / AUTONOMOUS         → wisselen naar autonome modus
  STATUS                    → stuur een ntfy-notificatie met huidige status terug

Configuratie via omgevingsvariabelen (of /etc/rc-car/ntfy-estop.conf):
  NTFY_URL      https://ntfy.basvenema.win
  NTFY_TOPIC    rc-car
  NTFY_TOKEN    tk_...
  DASHBOARD_URL http://localhost:8080
  STATUS_TOPIC  Homelab   (ntfy topic voor status-terugkoppelingen)
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
import time
from pathlib import Path

import requests

# ── Logging ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [ntfy-estop] %(levelname)s %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger(__name__)

# ── Configuratie ──────────────────────────────────────────────────────────
CONF_FILE = Path('/etc/rc-car/ntfy-estop.conf')

def load_config() -> dict:
    cfg = {}
    if CONF_FILE.exists():
        for line in CONF_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, _, v = line.partition('=')
                cfg[k.strip()] = v.strip()
    # omgevingsvariabelen overschrijven config-bestand
    for key in ('NTFY_URL', 'NTFY_TOPIC', 'NTFY_TOKEN', 'DASHBOARD_URL', 'STATUS_TOPIC'):
        if key in os.environ:
            cfg[key] = os.environ[key]
    return cfg

CFG = load_config()

NTFY_URL      = CFG.get('NTFY_URL',      'https://ntfy.basvenema.win')
NTFY_TOPIC    = CFG.get('NTFY_TOPIC',    'rc-car')
NTFY_TOKEN    = CFG.get('NTFY_TOKEN',    '')
DASHBOARD_URL = CFG.get('DASHBOARD_URL', 'http://localhost:8080')
STATUS_TOPIC  = CFG.get('STATUS_TOPIC',  'Homelab')

# ── Dashboard API ─────────────────────────────────────────────────────────
class DashboardClient:
    def __init__(self, base_url: str):
        self.base = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.timeout = 5

    def _post(self, path: str, data: dict | None = None) -> bool:
        try:
            r = self.session.post(f'{self.base}{path}', json=data or {})
            r.raise_for_status()
            return True
        except Exception as e:
            log.error('Dashboard API fout (%s): %s', path, e)
            return False

    def _get(self, path: str) -> dict | None:
        try:
            r = self.session.get(f'{self.base}{path}')
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.error('Dashboard GET fout (%s): %s', path, e)
            return None

    def emergency_stop(self) -> bool:
        ok = self._post('/api/mission/stop')
        if ok:
            log.warning('NOODSTOP uitgevoerd!')
        return ok

    def set_mode(self, mode: str) -> bool:
        ok = self._post('/api/mission/mode', {'mode': mode})
        if ok:
            log.info('Modus → %s', mode)
        return ok

    def nav_start(self) -> bool:
        return self._post('/api/navigation/start')

    def nav_pause(self) -> bool:
        return self._post('/api/navigation/pause')

    def nav_resume(self) -> bool:
        return self._post('/api/navigation/resume')

    def get_status(self) -> dict | None:
        return self._get('/api/status')


# ── ntfy terugkoppeling ───────────────────────────────────────────────────
def send_ntfy(topic: str, message: str, title: str = 'RC Car', priority: str = 'default'):
    if not NTFY_TOKEN:
        return
    try:
        requests.post(
            f'{NTFY_URL}/{topic}',
            data=message.encode(),
            headers={
                'Authorization': f'Bearer {NTFY_TOKEN}',
                'Title': title,
                'Priority': priority,
            },
            timeout=5,
        )
    except Exception as e:
        log.debug('ntfy terugkoppeling mislukt: %s', e)


# ── Commando verwerking ───────────────────────────────────────────────────
def handle_command(text: str, dashboard: DashboardClient):
    cmd = text.strip().upper()
    log.info('Commando ontvangen: %r', cmd)

    if cmd in ('STOP', 'NOODSTOP', 'E-STOP', 'ESTOP', '⛔'):
        ok = dashboard.emergency_stop()
        msg = '⛔ Noodstop uitgevoerd!' if ok else '⚠️ Noodstop mislukt!'
        send_ntfy(STATUS_TOPIC, msg, title='RC Car Noodstop', priority='urgent')

    elif cmd == 'PAUSE':
        ok = dashboard.nav_pause()
        send_ntfy(STATUS_TOPIC, '⏸ Navigatie gepauzeerd' if ok else '⚠️ Pauzeren mislukt')

    elif cmd == 'RESUME':
        ok = dashboard.nav_resume()
        send_ntfy(STATUS_TOPIC, '▶️ Navigatie hervat' if ok else '⚠️ Hervatten mislukt')

    elif cmd == 'START':
        ok = dashboard.nav_start()
        send_ntfy(STATUS_TOPIC, '▶️ Navigatie gestart' if ok else '⚠️ Starten mislukt')

    elif cmd == 'MANUAL':
        ok = dashboard.set_mode('manual')
        send_ntfy(STATUS_TOPIC, '🕹 Handmatige modus actief' if ok else '⚠️ Modus wisselen mislukt')

    elif cmd in ('AUTO', 'AUTONOMOUS', 'AUTONOOM'):
        ok = dashboard.set_mode('autonomous')
        send_ntfy(STATUS_TOPIC, '🤖 Autonome modus actief' if ok else '⚠️ Modus wisselen mislukt')

    elif cmd == 'STATUS':
        st = dashboard.get_status()
        if st:
            gps = f"{st.get('latitude', '?'):.5f}, {st.get('longitude', '?'):.5f}" \
                if st.get('latitude') else 'geen GPS'
            msg = (
                f"Modus: {st.get('mode','?')}\n"
                f"GPS: {gps}\n"
                f"Koers: {st.get('heading_deg','?'):.1f}°\n"
                f"Ontwijken: {st.get('avoidance_status','?')}\n"
                f"Noodstop: {'JA' if st.get('emergency_stop') else 'nee'}"
            )
        else:
            msg = '⚠️ Status ophalen mislukt (dashboard offline?)'
        send_ntfy(STATUS_TOPIC, msg, title='RC Car Status')

    else:
        log.debug('Onbekend commando: %r', cmd)


# ── SSE luisteraar ────────────────────────────────────────────────────────
def listen(dashboard: DashboardClient):
    url = f'{NTFY_URL}/{NTFY_TOPIC}/sse'
    headers = {'Accept': 'text/event-stream'}
    if NTFY_TOKEN:
        headers['Authorization'] = f'Bearer {NTFY_TOKEN}'

    log.info('Luisteren op %s (topic: %s)', NTFY_URL, NTFY_TOPIC)

    while True:
        try:
            with requests.get(url, headers=headers, stream=True, timeout=90) as resp:
                resp.raise_for_status()
                log.info('SSE verbinding actief')

                for line in resp.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    # SSE formaat: "data: {...json...}"
                    if line.startswith('data:'):
                        raw = line[5:].strip()
                        if not raw or raw == 'keep-alive':
                            continue
                        try:
                            event = json.loads(raw)
                        except json.JSONDecodeError:
                            continue

                        # Alleen 'message' events verwerken
                        if event.get('event', 'message') != 'message':
                            continue

                        text = event.get('message', '').strip()
                        if text:
                            handle_command(text, dashboard)

        except requests.exceptions.Timeout:
            log.debug('SSE keepalive timeout – herverbinden...')
        except requests.exceptions.ConnectionError as e:
            log.warning('Verbinding verbroken: %s – herverbinden in 10s', e)
            time.sleep(10)
        except Exception as e:
            log.error('SSE fout: %s – herverbinden in 15s', e)
            time.sleep(15)


# ── Hoofdprogramma ────────────────────────────────────────────────────────
def main():
    dashboard = DashboardClient(DASHBOARD_URL)

    # Graceful shutdown
    def _shutdown(sig, frame):
        log.info('Afsluiten...')
        sys.exit(0)
    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    # Wacht tot dashboard bereikbaar is
    log.info('Wachten op dashboard (%s)...', DASHBOARD_URL)
    for _ in range(30):
        try:
            requests.get(f'{DASHBOARD_URL}/api/status', timeout=2)
            log.info('Dashboard bereikbaar')
            break
        except Exception:
            time.sleep(2)
    else:
        log.warning('Dashboard niet bereikbaar na 60s – toch verdergaan')

    # Start luisteraar
    listen(dashboard)


if __name__ == '__main__':
    main()
