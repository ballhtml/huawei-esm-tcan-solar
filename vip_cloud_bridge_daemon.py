"""
EM11000 VIP Cloud Persistent Transparent Bridge Daemon
Pipes Wi-Fi Datalogger Plug directly to DessMonitor VIP Cloud (vip1.eybond.com:18899).
Maintains continuous keepalive so SmartESS app stays GREEN and updates every 5 seconds!
"""

import socket, select, time, struct, binascii, sys, os

LOCAL_PORT = 8899
CLOUD_HOST = 'vip1.eybond.com'
CLOUD_PORT = 18899
PLUG_IP = os.environ.get('PLUG_IP', '')
PLUG_UDP_PORT = 58899

LOG_FILE = r'z:\modbus\scratch\vip_bridge.log'

def log(msg):
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass

def get_local_ip():
    """Detect local LAN IP for dynamic UDP rearm configuration."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

LOCAL_IP = get_local_ip()

def send_udp_arm():
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    msg = f"set>server={LOCAL_IP}:{LOCAL_PORT};\r\n".encode('ascii')
    try:
        udp.sendto(msg, (PLUG_IP, PLUG_UDP_PORT))
        udp.sendto(msg, ('192.168.8.255', PLUG_UDP_PORT))
    except Exception:
        pass
    finally:
        udp.close()

def run_bridge():
    try:
        cloud_ip = socket.gethostbyname(CLOUD_HOST)
    except Exception:
        cloud_ip = '47.239.230.129'
        
    log(f"Starting VIP Cloud Bridge on 0.0.0.0:{LOCAL_PORT} -> {cloud_ip}:{CLOUD_PORT}")
    
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', LOCAL_PORT))
    server.listen(2)
    server.settimeout(2.0)
    
    last_arm_time = 0.0
    
    while True:
        log("Waiting for plug connection on port 8899...")
        plug_sock = None
        while not plug_sock:
            # Arm plug via UDP only while disconnected
            now = time.time()
            if now - last_arm_time >= 3.0:
                send_udp_arm()
                last_arm_time = now
                
            try:
                plug_sock, plug_addr = server.accept()
                log(f"Plug connected from {plug_addr}")
            except socket.timeout:
                continue
            except Exception as e:
                log(f"Server accept error: {e}")
                time.sleep(1.0)
                
        # Connect to VIP Cloud
        cloud_sock = None
        try:
            cloud_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            cloud_sock.settimeout(6.0)
            cloud_sock.connect((cloud_ip, CLOUD_PORT))
            log(f"Connected upstream to VIP Cloud {cloud_ip}:{CLOUD_PORT}")
        except Exception as e:
            log(f"Cloud connect error: {e}")
            if plug_sock:
                try: plug_sock.close()
                except: pass
            time.sleep(2.0)
            continue
            
        plug_sock.setblocking(False)
        cloud_sock.setblocking(False)
        
        last_activity = time.time()
        last_log_time = time.time()
        pkt_plug_to_cloud = 0
        pkt_cloud_to_plug = 0
        
        # Transparent proxy loop
        while True:
            try:
                r, _, _ = select.select([plug_sock, cloud_sock], [], [], 1.0)
                if not r:
                    if time.time() - last_activity > 60:
                        log("Session idle timeout (60s). Reconnecting...")
                        break
                    continue
                    
                if plug_sock in r:
                    data = plug_sock.recv(4096)
                    if not data:
                        log("Plug disconnected (EOF)")
                        break
                    cloud_sock.sendall(data)
                    last_activity = time.time()
                    pkt_plug_to_cloud += 1
                    
                if cloud_sock in r:
                    data = cloud_sock.recv(4096)
                    if not data:
                        log("Cloud disconnected (EOF)")
                        break
                    plug_sock.sendall(data)
                    last_activity = time.time()
                    pkt_cloud_to_plug += 1
                
                # Status heartbeat every 10s
                if time.time() - last_log_time >= 10.0:
                    log(f"Bridge streaming: {pkt_cloud_to_plug} pkts from Cloud, {pkt_plug_to_cloud} pkts from Plug")
                    last_log_time = time.time()
                    
            except Exception as e:
                log(f"Bridge loop error: {e}")
                break
                
        try: plug_sock.close()
        except: pass
        try: cloud_sock.close()
        except: pass
        time.sleep(1.0)

if __name__ == '__main__':
    run_bridge()
