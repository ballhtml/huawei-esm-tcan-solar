# ==============================================================================
# Huawei ESM-48100B1 Solar & Battery Management System
# Dual LILYGO T-CAN485 Architecture (ESPHome + CAN Interconnect + Inverter Bridge)
# ==============================================================================

ระบบบริหารจัดการแบตเตอรี่ลิเธียมฟอสเฟต **Huawei ESM-48100B1** (48V 100Ah จำนวน 4–8 ลูก) ร่วมกับอินเวอร์เตอร์ไฮบริด/ออฟกริด และ Home Assistant โดยใช้บอร์ดไมโครคอนโทรลเลอร์ **LILYGO T-CAN485 (ESP32)** จำนวน 2 บอร์ดเชื่อมต่อกันด้วย **CAN Bus (TWAI)**

---

## 🏗️ สถาปัตยกรรมของระบบ (Dual-Board Architecture)

```
 [ Huawei ESM-48100B1 BMS ]
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
   ├─ [Pylontech Protocol Emulator v6-PRO] ──> [RS485 Isolated Blue (GPIO 33/32)] ──> [ Solar Inverter ]
   └─ [MicroSD Data Logger (Port 8080)]
```

---

## ⚡ แก้ปัญหาสำคัญทางฮาร์ดแวร์ & เฟิร์มแวร์ (Proven Fixes)

1. **การแก้ปัญหากราวด์ลูป & หลุด Error 04 / 4b ตอนชาร์จแรง (>60A / 3000W):**
   * **Signal Ground Fix:** ต่อสาย BMS Signal Ground (สายขาวเขียว RJ45 Pin 3/6) จากพอร์ตแบตเตอรี่เข้ากับกราวด์ฝั่ง Isolated ของโมดูล RS485 เพื่อป้องกัน Common-Mode Voltage เกิน $\pm7\text{V}$
   * **Dedicated Isolated Module:** ห้ามใช้ชิป RS485 Onboard (MAX13487) เนื่องจากไม่มี Isolation กราวด์ ให้ใช้โมดูลภายนอกแบบมีชิปแยกกราวด์ (Isolated RS485) เท่านั้น
2. **Pylontech Emulator V6-PRO:**
   * แปลงสตริงข้อมูลโมเดล/ผู้ผลิตให้เป็น **Hex-Encoded ASCII** 100% ตามข้อกำหนดโปรโตคอล Pylontech
   * เพิ่ม **High-EMI Noise Immunity Filter** กรองสัญญาณรบกวนคลื่นแม่เหล็กไฟฟ้าตอนอินเวอร์เตอร์ชาร์จกระแสสูง ป้องกัน Serial Buffer Drop
   * ระบบ **Soft Current Throttling & Limp-home:** ส่งกระแสชาร์จขั้นต่ำช่วงสัญญาณสะดุด ป้องกันอินเวอร์เตอร์สั่งตัด BMS Lost (4b)

---

## 📁 โครงสร้างโปรเจกต์ (Project Directories)

* `huawei-esm-t-can485-8pack.yaml` — เฟิร์มแวร์ **Board 1 (Battery Master)** อ่านแบตเตอรี่ Pack 1–4 และบรอดแคสต์ข้อมูลผ่าน CAN Bus
* `project_v2_inverter_bridge/` — โปรเจกต์ชุดที่ 2 สำหรับ **Board 2 (Inverter Gateway & Logger)**
  * `inverter_bridge_v2.yaml` — คอนฟิก ESPHome สำหรับ Board 2
  * `components/pylontech_emulator/` — Pylontech BMS Emulator v6.0.0-PRO
  * `components/sd_logger/` — MicroSD Card Logger พร้อม Web Download Server
* `backup_proven_20261006/` — ชุดสำรองไฟล์ที่ผ่านการทดสอบและพิสูจน์แล้วว่าใช้งานได้จริง

---

## 🔌 แผนผังการต่อสาย CAN Bus ระหว่างบอร์ด 1 และ 2

ใช้สาย LAN คู่บิดเกลียว (Twisted Pair) เข้าช่องขันน็อตเทอร์มินอลสีเขียวบนบอร์ด:
* **ขาวส้ม + ส้ม** $\rightarrow$ เข้าช่อง **`CAN_H`**
* **ขาวน้ำเงิน + น้ำเงิน** $\rightarrow$ เข้าช่อง **`CAN_L`**
* **ขาวเขียว + เขียว** $\rightarrow$ เข้าช่อง **`G` (GND)**
