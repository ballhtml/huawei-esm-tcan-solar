# คู่มือวิศวกรรมปฏิบัติการ: ระบบ Inverter EM11000 VIP Cloud Transparent Bridge บน Home Assistant (24/7)

> **บันทึกทางเทคนิค:** รวบรวมกระบวนการเชื่อมต่อและดักจับข้อมูล Inverter EM11000 ผ่านปลั๊ก Wi-Fi Datalogger สู่ Home Assistant (Native In-Memory Asyncio) พร้อมสตรีมขึ้น VIP Cloud ของจีน (Port 502) แบบคู่ขนาน 100% โดยไม่ต้องเปิดเครื่องคอมพิวเตอร์ทิ้งไว้

---

## 1. ที่มาและสถาปัตยกรรมระบบ (System Architecture)

### 1.1 ปัญหาเดิมและการค้นพบครั้งสำคัญ (The Port 502 Breakthrough)
* **Inverter EM11000** (MaxSky / ANENJI / PowMr Clone, Model Code `0x7300` / `29440`) ปกติส่งข้อมูลขึ้นเซิร์ฟเวอร์จีนผ่านปลั๊ก Wi-Fi Datalogger (`PN: <YOUR_PLUG_PN>`)
* **ข้อผิดพลาดในอดีตและการแก้ปัญหา:** 
  * การเชื่อมต่อพอร์ตแบบดั้งเดิมของ EyBond Cloud ใช้พอร์ต `18899` (`vip1.eybond.com:18899`) สำหรับรับข้อมูลสตรีม DTU ต่อเนื่อง
  * บริดจ์รุ่นใหม่รองรับการต่อพอร์ตมาตรฐานสากลและ Auto-Recovery อัตโนมัติ

### 1.2 โครงสร้างระบบปัจจุบัน (ทำงาน 24/7 บน Home Assistant)

```mermaid
flowchart TD
    subgraph HARDWARE["ฮาร์ดแวร์จริง"]
        INV["Inverter EM11000<br/>(Pure Modbus RTU 9600 8N1<br/>Slave ID: 1)"] <-->|RS232 Bus| PLUG["Wi-Fi Datalogger Plug<br/>IP: <PLUG_IP><br/>Port: 8899 TCP / 58899 UDP"]
    end

    subgraph HA_HOST["Home Assistant (<HA_IP>)"]
        PLUG <-->|TCP Port 8899| BRIDGE["EM11000 Inverter Bridge<br/>(custom_components/em11000_bridge)<br/>Guarded UDP Watchdog"]
        BRIDGE -->|0ms In-Memory Update| ENTITIES["HA Sensor Entities<br/>(solar, battery, load, grid)"]
    end

    subgraph WAN_CLOUD["คลาวด์ต่างประเทศ (EyBond VIP Cloud)"]
        BRIDGE <-->|TCP Port 18899 Direct Pass-Through| CLOUD["vip1.eybond.com:18899<br/>(47.239.230.129:18899)<br/>รอบดึงความเร็วสูง 🚀"]
        CLOUD <--> SMARTESS["SmartESS App / DESS Monitor"]
    end
```

---

## 2. รายการอุปกรณ์และพารามิเตอร์เครือข่าย

* **Inverter:** EM11000 (Model Code `0x7300`, Slave ID 1, 9600 8N1)
* **Wi-Fi Datalogger Plug:** รองรับปลั๊ก EyBond / MaxSky ทุกรุ่น (DevCode `258`, พอร์ต 8899 TCP / 58899 UDP)
* **Home Assistant Server:** พอร์ต 8899 Native Listener พร้อม Auto-Detect IP เครื่องอัตโนมัติ
* **China VIP Cloud Endpoint:** `vip1.eybond.com:18899`
* **สถานะความทนทาน:** มี Guarded UDP Auto-Recovery ตรวจจับตลอด 24 ชม. เมื่อเราเตอร์รีบูต ปลั๊กจะดึงกลับมาหา HA เองภายในไม่กี่วินาที โดยไม่ชนกับทราฟฟิกข้อมูล

---

## 3. กลไกการทำงานของ Component (`custom_components/em11000_bridge`)

