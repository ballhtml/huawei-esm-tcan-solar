"""
EM11000 Autonomous Dual-Route Proxy & Poller
- Local High-Speed Polling (2.5s) -> Home Assistant REST API
- Cloud Upstream Forwarding (5.0s) -> China Cloud (dtu_ess.eybond.com:18899)
- Target: Inverter EM11000 via Wi-Fi Datalogger Plug (92B32409100334)
- Resilient Auto-Token Refresh & China Cloud EOF / CLOSE_WAIT recovery
"""

import socket
import select
import struct
import time
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone
import sys
import os

# Redirect stdout/stderr to log file if running headless (e.g. pythonw / Task Scheduler)
LOG_FILE = r'z:\modbus\em11000_proxy.log'
if sys.stdout is None:
    try:
        sys.stdout = open(LOG_FILE, 'a', buffering=1, encoding='utf-8')
        sys.stderr = sys.stdout
    except Exception:
        pass
else:
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass

# Configuration
LOCAL_IP = '192.168.8.160'       # Host IP running this proxy
PLUG_IP = '192.168.8.166'        # Datalogger plug IP
HA_HOST = '192.168.8.209'        # Home Assistant IP
HA_PORT = 8123
LOCAL_PORT = 8899                # EyBond local server port
CLOUD_HOST = 'vip1.eybond.com'     # True VIP Cloud for Wi-Fi Datalogger
CLOUD_PORT = 502                   # True EyBond native binary listener (NOT 18899 AT-terminal)
PLUG_SN = '92B32409100334'

POLL_INTERVAL_LOCAL = 3.5        # 3.5s smooth local polling (calm, steady display)
FORWARD_INTERVAL_CLOUD = 5.0     # 5.0s mirror copy for SmartESS app
CLOUD_RETRY_INTERVAL = 60.0      # 60s cooldown before reconnecting to China Cloud

# Deadband Filter Cache to prevent UI fluttering / jitter
# {entity_id: (last_val, last_update_time)}
_HA_CACHE = {}

# In-memory HA Auth state
_HA_REFRESH_TOKEN_INFO = None
_CURRENT_HA_TOKEN = None
_TOKEN_EXPIRES_AT = 0.0

def load_refresh_token_info():
    """Load the first working refresh token info from HA storage."""
    global _HA_REFRESH_TOKEN_INFO
    try:
        auth_data = json.load(open(r'\\192.168.8.209\config\.storage\auth', encoding='utf-8'))
        for t in auth_data['data']['refresh_tokens']:
            cid = t.get('client_id')
            token_val = t.get('token')
            if not cid or not token_val:
                continue
            # Test refresh
            try:
                pdata = urllib.parse.urlencode({
                    'client_id': cid,
                    'grant_type': 'refresh_token',
                    'refresh_token': token_val
                }).encode('utf-8')
                req = urllib.request.Request(
                    f'http://{HA_HOST}:{HA_PORT}/auth/token',
                    data=pdata,
                    headers={'Content-Type': 'application/x-www-form-urlencoded'}
                )
                res = json.loads(urllib.request.urlopen(req, timeout=4).read().decode('utf-8'))
                if 'access_token' in res:
                    _HA_REFRESH_TOKEN_INFO = {'client_id': cid, 'token': token_val}
                    return _HA_REFRESH_TOKEN_INFO
            except Exception:
                continue
    except Exception as e:
        print(f"[!] Error loading HA refresh tokens from storage: {e}")
    return None

