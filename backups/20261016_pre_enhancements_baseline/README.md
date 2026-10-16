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

| บอร์ด | ชุดเชื่อมต่อ | ขาบนบอร์ด T-CAN485 (Header H1) | ขาบนโมดูล TTL-RS485 | ฝั่ง RJ45 / ปลายทาง | ฟังก์ชันและสถานะ |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Board 1 (108)** | **โมดูล 1: Pack 1–3, 5–7** | **GPIO 33 TX** (Header H1 Pin 3)<br>**GPIO 32 RX** (Header H1 Pin 4)<br>**5V** (ขั้วไฟ 5V บอร์ด)<br>**GND** (Header H1 Pin 2 หรือ 12) | **RXD**<br>**TXD**<br>**VCC**<br>**GND** | RJ45 Pin 2 (ส้ม = A+)<br>RJ45 Pin 1 (ขาวส้ม = B-) | บัสหลักแบตเตอรี่ 6 ลูก (Slave IDs: 214–221) |
| **Board 1 (108)** | **โมดูล 2: Pack 4** | **GPIO 18 TX** (Header H1 Pin 10)<br>**GPIO 25 RX** (Header H1 Pin 1)<br>**5V** (ขั้วไฟ 5V บอร์ด)<br>**GND** (Header H1 Pin 2 หรือ 12) | **RXD**<br>**TXD**<br>**VCC**<br>**GND**<br>*Isolated GND* | RJ45 Pin 2 (ส้ม = A+)<br>RJ45 Pin 1 (ขาวส้ม = B-)<br>**RJ45 Pin 3/6 (ขาวเขียว)** | บัสแยก Modbus ID 214 สำหรับลูกที่ 4 ป้องกัน Address ชนกับลูกที่ 1 |
| **Board 1 <-> 2** | **CAN Interconnect** | **GPIO 27** (TX Onboard)<br>**GPIO 26** (RX Onboard)<br>**GND** (Terminal บอร์ด) | ขั้ว **CAN_H** (ขันน็อต)<br>ขั้ว **CAN_L** (ขันน็อต)<br>ขั้ว **G** (ขันน็อต) | สาย LAN ขาวส้ม+ส้ม<br>สาย LAN ขาวน้ำเงิน+น้ำเงิน<br>สาย LAN ขาวเขียว+เขียว | สื่อสารระหว่าง 2 บอร์ดความเร็ว 500kbps (ส่งระบบรวม 0x355/0x356 และรับ Pack 8 0x358) |
| **Board 2 (109)** | **โมดูล Inverter (Li2)** | **GPIO 33 TX** (Header H1 Pin 3)<br>**GPIO 32 RX** (Header H1 Pin 4)<br>**5V** (ขั้วไฟ 5V บอร์ด)<br>**GND** (Header H1 Pin 2 หรือ 12) | **RXD**<br>**TXD**<br>**VCC**<br>**GND**<br>*Isolated GND* | RJ45 Pin 5 (RS485-A+)<br>RJ45 Pin 3 (RS485-B-)<br>RJ45 Pin 8 (BMS GND) | จำลอง Pylontech Protocol (Li2) ส่งให้อินเวอร์เตอร์ แก้ Warning b4 |
| **Board 2 (109)** | **โมดูล Pack 8** | **Pin 1 (GPIO 25)**: ทำหน้าที่ **TX**<br>**Pin 10 (GPIO 18)**: ทำหน้าที่ **RX**<br>**5V** (ขั้วไฟ 5V บอร์ด)<br>**GND** (Header H1 Pin 2 หรือ 12) | **RXD** (เข้า Pin 1)<br>**TXD** (เข้า Pin 10)<br>**VCC**<br>**GND**<br>*Isolated GND* | RJ45 Pin 2 (ส้ม = A+)<br>RJ45 Pin 1 (ขาวส้ม = B-)<br>**RJ45 Pin 3/6 (ขาวเขียว)** | บัสแยก Modbus ID 214 สำหรับลูกที่ 8 อ่านค่าแล้วยิงข้าม CAN 0x358 ไปบอร์ด 108 |

---

