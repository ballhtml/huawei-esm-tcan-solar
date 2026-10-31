# SmartESS & EyBond Wi-Fi Datalogger: Real-Time Local Triage Bridge & Dual-MPPT Engine (v2.0.0)

[![Home Assistant: Native Integration](https://img.shields.io/badge/Home%20Assistant-Custom%20Integration-blue.svg)](https://www.home-assistant.io/)
[![Hardware Modification: None](https://img.shields.io/badge/Hardware%20Mod-Zero%20(100%25%20Stock)-brightgreen.svg)](#)
[![SmartESS Cloud Coexistence: 100%](https://img.shields.io/badge/SmartESS%20App-100%25%20Functional-success.svg)](#)
[![Update Rate: 3.0s Live](https://img.shields.io/badge/Telemetry%20Interval-3.0s%20Real--Time-orange.svg)](#)

An enterprise-grade, zero-hardware reference solution for hybrid and off-grid solar inverters using **EyBond / SmartESS Wi-Fi Datalogger plugs** (ANENJI, PowMr, Deye, EASun, Anern, SunUno, Maxsky, SMG Protocol 4).

Eliminates the notorious **30–80 second cloud telemetry delay**, unlocks **true Dual-MPPT independent string monitoring**, and achieves **instantaneous 3.0s Home Assistant dashboard updates** while keeping the official **SmartESS mobile app 100% functional**.

---

## 🌍 The Universal Problem in the Solar Community

Tens of thousands of hybrid inverter owners worldwide rely on EyBond Wi-Fi Dataloggers (often branded as SmartESS, DessMonitor, or Solarman). Users have historically faced an agonizing trade-off:

1. **The Cloud Bottleneck (30–80s Lag):**
   * The Wi-Fi plug uploads a batch of telemetry to the Chinese cloud (`vip1.eybond.com`) only once every 35 to 80 seconds.
   * Home Assistant integrations polling the cloud API suffer from severe latency, making real-time home energy management, excess solar diversion (EV charging, water heaters), and instantaneous load tracking impossible.
2. **The "Either/Or" Dilemma:**
   * Traditional local workarounds force users to cut off the cloud (e.g. by reflashing the plug with OpenBeken/ESPHome or disconnecting it to use an ESP32 on RS232).
   * This completely breaks the manufacturer's mobile app (SmartESS), causing friction for family members and losing remote diagnostic capabilities.
3. **The Dual-MPPT String Blind Spot:**
   * Many integrations lump solar power together into a single estimated value, failing to report individual string voltages, currents, and power for dual-tracker inverters.

---

## ⚡ The "Triage Nurse" Architecture (v2.0.0)

Instead of acting as a dumb "mail carrier" (transparent proxy) or an "either/or" cloud blocker, the **v2.0.0 Triage Nurse Engine** runs locally inside Home Assistant as an intelligent multiplexing proxy:

```mermaid
flowchart LR
    Inv["Hybrid Inverter<br/>(Dual MPPT)"] <-->|RS232 Modbus RTU| Plug["EyBond Wi-Fi Plug<br/>(Stock Firmware)"]
    Plug <-->|TCP :8899 (LAN)| Bridge["em11000_bridge<br/>(Local Triage Nurse)"]
    Bridge <-->|3.0s Direct Telemetry (0ms)| HA["Home Assistant<br/>(Lovelace Dashboard)"]
    Bridge <-->|TCP :18899 Multiplexed| Cloud["VIP Cloud China<br/>(vip1.eybond.com)"]
    Cloud <-->|Push / Sync| App["SmartESS Mobile App<br/>(iOS / Android)"]
```

### Key Technical Mechanisms:
1. **Local Modbus Triage Injection (~45ms):**
   Every 3.0 seconds, the bridge injects targeted Modbus RTU read queries (`FC 03`) into the local TCP connection. The plug responds in ~45ms, delivering fresh vitals directly from the inverter before relaying data to the cloud.
2. **True Dual-MPPT String Separation:**
   Extracts genuine hardware registers directly from the inverter's MPPT controllers:
   * **String 1 (PV1):** Voltage (`Reg 351`), Current (`Reg 352`), Power (`Reg 353`)
   * **String 2 (PV2):** Voltage (`Reg 389`), Current (`Reg 390`), Power (`Reg 391`)
   * **Total Solar Power:** Accurate hardware sum ($P_{\text{PV1}} + P_{\text{PV2}}$) without speculative estimations.
3. **Single-Threaded Multiplexing & Zero Loss:**
   The bridge manages upstream and downstream sockets sequentially with BSD `select()`. Cloud packets arriving during the 45ms triage window reside safely in the OS TCP socket receive buffer and are relayed immediately afterwards.
4. **Native Home Assistant Coordinator Hook:**
   Pushes decoded telemetry directly into the `dess_solar` coordinator on the event loop. Dashboard cards update instantly via WebSockets in **0 ms**.
5. **Zero Hardware Modifications & Zero Router Tampering:**
   No DNS spoofing, no router iptables redirects, and no hardware disassembly required. If the home router reboots at 04:00 AM, the bridge's UDP watchdog autonomously re-steers the plug within 1.5 seconds.

---

## 📊 Modbus Register Map (ANENJI / Protocol 4 Standard)

| Parameter | Register Address | Units / Scale | Modbus Block |
| :--- | :---: | :---: | :--- |
| **Grid Voltage** | `338` | $0.1\text{ V}$ | Block D (Reg 338–353) |
| **AC Output Voltage** | `346` | $0.1\text{ V}$ | Block D |
| **AC Output Current** | `347` | $0.1\text{ A}$ | Block D |
| **Output Active Power** | `348` | $1\text{ W}$ (signed) | Block D |
| **Load Percentage** | `350` | $1\text{ \%}$ | Block D |
| **PV1 String Voltage** | `351` | $0.1\text{ V}$ | Block D |
| **PV1 String Current** | `352` | $0.1\text{ A}$ | Block D |
| **PV1 String Power** | `353` | $1\text{ W}$ | Block D |
| **PV2 String Voltage** | `389` | $0.1\text{ V}$ | Block PV2 (Reg 389–391) |
| **PV2 String Current** | `390` | $0.1\text{ A}$ | Block PV2 |
| **PV2 String Power** | `391` | $1\text{ W}$ | Block PV2 |
| **Battery Voltage** | `277` | $0.1\text{ V}$ | Block B (Reg 277–281) |
| **Battery Current** | `278` | $0.1\text{ A}$ (signed) | Block B |
| **Battery Power** | `279` | $1\text{ W}$ (signed) | Block B |
| **Heatsink / DC Temp** | `280` | $1\text{ }^\circ\text{C}$ | Block B |
| **Battery SOC** | `281` | $1\text{ \%}$ | Block B |

---

## 🚀 Quick Start Guide

### 1. Installation
Copy `custom_components/em11000_bridge` into your Home Assistant `/config/custom_components/` directory:
```bash
/config/custom_components/em11000_bridge/
├── __init__.py
├── const.py
└── manifest.json
```

### 2. Configuration (`configuration.yaml`)
Enable the bridge with zero-configuration defaults:
```yaml
# EM11000 High-Speed Inverter Bridge (Local 3.0s Triage + Cloud Multiplexer)
em11000_bridge:
```

*(Optional custom configuration)*:
```yaml
em11000_bridge:
  listen_port: 8899              # Local TCP port for the Wi-Fi plug
  cloud_host: "vip1.eybond.com"  # Upstream SmartESS cloud server
  cloud_port: 18899              # EyBond VIP upstream port
```

### 3. Wi-Fi Plug Steering (One-Time Setup)
Point your EyBond Wi-Fi Datalogger to Home Assistant's IP instead of the cloud directly:
* Open a browser to your Wi-Fi plug's local web portal (e.g., `http://192.168.x.x`, default login: `admin`/`admin`).
* In **Advanced Settings / Server Settings**:
  * **Server Address:** `<Your_Home_Assistant_IP>` (e.g. `192.168.8.209`)
  * **Port:** `8899`
* Save and restart the plug.

*Note: The bridge will automatically handle upstream traffic to `vip1.eybond.com:18899`, ensuring your SmartESS app continues to work without interruption.*

---

## 🔬 Live Telemetry Verification Proof

```text
[12:00:43] PV1: 170.1V / 2193W | PV2: 155.0V / 2286W | Total Solar: 4479W | Home Load: 1367W
[12:00:46] PV1: 170.1V / 2203W | PV2: 153.7V / 2273W | Total Solar: 4476W | Home Load: 1358W
[12:00:49] PV1: 170.1V / 2203W | PV2: 153.7V / 2273W | Total Solar: 4476W | Home Load: 1358W
[12:00:52] PV1: 168.4V / 2233W | PV2: 154.4V / 2310W | Total Solar: 4543W | Home Load: 1378W
```

* **Update Interval:** Every 3.0 seconds consistently.
* **Latency:** $< 50\text{ ms}$ local query duration.
* **SmartESS App:** Synchronized simultaneously via cloud upstream streaming.

---

## 📄 License
This project is released under the **MIT License**. Community contributions and forks for other inverter protocols (PI30, SRNE, Deye) are warmly welcomed!