def get_ha_access_token(force_refresh=False):
    """Proactively refresh access token before it expires."""
    global _CURRENT_HA_TOKEN, _TOKEN_EXPIRES_AT, _HA_REFRESH_TOKEN_INFO
    now = time.time()
    if _CURRENT_HA_TOKEN and not force_refresh and now < _TOKEN_EXPIRES_AT:
        return _CURRENT_HA_TOKEN

    if not _HA_REFRESH_TOKEN_INFO:
        load_refresh_token_info()

    if not _HA_REFRESH_TOKEN_INFO:
        print("[!] No valid HA refresh token available!")
        return None

    try:
        pdata = urllib.parse.urlencode({
            'client_id': _HA_REFRESH_TOKEN_INFO['client_id'],
            'grant_type': 'refresh_token',
            'refresh_token': _HA_REFRESH_TOKEN_INFO['token']
        }).encode('utf-8')
        req = urllib.request.Request(
            f'http://{HA_HOST}:{HA_PORT}/auth/token',
            data=pdata,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        res = json.loads(urllib.request.urlopen(req, timeout=4).read().decode('utf-8'))
        _CURRENT_HA_TOKEN = res['access_token']
        # Refresh 5 minutes before actual expiry (default 1800s -> 1500s)
        expires_in = res.get('expires_in', 1800)
        _TOKEN_EXPIRES_AT = now + max(300, expires_in - 300)
        return _CURRENT_HA_TOKEN
    except Exception as e:
        print(f"[!] Token refresh request failed: {e}")
        # Try reloading credentials from disk in case token was revoked
        _HA_REFRESH_TOKEN_INFO = None
        load_refresh_token_info()
    return _CURRENT_HA_TOKEN

def crc16(data: bytes) -> bytes:
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
    pdu = struct.pack('>BBHH', slave, 3, start_reg, count)
    return pdu + crc16(pdu)

def update_ha_sensor(entity_id: str, state_val, unit: str, friendly_name: str, device_class: str = None, state_class: str = "measurement", min_delta: float = 0.0, max_interval: float = 12.0):
    global _HA_CACHE
    
    # Deadband & rate limit check
    now = time.time()
    cached = _HA_CACHE.get(entity_id)
    if cached is not None and isinstance(state_val, (int, float)):
        last_val, last_time = cached
        delta = abs(float(state_val) - float(last_val))
        if delta < min_delta and (now - last_time) < max_interval:
            return True  # Suppress micro-jitter, keep card steady
            
    token = get_ha_access_token()
    if not token:
        return False

    url = f"http://{HA_HOST}:{HA_PORT}/api/states/{entity_id}"
    attrs = {
        "friendly_name": friendly_name,
        "unit_of_measurement": unit
    }
    if device_class:
        attrs["device_class"] = device_class
    if state_class:
        attrs["state_class"] = state_class
    payload = json.dumps({
        "state": str(state_val),
        "attributes": attrs
    }).encode('utf-8')

    for attempt in range(2):
        act_token = get_ha_access_token(force_refresh=(attempt > 0))
        if not act_token:
            return False
        req = urllib.request.Request(url, data=payload, headers={
            "Authorization": f"Bearer {act_token}",
            "Content-Type": "application/json"
        }, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=1.5):
                pass
            if isinstance(state_val, (int, float)):
                _HA_CACHE[entity_id] = (state_val, now)
            return True
        except urllib.error.HTTPError as e:
            if e.code == 401 and attempt == 0:
                continue
            return False
        except Exception:
            return False
    return False

def rearm_plug_udp():
    """Broadcast UDP to convince plug to point to LOCAL_PORT."""
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    msg = f"set>server={LOCAL_IP}:{LOCAL_PORT};\r\n".encode('ascii')
    try:
        udp.sendto(msg, (PLUG_IP, 58899))
        udp.sendto(msg, ('192.168.8.255', 58899))
    except Exception:
        pass
    finally:
        udp.close()

def main():
    print("==================================================")
    print("EM11000 DUAL PROXY: 2.5s Local HA + 5s China Cloud")
    print("==================================================")
    
    token = get_ha_access_token()
    if not token:
        print("[!] ERROR: Cannot obtain Home Assistant access token. Check network/SMB.")
        return

    print("[+] HA Access Token obtained successfully.")

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', LOCAL_PORT))
    server.listen(2)
    server.settimeout(3.0)

    print(f"[*] TCP Server listening on 0.0.0.0:{LOCAL_PORT}")
    print(f"[*] Arming plug via UDP port 58899...")
    rearm_plug_udp()

    client_sock = None
    cloud_sock = None
    tid = 100
    rx_devcode = 258
    last_cloud_forward = 0.0
    last_cloud_attempt = 0.0
    last_rearm_time = 0.0

    while True:
        # Wait for plug connection
        if not client_sock:
            now_sec = time.time()
            if now_sec - last_rearm_time >= 3.0:
                rearm_plug_udp()
                last_rearm_time = now_sec
            try:
                client_sock, client_addr = server.accept()
                client_sock.settimeout(2.5)
                print(f"[+] Plug connected from {client_addr}!")
                
                # Send EyBond Sync/Heartbeat (FC=1)
                now = datetime.now(timezone.utc)
                hb_payload = bytes([
                    (now.year - 2000) & 0xFF, now.month, now.day,
                    now.hour, now.minute, now.second
                ]) + struct.pack('>H', 2) # 2-second heartbeat
                hb_hdr = struct.pack('>HHHBB', 1, 0, 8 + len(hb_payload) - 6, 1, 1)
                client_sock.sendall(hb_hdr + hb_payload)
                hb_resp = client_sock.recv(1024)
                if len(hb_resp) >= 8:
                    rx_tid, rx_devcode, _, _, _ = struct.unpack('>HHHBB', hb_resp[:8])
                print(f"[+] Heartbeat ACK received. DevCode={rx_devcode}")
            except socket.timeout:
                continue
            except Exception as e:
                print(f"[-] Connection setup failed: {e}")
                if client_sock:
                    try: client_sock.close()
                    except: pass
                client_sock = None
                time.sleep(1.0)
                continue

        # Connect to China Cloud for mirror forwarding (with cooldown)
        now_time = time.time()
        if not cloud_sock and (now_time - last_cloud_attempt >= CLOUD_RETRY_INTERVAL):
            last_cloud_attempt = now_time
            try:
                cloud_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                cloud_sock.settimeout(4.0)
                cloud_sock.connect((CLOUD_HOST, CLOUD_PORT))
                print(f"[+] Connected to VIP Cloud {CLOUD_HOST}:{CLOUD_PORT}")
                cloud_sock.setblocking(False)
            except Exception as e:
                print(f"[!] Warning: China Cloud mirror inactive ({e}). Local 3.5s continues unaffected.")
                if cloud_sock:
                    try: cloud_sock.close()
                    except: pass
                cloud_sock = None

        # Main Polling Loop
        try:
            t_start = time.time()
            tid = (tid + 1) & 0xFFFF

            # Query Block A: Reg 198 to 204 (SOC setting & Frequency)
            cmd1 = build_modbus_read(1, 198, 7)
            hdr1 = struct.pack('>HHHBB', tid, rx_devcode, 8 + len(cmd1) - 6, 1, 4)
            client_sock.sendall(hdr1 + cmd1)
            resp1 = client_sock.recv(1024)

            # Query Block B: Reg 277 to 286 (Battery V, I, P, Temp, SOC)
            tid = (tid + 1) & 0xFFFF
            cmd2 = build_modbus_read(1, 277, 10)
            hdr2 = struct.pack('>HHHBB', tid, rx_devcode, 8 + len(cmd2) - 6, 1, 4)
            client_sock.sendall(hdr2 + cmd2)
            resp2 = client_sock.recv(1024)

            # Query Block C: Reg 302 to 306 (PV1 Volt, PV2 Volt, Inverter Temp)
            tid = (tid + 1) & 0xFFFF
            cmd3 = build_modbus_read(1, 302, 5)
            hdr3 = struct.pack('>HHHBB', tid, rx_devcode, 8 + len(cmd3) - 6, 1, 4)
            client_sock.sendall(hdr3 + cmd3)
            resp3 = client_sock.recv(1024)

            # Query Block D: Reg 338 to 350 (AC Output V, Grid V, Load W, Active W, Apparent VA, Load %)
            tid = (tid + 1) & 0xFFFF
            cmd4 = build_modbus_read(1, 338, 13)
            hdr4 = struct.pack('>HHHBB', tid, rx_devcode, 8 + len(cmd4) - 6, 1, 4)
            client_sock.sendall(hdr4 + cmd4)
            resp4 = client_sock.recv(1024)

            rtt_ms = (time.time() - t_start) * 1000

            # Parse Block A (Grid Frequency)
            hz_grid = None
            if len(resp1) >= 23 and len(resp1) > 9 and resp1[9] == 3:
                mb1 = resp1[8:]
                if len(mb1) >= 15:
                    hz_grid = struct.unpack('>H', mb1[13:15])[0] / 100.0

            # Parse Block B (Battery V, I, Power, Temp, SOC)
            v_batt, i_batt, p_batt, t_pv, soc_batt = None, None, None, None, None
            if len(resp2) >= 21 and len(resp2) > 9 and resp2[9] == 3:
                mb2 = resp2[8:]
                if len(mb2) >= 13:
                    v_batt = struct.unpack('>H', mb2[3:5])[0] / 10.0
                    i_raw = struct.unpack('>h', mb2[5:7])[0]
                    i_batt = i_raw / 10.0
                    p_raw = struct.unpack('>h', mb2[7:9])[0]
                    p_batt = float(p_raw)
                    t_pv = struct.unpack('>H', mb2[9:11])[0]
                    soc_batt = struct.unpack('>H', mb2[11:13])[0]

            # Parse Block C (PV1, PV2 Voltage, Inverter Temp)
            v_pv1, v_pv2, t_inv = None, None, None
            if len(resp3) >= 19 and len(resp3) > 9 and resp3[9] == 3:
                mb3 = resp3[8:]
                if len(mb3) >= 11:
                    v_pv1 = struct.unpack('>H', mb3[3:5])[0] / 10.0
                    v_pv2 = struct.unpack('>H', mb3[5:7])[0] / 10.0
                    t_inv = struct.unpack('>H', mb3[9:11])[0]

            # Parse Block D (AC Output Volt, Grid Volt, Load W, Active W, Load %)
            v_ac, v_grid, p_load, p_active, pct_load = None, None, None, None, None
            if len(resp4) >= 37 and len(resp4) > 9 and resp4[9] == 3:
                mb4 = resp4[8:]
                if len(mb4) >= 29:
                    v_ac = struct.unpack('>H', mb4[3:5])[0] / 10.0
                    v_grid = struct.unpack('>H', mb4[11:13])[0] / 10.0
                    p_load = float(struct.unpack('>H', mb4[15:17])[0])
                    p_active = float(struct.unpack('>H', mb4[23:25])[0])
                    pct_load = float(struct.unpack('>H', mb4[27:29])[0])

            # Calculate Solar Total Power (Physical Conservation Law + PV Voltage Check)
            pv_active = (v_pv1 is not None and v_pv1 > 25.0) or (v_pv2 is not None and v_pv2 > 25.0)
            if pv_active and p_load is not None and p_batt is not None:
                # Energy Balance: Solar = Load Power + Battery Charging Power (p_batt > 0 means charge)
                # If battery discharging (p_batt < 0), Solar supplies (Load - Discharge)
                p_solar = max(0.0, p_load + p_batt)
                # If solar irradiance is negligible (morning shade), clamp small residual values
                if p_solar < 20.0 and (v_pv1 or 0) < 60.0:
                    p_solar = 0.0
            else:
                p_solar = 0.0

            # Split string power if dual string
            p_pv1 = p_solar * 0.5 if p_solar > 0 else 0.0
            p_pv2 = p_solar * 0.5 if p_solar > 0 else 0.0

            # Push to Home Assistant (Local with deadband smoothing)
            if hz_grid is not None:
                update_ha_sensor("sensor.home_energy_em11000_grid_frequency", hz_grid, "Hz", "EM11000 Grid Frequency", "frequency", min_delta=0.03, max_interval=15.0)
            if v_batt is not None:
                update_ha_sensor("sensor.home_energy_em11000_battery_voltage", v_batt, "V", "EM11000 Battery Voltage", "voltage", min_delta=0.2, max_interval=10.0)
            if i_batt is not None:
                update_ha_sensor("sensor.home_energy_em11000_battery_current", i_batt, "A", "EM11000 Battery Current", "current", min_delta=0.3, max_interval=10.0)
            if p_batt is not None:
                update_ha_sensor("sensor.home_energy_em11000_battery_power", p_batt, "W", "EM11000 Battery Power", "power", min_delta=15.0, max_interval=8.0)
            if soc_batt is not None and 0 <= soc_batt <= 100:
                update_ha_sensor("sensor.home_energy_em11000_battery_soc", soc_batt, "%", "EM11000 Battery SOC", "battery", min_delta=0.5, max_interval=20.0)
            if v_ac is not None:
                update_ha_sensor("sensor.home_energy_em11000_ac_output_voltage", v_ac, "V", "EM11000 AC Output Voltage", "voltage", min_delta=0.5, max_interval=10.0)
            if v_grid is not None:
                update_ha_sensor("sensor.home_energy_em11000_grid_voltage", v_grid, "V", "EM11000 Grid Voltage", "voltage", min_delta=0.5, max_interval=10.0)
            if p_load is not None:
                update_ha_sensor("sensor.home_energy_em11000_load_power", int(p_load), "W", "EM11000 Load Power", "power", min_delta=15.0, max_interval=8.0)
            if p_active is not None:
                update_ha_sensor("sensor.home_energy_em11000_output_power", int(p_active), "W", "EM11000 Output Power", "power", min_delta=15.0, max_interval=8.0)
            if pct_load is not None:
                update_ha_sensor("sensor.home_energy_em11000_load_percentage", int(pct_load), "%", "EM11000 Load Percentage", min_delta=1.0, max_interval=15.0)

            # Solar PV Sensors
            update_ha_sensor("sensor.home_energy_em11000_solar_total_power", int(p_solar), "W", "EM11000 Solar Total Power", "power", min_delta=15.0, max_interval=6.0)
            if v_pv1 is not None:
                update_ha_sensor("sensor.home_energy_em11000_pv1_voltage", v_pv1, "V", "EM11000 PV1 Voltage", "voltage", min_delta=0.5, max_interval=10.0)
                update_ha_sensor("sensor.home_energy_em11000_pv1_power", int(p_pv1), "W", "EM11000 PV1 Power", "power", min_delta=10.0, max_interval=6.0)
            if v_pv2 is not None:
                update_ha_sensor("sensor.home_energy_em11000_pv2_voltage", v_pv2, "V", "EM11000 PV2 Voltage", "voltage", min_delta=0.5, max_interval=10.0)
                update_ha_sensor("sensor.home_energy_em11000_pv2_power", int(p_pv2), "W", "EM11000 PV2 Power", "power", min_delta=10.0, max_interval=6.0)
            if t_pv is not None and 0 < t_pv < 120:
                update_ha_sensor("sensor.home_energy_em11000_pv_temperature", t_pv, "°C", "EM11000 PV Temperature", "temperature", min_delta=1.0, max_interval=30.0)
            if t_inv is not None and 0 < t_inv < 120:
                update_ha_sensor("sensor.home_energy_em11000_inverter_temperature", t_inv, "°C", "EM11000 Inverter Temperature", "temperature", min_delta=1.0, max_interval=30.0)

            # Check 5s Cloud forward with EOF / CLOSE_WAIT prevention
            now_sec = time.time()
            if cloud_sock and (now_sec - last_cloud_forward >= FORWARD_INTERVAL_CLOUD):
                try:
                    r, _, _ = select.select([cloud_sock], [], [], 0.05)
                    if r:
                        cloud_req = cloud_sock.recv(1024)
                        if not cloud_req:
                            print("[!] China Cloud disconnected (EOF). Resetting cloud socket.")
                            try:
                                cloud_sock.close()
                            except Exception:
                                pass
                            cloud_sock = None
                        else:
                            client_sock.sendall(cloud_req)
                            cloud_resp = client_sock.recv(1024)
                            cloud_sock.sendall(cloud_resp)
                    last_cloud_forward = now_sec
                except Exception as e:
                    print(f"[-] Cloud forward error: {e}")
                    try:
                        cloud_sock.close()
                    except Exception:
                        pass
                    cloud_sock = None

            print(f"[{time.strftime('%H:%M:%S')}] [LIVE {POLL_INTERVAL_LOCAL}s] Solar: {p_solar:.0f}W (PV1: {v_pv1}V) | Batt: {v_batt}V, {i_batt}A ({p_batt:.0f}W, {soc_batt}%) | Load: {p_load:.0f}W | AC: {v_ac}V | Grid: {hz_grid}Hz | RTT: {rtt_ms:.0f}ms")

            # Maintain exactly 2.5s pace
            elapsed = time.time() - t_start
            sleep_time = max(0.05, POLL_INTERVAL_LOCAL - elapsed)
            time.sleep(sleep_time)

        except (socket.timeout, ConnectionResetError, BrokenPipeError) as e:
            print(f"[!] Socket dropped ({e}). Re-arming listener...")
            if client_sock:
                try:
                    client_sock.close()
                except Exception:
                    pass
                client_sock = None
            if cloud_sock:
                try:
                    cloud_sock.close()
                except Exception:
                    pass
                cloud_sock = None
            time.sleep(1.0)
        except Exception as e:
            print(f"[!] Polling loop exception: {e}")
            time.sleep(1.0)

def run_forever():
    while True:
        try:
            main()
        except KeyboardInterrupt:
            print("[*] Proxy stopped by user.")
            break
        except BaseException as e:
            print(f"[!] Critical proxy crash ({type(e).__name__}): {e}. Auto-restarting in 3s...", file=sys.stderr)
            import traceback
            traceback.print_exc()
            time.sleep(3.0)

if __name__ == '__main__':
    run_forever()