#### แผนผังขา Header H1 บนบอร์ด LilyGO T-CAN485 (จาก Schematic แท้):
```text
        [ฝั่งซ้าย - เลขคี่]                  [ฝั่งขวา - เลขคู่]
     Pin 1  : GPIO 25 (RX/TX)  ◄───┐      Pin 2  : GND
     Pin 3  : GPIO 33 (TX)         │      Pin 4  : GPIO 32 (RX)
     Pin 5  : GPIO 12              │      Pin 6  : GPIO 5
     Pin 7  : GPIO 35 (In only)    │      Pin 8  : GPIO 34 (In only)
     Pin 9  : 3.3V                 └────► Pin 10 : GPIO 18 (TX/RX)
     Pin 11 : 3.3V                        Pin 12 : GND
```
> ⚠️ **จุดสังเกตสำคัญ:** ขา Pin 1 และ Pin 10 **ไม่ได้อยู่ติดกัน** แต่อยู่ทแยงมุมคนละฝั่งของ Header H1 (Pin 1 อยู่บนสุดซ้าย, Pin 10 อยู่รองล่างสุดขวา)

---

### 🔍 ไขปริศนา: ทำไมพอร์ต 18/25 ถึงทำงานได้สำเร็จ (Root Cause & Solution)

1. **ปัญหาการจัดวางขาทางกายภาพ (Physical Pin Layout):**
   * เดิมทีผู้ใช้คุ้นเคยกับพอร์ต `33/32` ซึ่งขาทั้งสองอยู่ติดกันในแถวที่สอง (Pin 3 กับ Pin 4)
   * แต่พอร์ต `18/25` บนบอร์ด T-CAN485 มีขา GPIO 25 อยู่ที่ **Pin 1 (บนสุดซ้าย)** และ GPIO 18 อยู่ที่ **Pin 10 (รองล่างสุดขวา)** เมื่อเสียบสายต้องแยกสายเสียบสองฝั่งของ Header H1
2. **การสลับคู่สายในระดับซอฟต์แวร์ (ESP32 GPIO Matrix Magic):**
   * เมื่อผู้ใช้เสียบสายจากโมดูล RS485 เข้าที่ Pin 1 และ Pin 10 สัญญาณฝั่งโมดูล (TXD/RXD) เข้ามาสลับทิศทางกับค่าคอนฟิกเริ่มต้น
   * เราใช้คุณสมบัติ **GPIO Matrix ของ ESP32** สลับการแมปขาในเฟิร์มแวร์:
     ```yaml
     # Board 109 Firmware Config:
     - id: uart_port2_18_25
       tx_pin: GPIO25   # กำหนดให้ Pin 1 ส่งข้อมูลออก (TX)
       rx_pin: GPIO18   # กำหนดให้ Pin 10 รับข้อมูลเข้า (RX)
       baud_rate: 9600
       parity: EVEN
       stop_bits: 1
     ```
   * **ผลลัพธ์:** แมตช์กับทิศทางสายจริงที่เสียบทันที 100% โดยผู้ใช้ไม่ต้องถอดขยับสายให้เสี่ยงต่อการหลุดหลวม
3. **การส่งต่อข้อมูลข้ามบอร์ด (CAN Bus Telemetry Bridge 0x358):**
   * บอร์ด 109 อ่าน Pack 8 ที่ Slave ID 214 ได้ค่าแรงดัน กระแส SOC SOH และอุณหภูมิครบถ้วน
   * บอร์ด 109 แพ็กข้อมูลยิงข้ามสาย CAN Bus ใน **Frame `0x358`** ทุก 2 วินาที
   * บอร์ด 108 ดักรับ Frame `0x358` แล้ว Publish เข้าตัวแปร `pack8_...` ทันที ทำให้:
     * บอร์ด 108 นับจำนวนแบตเตอรี่ครบ **8 ลูก (800 Ah)**
     * Home Assistant แสดงผลการ์ด Pack 8 (`sensor.tcanesm_pack_8_...`) สดใสทันที

---

### 3. รายละเอียดการต่อสายแต่ละชุด (Detailed Wiring per Module)

