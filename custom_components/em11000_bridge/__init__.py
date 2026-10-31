"""
EM11000 High-Speed Local Triage Bridge & VIP Cloud Multiplexer for Home Assistant (v2.0.0)
- High-Performance Native BSD Sockets with select() - Zero-lag, Zero-buffer transparent streaming
- Independent Upstream Lifecycle: Cloud socket EOF / cycling NEVER drops the local Wi-Fi plug session
- Triage Screening Engine (3.0s interval): Injects local Modbus RTU queries directly to the datalogger plug on LAN
  * Independent Dual-MPPT Telemetry:
    - String 1 (PV1): Reg 351 (Voltage, 0.1V), Reg 352 (Current, 0.1A), Reg 353 (Power, W)
    - String 2 (PV2): Reg 389 (Voltage, 0.1V), Reg 390 (Current, 0.1A), Reg 391 (Power, W)
    - Total Solar Power: Sum of actual string power (PV1 + PV2) without speculative estimation
  * AC Load & Grid Telemetry:
    - Reg 338 (Grid Voltage), Reg 346 (AC Output Voltage), Reg 347 (Output Current),
    - Reg 348 (Output Active Power), Reg 350 (Load Percentage)
  * Battery Telemetry:
    - Reg 277 (Voltage), Reg 278 (Current), Reg 279 (Power), Reg 280 (DC Temp), Reg 281 (SOC)
- Zero-Delay Coordinator Hook: Dispatches directly to dess_solar coordinator for instant 0ms dashboard updates
- Upstream Multiplexing: Forwards to/from China VIP Cloud so official SmartESS mobile app remains 100% active
- Dynamic Zero-Configuration: Auto-detects Home Assistant host IP and Datalogger Serial Number (SN)
- Auto-recovers gracefully from periodic router reboot events via targeted UDP steering
- Dedicated Audit Logger to /config/em11000_reboot_audit.log
"""

from __future__ import annotations

import logging
import os
import re
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
    CONF_PLUG_IP,
    CONF_LISTEN_PORT,
    CONF_UDP_PORT,
    CONF_CLOUD_HOST,
    CONF_CLOUD_PORT,
    CONF_HA_IP,
    DEFAULT_LISTEN_PORT,
    DEFAULT_UDP_PORT,
    DEFAULT_CLOUD_HOST,
    DEFAULT_CLOUD_PORT,
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

def get_local_ip() -> str:
    """Auto-detect primary IPv4 address of this Home Assistant host."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

def crc16(data: bytes) -> bytes:
    """Compute standard Modbus RTU CRC16."""
    crc = 0xFFFF
    for pos in data:
        crc ^= pos
        for _ in range(8):
            if (crc & 1) != 0:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return struct.pack('<H', crc)

def build_modbus_read(slave: int, start_reg: int, count: int) -> bytes:
    """Build Modbus Read Holding Registers (FC 03) frame."""
    pdu = struct.pack('>BBHH', slave, 3, start_reg, count)
    return pdu + crc16(pdu)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the EM11000 Inverter Bridge component."""
    conf = config.get(DOMAIN) or {}
    audit_log("[INIT] EM11000 VIP Cloud Resilient Triage-Bridge starting up on Home Assistant...")

    bridge = EM11000SelectBridge(hass, conf)
    bridge.start()
    hass.data[DOMAIN] = {"bridge": bridge}

    async def _on_stop(_event):
        audit_log("[STOP] EM11000 Inverter Bridge stopping...")
        bridge.stop()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _on_stop)
    return True