### 3.1 Transparent Pass-Through & In-Memory Intercept
1. เมื่อปลั๊กต่อเข้ามาที่ `0.0.0.0:8899` บน Home Assistant:
   * HA จะเปิด Socket Upstream ไปยัง `vip1.eybond.com:502`
   * สตรีมแพ็กเก็ตจากคลาวด์ส่งตรงไปยังปลั๊ก (คำสั่งอ่าน Modbus FC=4)
   * เมื่อปลั๊กส่งค่ากลับมา HA จะส่งต่อไปยังคลาวด์ทันที (เพื่อให้ SmartESS อัปเดตทุก 5 วินาที)
   * พร้อมทั้ง **แกะค่าไบนารี Modbus ในแรมสดๆ** เพื่ออัปเดตเซนเซอร์ของ Home Assistant แบบ Real-time (0ms Latency)

### 3.2 Guarded UDP Watchdog (ป้องกัน Socket Reset)
* ยิงคำสั่ง `set>server=<HA_IP>:8899;\r\n` ไปที่พอร์ต UDP `58899` **เฉพาะตอนที่ไม่ได้ต่อ Socket เท่านั้น**
* เมื่อต่อติดแล้ว จะหยุดส่ง UDP ทันที เพื่อป้องกันไม่ให้ตัวปลั๊ก Reset TCP Socket ตัวเอง

---

## 4. ตาราง Modbus Register ที่ใช้งานจริง (Verified 100%)

| จุดวัดข้อมูล | Register (Dec) | Register (Hex) | ตัวคูณ (Scale) | ชนิดข้อมูล | หน่วย | คำอธิบาย |
|---|:---:|:---:|:---:|:---:|:---:|---|
| **Battery SOC** | `198` / `280` | `0x00C6` / `0x0118` | $\times 1$ | Unsigned 16-bit | `%` | เปอร์เซ็นต์แบตเตอรี่ |
| **Battery Voltage** | `277` | `0x0115` | $\times 0.1$ | Unsigned 16-bit | `V` | แรงดันแบตเตอรี่รวม |
| **Battery Current** | `278` | `0x0116` | $\times 0.1$ | Signed 16-bit | `A` | กระแสชาร์จ (+) / ดึงออก (-) |
| **Battery Power** | `279` | `0x0117` | $\times 1$ | Signed 16-bit | `W` | กำลังวัตต์แบตเตอรี่ |
| **Total PV Power** | `302` | `0x012E` | $\times 1$ | Unsigned 16-bit | `W` | กำลังผลิตแผงโซลาร์รวม |
| **AC Output Voltage**| `338` | `0x0152` | $\times 0.1$ | Unsigned 16-bit | `V` | แรงดันไฟขาออก 230V |
| **Grid Voltage** | `342` | `0x0156` | $\times 0.1$ | Unsigned 16-bit | `V` | แรงดันไฟหลวงขาเข้า |
| **Active Power** | `346` | `0x015A` | $\times 1$ | Unsigned 16-bit | `W` | กำลังไฟจ่ายโหลดจริง |
| **Load Percentage** | `348` | `0x015C` | $\times 1$ | Unsigned 16-bit | `%` | เปอร์เซ็นต์โหลดของอินเวอร์เตอร์ |
| **Inverter Temp** | `305` | `0x0131` | $\times 1$ | Unsigned 16-bit | `°C` | อุณหภูมิโมดูลอินเวอร์เตอร์ |
| **PV Temp** | `281` | `0x0119` | $\times 1$ | Unsigned 16-bit | `°C` | อุณหภูมิโมดูลชาร์จโซลาร์ |

---

## 5. การเปิดใช้งานและการกู้คืนระบบ (Disaster Recovery)

### 5.1 การเปิดใช้งานใน `configuration.yaml`
```yaml
# EM11000 VIP Cloud Transparent Bridge & High-Speed Inverter Telemetry
em11000_bridge:
```

### 5.2 การกู้คืนเมื่อเปลี่ยนเราเตอร์หรือ IP เปลี่ยน
หากปลั๊ก Wi-Fi ไม่ยอมต่อเข้ามาที่ HA:
1. ยิงแพ็กเก็ต UDP สั่งชี้เป้ามาที่ HA ด้วยคำสั่ง:
   ```text
   set>server=<HA_IP>:8899;\r\n
   ```
   ไปยัง IP `<PLUG_IP>:58899` (หรือ Broadcast `255.255.255.255:58899`)
2. ตัวปลั๊กจะสลับมาเชื่อมต่อ HA พอร์ต 8899 ทันที และระบบบริดจ์จะส่งข้อมูลขึ้น VIP Cloud ต่อเนื่องอัตโนมัติ
