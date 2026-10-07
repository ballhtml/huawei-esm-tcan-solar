# Backup Manifest: Proven Working Configuration (2026-10-06)

## System Status at Backup
- **Hardware:** LILYGO T-CAN485 (ESP32) + 2x Isolated TTL-to-RS485 Modules
- **Battery Packs:** 4x Huawei ESM-48100B1 (400 Ah System)
- **Live Test Results:**
  - Sustained continuous AC charge current: **+62.94 A (3,181 W)**
  - System Voltage: **50.8 V**
  - Read success rate: **100% across all 4 packs** (No timeouts)
  - Power source: Standard Phone Charger (AC 220V) with Signal Ground on Module 2

## Wiring Map
- **Module 1 (Packs 1–3, IDs 214, 215, 216):**
  - ESP32 TX: `GPIO 33` (H1 Pin 8) -> Module RXD
  - ESP32 RX: `GPIO 32` (H1 Pin 3) -> Module TXD
  - VCC: 5V (H1 Pin 22/24)
  - GND: System GND (H1 Pin 19)
  - RS485 A: RJ45 Pin 2 (Orange)
  - RS485 B: RJ45 Pin 1 (White-Orange)

- **Module 2 (Pack 4, ID 214 Isolated Bus):**
  - ESP32 TX: `GPIO 18` (H1 Pin 1) -> Module RXD
  - ESP32 RX: `GPIO 25` (H1 Pin 4) -> Module TXD
  - VCC: 5V (H1 Pin 22/24)
  - GND: System GND (H1 Pin 23)
  - RS485 A: RJ45 Pin 2 (Orange)
  - RS485 B: RJ45 Pin 1 (White-Orange)
  - **RS485 GND (Green Terminal):** RJ45 Pin 3/6 (White-Green) -> **CRITICAL for noise immunity**

## Files Backed Up
1. `huawei-esm-t-can485-8pack.yaml` (Full ESPHome Source)
2. `tcanesm_factory_proven.bin` (Complete binary ready for direct USB flashing at 0x0)
3. `tcanesm_ota_proven.bin` (Binary ready for OTA update)
