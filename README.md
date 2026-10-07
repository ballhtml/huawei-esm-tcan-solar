# ==============================================================================
# Huawei ESM-48100B1 Solar & Battery Management System
# Dual LILYGO T-CAN485 Architecture (ESPHome + CAN Interconnect + Inverter Bridge)
# ==============================================================================

ระบบบริหารจัดการแบตเตอรี่ลิเธียมฟอสเฟต **Huawei ESM-48100B1** (48V 100Ah จำนวน 4–8 ลูก รวม 400–800Ah) ร่วมกับอินเวอร์เตอร์ไฮบริด/ออฟกริด และ Home Assistant โดยใช้บอร์ดไมโครคอนโทรลเลอร์ **LILYGO T-CAN485 (ESP32)** จำนวน 2 บอร์ดเชื่อมต่อกันด้วย **CAN Bus (TWAI 500kbps)**

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

### 2. บอร์ด 1: Battery Master (IP 192.168.8.108)
ทำหน้าที่อ่านข้อมูล Modbus จากแบตเตอรี่ทั้ง 4 ลูก

#### A. โมดูลที่ 1 (บอร์ดน้ำเงิน Isolated) สำหรับ Pack 1, 2, 3 (Slave IDs: 214, 215, 216)
* **ESP32 TX:** `GPIO 33` (Header H1 Pin 8) $\rightarrow$ โมดูล RXD
* **ESP32 RX:** `GPIO 32` (Header H1 Pin 3) $\rightarrow$ โมดูล TXD
* **ไฟเลี้ยง:** VCC 5V (H1 Pin 22/24), GND (H1 Pin 19)
* **ฝั่งต่อแบตเตอรี่ (RJ45):**
  * **RS485 A+ :** Pin 2 (สายส้ม)
  * **RS485 B- :** Pin 1 (สายขาว-ส้ม)

#### B. โมดูลที่ 2 (บอร์ดแดง/น้ำเงิน Isolated) สำหรับ Pack 4 (Slave ID: 214 แยกบัส)
*เหตุผลที่ต้องแยกบัส:* แบตลูกที่ 4 มี Address ID 214 ชนกับลูกที่ 1 โดยไม่ต้องไปยุ่งกับ DIP switch
* **ESP32 TX:** `GPIO 18` (Header H1 Pin 1) $\rightarrow$ โมดูล RXD
* **ESP32 RX:** `GPIO 25` (Header H1 Pin 4) $\rightarrow$ โมดูล TXD
* **ไฟเลี้ยง:** VCC 5V (H1 Pin 22/24), GND (H1 Pin 23)
* **ฝั่งต่อแบตเตอรี่ (RJ45):**
  * **RS485 A+ :** Pin 2 (สายส้ม)
  * **RS485 B- :** Pin 1 (สายขาว-ส้ม)
  * **RS485 GND :** Pin 3/6 (สายขาว-เขียว) $\rightarrow$ **ต่อเข้าขั้ว GND ฝั่ง Isolated ของโมดูล (หัวใจสำคัญแก้กราวด์ลูป)**

---

### 3. การเชื่อมต่อ CAN Bus ระหว่าง Board 1 และ Board 2
เชื่อมโยงสื่อสารความเร็ว 500kbps ข้ามบอร์ดผ่านสาย LAN แบบรวบคู่ (Double Twisted-Pair):
* **[ขาวส้ม + ส้ม]** รวมกัน $\rightarrow$ ขันเข้าช่อง **`CAN_H`** (Board 1 ไป Board 2)
* **[ขาวน้ำเงิน + น้ำเงิน]** รวมกัน $\rightarrow$ ขันเข้าช่อง **`CAN_L`** (Board 1 ไป Board 2)
* **[ขาวเขียว + เขียว]** รวมกัน $\rightarrow$ ขันเข้าช่อง **`G` (GND)** (ดึงระดับกราวด์อ้างอิงเท่ากัน)
* *(คู่น้ำตาลเก็บสำรองไว้)*

---

### 4. บอร์ด 2: Inverter Gateway & Logger (IP 192.168.8.109 - Project V2)
ทำหน้าที่รับข้อมูลจาก CAN Bus แล้วแปลงเป็น Pylontech RS485 ส่งให้อินเวอร์เตอร์

#### A. พอร์ต Pylontech RS485 ไปยังอินเวอร์เตอร์ (BMS Port)
* ใช้ **โมดูลสีน้ำเงินที่มี Isolated** (ป้องกัน High Common-Mode Voltage จากอินเวอร์เตอร์)
* **ESP32 TX:** `GPIO 33` $\rightarrow$ โมดูล RXD
* **ESP32 RX:** `GPIO 32` $\rightarrow$ โมดูล TXD
* **ฝั่งต่อ Inverter (RJ45 BMS Port):**
  * **RS485 A+ :** ต่อเข้าขา RS485-A ของ Inverter (ตามสเปก RJ45 ของแต่ละยี่ห้อ เช่น Pin 1 หรือ Pin 7)
  * **RS485 B- :** ต่อเข้าขา RS485-B ของ Inverter (เช่น Pin 2 หรือ Pin 8)
  * **RS485 GND :** ต่อขา GND ของพอร์ต BMS Inverter เข้ากับ GND ฝั่ง Isolated ของโมดูลน้ำเงิน

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
