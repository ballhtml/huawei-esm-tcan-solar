# ==============================================================================
# Huawei ESM-48100B1 Solar & Battery Management System
# Dual LILYGO T-CAN485 Architecture (ESPHome + CAN Interconnect + Inverter Bridge)
# ==============================================================================

ระบบบริหารจัดการแบตเตอรี่ลิเธียมฟอสเฟต **Huawei ESM-48100B1** (48V 100Ah จำนวน 4–8 ลูก รวม 400–800Ah) ร่วมกับอินเวอร์เตอร์ไฮบริด/ออฟกริด และ Home Assistant โดยใช้บอร์ดไมโครคอนโทรลเลอร์ **LILYGO T-CAN485 (ESP32)** จำนวน 2 บอร์ดเชื่อมต่อกันด้วย **CAN Bus (TWAI 500kbps)**

## 🧰 อุปกรณ์หลักในระบบ (Core Hardware Components)

1. **บอร์ดควบคุมหลัก (Main Controller):**
   * **LILYGO T-CAN485 (ESP32 CAN/RS485 Board):**
     * ชิปประมวลผล Dual-Core ESP32 (Wi-Fi / Bluetooth / Native TWAI CAN)
     * มี CAN Bus Transceiver ในตัว (ต่อใช้งานผ่าน `GPIO 26 / 27` ทำงานที่ความเร็วสูง 500kbps)
     * ช่องต่อ MicroSD Card (TF Card) ในตัวสำหรับบันทึก Log ข้อมูลแบตเตอรี่แบบออฟไลน์
     * ใช้งานทั้งหมด 2 บอร์ด (Board 1: Battery Master, Board 2: Inverter Bridge & Logger)

2. **พระเอกกู้วิกฤตระบบ (The Hero Component):**
   * **DC 3.3V/5V โมดูลแยกประเภทกัลวานิก TTL to RS485 (Isolated TTL to RS485 Module):**
     * ชิปแยกสัญญาณและไฟเลี้ยงแบบกัลวานิกสมบูรณ์ (Galvanic Isolation 1.5kV+)
     * รองรับฟังก์ชันควบคุมทิศทางข้อมูลอัตโนมัติ (Automatic Flow Control / Auto Direction) ไม่ต้องต่อขา DE/RE
     * รองรับ Baudrate สูงสุดถึง **2 Mbps** (High Speed)
     * **หน้าที่สำคัญ:** ตัดวงจรกราวด์ลูป (Ground Loop Isolation) ระหว่างแบตเตอรี่ อินเวอร์เตอร์ และ ESP32 100% ป้องกัน Common-Mode Voltage เกิน $\pm7\text{V}$ ไม่ให้ชิปตัดการทำงานตอนชาร์จกระแสสูงเกิน 60A / 3000W

---

## 🏗️ สถาปัตยกรรมของระบบ (System Architecture)

```
 [ 4x Huawei ESM-48100B1 BMS ]
   │
   ├─ Pack 1, 2, 3 (ID 214, 215, 216) ──> [RS485 Isolated Blue Module (GPIO 33/32)] ┐
   └─ Pack 4 (ID 214 - Isolated Bus)  ──> [RS485 Isolated Red Module  (GPIO 18/25)] ┼─> [ Board 1: Battery Master ]
                                                                                   │     (IP: 192.168.8.108)
                                                                                   │
                 ┌─────────────────────────────────────────────────────────────────┘
                 │ CAN Bus (TWAI 500kbps) 
                 │ [ขาวส้ม+ส้ม: CAN_H | ขาวน้ำเงิน+น้ำเงิน: CAN_L | ขาวเขียว+เขียว: GND]
                 ▼
 [ Board 2: Inverter Bridge & Logger ] (Project V2)
   (IP: 192.168.8.109)
   │
   ├─ [Pylontech Protocol Emulator v6-PRO] ──> [RS485 Isolated Blue (GPIO 33/32)] ──> [ Solar Inverter (BMS Port) ]
   └─ [MicroSD Data Logger (Port 8080)]
```

