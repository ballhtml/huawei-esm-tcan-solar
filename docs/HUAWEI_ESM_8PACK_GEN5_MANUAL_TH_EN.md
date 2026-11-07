# คู่มือวิศวกรรมและการใช้งานระบบแบตเตอรี่ Huawei ESM-48100B1 (8 แพ็ก 38.4 kWh / 120 เซลล์) & อินเวอร์เตอร์ Closed-Loop (Gen 5: v5.0.0)
# Huawei ESM-48100B1 (8-Pack 38.4 kWh / 120 Cells) & Closed-Loop Inverter Engineering Manual (Gen 5: v5.0.0)

[![Release: v5.0.0 Gen 5](https://img.shields.io/badge/Release-v5.0.0%20(Gen%205)-brightgreen.svg)](#)
[![Node 108 BMS Master](https://img.shields.io/badge/Node%20108%20(BMS%20Master)-v6.5.0-blue.svg)](../huawei-esm-t-can485-8pack.yaml)
[![Node 109 Inverter Bridge](https://img.shields.io/badge/Node%20109%20(Inverter%20Bridge)-v1.3.0-orange.svg)](../huawei-esm-tcan-inverter-bridge.yaml)
[![Pylontech LI2 Engine](https://img.shields.io/badge/Pylontech%20LI2%20Engine-v6.5.0--PRO-purple.svg)](../components_v4/pylontech_emulator/pylontech_emulator.h)

---

## 🇹🇭 ส่วนที่ 1: คู่มือสถาปัตยกรรมและการใช้งานฉบับภาษาไทย (Thai Edition)

### 1. ภาพรวมระบบ (System Overview)
ระบบจัดการพลังงานอัจฉริยะแบบ Closed-Loop สำหรับแบตเตอรี่ลิเธียมฟอสเฟต **Huawei ESM-48100B1 จำนวน 8 โมดูลขนานกัน (พิกัด 48V 800Ah / 38.4 kWh / 120 เซลล์)** เชื่อมต่อกับอินเวอร์เตอร์ไฮบริด **MaxSky / ANENJI / PowMr EM11000 (11 kW)** ผ่านโปรโตคอล **Pylontech (`LI2`)** โดยใช้บอร์ดไมโครคอนโทรลเลอร์อุตสาหกรรม **LILYGO T-CAN485 (ESP32)** จำนวน 2 โหนดทำงานร่วมกันแบบ **Tri-Redundant (CAN Bus + Direct Unicast UDP + ESP-NOW)**

#### สถาปัตยกรรมการแยกบัสอิสระ (Dual-Node & Multi-Bus Hardware Isolation)
เพื่อแก้ปัญหาแอดเดรสชนกันที่ `ID 214 (0xD6)` ของแบตเตอรี่ Huawei ESM บางโมดูล **โดยไม่ต้องปรับสวิตช์หรือแก้ไขฮาร์ดแวร์ภายในตัวแบตเตอรี่ที่ต่ออยู่บนบัสบาร์**:
- **บอร์ดที่ 1 — Node 108 (`192.168.8.108` / `huawei-esm-t-can485-8pack.yaml` v6.5.0):**
  - **Port 1 (`GPIO 33/32` - `uart_bms`):** อ่านค่า Pack #1 (`0xD6`), Pack #2 (`0xD7`), Pack #3 (`0xD8`), Pack #5 (`0xD9`), Pack #6 (`0xDA`), และ Pack #7 (`0xDB`)
  - **Port 2 (`GPIO 18/25` - `uart_pack4`):** บัส RS485 แยกอิสระเฉพาะ **Pack #4 (`0xD6`)**
- **บอร์ดที่ 2 — Node 109 (`192.168.8.109` / `huawei-esm-tcan-inverter-bridge.yaml` v1.3.0):**
  - **Port 1 (`GPIO 33/32` - `uart_port1_33_32`):** จำลองโปรโตคอล Pylontech (`LI2` RS232/RS485) ตอบกลับอินเวอร์เตอร์ MaxSky EM11000
  - **Port 2 (`GPIO 18/25` - `uart_port2_18_25`):** บัส RS485 แยกอิสระเฉพาะ **Pack #8 (`0xD6`)** แล้วส่งข้อมูลทั้ง 15 เซลล์ของ Pack #8 ย้อนกลับไปรวมที่ Node 108 ผ่าน CAN Bus (`0x358..0x35C`) และ ESP-NOW (`0x5038`)

| แพ็ก # | รุ่นโมดูล (Model) | ความจุ | Modbus Slave ID | บอร์ดและพอร์ตสื่อสาร | สถานะบัส |
| :---: | :--- | :---: | :---: | :--- | :---: |
| **Pack #1** | Huawei ESM-48100B1 (15S) | 48V 100Ah | `ID 214 (0xD6)` | Node 108 • Port 1 (`GPIO 33/32`) | บัสหลัก |
| **Pack #2** | Huawei ESM-48100B1 (15S) | 48V 100Ah | `ID 215 (0xD7)` | Node 108 • Port 1 (`GPIO 33/32`) | บัสหลัก |
| **Pack #3** | Huawei ESM-48100B1 (15S) | 48V 100Ah | `ID 216 (0xD8)` | Node 108 • Port 1 (`GPIO 33/32`) | บัสหลัก |
| **Pack #4** | Huawei ESM-48100B1 (15S) | 48V 100Ah | `ID 214 (0xD6)` | Node 108 • Port 2 (`GPIO 18/25`) | 🛡️ บัสแยกอิสระ |
| **Pack #5** | Huawei ESM-48100B1 (15S) | 48V 100Ah | `ID 217 (0xD9)` | Node 108 • Port 1 (`GPIO 33/32`) | บัสหลัก |
| **Pack #6** | Huawei ESM-48100B1 (15S) | 48V 100Ah | `ID 218 (0xDA)` | Node 108 • Port 1 (`GPIO 33/32`) | บัสหลัก |
| **Pack #7** | Huawei ESM-48100B1 (15S) | 48V 100Ah | `ID 219 (0xDB)` | Node 108 • Port 1 (`GPIO 33/32`) | บัสหลัก |
| **Pack #8** | Huawei ESM-48100B1 (15S) | 48V 100Ah | `ID 214 (0xD6)` | Node 109 • Port 2 (`GPIO 18/25` ข้าม CAN) | 🛡️ บัสแยกอิสระ |

---

### 2. นวัตกรรมหลักในเวอร์ชัน Gen 5 (`v5.0.0`)

#### 2.1 ระบบชาร์จสมดุลขนาน 2 ระยะ (2-Stage Back-EMF Parallel Balancing)
ในระบบแบตเตอรี่ขนาน 8 แพ็ก แพ็กที่มีความต้านทานสายต่ำกว่าหรือมีเซลล์นำ (เช่น Pack #4) มักจะพุ่งแตะ `3.55V–3.58V` ก่อนแพ็กอื่น หากใช้วิธีหรี่กระแสชาร์จรวม (CCL) ลงเหลือ `20A` จะทำให้แพ็กที่ยังชาร์จไม่เต็ม (เช่น Pack #1) พลอยอดไฟไปด้วย และทำให้อินเวอร์เตอร์ดึงไฟหลวง (PEA) มาผสมทั้งที่แดดแรง

**กลไกการแก้ปัญหาใน Gen 5 (`pylontech_emulator.h` v6.5.0-PRO):**
1. **Stage 1 — Staging Balance (`52.5V` CV Clamp + `120A` Wide-Open CCL):**
   - เมื่อเซลล์สูงสุด (`max_cell`) แตะ `>= 3460 mV` ในขณะที่เซลล์ต่ำสุด (`min_cell`) ยังต่ำกว่า `< 3400 mV`
   - ระบบจะสั่งกดเพดานแรงดันชาร์จของอินเวอร์เตอร์ลงมาล็อกที่ **`52.5V`** (`3.50V/เซลล์`) แต่ **เปิดเพดานกระแสชาร์จ (CCL) กว้างไว้ที่ `120.0A`**
   - แพ็กที่แรงดันถึง `52.5V` แล้วจะเกิดแรงดันต้านกลับ (Back-EMF) ทำให้กระแสไหลเข้าตัวเองลดลงเหลือ `< 1A` โดยธรรมชาติ ส่วนกระแสโซลาร์จะไหลเทไปชาร์จแพ็กที่แรงดันยังต่ำกว่า `52.5V` เต็มพิกัด
2. **Stage 2 — Balancing Bridge (`52.8V` CV Clamp + `100A` CCL):**
   - เมื่อเซลล์รั้งท้ายไต่พ้น `3400 mV` ขึ้นมาอยู่ในช่วง `3400–3425 mV` (หรือค่าความต่างเซลล์รวม `cell_delta_mv >= 60 mV`)
   - ระบบจะขยับเพดานแรงดันขึ้นอย่างนุ่มนวลมาที่ **`52.8V`** พร้อมเปิดกระแส **`100.0A`** เพื่อป้องกันไม่ให้แรงดันกระโดดข้ามไป `53.4V` ทันที
3. **Asymmetric Voltage Slew-Rate Limiter (ตัวหน่วงความชันแรงดันแบบอสมมาตร):**
   - **ขาลง (Step-Down):** ลดเพดานแรงดันลงเร็ว `-0.2V ต่อ 1 วินาที` ทันทีที่ตรวจพบเซลล์แตะ `>= 3.55V` เพื่อปกป้องเซลล์ทันที
   - **ขาขึ้น (Step-Up):** ไต่เพดานแรงดันขึ้นช้าๆ ไม่เกิน `+0.1V ต่อ 5 วินาที` ป้องกันวงจร MPPT ของอินเวอร์เตอร์กระชากกระแส

#### 2.2 ระบบเกลี่ยโหลดขาจ่ายไฟออก & ปลุกแบตข้ามบอร์ดอัตโนมัติ (Active Discharge Equalization & Cross-Node CAN `0x35F` Auto-Wake)
- **การเกลี่ยกระแสจ่ายออก (`get_dynamic_discharge_limit_100ma`):**
  - ตรวจสอบผลต่างแรงดันแพ็ก (`pack_delta_v >= 0.25V / 0.35V`) และผลต่างกระแสจ่ายออกรายแพ็ก (`disch_curr_delta >= 4.0A / 6.0A`) โดยปรับเพดาน DCL ลงมาที่ `100A` หรือ `80A` อย่างนุ่มนวลเพื่อไม่ให้แพ็กใดแพ็กหนึ่งรับภาระหนักเกินไป
  - แสดงสถานะ `DCL_...` เฉพาะเมื่อมีกระแสจ่ายออกจริง (`cur_a < -2.0A`) ไม่เขียนทับสถานะฝั่งชาร์จ
- **การปลุกแบตเตอรี่ที่หลับข้ามบอร์ดอัตโนมัติ (`auto_wake_sleeping_packs` + CAN `0x35F`):**
  - เมื่อ Node 108 ตรวจพบว่ามีแพ็กใดจ่ายไฟหนัก `<= -6.0A` ในขณะที่แพ็กอื่นหลับ (`> -2.0A`) Node 108 จะส่งคำสั่ง Modbus Function `0x06` (Register `0x101B = 100A`) ไปปลุก Pack 1–3, 5–7 บน `uart_bms`, ปลุก Pack 4 บน `uart_pack4` และส่งเฟรม **CAN ID `0x35F`** ข้ามไปสั่ง Node 109 ให้รัน `wake_pack8_script` เพื่อปลุก Pack 8 (`0xD6` บน Port 2) พร้อมกันครบทั้ง 8 แพ็ก

#### 2.3 ระบบสื่อสารสำรอง 3 ช่องทางพร้อมซิงค์ `MaxCell / MinCell` 100% (Tri-Redundant Telemetry Fusion)
- **ช่องทางที่ 1 — CAN Bus TWAI (500 kbps):**
  - `0x355`: ส่งค่า `SOC (2B)`, `SOH (2B)`, `MinCell mV (2B)`, `MaxCell mV (2B)` ทุก 1 วินาที
  - `0x356`: ส่งค่า `System V (2B)`, `System I (2B)`, `Max Temp (2B)`, `Min Pack V (2B)` ทุก 1 วินาที
  - `0x358..0x35C`: ส่งค่าแรงดัน กระแส SOC และแรงดันรายเซลล์ทั้ง 15 เซลล์ของ Pack #8 จาก Node 109 กลับไปยัง Node 108
  - `0x35F`: คำสั่งปลุก Pack #8 ข้ามบอร์ดจาก Node 108 ไปยัง Node 109
- **ช่องทางที่ 2 — Direct Unicast UDP (`Port 18888` & `Port 5005`):**
  - ส่งแพ็กเก็ตสรุป 18 ไบต์ (รวม `MinCell` และ `MaxCell`) ไปยัง `192.168.8.109:18888` และส่งเมทริกซ์ข้อมูลครบทั้ง 120 เซลล์ (`TcanTelemetryPacket`) แบบ Direct Unicast ไปยัง `192.168.8.109:5005` และหน้าจอ CYD `192.168.8.110:5005`
- **ช่องทางที่ 3 — ESP-NOW Zero-Latency Failover (`0x454E` & `0x5038`):**
  - สื่อสารไร้สายระดับ MAC Layer โดยตรงระหว่างชิป ESP32 ทั้งสองบอร์ด พร้อม Bitmask สถานะออนไลน์รายแพ็ก (`online_mask = 1U << idx`) และ Checksum 16 บิต หาก CAN Bus ขาดหายเกิน 2 วินาที ระบบจะสลับมาใช้ข้อมูลจาก ESP-NOW ทันทีโดยไม่พึ่งพา Router Wi-Fi

---

### 3. มาตรฐานการจัดการไฟล์คู่ขนาน (Dual-Version File Standard)
เพื่อความปลอดภัยในการเผยแพร่โค้ดขึ้นสู่ GitHub โดยไม่ให้รหัสผ่าน Wi-Fi ภายในบ้านรั่วไหล โปรเจกต์นี้ใช้ระบบไฟล์คู่ขนาน:
1. **ชุดใช้งานจริง (`*-prod.yaml`):**
   - `huawei-esm-t-can485-8pack-prod.yaml` และ `huawei-esm-tcan-inverter-bridge-prod.yaml`
   - มีข้อมูล Wi-Fi จริงของบ้าน ใช้สำหรับรันคำสั่ง `esphome compile` และ `esphome upload` ลงบอร์ดจริง (ถูกบล็อกด้วย `.gitignore` ไม่ให้อัปโหลดขึ้น GitHub)
2. **ชุดเผยแพร่สาธารณะ (`*.yaml`):**
   - `huawei-esm-t-can485-8pack.yaml` และ `huawei-esm-tcan-inverter-bridge.yaml`
   - โค้ดและอัลกอริทึมตรงกับไฟล์ `-prod.yaml` ทุกบรรทัด 100% แต่แทนที่ชื่อและรหัสผ่าน Wi-Fi ด้วย `YOUR_WIFI_SSID` และ `YOUR_WIFI_PASSWORD` สำหรับเก็บและเผยแพร่บน GitHub

#### คำสั่งคอมไพล์และอัปเดตเฟิร์มแวร์ (OTA Flashing Commands)
```powershell
# 1. คอมไพล์และอัปโหลดเฟิร์มแวร์บอร์ด 109 (Inverter Bridge - v1.3.0)
esphome compile huawei-esm-tcan-inverter-bridge-prod.yaml
esphome upload --device 192.168.8.109 huawei-esm-tcan-inverter-bridge-prod.yaml

# 2. คอมไพล์และอัปโหลดเฟิร์มแวร์บอร์ด 108 (BMS 8-Pack Master - v6.5.0)
esphome compile huawei-esm-t-can485-8pack-prod.yaml
esphome upload --device 192.168.8.108 huawei-esm-t-can485-8pack-prod.yaml
```

---
---

## 🌐 Part 2: Complete Engineering & Operations Manual (English Edition)

### 1. System Architecture & Multi-Bus Isolation
This repository provides a production-proven, closed-loop Battery Management & Inverter Control architecture for **8x parallel Huawei ESM-48100B1 (48V 800Ah / 38.4 kWh / 120 cells)** lithium iron phosphate modules paired with an 11 kW hybrid inverter (**MaxSky / ANENJI / PowMr EM11000**) via the **Pylontech (`LI2`)** protocol.

#### Hardware Bus Isolation (Zero DIP-Switch Modification Required)
Certain Huawei ESM-48100B1 firmware revisions lock their Modbus Slave ID to `214 (0xD6)`. To run 8 packs in parallel without opening the battery chassis or modifying live busbar-connected packs:
- **Node 108 — BMS Master (`192.168.8.108` / `huawei-esm-t-can485-8pack.yaml` v6.5.0):**
  - **Port 1 (`GPIO 33/32` - `uart_bms`):** Polls Pack #1 (`0xD6`), Pack #2 (`0xD7`), Pack #3 (`0xD8`), Pack #5 (`0xD9`), Pack #6 (`0xDA`), and Pack #7 (`0xDB`).
  - **Port 2 (`GPIO 18/25` - `uart_pack4`):** Dedicated isolated RS485 bus exclusively for **Pack #4 (`0xD6`)**.
- **Node 109 — Inverter Bridge & Logger (`192.168.8.109` / `huawei-esm-tcan-inverter-bridge.yaml` v1.3.0):**
  - **Port 1 (`GPIO 33/32` - `uart_port1_33_32`):** Runs the **Pylontech LI2 Emulator (`v6.5.0-PRO`)** communicating with the hybrid inverter at 9600 baud.
  - **Port 2 (`GPIO 18/25` - `uart_port2_18_25`):** Dedicated isolated RS485 bus exclusively for **Pack #8 (`0xD6`)**, backhauling all 15 cell voltages and pack metrics to Node 108 via CAN (`0x358..0x35C`) and ESP-NOW (`0x5038`).

---

### 2. Core Engineering Innovations in Gen 5 (`v5.0.0`)

#### 2.1 Continuous 2-Stage Back-EMF Parallel Balancing & Voltage Slew-Rate Control
In large multi-pack parallel banks, cable impedance variations and cell aging cause leading packs (e.g., Pack #4) to hit the upper LiFePO4 voltage knee (`>= 3.50V/cell`) while lagging packs (e.g., Pack #1) are still at `3.38V/cell`. Traditional BMS emulators throttle the total Charge Current Limit (CCL) down to `15A–20A`, starving the lagging packs and forcing the hybrid inverter to import grid power during peak solar hours.

**The Gen 5 Solution (`pylontech_emulator.h` v6.5.0-PRO):**
1. **Stage 1 — Staging Parallel Balance (`52.5V` CV Clamp + `120A` Wide-Open CCL):**
   - Triggered when `max_cell >= 3460 mV` while `min_cell < 3400 mV`.
   - Clamps the inverter's Target Charge Voltage (CV) to **`52.5V`** (`3.50V/cell` average) while keeping **CCL wide open at `120.0A`**.
   - By Kirchhoff's and Ohm's laws ($I = (V_{\text{bus}} - V_{\text{EMF}}) / R$), packs that have already reached `52.5V` naturally float at `< 1A`, while lagging packs absorb the full `120A` solar current without triggering single-cell OVP.
2. **Stage 2 — Smooth Balancing Bridge (`52.8V` CV Clamp + `100A` CCL):**
   - Triggered when `min_cell` rises into the `3400–3425 mV` transition zone (or `cell_delta_mv >= 60 mV`).
   - Bridges the busbar target voltage to **`52.8V`** at **`100.0A`**, eliminating abrupt step-jumps to `53.4V`.
3. **Asymmetric Voltage Slew-Rate Limiter:**
   - **Fast Downward Relief (`-200 mV / 1s`):** Immediately lowers target CV when any cell touches `>= 3550 mV`.
   - **Gentle Upward Ramp (`+100 mV / 5s`):** Prevents sudden MPPT voltage step-jumps and current overshoots when transitioning between charging stages.

#### 2.2 Active Discharge Equalization & Cross-Node CAN `0x35F` Auto-Wake
- **Dynamic Discharge Tapering (`get_dynamic_discharge_limit_100ma`):**
  - Continuously monitors inter-pack voltage delta (`>= 0.25V / 0.35V`) and per-pack discharge current delta (`>= 4.0A / 6.0A`), smoothly tapering total DCL to `80A–100A` so no individual pack is overloaded.
  - Direction-aware status reporting ensures `DCL_...` reasons are only reported when the bank is actively discharging (`cur_a < -2.0A`).
- **Cross-Node Autonomous Pack Wake (`auto_wake_sleeping_packs` + CAN `0x35F`):**
  - If any pack discharges at `<= -6.0A` while another pack rests in standby (`> -2.0A`), Node 108 broadcasts Modbus wake commands (`0x06` to Register `0x101B = 100A`) across Port 1 (Packs 1–3, 5–7) and Port 2 (Pack 4), and transmits **CAN Frame `0x35F`** to Node 109, triggering `wake_pack8_script` on Node 109 Port 2 to wake Pack 8 simultaneously.

#### 2.3 Tri-Redundant Telemetry Fusion (CAN + Direct Unicast UDP + ESP-NOW)
- **Primary (TWAI CAN 500 kbps):** Carries `SOC`, `SOH`, `MinCell mV`, and `MaxCell mV` in `0x355` (8 bytes) and `SysV`, `SysI`, `Temp`, and `MinPackV` in `0x356` (8 bytes), plus Pack 8 backhaul (`0x358..0x35C`) and remote wake (`0x35F`).
- **Secondary (Direct Unicast UDP `18888` & `5005`):** Streams 18-byte summary frames to `192.168.8.109:18888` and full 120-cell telemetry structures (`TcanTelemetryPacket`) via direct unicast to `192.168.8.109:5005` and `192.168.8.110:5005`.
- **Tertiary (ESP-NOW MAC-Layer Failover):** Zero-router-dependency wireless link (`EspNowBmsPacket` `0x454E` and `EspNowPack8Packet` `0x5038`) with per-pack online bitmask (`1U << idx`) and 16-bit checksums. Automatically takes over within `< 2000ms` if CAN traffic stalls.

---

### 3. Deployment & Configuration Guide
1. Copy [`tcan_telemetry_shared.h`](../tcan_telemetry_shared.h), [`components_v4/`](../components_v4), [`huawei-esm-t-can485-8pack.yaml`](../huawei-esm-t-can485-8pack.yaml), and [`huawei-esm-tcan-inverter-bridge.yaml`](../huawei-esm-tcan-inverter-bridge.yaml) into your ESPHome workspace.
2. Replace `YOUR_WIFI_SSID` and `YOUR_WIFI_PASSWORD` with your local Wi-Fi credentials (or maintain separate `*-prod.yaml` files ignored by git).
3. Compile and flash both boards via OTA:
   ```bash
   esphome run huawei-esm-tcan-inverter-bridge.yaml --device 192.168.8.109
   esphome run huawei-esm-t-can485-8pack.yaml --device 192.168.8.108
   ```
4. Import [`ha_dashboard_solar_battery_8pack.yaml`](../ha_dashboard_solar_battery_8pack.yaml) into your Home Assistant Lovelace dashboard for real-time 120-cell analytics, live online/offline bus badges, and dynamic color-coded charge/discharge status cards.