class EM11000SelectBridge:
    def __init__(self, hass: HomeAssistant, config: dict) -> None:
        self.hass = hass
        self.running = True
        self.thread: threading.Thread | None = None

        # Configuration options (with universal standard defaults)
        self.configured_plug_ip: str | None = config.get(CONF_PLUG_IP)
        self.listen_port: int = int(config.get(CONF_LISTEN_PORT, DEFAULT_LISTEN_PORT))
        self.udp_port: int = int(config.get(CONF_UDP_PORT, DEFAULT_UDP_PORT))
        self.cloud_host: str = config.get(CONF_CLOUD_HOST, DEFAULT_CLOUD_HOST)
        self.cloud_port: int = int(config.get(CONF_CLOUD_PORT, DEFAULT_CLOUD_PORT))
        self.ha_ip: str = config.get(CONF_HA_IP) or get_local_ip()

        # Runtime dynamic state
        self.active_plug_ip: str | None = self.configured_plug_ip
        self.plug_sn: str | None = None
        self.cloud_ip: str = "47.239.230.129"
        self.disconnect_time: float | None = time.time()
        self.rearm_count = 0
        self.last_rearm_time = 0.0
        self.last_periodic_audit = time.time()
        self.frames_plug_to_cloud = 0
        self.frames_cloud_to_plug = 0
        self.local_triage_count = 0

        self.tid = 100
        self.rx_devcode = 258

        # Deadband & rate limit cache {entity_id: (last_val, last_time)}
        self._cache: dict[str, tuple[float, float]] = {}

    def start(self) -> None:
        self.thread = threading.Thread(target=self._run_loop, name="em11000_select_bridge", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.running = False

    def send_rearm_udp(self) -> None:
        """Send UDP steering signal to Wi-Fi plug with rate-limiting backoff."""
        now = time.time()
        if self.rearm_count == 0:
            interval = 2.0
        elif self.rearm_count < 3:
            interval = 5.0
        elif self.rearm_count < 6:
            interval = 15.0
        else:
            interval = 120.0

        if (now - self.last_rearm_time) < interval:
            return

        self.last_rearm_time = now
        self.rearm_count += 1
        try:
            u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            u.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            u.settimeout(1.0)
            msg = f"set>server={self.ha_ip}:{self.listen_port};\r\n".encode("ascii")
            if self.active_plug_ip:
                u.sendto(msg, (self.active_plug_ip, self.udp_port))
            # Broadcast to local subnet
            u.sendto(msg, ("255.255.255.255", self.udp_port))
            u.close()
            target_desc = self.active_plug_ip or "255.255.255.255 (broadcast)"
            audit_log(f"[WATCHDOG] Wi-Fi plug offline. Sent UDP steering #{self.rearm_count} (server={self.ha_ip}:{self.listen_port}) to {target_desc}:{self.udp_port}")
        except Exception as e:
            _LOGGER.debug("UDP rearm error: %s", e)

    def _set_sensor_state(
        self,
        entity_id: str,
        state_val: Any,
        unit: str,
        friendly_name: str,
        device_class: str | None = None,
        state_class: str = "measurement",
        icon: str | None = None,
        min_delta: float = 0.0,
        max_interval: float = 10.0,
    ) -> None:
        """Push sensor state directly into Home Assistant state machine with deadband smoothing."""
        now = time.time()
        if isinstance(state_val, (int, float)):
            cached = self._cache.get(entity_id)
            if cached is not None:
                last_val, last_time = cached
                if abs(float(state_val) - float(last_val)) < min_delta and (now - last_time) < max_interval:
                    return
            self._cache[entity_id] = (float(state_val), now)

        attrs: dict[str, Any] = {
            "friendly_name": friendly_name,
            "unit_of_measurement": unit,
            "state_class": state_class,
        }
        if device_class:
            attrs["device_class"] = device_class
        if icon:
            attrs["icon"] = icon

        # Thread-safe dispatch to Home Assistant event loop
        self.hass.loop.call_soon_threadsafe(
            self.hass.states.async_set, entity_id, str(state_val), attrs
        )

    def _dispatch_to_dess_solar(self, triage: dict[str, Any]) -> None:
        """Thread-safe dispatch to notify dess_solar coordinator of new local triage telemetry."""
        def _dispatch():
            dess_data = self.hass.data.get("dess_solar", {})
            for entry_id, coordinator in dess_data.items():
                if hasattr(coordinator, "async_receive_local_triage"):
                    coordinator.async_receive_local_triage(triage)
        self.hass.loop.call_soon_threadsafe(_dispatch)

    def _update_status(self, status: str, icon: str = "mdi:lan-check") -> None:
        attrs = {
            "friendly_name": "EM11000 Bridge Status",
            "icon": icon,
            "ha_ip": self.ha_ip,
            "listen_port": self.listen_port,
            "cloud": f"{self.cloud_host}:{self.cloud_port} ({self.cloud_ip})",
            "local_triage_count": self.local_triage_count,
        }
        if self.active_plug_ip:
            attrs["plug_ip"] = self.active_plug_ip
        if self.plug_sn:
            attrs["plug_sn"] = self.plug_sn
        self.hass.loop.call_soon_threadsafe(
            self.hass.states.async_set, "sensor.home_energy_em11000_bridge_status", status, attrs
        )

    def _do_local_triage_query(self, plug_sock: socket.socket) -> bool:
        """Send high-speed local Modbus queries (Block D+PV1, PV2, Batt) to extract live telemetry in ~45ms."""
        try:
            # 1. Query Block D & PV1: Reg 338 to 353 (16 registers)
            # 338: Grid V, 346: AC Output V, 347: AC Current, 348: Output Active Power,
            # 350: Load %, 351: PV1 Voltage, 352: PV1 Current, 353: PV1 Power
            self.tid = (self.tid + 1) & 0xFFFF
            cmd_d = build_modbus_read(1, 338, 16)
            hdr_d = struct.pack('>HHHBB', self.tid, self.rx_devcode, 8 + len(cmd_d) - 6, 1, 4)
            plug_sock.sendall(hdr_d + cmd_d)

            # Wait for response with 0.35s timeout
            r_d, _, _ = select.select([plug_sock], [], [], 0.35)
            if not r_d:
                return False
            resp_d = plug_sock.recv(1024)
            if not resp_d or len(resp_d) < 43 or resp_d[9] != 3:
                return False

            mb_d = resp_d[8:]
            v_grid = struct.unpack('>H', mb_d[3:5])[0] / 10.0
            v_ac = struct.unpack('>H', mb_d[19:21])[0] / 10.0
            i_ac = struct.unpack('>H', mb_d[21:23])[0] / 10.0
            p_active = float(struct.unpack('>h', mb_d[23:25])[0])
            p_load = max(0.0, p_active)
            pct_load = float(struct.unpack('>H', mb_d[27:29])[0])
            v_pv1 = struct.unpack('>H', mb_d[29:31])[0] / 10.0
            i_pv1 = struct.unpack('>H', mb_d[31:33])[0] / 10.0
            p_pv1 = float(struct.unpack('>H', mb_d[33:35])[0])

            # 2. Query Block PV2: Reg 389 to 391 (3 registers)
            # 389: PV2 Voltage, 390: PV2 Current, 391: PV2 Power
            self.tid = (self.tid + 1) & 0xFFFF
            cmd_pv2 = build_modbus_read(1, 389, 3)
            hdr_pv2 = struct.pack('>HHHBB', self.tid, self.rx_devcode, 8 + len(cmd_pv2) - 6, 1, 4)
            plug_sock.sendall(hdr_pv2 + cmd_pv2)

            r_pv2, _, _ = select.select([plug_sock], [], [], 0.35)
            if not r_pv2:
                return False
            resp_pv2 = plug_sock.recv(1024)
            if not resp_pv2 or len(resp_pv2) < 17 or resp_pv2[9] != 3:
                return False

            mb_pv2 = resp_pv2[8:]
            v_pv2 = struct.unpack('>H', mb_pv2[3:5])[0] / 10.0
            i_pv2 = struct.unpack('>H', mb_pv2[5:7])[0] / 10.0
            p_pv2 = float(struct.unpack('>H', mb_pv2[7:9])[0])

            # 3. Query Block B: Reg 277 to 281 (5 registers)
            # 277: Batt V, 278: Batt I, 279: Batt Power, 280: DC Temp, 281: Batt SOC
            self.tid = (self.tid + 1) & 0xFFFF
            cmd_b = build_modbus_read(1, 277, 5)
            hdr_b = struct.pack('>HHHBB', self.tid, self.rx_devcode, 8 + len(cmd_b) - 6, 1, 4)
            plug_sock.sendall(hdr_b + cmd_b)

            r_b, _, _ = select.select([plug_sock], [], [], 0.35)
            if not r_b:
                return False
            resp_b = plug_sock.recv(1024)
            if not resp_b or len(resp_b) < 21 or resp_b[9] != 3:
                return False

            mb_b = resp_b[8:]
            v_batt = struct.unpack('>H', mb_b[3:5])[0] / 10.0
            i_batt = struct.unpack('>h', mb_b[5:7])[0] / 10.0
            p_batt = float(struct.unpack('>h', mb_b[7:9])[0])
            t_dc = float(struct.unpack('>H', mb_b[9:11])[0])
            soc_batt = struct.unpack('>H', mb_b[11:13])[0]

            # Genuine Total Solar Power directly from separate string sum!
            p_solar = p_pv1 + p_pv2

            # Dispatch high-speed local triage directly to dess_solar coordinator!
            triage_data = {
                "output_power": int(p_active),
                "load_power": int(p_load),
                "solar_total_power": int(p_solar),
                "pv1_power": int(p_pv1),
                "pv2_power": int(p_pv2),
                "pv1_voltage": round(v_pv1, 1),
                "pv2_voltage": round(v_pv2, 1),
                "pv1_current": round(i_pv1, 1),
                "pv2_current": round(i_pv2, 1),
                "grid_voltage": round(v_grid, 1),
                "output_voltage": round(v_ac, 1),
                "load_percentage": round(pct_load, 1),
                "battery_voltage": round(v_batt, 1),
                "battery_current": round(i_batt, 1),
                "battery_power": round(p_batt, 1),
                "battery_soc": round(soc_batt, 1),
                "inverter_temperature": round(t_dc, 1),
            }
            self._dispatch_to_dess_solar(triage_data)

            # Also push directly to HA states as fallback
            self._set_sensor_state("sensor.home_energy_em11000_output_power", int(p_active), "W", "Home Energy EM11000 Output Active Power", "power", icon="mdi:flash", min_delta=3.0, max_interval=3.0)
            self._set_sensor_state("sensor.home_energy_em11000_pv1_power", int(p_pv1), "W", "Home Energy EM11000 PV1 Power", "power", icon="mdi:solar-power-variant", min_delta=5.0, max_interval=3.0)
            self._set_sensor_state("sensor.home_energy_em11000_pv2_power", int(p_pv2), "W", "Home Energy EM11000 PV2 Power", "power", icon="mdi:solar-power-variant", min_delta=5.0, max_interval=3.0)
            self._set_sensor_state("sensor.home_energy_em11000_solar_total_power", int(p_solar), "W", "Home Energy EM11000 Solar Total Power", "power", icon="mdi:solar-power", min_delta=5.0, max_interval=3.0)
            self._set_sensor_state("sensor.home_energy_em11000_load_power", int(p_load), "W", "Home Energy EM11000 Load Power", "power", icon="mdi:home-lightning-bolt", min_delta=3.0, max_interval=3.0)
            self._set_sensor_state("sensor.home_energy_em11000_grid_voltage", round(v_grid, 1), "V", "Home Energy EM11000 Grid Voltage", "voltage", icon="mdi:transmission-tower", min_delta=0.3, max_interval=5.0)
            self._set_sensor_state("sensor.home_energy_em11000_ac_output_voltage", round(v_ac, 1), "V", "Home Energy EM11000 Output Voltage", "voltage", min_delta=0.3, max_interval=5.0)
            self._set_sensor_state("sensor.home_energy_em11000_pv1_voltage", round(v_pv1, 1), "V", "Home Energy EM11000 PV1 Voltage", "voltage", min_delta=0.5, max_interval=5.0)
            self._set_sensor_state("sensor.home_energy_em11000_pv2_voltage", round(v_pv2, 1), "V", "Home Energy EM11000 PV2 Voltage", "voltage", min_delta=0.5, max_interval=5.0)
            self._set_sensor_state("sensor.home_energy_em11000_data_source", "Local", "", "EM11000 Telemetry Source", icon="mdi:lightning-bolt-circle")

            self.local_triage_count += 1
            if self.local_triage_count % 20 == 1:
                audit_log(f"[TRIAGE #{self.local_triage_count}] Real-Time: Load={p_load:.0f}W (Out={p_active:.0f}W) | Solar={p_solar:.0f}W (PV1={p_pv1:.0f}W, PV2={p_pv2:.0f}W) | Batt={v_batt:.1f}V {i_batt:+.1f}A ({p_batt:+.0f}W, {soc_batt}%) | Grid={v_grid:.1f}V")
            return True

        except Exception as e:
            audit_log(f"[TRIAGE_ERR] Query failed: {e}")
            return False

    def _run_loop(self) -> None:
        try:
            self.cloud_ip = socket.gethostbyname(self.cloud_host)
        except Exception:
            self.cloud_ip = "47.239.230.129"

        audit_log(f"[RESOLVE] VIP Cloud {self.cloud_host} resolved to {self.cloud_ip}:{self.cloud_port} (HA Host IP: {self.ha_ip})")

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind(("0.0.0.0", self.listen_port))
            server.listen(2)
            server.settimeout(1.5)
            audit_log(f"[SERVER] TCP Server listening on 0.0.0.0:{self.listen_port}. Triage Nurse Mode Ready.")
        except Exception as e:
            audit_log(f"[BIND_ERROR] Server bind failed on port {self.listen_port}: {e}")
            return

        while self.running:
            plug_sock = None
            # Wait for Wi-Fi plug connection
            while self.running and not plug_sock:
                self.send_rearm_udp()
                try:
                    sock, plug_addr = server.accept()
                    if self.configured_plug_ip and plug_addr[0] != self.configured_plug_ip:
                        audit_log(f"[STRAY_CONN] Rejected connection from unauthorized IP {plug_addr}")
                        try: sock.close()
                        except Exception: pass
                        continue

                    plug_sock = sock
                    self.active_plug_ip = plug_addr[0]
                    d_sec = (time.time() - self.disconnect_time) if self.disconnect_time else 0.0
                    audit_log(f"[CONNECT] Wi-Fi Plug connected from {plug_addr} (offline {d_sec:.1f}s). Starting Triage Screening.")
                    self.disconnect_time = None
                    self.rearm_count = 0
                    self.last_rearm_time = time.time()
                    self._update_status("Connected", "mdi:lan-check")

                    # EyBond Heartbeat sync handshake
                    try:
                        sock.settimeout(1.5)
                        now_dt = time.gmtime()
                        hb_payload = bytes([
                            (now_dt.tm_year - 2000) & 0xFF, now_dt.tm_mon, now_dt.tm_mday,
                            now_dt.tm_hour, now_dt.tm_min, now_dt.tm_sec
                        ]) + struct.pack('>H', 2)
                        hb_hdr = struct.pack('>HHHBB', 1, 0, 8 + len(hb_payload) - 6, 1, 1)
                        sock.sendall(hb_hdr + hb_payload)
                        hb_resp = sock.recv(512)
                        if hb_resp and len(hb_resp) >= 8:
                            _, rx_dev, _, _, _ = struct.unpack('>HHHBB', hb_resp[:8])
                            if rx_dev > 0:
                                self.rx_devcode = rx_dev
                                audit_log(f"[HANDSHAKE] Heartbeat ACK received. DevCode={self.rx_devcode}")
                    except Exception as ex:
                        audit_log(f"[HANDSHAKE_WARN] Handshake exception: {ex}")

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
                cloud_sock.settimeout(4.0)
                cloud_sock.connect((self.cloud_ip, self.cloud_port))
                cloud_sock.setblocking(False)
                audit_log(f"[UPSTREAM] Connected upstream to VIP Cloud {self.cloud_ip}:{self.cloud_port} successfully!")
            except Exception as e:
                audit_log(f"[UPSTREAM_ERR] Initial cloud connection failed ({e}). Plug remains active on LAN.")
                cloud_sock = None

            last_status_log = time.time()
            last_triage_poll = 0.0
            pkt_plug = 0
            pkt_cloud = 0

            # High-Performance Triage Loop: Local 3.0s Polling + Cloud Multiplexing
            while self.running:
                try:
                    now = time.time()

                    # 1. Triage Screening: Poll local metrics every 3.0 seconds!
                    if now - last_triage_poll >= 3.0:
                        last_triage_poll = now
                        plug_sock.settimeout(0.5)
                        triage_ok = self._do_local_triage_query(plug_sock)
                        plug_sock.setblocking(False)
                        if not triage_ok:
                            # If socket broken during triage, reconnect
                            pass

                    # 2. Multiplexing select: Check for Cloud requests & unsolicited Plug frames
                    read_list = [plug_sock]
                    if cloud_sock is not None:
                        read_list.append(cloud_sock)

                    r, _, _ = select.select(read_list, [], [], 0.2)

                    if not r:
                        # Periodic health rollup every 30 minutes
                        if now - self.last_periodic_audit >= 1800.0:
                            self.last_periodic_audit = now
                            p_out = self.hass.states.get("sensor.home_energy_em11000_output_power")
                            v_bat = self.hass.states.get("sensor.home_energy_em11000_battery_voltage")
                            audit_log(f"[HEARTBEAT] Bridge healthy. Triage count: {self.local_triage_count}. State: Output={p_out.state if p_out else '?'}W, Batt={v_bat.state if v_bat else '?'}V")
                        continue

                    # Incoming from Plug -> Relay Upstream to Cloud
                    if plug_sock in r:
                        data = plug_sock.recv(4096)
                        if not data:
                            audit_log("[DISCONNECT] Plug socket closed (EOF). Wi-Fi plug disconnected.")
                            break
                        pkt_plug += 1
                        self.frames_plug_to_cloud += 1

                        if not self.plug_sn:
                            m_sn = re.search(rb"[0-9A-Z]{14}", data)
                            if m_sn:
                                self.plug_sn = m_sn.group(0).decode("ascii")
                                audit_log(f"[DISCOVERY] Auto-detected Datalogger Plug Serial Number: {self.plug_sn}")
                                self._update_status("Connected", "mdi:lan-check")

                        # Forward to Cloud if connected
                        if cloud_sock is not None:
                            try:
                                cloud_sock.sendall(data)
                            except Exception:
                                try: cloud_sock.close()
                                except Exception: pass
                                cloud_sock = None

                    # Incoming from Cloud -> Relay to Plug (Without closing plug on EOF)
                    if cloud_sock is not None and cloud_sock in r:
                        try:
                            data = cloud_sock.recv(4096)
                        except Exception:
                            data = b""

                        if not data:
                            audit_log("[UPSTREAM] Cloud cycled connection (EOF). Closed upstream socket only, Plug remains 100% ONLINE.")
                            try: cloud_sock.close()
                            except Exception: pass
                            cloud_sock = None
                            continue

                        try:
                            plug_sock.sendall(data)
                            pkt_cloud += 1
                            self.frames_cloud_to_plug += 1
                        except Exception as e:
                            audit_log(f"[PLUG_SEND_ERR] {e}")
                            break

                    # Log streaming activity every 30s
                    if now - last_status_log >= 30.0 and (pkt_plug > 0 or pkt_cloud > 0):
                        last_status_log = now
                        audit_log(f"[STREAMING] Active: {pkt_plug} pkts from Plug -> Cloud, {pkt_cloud} pkts from Cloud -> Plug (Triage: {self.local_triage_count})")

                except Exception as e:
                    audit_log(f"[STREAM_ERR] Loop exception: {e}")
                    break

            try: plug_sock.close()
            except Exception: pass
            if cloud_sock:
                try: cloud_sock.close()
                except Exception: pass

            self.disconnect_time = time.time()
            self._update_status("Re-arming", "mdi:lan-disconnect")
            audit_log("[WAIT] Plug session ended. Re-arming for next connection...")
            time.sleep(0.5)

        try: server.close()
        except Exception: pass
        audit_log("[STOPPED] EM11000 Triage Bridge terminated cleanly.")