---

## 🔌 คู่มือการต่อวงจรและฮาร์ดแวร์โดยละเอียด (Hardware Wiring Guide)

### 1. แหล่งจ่ายไฟและไฟเลี้ยงระบบ (Power Supply & Box Enclosure)
* **แหล่งจ่ายไฟหลัก:** ใช้อะแดปเตอร์ **5V 2A (เช่น Glink GAC5-2)** ผ่านขั้วต่อ **DC Female Jack (5.5x2.1mm แบบกดขันน็อต)** ติดข้างกล่อง
* ⚠️ **ข้อควรระวังสำคัญ:** ห้ามใช้ไฟ 12V หรือ 24V เด็ดขาด เนื่องจากบอร์ดหน้าจอ CYD (ESP32-2432S028R) และโมดูล Isolated RS485 รับแรงดันลอจิกได้สูงสุด 5V เท่านั้น
* **การกระจายไฟ:** พ่วงสายไฟบวก/ลบจาก DC Jack ไปเข้าขั้ว Power Terminal (+/-) ของบอร์ด T-CAN485 แล้วจั๊มต่อไปยังโมดูล RS485 และจอ CYD

---

---

### 2. ตารางสรุป GPIO และ Pinout เชื่อมต่อ TTL โมดูลทั้งหมด (Complete Pinout Table)

| บอร์ด | ชุดเชื่อมต่อ | ขาบนบอร์ด T-CAN485 (Header Pin) | ขาบนโมดูล TTL-RS485 | ฝั่ง RJ45 / ปลายทาง | หมายเหตุ |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Board 1** | **โมดูล 1: Pack 1–3** | **GPIO 33** (Header H1 Pin 8)<br>**GPIO 32** (Header H1 Pin 3)<br>**5V** (H1 Pin 22/24)<br>**GND** (H1 Pin 19) | **RXD**<br>**TXD**<br>**VCC**<br>**GND** | RJ45 Pin 2 (ส้ม = A+)<br>RJ45 Pin 1 (ขาวส้ม = B-) | บัสหลักแบตเตอรี่ (Slave IDs: 214, 215, 216) |
| **Board 1** | **โมดูล 2: Pack 4** | **GPIO 18** (Header H1 Pin 1)<br>**GPIO 25** (Header H1 Pin 4)<br>**5V** (H1 Pin 22/24)<br>**GND** (H1 Pin 23) | **RXD**<br>**TXD**<br>**VCC**<br>**GND**<br>*Isolated GND* | RJ45 Pin 2 (ส้ม = A+)<br>RJ45 Pin 1 (ขาวส้ม = B-)<br>**RJ45 Pin 3/6 (ขาวเขียว)** | บัสแยก Pack 4 (ID 214 ชนกับลูกที่ 1)<br>***RJ45 Pin 3/6 ต่อเข้า Isolated GND แก้กราวด์ลูป*** |
| **Board 1 <-> 2** | **CAN Interconnect** | **GPIO 27** (TX Onboard)<br>**GPIO 26** (RX Onboard)<br>**GND** (Terminal บอร์ด) | ขั้ว **CAN_H** (ขันน็อต)<br>ขั้ว **CAN_L** (ขันน็อต)<br>ขั้ว **G** (ขันน็อต) | สาย LAN ขาวส้ม+ส้ม<br>สาย LAN ขาวน้ำเงิน+น้ำเงิน<br>สาย LAN ขาวเขียว+เขียว | สื่อสารระหว่าง 2 บอร์ดความเร็ว 500kbps |
| **Board 2** | **โมดูล Inverter** | **GPIO 33** (Header H1 Pin 8)<br>**GPIO 32** (Header H1 Pin 3)<br>**5V** (H1 Pin 22/24)<br>**GND** (H1 Pin 19) | **RXD**<br>**TXD**<br>**VCC**<br>**GND**<br>*Isolated GND* | พอร์ต BMS Inverter A+<br>พอร์ต BMS Inverter B-<br>พอร์ต BMS Inverter GND | จำลอง Pylontech Protocol ส่งให้อินเวอร์เตอร์ |

