# Huawei ESM-48100B1 (8-Pack 38.4 kWh / 120 Cells) & Closed-Loop Inverter Integration (Gen 5: v5.3.0)

[![Release: v5.2.0 Gen 5](https://img.shields.io/badge/Release-v5.3.0%20(Gen%205)-brightgreen.svg)](docs/HUAWEI_ESM_8PACK_GEN5_MANUAL_TH_EN.md)
[![Hardware: Dual LILYGO T-CAN485](https://img.shields.io/badge/Hardware-2x%20LILYGO%20T--CAN485%20(ESP32)-blue.svg)](https://github.com/Xinyuan-LilyGO/T-CAN485)
[![Framework: ESPHome](https://img.shields.io/badge/Framework-ESPHome%202026.6+-green.svg)](https://esphome.io/)
[![Protocol: Pylontech LI2 & Modbus RTU](https://img.shields.io/badge/Protocol-Pylontech%20LI2%20%7C%20CAN%20%7C%20ESP--NOW-orange.svg)](#)
[![Home Assistant: Native Energy Flow](https://img.shields.io/badge/Home%20Assistant-120--Cell%20Dashboard%20Ready-41BDF5.svg)](ha_dashboard_solar_battery_8pack.yaml)
[![License: MIT](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)

> 📖 **คู่มือฉบับสมบูรณ์ (ภาษาไทย & English):** อ่านรายละเอียดเชิงลึกทั้งหมดได้ที่ **[docs/HUAWEI_ESM_8PACK_GEN5_MANUAL_TH_EN.md](docs/HUAWEI_ESM_8PACK_GEN5_MANUAL_TH_EN.md)**

An enterprise-grade, open-source reference implementation for integrating **8x Huawei ESM-48100B1 lithium battery modules (48V 800Ah / 38.4 kWh / 120 cells)** with high-power hybrid inverters (**MaxSky / ANENJI / PowMr EM11000 11kW**, Deye, SRNE, Growatt) using **dual-node multi-bus hardware isolation**, **2-Stage Back-EMF Parallel Balancing (`v6.5.0-PRO`)**, **Tri-Redundant Interconnect (CAN + Direct Unicast UDP + ESP-NOW)**, and **Active Discharge Load Equalization**.

---

## 🆕 What's New in v5.3.0 (Auto-EEPROM Unlock & Solar Charge Equalizer Release)

| Module / Component | File | Version | Key Enhancements |
| :--- | :--- | :---: | :--- |
| **Auto-EEPROM Permanent Unlock** | [`tcan_telemetry_shared.h`](tcan_telemetry_shared.h) | **`v5.3.0`** | **Automatic one-time write on boot** of `0x101B = 1000` (100.0A Default Charge Limit in EEPROM) across all 8 packs (Packs 1-7 on Node 108, Pack 8 on Node 109). Permanently unlocks derated/throttled packs (Pack 6 & 7) to 100A with zero manual intervention |
| **Solar Charge Equalizer (Active Diversion)** | [`huawei-esm-t-can485-8pack.yaml`](huawei-esm-t-can485-8pack.yaml) & [`huawei-esm-tcan-inverter-bridge.yaml`](huawei-esm-tcan-inverter-bridge.yaml) | **`v5.3.0`** | Dynamically throttles RAM `0x100D (Charge Limit Coef)` to 80 (8.0A) on high-SoC / spiking packs (>=85% SoC) during solar charging to **divert MPPT solar current into hungry packs (Packs 2, 4, 6, 7)** and prevent early busbar voltage clamping |
| **8-Byte CAN 0x35F & UDP Equalizer Link** | [`huawei-esm-t-can485-8pack.yaml`](huawei-esm-t-can485-8pack.yaml) & [`huawei-esm-tcan-inverter-bridge.yaml`](huawei-esm-tcan-inverter-bridge.yaml) | **`v5.3.0`** | Extended CAN ID `0x35F` and UDP port 18888 payload to synchronize both `g_eq_disch_coef[7]` AND `g_eq_chg_coef[7]` to Node 109 for bidirectional Pack 8 equalizing |

---

## 🆕 What's New in v5.2.0 (Anti-Chatter & Surge Hardening Release)

| Module / Component | File | Version | Key Enhancements |
| :--- | :--- | :---: | :--- |
| **Anti-Chatter Single-Latch Engine** | [`tcan_telemetry_shared.h`](tcan_telemetry_shared.h) & [`huawei-esm-t-can485-8pack.yaml`](huawei-esm-t-can485-8pack.yaml) | **`v5.2.0`** | **Eliminated relay clicking chatter** permanently via `g_eq_last_mode_sent` single-latch gating and `sleeping_m2 > 0` condition; widened evaluation window to 30s |
| **Grid Backup Floor (25% Sync)** | [`home_assistant/configuration.yaml`](home_assistant/configuration.yaml) & [`home_assistant/storage/lovelace.home_energy`](home_assistant/storage/lovelace.home_energy) | **`v5.2.0`** | Raised household grid standby cutoff to **`25.0% SoC / 48.0V`** across firmware and HA sensors to eliminate sag on high-power kitchen loads (kettles, rice cookers) |
| **Off-Grid Surge Hardening Floor** | [`components_v4/pylontech_emulator/pylontech_emulator.h`](components_v4/pylontech_emulator/pylontech_emulator.h) | **`v5.2.0`** | Elevated emergency off-grid cutoff from 46.0V to **`46.8V` (~18% SoC)** and cell floor to **`3.050V`** to provide surge headroom against inrush current from portable air conditioners and boilers |
| **Home Assistant Lovelace Sync** | [`home_assistant/storage/lovelace.home_energy`](home_assistant/storage/lovelace.home_energy) | **`v5.2.0`** | Real-Time Load Sharing status threshold adjusted to `p.i >= 0.3A` for **🟢 ชาร์จ**, synced usable energy cards and cache busters |

---

## 🆕 What's New in v5.0.0 (Gen 5 Release)

| Module / Component | File | Version | Key Gen 5 Enhancements |
| :--- | :--- | :---: | :--- |
| **Node 108 (BMS 8-Pack Master)** | [`huawei-esm-t-can485-8pack.yaml`](huawei-esm-t-can485-8pack.yaml) | **`v6.5.0`** | Full 120-cell Max/Min sync across CAN (`0x355`), Direct Unicast UDP (`18888`/`5005`), & ESP-NOW (`0x454E`); Cross-Node CAN (`0x35F`) Auto-Wake for Pack 8; true per-pack bitmask (`online_mask`) |
| **Node 109 (Inverter Bridge & Logger)** | [`huawei-esm-tcan-inverter-bridge.yaml`](huawei-esm-tcan-inverter-bridge.yaml) | **`v1.3.0`** | Dedicated Pack 8 isolated polling & CAN/ESP-NOW backhaul (`0x358..0x35C`); CAN `0x35F` remote wake handler (`wake_pack8_script`); MicroSD 1s CSV datalogger |
| **Pylontech LI2 Closed-Loop Engine** | [`components_v4/pylontech_emulator/pylontech_emulator.h`](components_v4/pylontech_emulator/pylontech_emulator.h) | **`v6.5.0-PRO`** | **2-Stage Parallel Balancing (`52.5V` → `52.8V`)** with **Asymmetric Voltage Slew-Rate Limiter** (`+0.1V/5s` up, `-0.2V/1s` down); non-latching `g_reported_max_cell_mv`; direction-aware `DCL` throttling status |
| **Shared Telemetry Protocol** | [`tcan_telemetry_shared.h`](tcan_telemetry_shared.h) | **`v5.0.0`** | Direct Unicast UDP `5005` streaming to both Node 109 (`192.168.8.109`) and CYD Display (`192.168.8.110`) + zero-router ESP-NOW checksummed packets |
| **Home Assistant 120-Cell Dashboard** | [`ha_dashboard_solar_battery_8pack.yaml`](ha_dashboard_solar_battery_8pack.yaml) | **`v5.0.0`** | Live online/offline indicators for isolated buses (Pack 4 & Pack 8), dynamic multi-threshold color-coded SOC/Current/Power cards, and hardware-accurate DIP Slave IDs |

---

## ⚡ Core Engineering Breakthroughs (สรุปจุดเด่นทางวิศวกรรม)

1. **8-Pack Parallel Huawei ESM-48100B1 Telemetry (120 Cells) & Dual Isolated Buses:**
   * Polls all 8 packs (120 cells, individual pack currents, SOH, temperatures, and alarms) without changing physical DIP switches on locked `ID 214 (0xD6)` modules:
     * **Node 108 Port 1 (`GPIO 33/32`):** Pack 1 (`0xD6`), Pack 2 (`0xD7`), Pack 3 (`0xD8`), Pack 5 (`0xD9`), Pack 6 (`0xDA`), Pack 7 (`0xDB`)
     * **Node 108 Port 2 (`GPIO 18/25`):** Isolated RS485 bus for **Pack 4 (`0xD6`)**
     * **Node 109 Port 2 (`GPIO 18/25`):** Isolated RS485 bus for **Pack 8 (`0xD6`)**, backhauled to Node 108 via CAN (`0x358..0x35C`) and ESP-NOW (`0x5038`)

2. **Continuous 2-Stage Back-EMF Parallel Balancing (`52.5V` → `52.8V` CV Clamp + `120A` Wide-Open CCL):**
   * Eliminates multi-pack starvation where one leading pack (e.g., Pack 4) hits `>= 3.48V/cell` early while lagging packs (e.g., Pack 1) are still `< 3.40V/cell`.
   * **Stage 1 (`52.5V` / `120A`):** Clamps the inverter busbar target voltage to `52.5V` (`3.50V/cell` avg) while keeping Charge Current Limit (CCL) wide open at `120.0A`. Full packs naturally float via Back-EMF (`< 1A`), while hungry packs absorb full solar power.
   * **Stage 2 (`52.8V` / `100A`):** Smoothly bridges busbar target voltage to `52.8V` when `min_cell` enters `3400–3425 mV`, governed by an **Asymmetric Voltage Slew-Rate Limiter** (`+0.1V / 5s` step-up, `-0.2V / 1s` step-down) to prevent MPPT current surges.

3. **Active Discharge Load Equalization & Cross-Node CAN `0x35F` Auto-Wake:**
   * Monitors inter-pack voltage delta (`>= 0.25V / 0.35V`) and per-pack discharge current delta, tapering DCL to `80A–100A` to protect individual packs from overload.
   * If any pack discharges `<= -6.0A` while another pack is sleeping (`> -2.0A`), Node 108 automatically sends Modbus wake frames (`0x06` Reg `0x101B = 100A`) to Packs 1–7 and transmits **CAN Frame `0x35F`** to Node 109 to wake Pack 8 (`wake_pack8_script`).

4. **Tri-Redundant Interconnect Link (CAN + Direct Unicast UDP + ESP-NOW):**
   * **Primary:** TWAI CAN Bus (500 kbps) transmitting `0x355` (SOC, SOH, MinCell, MaxCell), `0x356` (SysV, SysI, Temp, MinPackV), `0x358..0x35C` (Pack 8 15-cell backhaul), and `0x35F` (Remote Wake).
   * **Secondary:** Direct Unicast UDP streaming on Port `18888` (18-byte summary) and Port `5005` (full 8-pack / 120-cell `TcanTelemetryPacket`).
   * **Tertiary:** Zero-router-dependency **ESP-NOW** broadcast (`0x454E` & `0x5038`) with <2000ms automatic hot-failover.

5. **EyBond Wi-Fi Datalogger VIP Transparent Bridge (Port 502 / 8899):**
   * Local Home Assistant triage bridge (`custom_components/em11000_bridge`) providing 2.5s–3.0s local Dual-MPPT telemetry while keeping the official SmartESS / DessMonitor cloud app 100% functional.

---

## 📐 System Architecture (Gen 5 Dual-Node Topology)

```
                                  48V DC High-Capacity Busbar (800Ah / 38.4 kWh / 120 Cells)
    ┌───────────────────────────┬───────────────────────────────────────────────┬───────────────────────────┐
    │                           │                                               │                           │
  Packs 1,2,3,5,6,7         Pack 4 (ID 214 / 0xD6)                          Pack 8 (ID 214 / 0xD6)      11kW Hybrid Inverter
  (0xD6..0xD8, 0xD9..0xDB)  (Isolated Bus Port 2)                           (Isolated Bus Port 2)       (MaxSky EM11000)
    │                           │                                               │                           ▲
    ▼ (GPIO 33/32)              ▼ (GPIO 18/25)                                  ▼ (GPIO 18/25)              │ RS232 Pylontech LI2
┌─────────────────────────────────────────┐                                 ┌───────────────────────────────┴───────────┐
│ Node 108: BMS Master (192.168.8.108)    │  1. CAN Bus 500kbps (GPIO27/26) │ Node 109: Inverter Bridge (192.168.8.109) │
│ - Deterministic 8-Pack Modbus Engine    │◄───────────────────────────────►│ - Pylontech LI2 Emulator (v6.5.0-PRO)     │
│ - 120-Cell Max/Min Aggregator           │  2. Direct Unicast UDP 5005/18888│ - 2-Stage Parallel Balancing (52.5->52.8V)│
│ - Auto-Equalizer & CAN 0x35F Wake TX    │◄───────────────────────────────►│ - Asymmetric Voltage & Current Slew-Rate  │
│ - v6.5.0 Firmware                       │  3. ESP-NOW Failover (<2000ms)   │ - v1.3.0 Firmware + MicroSD CSV Logger    │
└─────────────────────────────────────────┘                                 └───────────────────────────────────────────┘
```

---

## 🚀 Quick Start & OTA Flashing

### 1. Configure Wi-Fi Credentials
Edit `YOUR_WIFI_SSID` and `YOUR_WIFI_PASSWORD` in [`huawei-esm-t-can485-8pack.yaml`](huawei-esm-t-can485-8pack.yaml) and [`huawei-esm-tcan-inverter-bridge.yaml`](huawei-esm-tcan-inverter-bridge.yaml) (or use the git-ignored `*-prod.yaml` files for production deployments).

### 2. Compile & Upload Firmware
```bash
# Node 109: Inverter Bridge & Pack 8 Controller (v1.3.0)
esphome compile huawei-esm-tcan-inverter-bridge.yaml
esphome upload --device 192.168.8.109 huawei-esm-tcan-inverter-bridge.yaml

# Node 108: 8-Pack BMS Master Controller (v6.5.0)
esphome compile huawei-esm-t-can485-8pack.yaml
esphome upload --device 192.168.8.108 huawei-esm-t-can485-8pack.yaml
```

### 3. Documentation & Runbooks
* 📘 **[Bilingual Gen 5 Engineering & Operations Manual (Thai / English)](docs/HUAWEI_ESM_8PACK_GEN5_MANUAL_TH_EN.md)**
* 📗 **[SmartESS / EyBond Local Triage Bridge Guide](docs/SMARTESS_EYBOND_LOCAL_TRIAGE_BRIDGE_GUIDE.md)**
* 📙 **[MaxSky EM11000 Home Assistant Integration Guide (TH)](MAXSKY_EM11000_HA_GUIDE_TH.md)**
* 📕 **[Huawei SMU02C & ESM-48100B1 Pinout & Service Guide (TH)](HUAWEI_SMU02C_ESM48100_PINOUT_SERVICE_GUIDE_TH.md)**

---

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