#### ชุดที่ 1: บอร์ด 1 ต่อเข้าโมดูล Isolated สำหรับ Pack 1, 2, 3 (Slave IDs: 214, 215, 216)
* **ฝั่งลอจิก TTL (เข้า ESP32 T-CAN485):**
  * `RXD` ของโมดูล $\rightarrow$ ต่อเข้า **`GPIO 33 (TX)`** (Header H1 Pin 3)
  * `TXD` ของโมดูล $\rightarrow$ ต่อเข้า **`GPIO 32 (RX)`** (Header H1 Pin 4)
  * `VCC` ของโมดูล $\rightarrow$ ต่อเข้า **`5V`**
  * `GND` ของโมดูล $\rightarrow$ ต่อเข้า **`GND`** (Header H1 Pin 2 หรือ 12)
* **ฝั่งบัส RS485 (เข้าหัว RJ45 แบตเตอรี่ลูกที่ 1, 2, 3):**
  * **A+** $\rightarrow$ ต่อสายสีส้ม (RJ45 Pin 2)
  * **B-** $\rightarrow$ ต่อสายสีขาว-ส้ม (RJ45 Pin 1)

#### ชุดที่ 2: บอร์ด 1 ต่อเข้าโมดูล Isolated สำหรับ Pack 4 (Slave ID: 214 บัสแยก)
*เหตุผลที่ต้องแยกบัส:* แบตลูกที่ 4 มี Address ID 214 ซ้ำกับลูกที่ 1 โดยไม่ต้องไปปรับสวิตช์ DIP ที่ตัวแบต
* **ฝั่งลอจิก TTL (เข้า ESP32 T-CAN485):**
  * `RXD` ของโมดูล $\rightarrow$ ต่อเข้า **`GPIO 18 (TX)`** (Header H1 Pin 10)
  * `TXD` ของโมดูล $\rightarrow$ ต่อเข้า **`GPIO 25 (RX)`** (Header H1 Pin 1)
  * `VCC` ของโมดูล $\rightarrow$ ต่อเข้า **`5V`**
  * `GND` ของโมดูล $\rightarrow$ ต่อเข้า **`GND`** (Header H1 Pin 2 หรือ 12)
* **ฝั่งบัส RS485 (เข้าหัว RJ45 แบตเตอรี่):**
  * **A+** $\rightarrow$ ต่อสายสีส้ม (RJ45 Pin 2)
  * **B-** $\rightarrow$ ต่อสายสีขาว-ส้ม (RJ45 Pin 1)
  * **GND (Isolated):** ต่อสายสีขาว-เขียว (RJ45 Pin 3 หรือ Pin 6) $\rightarrow$ **เข้าช่อง GND ฝั่ง RS485 ของโมดูล (หัวใจสำคัญแก้ Common-Mode)**

#### ชุดที่ 3: การเชื่อมต่อ CAN Bus ข้ามบอร์ด (Board 1 <-> Board 2)
* เชื่อมโยงผ่านช่องขันน็อตเทอร์มินอลสีเขียว (CAN Port Onboard ที่ควบคุมด้วย GPIO 27/26):
  * **`CAN_H`** (Board 1) $\leftrightarrow$ **`CAN_H`** (Board 2) ด้วยสาย **ขาวส้ม + ส้ม**
  * **`CAN_L`** (Board 1) $\leftrightarrow$ **`CAN_L`** (Board 2) ด้วยสาย **ขาวน้ำเงิน + น้ำเงิน**
  * **`G` (GND)** (Board 1) $\leftrightarrow$ **`G` (GND)** (Board 2) ด้วยสาย **ขาวเขียว + เขียว**

#### ชุดที่ 4: บอร์ด 2 ต่อเข้าโมดูล Isolated สำหรับ Inverter Li2 (BMS Port)
* **ฝั่งลอจิก TTL (เข้า ESP32 T-CAN485 บอร์ดที่ 2):**
  * `RXD` ของโมดูล $\rightarrow$ ต่อเข้า **`GPIO 33 (TX)`** (Header H1 Pin 3)
  * `TXD` ของโมดูล $\rightarrow$ ต่อเข้า **`GPIO 32 (RX)`** (Header H1 Pin 4)
  * `VCC` ของโมดูล $\rightarrow$ ต่อเข้า **`5V`**
  * `GND` ของโมดูล $\rightarrow$ ต่อเข้า **`GND`** (Header H1 Pin 2 หรือ 12)