---

### 3. รายละเอียดการต่อสายแต่ละชุด (Detailed Wiring per Module)

#### ชุดที่ 1: บอร์ด 1 ต่อเข้าโมดูล Isolated สำหรับ Pack 1, 2, 3 (Slave IDs: 214, 215, 216)
* **ฝั่งลอจิก TTL (เข้า ESP32 T-CAN485):**
  * `RXD` ของโมดูล $\rightarrow$ ต่อเข้า **`GPIO 33`** (Header H1 Pin 8)
  * `TXD` ของโมดูล $\rightarrow$ ต่อเข้า **`GPIO 32`** (Header H1 Pin 3)
  * `VCC` ของโมดูล $\rightarrow$ ต่อเข้า **`5V`** (Header H1 Pin 22 หรือ 24)
  * `GND` ของโมดูล $\rightarrow$ ต่อเข้า **`GND`** (Header H1 Pin 19)
* **ฝั่งบัส RS485 (เข้าหัว RJ45 แบตเตอรี่ลูกที่ 1, 2, 3):**
  * **A+** $\rightarrow$ ต่อสายสีส้ม (RJ45 Pin 2)
  * **B-** $\rightarrow$ ต่อสายสีขาว-ส้ม (RJ45 Pin 1)

#### ชุดที่ 2: บอร์ด 1 ต่อเข้าโมดูล Isolated สำหรับ Pack 4 (Slave ID: 214 บัสแยก)
*เหตุผลที่ต้องแยกบัส:* แบตลูกที่ 4 มี Address ID 214 ซ้ำกับลูกที่ 1 โดยเราไม่ต้องไปปรับสวิตช์ DIP ที่ตัวแบต
* **ฝั่งลอจิก TTL (เข้า ESP32 T-CAN485):**
  * `RXD` ของโมดูล $\rightarrow$ ต่อเข้า **`GPIO 18`** (Header H1 Pin 1)
  * `TXD` ของโมดูล $\rightarrow$ ต่อเข้า **`GPIO 25`** (Header H1 Pin 4)
  * `VCC` ของโมดูล $\rightarrow$ ต่อเข้า **`5V`** (Header H1 Pin 22 หรือ 24)
  * `GND` ของโมดูล $\rightarrow$ ต่อเข้า **`GND`** (Header H1 Pin 23)
* **ฝั่งบัส RS485 (เข้าหัว RJ45 แบตเตอรี่ลูกที่ 4):**
  * **A+** $\rightarrow$ ต่อสายสีส้ม (RJ45 Pin 2)
  * **B-** $\rightarrow$ ต่อสายสีขาว-ส้ม (RJ45 Pin 1)
  * **GND (Isolated):** ต่อสายสีขาว-เขียว (RJ45 Pin 3 หรือ Pin 6) $\rightarrow$ **เข้าช่อง GND ฝั่ง RS485 ของโมดูล (หัวใจสำคัญแก้ Common-Mode)**

#### ชุดที่ 3: การเชื่อมต่อ CAN Bus ข้ามบอร์ด (Board 1 <-> Board 2)
* เชื่อมโยงผ่านช่องขันน็อตเทอร์มินอลสีเขียว (CAN Port Onboard ที่ควบคุมด้วย GPIO 27/26):
  * **`CAN_H`** (Board 1) $\leftrightarrow$ **`CAN_H`** (Board 2) ด้วยสาย **ขาวส้ม + ส้ม**
  * **`CAN_L`** (Board 1) $\leftrightarrow$ **`CAN_L`** (Board 2) ด้วยสาย **ขาวน้ำเงิน + น้ำเงิน**
  * **`G` (GND)** (Board 1) $\leftrightarrow$ **`G` (GND)** (Board 2) ด้วยสาย **ขาวเขียว + เขียว**

