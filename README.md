# Huawei ESM-48100B1 (8-Pack 38.4 kWh) & Inverter Closed-Loop Integration

[![Hardware: LilyGO T-CAN485](https://img.shields.io/badge/Hardware-LILYGO%20T--CAN485%20(ESP32)-blue.svg)](https://github.com/Xinyuan-LilyGO/T-CAN485)
[![Framework: ESPHome](https://img.shields.io/badge/Framework-ESPHome-green.svg)](https://esphome.io/)
[![Protocol: Pylontech CAN & Modbus RTU](https://img.shields.io/badge/Protocol-Pylontech%20CAN%20%7C%20Modbus%20RTU-orange.svg)](#)
[![Home Assistant: Native Energy Flow](https://img.shields.io/badge/Home%20Assistant-Energy%20Dashboard%20Ready-41BDF5.svg)](https://www.home-assistant.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)

An enterprise-grade, open-source reference implementation for integrating **8x Huawei ESM-48100B1 lithium battery modules (48V 800Ah / 38.4 kWh / 120 cells)** with high-power off-grid/hybrid inverters (ANENJI, PowMr, Deye, SRNE, Growatt) using **dual-bus hardware isolation**, **native Pylontech closed-loop CAN emulation (`Li2`)**, and a **zero-latency EyBond VIP transparent bridge**.

---

## ⚡ Core Engineering Breakthroughs

1. **8-Pack Parallel Huawei ESM-48100B1 Telemetry (120 Cells):**
   * Reads cell voltages, individual pack currents, SOH, internal resistance, alarms, and temperatures simultaneously.
   * **Pack 4 Address Collision Fix (ID 214):** Huawei ESM modules often carry fixed factory firmware locking Pack 4 to ID 214 (`0xD6`). This setup uses dual isolated RS485 transceivers on the LilyGO T-CAN485, creating a dedicated isolated bus for Pack 4 **without altering DIP switches on live, busbar-connected batteries**.
   * **Deterministic Modbus Pacing:** Custom C++ Accessor tuning (`frame_delay: 250ms`, `long_rx_delay: 350ms`) guarantees 100% collision-free polling across all 8 modules.

2. **Native Pylontech CAN Bus Emulator (`Li2` Closed-Loop):**
   * Embedded C++ TWAI driver (`stitched_pylontech_emulator.h`) running on ESP32 broadcasts standard Pylontech protocol frames (`0x351`, `0x355`, `0x356`, `0x359`, `0x35C`, `0x35E`) at 500 kbps.
   * Dynamically calculates **Charge Current Limit (CCL)** and **Discharge Current Limit (DCL)** based on lowest/highest pack voltages and cell temperatures, enforcing closed-loop inverter protection.

3. **EyBond Wi-Fi Datalogger VIP Transparent Bridge (Port 502):**
   * Resolves the vendor lock-in of EyBond/SmartESS Wi-Fi data loggers.
   * Discovered the true EyBond server endpoint is **TCP Port 502** (`vip1.eybond.com:502`), not port 18899 (which is an AT cellular terminal that drops connections after 15 seconds).
   * Proxies binary Modbus frames to the cloud so the **official SmartESS mobile app remains 100% functional** while Home Assistant intercepts telemetry locally at 2.5s intervals.
   * **Guarded UDP Watchdog:** Sends zero-configuration LAN signals (`set>server=<HA_IP>:8899;\r\n` to port 58899) to recover the logger within 1.5 seconds if the home router reboots at 04:00 AM. **Requires zero router modification, zero DNS spoofing, and no OpenWrt/pfSense.**

4. **Real-Time Battery Load Sharing Lovelace Dashboard:**
   * High-density Home Assistant UI featuring live power flow, dynamic pack current ranking, cell drift analysis, and exact Thai PEA TOU tiered electricity cost calculations.

---

## 📐 System Architecture

```
                                  48V DC High-Capacity Busbar (38.4 kWh)
    ┌────────────────────────────────────────────────────────────────────────────────────────┐
    │                                                                                        │
  Pack 1 (ID 1)  Pack 2 (ID 2)  Pack 3 (ID 3)  Pack 5 (ID 5)  Pack 6 (ID 6)  Pack 7 (ID 7)  Pack 8 (ID 8)  Pack 4 (ID 214)
    │              │              │              │              │              │              │               │
    └──────────────┴──────────────┴──────┬───────┴──────────────┴──────────────┴──────────────┘               │ (Dedicated Bus)
                                         │ RS485 Main Bus (9600 8E1)                                          │ RS485 Isolated Bus
                                         ▼                                                                    ▼
                            ┌────────────────────────┐                                          ┌────────────────────────┐
                            │ Isolated RS485 Module  │                                          │ Isolated RS485 Module  │
                            │ (Blue / GPIO 33 & 32)  │                                          │ (Red / GPIO 18 & 25)   │
                            └───────────┬────────────┘                                          └───────────┬────────────┘
                                        │                                                                   │
                                        └─────────────────────┐               ┌─────────────────────────────┘
                                                              ▼               ▼
                                                   ┌─────────────────────────────────────┐
                                                   │   LILYGO T-CAN485 Controller (ESP32)│ (IP: 192.168.8.108)
                                                   │  - ESPHome Modbus Pacing Engine     │
                                                   │  - Pylontech CAN Emulator (TWAI)    │
                                                   └──────────────────┬──────────────────┘
                                                                      │ CAN_H / CAN_L (500 kbps)
                                                                      ▼
                                                   ┌─────────────────────────────────────┐
                                                   │     11kW Hybrid Inverter (Li2)      │
                                                   │  (ANENJI / PowMr / Deye BMS Port)   │
                                                   └──────────────────┬──────────────────┘
                                                                      │ RS232 / Datalogger Port
                                                                      ▼
                                                   ┌─────────────────────────────────────┐
                                                   │ EyBond Wi-Fi Datalogger (.166:58899)│
                                                   └──────────────────┬──────────────────┘
                                                                      │ Local LAN TCP :8899
                                                                      ▼
                                                   ┌─────────────────────────────────────┐
                                                   │ Home Assistant VIP Bridge (.209)    │
                                                   │ - Zero-latency Local Sensors (2.5s) │
                                                   │ - Guarded UDP Auto-Recovery Watchdog│
                                                   └──────────────────┬──────────────────┘
                                                                      │ Upstream TCP :502
                                                                      ▼
                                                   ┌─────────────────────────────────────┐
                                                   │ China VIP Cloud (47.239.230.129:502)│
                                                   │ (SmartESS / DessMonitor App 100% OK)│
                                                   └─────────────────────────────────────┘
```

---

## 🛠️ Hardware Requirements

| Component | Description | Purpose |
| :--- | :--- | :--- |
| **LILYGO T-CAN485** | ESP32 board with native CAN transceiver & RS485 | Master controller running ESPHome & TWAI CAN |
| **Galvanic Isolated RS485** | High-speed 3.3V/5V TTL to RS485 modules (Auto Direction) | Eliminates ground loops between battery bank & inverter |
| **RJ45 Splitters & Cat6** | Standard 8P8C twisted pair cables | Pin 1/4 = RS485-A (+), Pin 2/3 = RS485-B (-), Pin 7/8 = CAN |
| **Huawei ESM-48100B1** | 48V 100Ah LiFePO4 Telecom Battery Packs (Up to 8 units) | Primary energy storage |
| **Hybrid Inverter** | ANENJI ANJ-HHS-11KW / PowMr POW-HVM11KP or compatible | Dual-MPPT 48V hybrid inverter |

---

## 🚀 Quick Start Guide

### 1. Flash ESPHome Firmware
Copy `tcan_telemetry_shared.h` and `huawei-esm-t-can485-8pack.yaml` into your ESPHome directory:
```bash
esphome compile huawei-esm-t-can485-8pack.yaml
esphome upload huawei-esm-t-can485-8pack.yaml --device 192.168.8.108
```

### 2. Deploy EyBond VIP Cloud Bridge on Home Assistant
Copy the `custom_components/em11000_bridge` directory to your Home Assistant `/config/custom_components/`:
```bash
# Add to configuration.yaml
em11000_bridge:
```
Restart Home Assistant. The bridge will listen on port `8899`, intercept local telemetry, maintain the upstream link to `vip1.eybond.com:502`, and auto-recover the plug if your router reboots.

### 3. Verify Live Telemetry
Open Home Assistant -> **Developer Tools** -> **States**:
* `sensor.huawei_esm_battery_system_total_battery_system_voltage` (e.g., `48.4 V`)
* `sensor.huawei_esm_battery_system_total_battery_system_current` (e.g., `-36.5 A`)
* `sensor.huawei_esm_battery_system_total_battery_system_soc` (e.g., `85%`)
* `sensor.home_energy_em11000_bridge_status` (`Connected`)

---

## 📊 Live Dashboard Preview

The repository includes ready-to-import Lovelace dashboards featuring:
* **Sunsynk Power Flow Card:** Dual-MPPT strings, battery power flow, grid bypass, and inverter efficiency.
* **Real-Time Load Sharing Table:** Live current and power ranking showing which packs are carrying the highest charge or discharge current.
* **120-Cell Drilldown:** Max/Min cell voltage delta tracking down to 1 mV precision.
* **PEA Step-Rate Billing Meter:** Accurate calculation of Thai provincial electricity authority bills.

---

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
