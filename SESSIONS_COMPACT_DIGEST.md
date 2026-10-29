# SESSIONS_COMPACT_DIGEST (สาระสำคัญรวมทุกเซสชัน)
> **สถานะ:** บันทึกสรุปกระชับสำหรับให้ Agent และผู้พัฒนาดึงบริบทไปใช้งานซ่อมแซม/พัฒนาต่อได้ทันที โดยไม่ต้องโหลดประวัติแชทยาว

---

## 1. Battery Master & Ground Loop Isolation (Board 1: IP 192.168.8.108)
* **ฮาร์ดแวร์:** LILYGO T-CAN485 ESP32 + โมดูล Isolated TTL-to-RS485 (2Mbps) 2 ตัว
* **พินเชื่อมต่อ:**
  * โมดูล 1 (Packs 1, 2, 3, 5, 6, 7): `GPIO 33 (TX)` / `GPIO 32 (RX)`
  * โมดูล 2 (Pack 4 - บัสแยก Address 214): `GPIO 18 (TX)` / `GPIO 25 (RX)`
* **จุดแก้ปัญหาสำคัญ:**
  * ชิป Onboard (MAX13487) ไม่มี Galvanic Isolation หลุด Error ตอนชาร์จพีค >60A $\rightarrow$ แก้โดยใช้โมดูล Isolated ภายนอก และต่อสาย Signal Ground (RJ45 Pin 3/6) เข้า GND โมดูล
  * ห้ามยุ่งกับสวิตช์ DIP ของแบตเตอรี่หน้างาน $\rightarrow$ แก้โดยสร้างบัส Modbus ที่สองแยกเฉพาะ Pack 4

---

## 2. Inverter Bridge & Pack 8 Bridging (Board 2: IP 192.168.8.109)
* **ฮาร์ดแวร์:** LILYGO T-CAN485 ESP32 + โมดูล Isolated RS485 2 ตัว
* **พินเชื่อมต่อ:**
  * โมดูล Inverter BMS Port: `GPIO 33 (TX)` / `GPIO 32 (RX)` $\rightarrow$ เข้า RJ45 Pin 5 (A+), Pin 3 (B-), Pin 8 (GND)
  * โมดูล Pack 8 (บัสแยก Address 214): แมปขาสลับในเฟิร์มแวร์ ESP32 GPIO Matrix: `tx_pin: GPIO25` (Header H1 Pin 1) / `rx_pin: GPIO18` (Header H1 Pin 10)
* **การเชื่อมต่อระหว่าง Board 1 <-> Board 2:**
  * ผ่าน Onboard CAN Bus (TWAI 500kbps): `GPIO 27 (TX)` / `GPIO 26 (RX)`
  * Board 109 ส่ง Pack 8 ผ่าน CAN Frame `0x358` ไป Board 108
  * Board 108 ส่งสรุประบบรวมผ่าน CAN Frames `0x355` / `0x356` มา Board 109
* **Pylontech Emulator v6-PRO:**
  * จำลองโปรโตคอล Pylontech BMS (โหมด Li2) แปลงชื่อสตริงเป็น Hex-Encoded ASCII
  * เพิ่ม Dynamic Voltage Step-Down, Anti-Hunting Sag Filter และ Soft Throttling ตัดปัญหา Inverter แจ้ง Error 04 / Warning b4

---

## 3. Inverter EM11000 Local Transparent Proxy
* **สถาปัตยกรรม:** `em11000_dual_proxy.py` รันบน Synology / Home Assistant (`192.168.8.209`)
* **การทำงาน:**
  * ปลั๊ก Wi-Fi Datalogger เดิม (`192.168.8.166`) ถูกเปลี่ยนปลายทางเซิร์ฟเวอร์ผ่านคำสั่ง UDP 58899 (`set>server=...`)
  * Proxy รับ TCP พอร์ต 8899 ดึงค่า Modbus RTU (Slave ID 1, 9600 8N1) ทุก 2.0 วินาที แล้ว Push เข้า Home Assistant REST API
  * Proxy ส่งสำเนาข้อมูล (Mirror) ต่อไปยังคลาวด์จีน `dtu_ess.eybond.com:18899` ทุก 5.0 วินาที ทำให้แอป SmartESS/DESS ทำงานได้ปกติ
* **การต่อบอร์ด ESP32 ตรงในอนาคต (ถ้าทำ):**
  * ใช้บอร์ดแปลง SP3232 แบบแถบยาว (VCC 3.3V, GND, TxIN เข้า GPIO17, RxOUT เข้า GPIO16)
  * หากใช้ B0505S แยกไฟ ต้องมีโมดูลแยกสัญญาณแม่เหล็ก ADuM1201 คั่นกลางเสมอ

---

## 4. สถานะแบตเตอรี่และการเงิน Home Assistant
* **สถานะแบตเตอรี่:** 8 Packs (800 Ah / 38.4 kWh / 120 เซลล์) ขนานสายไฟ DC Main Busbar สมบูรณ์ 100%
* **แดชบอร์ด Lovelace 3 แท็บ:**
  * Tab 1: `/home-energy` (ภาพรวมพลังงาน, Sunsynk Flow, บิลค่าไฟ PEA TOU หักค่าไฟฟรี 50 หน่วย)
  * Tab 2: `/home-energy/cells` (เมทริกซ์ 120 เซลล์, Cell Drift Delta mV, SOH, Cycle kWh)
  * Tab 3: `/home-energy/inverter-setup` (ปุ่มสั่งเปลี่ยนโหมด SBU/SUB, กระแสชาร์จ และแรงดันตัดวงจร)