#### ชุดที่ 4: บอร์ด 2 ต่อเข้าโมดูล Isolated สำหรับเชื่อมต่อไปยัง Inverter (BMS Port)
* **ฝั่งลอจิก TTL (เข้า ESP32 T-CAN485 บอร์ดที่ 2):**
  * `RXD` ของโมดูล $\rightarrow$ ต่อเข้า **`GPIO 33`** (Header H1 Pin 8)
  * `TXD` ของโมดูล $\rightarrow$ ต่อเข้า **`GPIO 32`** (Header H1 Pin 3)
  * `VCC` ของโมดูล $\rightarrow$ ต่อเข้า **`5V`** (Header H1 Pin 22/24)
  * `GND` ของโมดูล $\rightarrow$ ต่อเข้า **`GND`** (Header H1 Pin 19)
* **ฝั่งบัส RS485 (เข้าช่อง RJ45 พอร์ต BMS ของ Inverter):**
  * **A+** $\rightarrow$ ต่อขา RS485-A ของ Inverter (สเปกแต่ละรุ่น เช่น Pin 1 หรือ Pin 7)
  * **B-** $\rightarrow$ ต่อขา RS485-B ของ Inverter (เช่น Pin 2 หรือ Pin 8)
  * **GND (Isolated):** ต่อขากราวด์ของพอร์ต BMS อินเวอร์เตอร์ เข้ากับช่อง GND ฝั่ง RS485 ของโมดูลน้ำเงิน

#### B. พอร์ต MicroSD Card Onboard
* ทำงานผ่านสล็อต TF Card บนบอร์ด T-CAN485 เพื่อบันทึก CSV Log และดาวน์โหลดผ่าน Web Port 8080

---

## ⚡ แก้ปัญหาสำคัญทางฮาร์ดแวร์ & เฟิร์มแวร์ (Proven Fixes)

1. **การแก้ปัญหากราวด์ลูป & หลุด Error 04 / 4b ตอนชาร์จแรง (>60A / 3000W):**
   * **Signal Ground Fix:** ต่อสาย BMS Signal Ground (ขาวเขียว RJ45 Pin 3/6) เข้ากับ GND ฝั่ง Isolated เพื่อดึง Common-Mode Voltage ให้อยู่ในย่านปลอดภัย $\pm7\text{V}$ ป้องกันชิป RS485 ตัดการทำงาน
   * **Dedicated Isolated Modules:** ไม่ใช้ชิป RS485 Onboard (MAX13487 บน GPIO22/21) เนื่องจากไม่มี Isolation กราวด์ ให้ใช้โมดูลแยกกราวด์ภายนอก
2. **Pylontech Emulator V6-PRO:**
   * แปลงสตริงข้อมูลโมเดล/ผู้ผลิตให้เป็น **Hex-Encoded ASCII** 100% ตามข้อกำหนด Pylontech
   * เพิ่ม **High-EMI Noise Immunity Filter** ไม่ทิ้ง Buffer ทิ้งทั้งเฟรมเมื่อมีคลื่นแม่เหล็กกวนช่วงกระแสชาร์จพีค
   * ระบบ **Soft Current Throttling & Limp-home (10A):** ป้องกัน Inverter สั่งตัด BMS Lost (Error 04)

---

## 📁 โครงสร้างโปรเจกต์ (Project Structure)

* `huawei-esm-t-can485-8pack.yaml` — เฟิร์มแวร์ **Board 1 (Battery Master)**
* `project_v2_inverter_bridge/` — โปรเจกต์ชุดที่ 2 สำหรับ **Board 2 (Inverter Gateway & Logger)**
  * `inverter_bridge_v2.yaml` — คอนฟิก ESPHome Board 2
  * `components/pylontech_emulator/` — Pylontech BMS Emulator v6.0.0-PRO
  * `components/sd_logger/` — MicroSD Card Data Logger
* `backup_proven_20261006/` — ชุดสำรองไฟล์ที่ผ่านการทดสอบและพิสูจน์แล้วว่าใช้งานได้จริง 100%