* **ฝั่งบัส RS485 (เข้าช่อง RJ45 พอร์ต BMS ของ Inverter):**
  * **A+** $\rightarrow$ RJ45 Pin 5 (MaxSky / Axpert RS485-A+)
  * **B-** $\rightarrow$ RJ45 Pin 3 (MaxSky / Axpert RS485-B-)
  * **GND (Isolated):** RJ45 Pin 8 (BMS GND) เข้ากับช่อง GND ฝั่ง RS485 ของโมดูล

#### ชุดที่ 5: บอร์ด 2 ต่อเข้าโมดูล Isolated สำหรับ Pack 8 (Slave ID: 214 บัสแยก)
* **ฝั่งลอจิก TTL (เข้า ESP32 T-CAN485 บอร์ดที่ 2):**
  * เส้นสายจากโมดูล $\rightarrow$ เสียบเข้า **`Pin 1 (GPIO 25 - TX เฟิร์มแวร์)`**
  * เส้นสายจากโมดูล $\rightarrow$ เสียบเข้า **`Pin 10 (GPIO 18 - RX เฟิร์มแวร์)`**
  * `VCC` ของโมดูล $\rightarrow$ ต่อเข้า **`5V`**
  * `GND` ของโมดูล $\rightarrow$ ต่อเข้า **`GND`** (Header H1 Pin 2 หรือ 12)
* **ฝั่งบัส RS485 (เข้าหัว RJ45 แบตเตอรี่ลูกที่ 8):**
  * **A+** $\rightarrow$ ต่อสายสีส้ม (RJ45 Pin 2)
  * **B-** $\rightarrow$ ต่อสายสีขาว-ส้ม (RJ45 Pin 1)
  * **GND (Isolated):** ต่อสายสีขาว-เขียว (RJ45 Pin 3/6) เข้า GND RS485 ของโมดูล

---

### 🛡️ ขั้นตอนปฏิบัติการขนาน Pack 8 เข้า Busbar ไฟหลัก (คืนนี้)

> [!IMPORTANT]
> ปัจจุบัน Pack 8 เชื่อมต่อการสื่อสาร BMS และคำนวณเข้าสู่ระบบแล้ว แต่ยัง **ไม่ได้ขนานสายไฟ DC Main Busbar เข้าตู้ไฟ** 

**ขั้นตอนการต่อสายกำลังไฟ (DC Power Cables) คืนนี้อย่างปลอดภัย:**
1. **รอให้แดดหมดสนิท (Solar PV = 0W):** ป้องกันไม่ให้แผงโซลาร์ชาร์จกระแสสูงขณะ thao สาย
2. **สลับ Inverter เข้าโหมด SUB (Solar-Utility-Battery):**
   * โหมดนี้ Inverter จะดึงไฟตรงจากการไฟฟ้า (Grid/Utility) มาจ่ายให้บ้าน 100% ทำให้ระบบไม่มีกระแสดึงออกจากแบตเตอรี่
3. **ปิดเบรกเกอร์ DC Battery (สับเบรกเกอร์แบตเตอรี่ลง):** เพื่อตัดไฟจากบัสบาร์ทองแดงหลัก
4. **ตรวจสอบแรงดันไฟฟ้าของ Pack 8 เทียบกับแบตลูกอื่น:**
   * ดูจากหน้าจอ HA หรือบอร์ด 108: ตรวจสอบว่าแรงดันของ Pack 8 (ปัจจุบันอยู่ที่ ~50.1V) ใกล้เคียงกับแบตลูกอื่นในตู้ (ไม่ต่างกันเกิน 1.0V) เพื่อป้องกันกระแสถ่ายเทชาร์จหากันรุนแรง (Inrush Current)
5. **ขันสายไฟขั้วบวก (+) และขั้วลบ (-) ของ Pack 8 เข้ากับบัสบาร์ทองแดง:**
   * ขันน็อตให้แน่นหนาตามแรงบิดมาตรฐาน (ป้องกันความร้อนสะสมที่จุดต่อ)
6. **เปิดเบรกเกอร์แบตเตอรี่ลูกเดิม และเปิดเบรกเกอร์ Pack 8 ขึ้น:**
   * แบตเตอรี่ทั้ง 8 ลูกจะขนานแรงดันเข้าหากันอย่างราบรื่น
7. **ปรับโหมด Inverter กลับตามต้องการ (SBU / SUB):** ระบบแบตเตอรี่ความจุรวม 800 Ah (40 kWh) พร้อมใช้งานเต็มรูปแบบครับ

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
