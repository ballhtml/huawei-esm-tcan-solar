"""
EM11000 VIP Cloud Transparent Bridge & High-Speed Local Sensor Component for Home Assistant
- High-Performance Native BSD Sockets with select() - Zero-lag, Zero-buffer transparent streaming
- Independent Upstream Lifecycle: Cloud socket EOF / cycling NEVER drops the local Wi-Fi plug session
- Proven 1:1 bidirectional pipe between Wi-Fi Datalogger (192.168.8.166) and VIP Cloud (vip1.eybond.com:502)
- Auto-recovers gracefully from 04:00 AM router reboot events
- Dedicated Audit Logger to /config/em11000_reboot_audit.log
"""

from __future__ import annotations

import logging
import os
import select
import socket
import struct
import threading
import time
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.const import EVENT_HOMEASSISTANT_STOP

from .const import (
    DOMAIN,
    DEFAULT_PORT,
    DEFAULT_PLUG_IP,
    DEFAULT_UDP_PORT,
    CLOUD_HOST,
    CLOUD_PORT,
)

_LOGGER = logging.getLogger(__name__)

AUDIT_LOG_FILE = "/config/em11000_reboot_audit.log"

def audit_log(msg: str) -> None:
    """Write timestamped audit log to /config/em11000_reboot_audit.log."""
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{ts}] {msg}"
    _LOGGER.info(entry)
    try:
        with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except Exception:
        pass

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the EM11000 Inverter Bridge component."""
    audit_log("[INIT] EM11000 VIP Cloud Resilient Select-Bridge starting up on Home Assistant...")

    bridge = EM11000SelectBridge(hass)
    bridge.start()
    hass.data[DOMAIN] = {"bridge": bridge}

    async def _on_stop(_event):
        audit_log("[STOP] EM11000 Inverter Bridge stopping...")
        bridge.stop()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _on_stop)
    return True

class EM11000SelectBridge:
    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.running = True
        self.thread: threading.Thread | None = None
        self.cloud_ip = "47.239.230.129"
        self.disconnect_time: float | None = time.time()
        self.rearm_count = 0
        self.last_rearm_time = 0.0
        self.last_periodic_audit = time.time()
        self.frames_plug_to_cloud = 0
        self.frames_cloud_to_plug = 0

    def start(self) -> None:
        self.thread = threading.Thread(target=self._run_loop, name="em11000_select_bridge", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.running = False

    def send_rearm_udp(self) -> None:
        """Send UDP steering signal to Wi-Fi plug with rate-limiting backoff."""
        now = time.time()
        if self.rearm_count == 0:
            interval = 1.0
        elif self.rearm_count < 3:
            interval = 4.0
        elif self.rearm_count < 8:
            interval = 10.0
        else:
            interval = 30.0

        if (now - self.last_rearm_time) < interval:
            return

        self.last_rearm_time = now
        self.rearm_count += 1
        try:
            u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            u.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            u.settimeout(1.0)
            msg = b"set>server=192.168.8.209:8899;\r\n"
            u.sendto(msg, (DEFAULT_PLUG_IP, DEFAULT_UDP_PORT))
            u.sendto(msg, ("192.168.8.255", DEFAULT_UDP_PORT))
            u.close()
            audit_log(f"[WATCHDOG] Wi-Fi plug offline. Sent UDP rearm #{self.rearm_count} to {DEFAULT_PLUG_IP}:{DEFAULT_UDP_PORT}")
        except Exception as e:
            _LOGGER.debug("UDP rearm error: %s", e)

    def _run_loop(self) -> None:
        try:
            self.cloud_ip = socket.gethostbyname(CLOUD_HOST)
        except Exception:
            self.cloud_ip = "47.239.230.129"

        audit_log(f"[RESOLVE] VIP Cloud {CLOUD_HOST} resolved to {self.cloud_ip}:{CLOUD_PORT}")

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind(("0.0.0.0", DEFAULT_PORT))
            server.listen(2)
            server.settimeout(1.5)
            audit_log(f"[SERVER] TCP Server listening on 0.0.0.0:{DEFAULT_PORT}. Ready for Wi-Fi Datalogger.")
        except Exception as e:
            audit_log(f"[BIND_ERROR] Server bind failed: {e}")
            return

        while self.running:
            plug_sock = None
            # Wait for Wi-Fi plug connection
            while self.running and not plug_sock:
                self.send_rearm_udp()
                try:
                    plug_sock, plug_addr = server.accept()
                    d_sec = (time.time() - self.disconnect_time) if self.disconnect_time else 0.0
                    audit_log(f"[CONNECT] Wi-Fi Plug connected from {plug_addr} (offline {d_sec:.1f}s, {self.rearm_count} UDP signals). Bridge session ACTIVE.")
                    self.disconnect_time = None
                    self.rearm_count = 0
                    self.last_rearm_time = time.time()
                    self.hass.states.set(
                        "sensor.home_energy_em11000_bridge_status",
                        "Connected",
                        {"friendly_name": "EM11000 Bridge Status", "icon": "mdi:lan-check", "cloud": f"{self.cloud_ip}:{CLOUD_PORT}"}
                    )
                except socket.timeout:
                    continue
                except Exception as e:
                    audit_log(f"[ACCEPT_ERR] {e}")
                    time.sleep(1.0)

            if not self.running:
                break

            plug_sock.setblocking(False)

            # Connect upstream to VIP Cloud
            cloud_sock = None
            try:
                cloud_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                cloud_sock.settimeout(5.0)
                cloud_sock.connect((self.cloud_ip, CLOUD_PORT))
                cloud_sock.setblocking(False)
                audit_log(f"[UPSTREAM] Connected upstream to VIP Cloud {self.cloud_ip}:{CLOUD_PORT} successfully!")
            except Exception as e:
                audit_log(f"[UPSTREAM_ERR] Initial cloud connection failed ({e}). Plug remains active, will connect on-demand.")
                cloud_sock = None

            last_status_log = time.time()
            pkt_plug = 0
            pkt_cloud = 0

            # High-Performance Decoupled select loop (Plug session NEVER terminates from Cloud EOF)
            while self.running:
                try:
                    read_list = [plug_sock]
                    if cloud_sock is not None:
                        read_list.append(cloud_sock)

                    r, _, _ = select.select(read_list, [], [], 0.5)

                    if not r:
                        # Periodic health rollup every 30 minutes
                        now = time.time()
                        if now - self.last_periodic_audit >= 1800.0:
                            self.last_periodic_audit = now
                            p_out = self.hass.states.get("sensor.home_energy_em11000_output_power")
                            v_bat = self.hass.states.get("sensor.home_energy_em11000_battery_voltage")
                            soc = self.hass.states.get("sensor.home_energy_em11000_battery_soc")
                            audit_log(f"[HEARTBEAT] Bridge healthy. Totals: {self.frames_plug_to_cloud} from Plug, {self.frames_cloud_to_plug} from Cloud. State: Output={p_out.state if p_out else '?'}W, Batt={v_bat.state if v_bat else '?'}V, SOC={soc.state if soc else '?'}%")
                        continue

                    # 1. Incoming from Plug -> Relay Upstream to Cloud
                    if plug_sock in r:
                        data = plug_sock.recv(4096)
                        if not data:
                            audit_log("[DISCONNECT] Plug socket closed (EOF). Wi-Fi plug disconnected.")
                            break
                        pkt_plug += 1
                        self.frames_plug_to_cloud += 1

                        # Connect cloud on-demand if closed
                        if cloud_sock is None:
                            try:
                                cloud_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                                cloud_sock.settimeout(4.0)
                                cloud_sock.connect((self.cloud_ip, CLOUD_PORT))
                                cloud_sock.setblocking(False)
                                audit_log(f"[UPSTREAM] Cloud socket reconnected on-demand to {self.cloud_ip}:{CLOUD_PORT}")
                            except Exception as e:
                                audit_log(f"[UPSTREAM_RETRY_ERR] {e}")
                                cloud_sock = None

                        if cloud_sock is not None:
                            try:
                                cloud_sock.sendall(data)
                            except Exception as e:
                                audit_log(f"[UPSTREAM_SEND_ERR] {e}")
                                try: cloud_sock.close()
                                except Exception: pass
                                cloud_sock = None

                    # 2. Incoming from Cloud -> Relay to Plug (Without closing plug on EOF)
                    if cloud_sock is not None and cloud_sock in r:
                        try:
                            data = cloud_sock.recv(4096)
                        except Exception as e:
                            audit_log(f"[UPSTREAM_RECV_ERR] {e}")
                            data = b""

                        if not data:
                            # Cloud closed socket (EOF) - DO NOT KILL PLUG!
                            audit_log("[UPSTREAM] Cloud cycled connection (EOF). Closed upstream socket only, Plug remains 100% ONLINE.")
                            try: cloud_sock.close()
                            except Exception: pass
                            cloud_sock = None
                            continue

                        # Forward cloud data directly to plug
                        try:
                            plug_sock.sendall(data)
                            pkt_cloud += 1
                            self.frames_cloud_to_plug += 1
                        except Exception as e:
                            audit_log(f"[PLUG_SEND_ERR] {e}")
                            break

                    # Log streaming activity every 10s if active
                    now = time.time()
                    if now - last_status_log >= 10.0 and (pkt_plug > 0 or pkt_cloud > 0):
                        last_status_log = now
                        audit_log(f"[STREAMING] Active: {pkt_plug} pkts from Plug -> Cloud, {pkt_cloud} pkts from Cloud -> Plug")

                except Exception as e:
                    audit_log(f"[STREAM_ERR] Exception: {e}")
                    break

            try: plug_sock.close()
            except Exception: pass
            if cloud_sock:
                try: cloud_sock.close()
                except Exception: pass

            self.disconnect_time = time.time()
            self.hass.states.set(
                "sensor.home_energy_em11000_bridge_status",
                "Re-arming",
                {"friendly_name": "EM11000 Bridge Status", "icon": "mdi:lan-disconnect"}
            )
            audit_log("[WAIT] Plug session ended. Re-arming for next connection...")
            time.sleep(0.5)

        try: server.close()
        except Exception: pass
        audit_log("[STOPPED] EM11000 Select Bridge terminated cleanly.")
