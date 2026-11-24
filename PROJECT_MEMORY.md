# ANTIGRAVITY MASTER SYSTEM MEMORY (SHARED BRAIN)
> **Permanent Cross-Project Knowledge Base & System Architecture**
> Shared between NAS Web IDE (`\\SA6400\docker\antigravity\memory\`) and Workstation PC (`Z:\modbus\`).
> Auto-loaded on session start to eliminate amnesia across context compaction and device switches.

---

## 1. Solar & Battery ESS Infrastructure (Active Production)

### Hardware Node Topology
| Node Name | Hardware Platform | IP Address | Primary Interface / Connection | Role & Behavior |
| :--- | :--- | :--- | :--- | :--- |
| **BMS Master (Node 108)** | LilyGO T-CAN485 ESP32 | `192.168.8.108` | Wi-Fi (`Home_Ball`) + Dual RS485 | Master BMS: Polls 8x Huawei ESM-48100B1 (120 cells), balancing states, ESP-NOW Primary |
| **Inverter Bridge (Node 109)** | LilyGO T-CAN485 ESP32 | `192.168.8.109` | Wi-Fi (`Home_Ball`) + MAX3232 RS232 | Inverter Bridge: RS232 to EM11000 Inverter, dynamic CCL/CV clamping, ESP-NOW Failover Backup |
| **Solar Inverter (EM11000)** | MaxSky EM11000 11kW Dual MPPT | `192.168.8.166` | Wi-Fi Stick (Dessmonitor Logger) | MaxSky 11kW Off-grid / Hybrid Inverter (devcode 6515 / ANENJI / EASun platform, SN: 92B32409100334), RS232 port 9600 8N1, Modbus registers 0x0100..0x0180 |
| **Home Assistant (HA)** | Green / Server VM | `192.168.8.209` | LAN Port 8123 | HA Core 2026.10.4, `ha-dessmonitor` v2.6.0, Solar Energy Lovelace Dashboard |
| **Synology NAS (SA6400)** | Intel i5-8400 / B365-PLUS / 16GB RAM | `192.168.8.158` | LAN DSM Port 5000 / Web IDE 8443 | XPEnology DSM 7.2 (Arc Loader), 24/7 Agent Server, Open WebUI (3000), Transmission (9091) |
| **Workstation PC** | Windows 11 PC | `192.168.8.161` | LAN 2.5G | Local dev station, ESPHome compilation, Antigravity harness |

### Battery Bank Constraints & Specs (8x Huawei ESM-48100B1)
- **Total Capacity:** 800 Ah / 38.4 kWh (15 LiFePO4 cells per pack = 120 individual cells monitored).
- **Current Operational Status (Active Standard):**
  - **All 8 packs are fully active and online in parallel** on heavy-duty DC copper busbars (Total: **800 Ah / 800A nominal capacity**).
  - **CRITICAL AGENT INVARIANT:** NEVER refer to the home ESS as 300 Ah, 3 packs, or 400 Ah in any calculations, sizing, or discussions. Earlier 3-pack and 4-pack references were temporary bench tests during firmware debugging; the live household system is strictly **800 Ah (8x 100 Ah packs)**.
- **Physical Connection:** All 8 packs permanently connected in parallel to common heavy-duty DC copper busbars.
- **Geographic Location (Permanent):** จังหวัดเลย (Mueang Loei District, Lat: 17.59768, Lon: 101.71790). Solar forecasts must always query Loei coordinates, NOT Bangkok.
- **Three-Tier File Lifecycle Standard (Permanent Rule):**
  - **Tier 1 — Development (`dev/` — ver dev / ทดสอบแก้ bug):** `dev/*-dev.yaml`, `dev/*.h`, `dev/components_v4/` (uses `Home_Ball` + isolated `*_dev` build paths, ignored by `.gitignore`). All bug fixes, audits, and unverified changes are developed and compiled/tested here first without sharing C++ headers with Production/Public.
  - **Tier 2 — Production (`*-prod.yaml` — ver ที่ใช้อยู่จริง):** Mirrors the known-good firmware currently running live on household hardware (`Home_Ball` / `99999999` and static IPs `192.168.8.108`, `109`, `110`, ignored by `.gitignore`). **NEVER overwrite `*-prod.yaml` or root C++ with unverified Dev edits** — promote from `dev/` only after live verification and user approval.
  - **Tier 3 — Public (`*.yaml` — สำหรับแจกบน GitHub):** Clean open-source distribution tracked in git (`YOUR_WIFI_SSID` / `YOUR_WIFI_PASSWORD`). Only update during intentional releases after verification; never commit `*-prod.yaml`, `*-dev.yaml`, or `dev/`.
- **Autonomous Equalizer (Node 108 - Gen 6 v6.6.0):** Uses `HuaweiSmartBalancer` FSM (`huawei_smart_balancer.h`, 38s epoch sync, SoC-headroom weighted fairness, +5A/epoch stepped release, closed-loop compliance re-assert via `reassert_disch`/`reassert_chg`) across RS485 Packs 1–7 (`exec_huawei_bms_equalizer_slot`) and remote Pack 8 (`CAN 0x35F` + `UDP 18888`). Wake RAM unlock refresh (`0x100B=1000`, `0x100D=1000`, plus `0xB798=0` only for Batch 3+ `idx>=4`) uses 2-epoch Mode != 3 debounce and monotonic `180s -> 300s -> 600s` backoff; never issues `0x000E=3` or cyclical `0x101B` EEPROM writes.
- **Manual Wake Buttons Policy:** Both wake_pack2_bms / wake_all_bms scripts and buttons on Node 108 are permanently remarked out (#) to prevent accidental manual gate runaway.
- **Critical Safety Rules:**
  - **NEVER** instruct or require changing DIP switches on active packs without explicit user consent.
  - **Pack 4 Isolation:** Pack 4 hardware address is `214` (`0xD6`). Kept on dedicated isolated RS485 UART channel on Node 108 to eliminate bus collisions with standard IDs (1, 2, 3, 5, 6, 7, 8).
- **Safety Standby Reserve & Cutoff Floor (Synchronized across Firmware & HA - Nov 2026):**
  - **Standby Cutoff Floor:** Raised to **30.0% SoC** (recover **35.0%**) and 48.0V across ESPHome Node 108 & 109 (`dev/`) to preserve extra backup for long PEA outages and prevent low-voltage Mode-0 BMS sleep/shutdown (`idle_sleep_guard` / `RESERVE_CUTOFF` keepalive keeps `0x100D=1000` awake while preserving `0x100B=0`).
  - **HA Usable Reserve Calculation:** `sensor.battery_shutdown_soc_setting = 30%`, usable formula = `(soc - 30) / 100 * total_kwh`, emergency reserve = `30%` (`11.52 kWh` out of `38.4 kWh`).
  - **HA Lovelace Cards:** `custom:sunsynk-power-flow-card` `shutdown_soc = 30`, `custom:solar-bar-card` = `พร้อมจ่าย (หัก 30% สำรอง)`, `shutdown_soc_offgrid = 20`.
- **Charging & Protection Thresholds:**
  - Float Voltage: 53.5V (~3.56V/cell)
  - Absorption / Max Voltage: 53.8V (~3.58V/cell)
  - Under-Voltage Cutoff (Off-grid Surge Protected): 46.8V (~3.12V/cell / 18% SoC), Minimum Cell Floor: 3.050V (prevents kettle & portable AC inverter trip)
  - Dynamic CCL Clamping: Maximum 140A, throttled down dynamically when highest cell voltage > 3.45V.
- **Tri-Redundant Failover:**
  - Node 108 & 109 communicate battery telemetry directly over ESP-NOW heartbeats (sub-millisecond latency).
  - If Wi-Fi fails, ESP-NOW maintains live battery safety and dynamic charging limits.
  - If ESP-NOW fails, Node 109 automatically falls back to safe charging mode (50A CCL limit).

---

## 2. NAS Server & Local AI Infrastructure (`192.168.8.158`)

- **Host Machine:** Intel Core i5-8400 (6 Cores, 2.80GHz - 4.00GHz), ASUS PRIME B365-PLUS, 16GB DDR4 RAM, 750W PSU.
  - **Mainboard Specs (ASUS PRIME B365-PLUS):** 4× DDR4 DIMM (max 64GB, up to 2666 MHz), 1× PCIe 3.0 x16 (CPU x16) + 1× PCIe 3.0 x16 (PCH max x4) + 4× PCIe x1, 2× M.2 (M.2_1 SATA/PCIe x2 + M.2_2 PCIe x4) + 6× SATA 6Gb/s (M.2_1 in SATA mode disables SATA_2), Intel VT-d, Above 4G Decoding, CSM toggle, Resizable BAR (BIOS ≥ 2203).
- **Operating System:** XPEnology DSM 7.2 (Model: SA6400) booted via Arc Loader.
- **Container Management:** Synology native **Container Manager** (Docker Compose engine).
- **Running Services:**
  - **Antigravity Web IDE:** `http://192.168.8.158:8443` (Password: `ballhtml`)
    - Configured in `\\SA6400\docker\antigravity\docker-compose.yml`
    - Mounts `AI_Share` and solar codebase directly into the Linux environment.
  - **Open WebUI (Arc AI):** `http://192.168.8.158:3000`
    - Web interface for local/remote LLM chatting.
  - **Transmission Torrent Manager:** `http://192.168.8.158:9091`
    - Automated download manager connected via `transmission-manager` agent skill.
- **Local AI Hardware Expansion Plan:**
  - Planned GPU: NVIDIA GeForce RTX 3060 12GB (budget < 8,000 THB).
  - Purpose: Run local LLMs (Ollama / DeepSeek / Qwen) for autonomous coding, bot execution, and MT5 without recurring API costs.
  - Cloud Fallback: Researched `kodelyx/free-gemini-api` for high-throughput cloud inference.

---

## 3. Financial & Trading Bot Ecosystem (MooSpot & Bitkub)

- **Workspace Path:** `Z:\moospot-dashboard\` (mapped from `\\SA6400\AI_Share\moospot-dashboard\`)
- **Core Architecture:**
  - `engine.py` & `exchange.py`: Bitkub API integration, automated order execution, and balance polling.
  - `logic.py` & `indicators.py`: Technical indicators, trend triggers, and risk management logic.
  - `notifier.py`: Real-time transaction and profit alerts sent to messaging webhooks.
  - Executable Builds: Packaged via PyInstaller (`MooSpot Dashboard v2.04` .. `v3.00.spec`).
- **Strategic Financial Goals:**
  - Bot generates cash flow to offset system upgrades and hardware costs.
  - Revolving credit line managed safely (limit <= 100,000 THB), prioritizing payment cycles around the 3rd-4th of each month.
  - Target constraint: Keep monthly billing installments strictly below 16,000 THB.

---

## 4. Smart Home & Network Infrastructure

- **Home Assistant Server:** `192.168.8.209` (HA Core 2026.10.4)
  - **Config SMB Share:** `\\192.168.8.209\config` — User: `ball` / Password: `ballhtml` (connect via `net use \\192.168.8.209\config /user:ball ballhtml /persistent:yes`)
  - `ha-dessmonitor` v2.6.0: Custom integration polling EM11000 inverter and syncing battery bank states.
  - Lovelace Dashboard: High-density solar cards displaying real-time 8-pack telemetry and 120-cell bar charts.
- **Xiaomi / Mi Smart Home Ecosystem:**
  - Integration Method: `Xiaomi Miot Auto` via HACS.
  - Controls: Fans, air purifiers, smart plugs, air conditioning units, and environmental sensors.
- **Network Routing & Automation:**
  - **Network Router:** Cudy WR11000 Multi-Gigabit Wi-Fi 6 Router (`192.168.8.1`), managed via `Z:\cudy\router.py`.
  - Active Port Forwards on Cudy WR11000:
    - `5000-5001` -> Synology DSM (`192.168.8.158`)
    - `8123` -> Home Assistant (`192.168.8.209`)
    - `9091` -> Transmission Torrent (`192.168.8.158`)
    - `8443` -> Antigravity Web IDE (`192.168.8.158`)
  - Primary Wi-Fi SSID: `Home_Ball` / Password: `99999999`
  - Fallback APs (Emergency recovery only):
    - SSID: `tcan-bridge-ap` / Password: `bms_setup_password`
    - SSID: `tcanesm-ap` / Password: `bms_setup_password`

- **Intelligent Inverter Pump (Prodn / Zhejiang Dafeng) - Home Assistant Integration:**
  - **Device & App:** Intelligent Inverter Pump (App: `INTELLIGENT INVERTER PUMP` v4.2.7, `com.dafeng.prodn`).
  - **Internal Hardware:** High-Flying HF-LPT230 Wi-Fi Module communicating with pump inverter board via 4-pin UART (9600 8N1).
  - **WARRANTY SAFETY INVARIANT (CRITICAL):** NEVER open, solder, or replace the internal HF-LPT230 Wi-Fi module with ESP32 to prevent voiding the manufacturer warranty. All integration must remain strictly non-invasive.
  - **Integration Architecture:**
    - **Primary Path (Cloud REST):** Home Assistant REST Sensor & REST Commands querying `http://<devarea>:8081/pass/getState?mac=<MAC>` every 5s and sending controls via `pass/control?mac=<MAC>&data=<HEX>`.
    - **Telemetry:** Real-time water pressure (`workPressure` bar), target pressure (`setPressure` bar), flow rate (`flow` m³/h), power (`power` W), IPM temperature (`temperature` °C), run state, mode, dry-run alarm (`lackWater`), pipe leak alarm (`leakage`), operating hours, and fault codes (E01..E13).
    - **Control Commands (3-Byte Hex):**
      - Set Target Pressure: `03` + Hex(bar * 100 in Little-Endian) e.g. 2.50 bar = `03fa00`
      - Starting Pressure Ratio: `09` + Hex(0..80%) + `00`
      - Set Mode: `070000` (Refill / 补水), `070100` (Downward / 下抽), `070200` (Upward / 上抽)
      - Refill Timer: `0A0100` (1h), `0A0300` (3h), `0A0600` (6h), `0A0C00` (12h)
      - Toggle Manual/Auto: `080100`
    - **Local Offline Fallback Path:** Router DNS rewrite on Cudy WR11000 (`admin.prodnzk.com` -> HA IP `192.168.8.209`) with lightweight mock API service in HA, eliminating cloud dependency without opening the pump casing.
  - **Source Scripts:** `Z:\modbus\scratch\re\inverter_pump\prodn_ha_integration.py` and `homeassistant_configuration.yaml`.

---

## 5. Software Repositories & Shared File Maps

- **GitHub Repository (Solar ESS):** `https://github.com/ballhtml/huawei-esm-tcan-solar.git` (Current Release: `v4.4.0`)
- **Local SMB Root:** `\\SA6400\AI_Share\` (Mapped as `Z:\`)
  - `Z:\modbus\` -> Solar & Battery ESPHome source code, configs, and production backups
  - `Z:\Antigravity_Agent\` -> Agent workspace, config backup, and memory mirrors
  - `Z:\moospot-dashboard\` -> Bitkub trading bot source code
  - `Z:\HA\` -> Home Assistant integration archives and dashboards
  - `Z:\cudy\` -> Router automation backend
  - `Z:\Agean\` -> Legacy cross-machine bridge archive (Antigravity Bridge)
- **Docker Production Share (SSD Volume 1):** `\\SA6400\antigravity\` (`/volume1/antigravity/`)
  - `docker-compose.yml` -> LinuxServer Code-Server Web IDE configuration
  - `.env` -> Web password (`ballhtml`) and system UID/GID definitions
  - `memory\PROJECT_MEMORY.md` -> Master shared brain file
  - `workspace\.agents\` -> Shared rules, domain guidelines, and installed skills

---

## 6. Recent Production Milestones & Community Upstream (Nov 2026)
- **Release v5.2.0 (Gen 5 Anti-Chatter & Surge Hardening - Nov 2026):**
  - **Anti-Chatter Single-Latch Engine:** Fixed hunting/relay clicking chatter in Huawei BMS packs during afternoon solar/load transitions via single-latch g_eq_last_mode_sent gating, requiring genuine sleeping_m2 > 0, and expanding polling interval to 30s.
  - **Grid Standby Safety Floor:** Synchronized household standby cutoff to 25% SoC / 48.0V across ESPHome Node 108/109 and Home Assistant (attery_shutdown_soc_setting = 25%, usable energy calculation (soc - 25) / 100 * total_kwh).
  - **Off-Grid Surge Hardening Floor:** Elevated emergency off-grid cutoff from 46.0V to 46.8V (~18% SoC) and cell floor to 3.050V on both the EM11000 inverter and pylontech_emulator.h to provide surge headroom against kettle and portable AC compressor inrush currents.
  - **Lovelace Real-Time Load Sharing:** Updated charge threshold to p.i >= 0.3A for active green charging indicator across all 8 parallel packs.


- **ha-dessmonitor v2.6.0 (Andreas Glaser):** Official release merged Devcode 6515 (Maxsky EM11000 11kW Dual-MPPT, Eybond WiFi logger FW 3.6.6.6) with full credit to @ballhtml (Issue #57).
- **Issue #71 (Groove-max / ha-eybond-local):** Delivered 15-hour soak test empirical proof (em11000_15h_soak_test.txt, 6,365 events) demonstrating 2,209 cloud EOF cycles handled with 2,207 auto-reconnects (99.91% success) and zero local telemetry dropouts.
- **Free Gemini API Engine (192.168.8.161:8001):** Active 5-account Google pool running via Edge profiles with WebSocket cookie auto-sync (ws://127.0.0.1:9226), providing 24/7 unlimited rotation of gemini-3.8-flash-thinking-medium and gemini-3.1-pro.
- **NAS Antigravity Studio (192.168.8.158:8443):** Live on SSD Volume 1 with left activity bar enabled, Continue.dev pre-configured with local Free Gemini models, and Open WebUI active on port 3000.


---

## 7. Global Multi-Agent Skills Ecosystem & NAS AI Hub (Nov 2026)

- **Total Synchronized Skills:** 118 verified skills deployed symmetrically across Workstation PC and Synology NAS (192.168.8.158).
- **Skill Storage Mirrors:**
  - Workstation Central Library: C:\Users\Administrator\.skillshub\
  - PC Harness Deployments: .gemini\config\skills\, .claude\skills\, .codex\skills\, z:\modbus\.agents\skills\
  - Synology NAS Container Workspace: /config/workspace/.agents/skills (\\SA6400\antigravity\workspace\.agents\skills)
  - Synology NAS Container User Home: /config/.agents/skills, /config/.skillshub, /config/.claude/skills, /config/.codex/skills, /config/.gemini/config/skills
- **Autonomous Knowledge Base:** SKILLS_INVENTORY.md deployed to workspace and memory roots for instant context indexing by Continue.dev, Open-WebUI, and local LLMs.
- **Skill Doctor Audit Grade:** Overall A+ (97%) across 47 real sessions (Efficiency 90%, Code Quality 100%, Procedure Compliance 99%, Verbosity 100%, Skill Coverage 100%).
- **Hardened Rules:** test-driven-builder patched with PowerShell command isolation (no && chaining) and pre-flight module skeleton verification.

### 7.1 Elephant-Goldfish Model (EGM), Multi-Agent Teamwork & Master Trigger Mapping
- **Origin & Purpose:** Derived from Google's open-source framework and Dave Rensin's architecture (*Elephants, Goldfish, and the New Golden Age of Software Engineering*). Eliminates conversational blind spots, confirmation bias, and unstated assumptions during architecture design.
- **Master Unified Pipeline (`/auto` / `จัดเต็ม`):**
  - **Single Umbrella Command:** `/auto [task]` หรือ `"จัดเต็ม [งาน]"` (รวมงานวิเคราะห์, ตรวจโค้ดทั้งโฟลเดอร์, วางสเปก EGM, เขียนโค้ด, และเทส ครบจบในคำเดียว)
  - **Built-in Zero-Token Invariant & Tooling Suite:**
    - แชตหลักห้ามดูดไฟล์โค้ดทั้งโฟลเดอร์หรือ log ยาวๆ เข้าแชตเด็ดขาด โดยจะส่งรายชื่อไฟล์ไปให้ `agy-worker-1..4` บน NAS Docker อ่านตรงจากดิสก์ (`/workspace/...`) ทันที แชตหลักอ่านเฉพาะ `summary.md` เท่านั้น (Zero Main Context Bloat)
    - **Code Compression (Repomix + Tree-sitter):** ใช้ `repomix_compress.py` สกัดเฉพาะ AST signatures (ตัด comments, empty lines, function bodies) ลดโทเคนลง >80% ก่อนส่งเข้าโมเดล
    - **Clean Web Ingestion (Defuddle):** ใช้ `defuddle_clean.py` คลีนหน้าเว็บ/Datasheet/ฟอรัม ตัด ad/nav เหลือ Markdown ล้วน ป้องกันบริบทบวม
    - **Visual Architecture (JSON Canvas 1.0):** ใช้ `canvas_builder.py` สร้างไดอะแกรม `.canvas` แบบแม่นยำ ไม่ต้องร่าง JSON ด้วยมือ
  - **Aliases:** `/team`, `/all`, `/swarm`, `/egm`, `"ทีม..."`, `"ให้ทีม..."`, `"ช่วยกัน..."`, `"รุมทำให้จบ..."` ทั้งหมดวิ่งเข้า Master Pipeline เดียวกันนี้โดยอัตโนมัติ ไม่มีการแยกคำสั่งซ้ำซ้อน
- **Role Mapping Across Hardware (Autonomous 4-Phase Pipeline):**
  - **Phase 1 — 🐘 The Elephant (Long-Horizon Planner & Autonomous Lead):** Main Antigravity Session (Main Pro Account). Holds deep project history, user preferences, and system invariants. Brainstorms and drafts formal specifications (`spec.md` / `design_draft.md`) **without writing implementation code**, and **autonomously assigns the optimal worker model** per task in `tasks.json` without asking the user (`gemini-4-argon-medium` for fast scans/tests, `gemini-4-hydrogen-medium` for hard coding/architecture, `claude-sonnet-5-5-medium` for cross-family fail-safe audits; avoids retiring `3.8` defaults).
  - **Phase 2 — 🐟 The Goldfish (Stateless Adversarial Reviewers):** The 4x `agy-worker-1..4` Docker containers running in Arc Container on Synology NAS (`192.168.8.158`) dispatched via `vm_queue.py batch`:
    - **Zero Context Bleed:** Workers are 100% stateless with zero session memory; they read ONLY the raw `spec.md` and referenced codebase.
    - **Zero Quota Burn:** Consumes 0% of Main AGY session quota.
    - **Council of Goldfish (4 Parallel Audit Perspectives):**
      - *Worker 1 (Comprehension & Flow):* Validates if an outsider can understand and execute the spec without oral tradition.
      - *Worker 2 (Architecture & Performance):* Audits timing, memory overhead, concurrency, and hardware limits (e.g. CAN/Modbus busload).
      - *Worker 3 (Security & Fail-safes):* Audits edge-case recovery, state-machine deadlocks, and defensive validation.
      - *Worker 4 (Blind Spots & Missing Specs):* Identifies unstated assumptions, ambiguous parameters, and test gaps.
  - **Phase 3 — ⚡ Swarm Parallel Implementation:** Workers on NAS divide module implementation and unit test construction across 4 parallel threads.
  - **Phase 4 — 🧑‍✈️ Lead Quality Gatekeeper & Delivery:** Main agent aggregates diffs from `summary.md`, verifies test evidence, checks safety invariants, and delivers complete result to user.
- **Scope of Application:**
  - **Prime Domains:** Reverse Engineering (REA / protocol analysis / firmware disassembly where confirmation bias is fatal), new multi-module subsystems, and mission-critical hardware controllers (e.g. Huawei R4875G1 CAN charger integration).
  - **Fast-Track Exemption:** Never enforce EGM on small bug fixes, UI adjustments, or single-line config tweaks (abides by Poteto Mode & The Laziness Protocol).


---

---

## 8. Huawei SMU02C & Battery Commissioning Hardware Reference

- **Comprehensive Manual:** `HUAWEI_SMU02C_ESM48100_PINOUT_SERVICE_GUIDE_TH.md` (preserved in `Z:\modbus\` and `\\SA6400\antigravity\workspace\`).
- **Hardware Pinout (110-Pin Hardmetric Connector on SMU02C):**
  - **48V- (GND):** Row 1 (Top), Columns 1 & 2
  - **48V+ (DC 42V–58V):** Row 5 (Bottom), Columns 1 & 2
  - **CAN_L:** Top row, immediately to the left of the center alignment notch
  - **CAN_H:** Top row, immediately to the right of the center alignment notch
  - **Front Panel FE (LAN):** 10/100M RJ45 connected directly to LAN for embedded WebLMT Web Server.
- **Default Network & Credentials:**
  - **Web URL:** `https://192.168.0.10` (Client PC static IP: `192.168.0.11 / 24`)
  - **Web Admin:** Username: `admin` / Password: `Changeme` (Fallback: `Changeme_123`, `Admin@123`)
  - **LCD Screen Password:** `000001`
  - **Mobile Site Energy App:** SSID: `RT2860AP`, Static IP: `192.168.8.2`, User: `liveapp` / Pass: `Changeme_123`
- **Tail Plug (尾插 / 转接板):** Available as bare PCB adapter (~20-80 RMB / 100-400 THB) breaking out 48V power and CAN bus terminals to RJ45 (standard T568B straight to battery `COM-IN`), bypassing the expensive 6,000 THB full test box.
- **Service Operations:** Clear latent EEPROM alarms, lift 40A/50A derating back to 100A (1.0C), resolve DIP ID 214 conflicts on Packs 4 and 8, and enable remote CAN-over-IP diagnostics via ESP32 bridge.


---

## 9. Inverter Real-Time Clock (RTC) & Temporal Controls (Devcode 6515)
- **Target Field ID:** `sys_eybond_read_95` (`Inverter Time`).
- **Calendar String Format:** Literal `YYYY-MM-DD HH:MM:SS` (identical to 6544's `sys_eybond_read_44023`).
- **HA Live Sync Button:** Added `button.home_energy_em11000_sync_inverter_clock` to `custom_components/dess_solar/button.py`.
- **URL Encoding Fix:** Fixed space character serialization in `custom_components/dess_solar/api.py` using `urllib.parse.quote_plus` and `yarl.URL(url, encoded=True)`.
- **Verified Empirical Readback:** On 2026-11-03 12:28:52, `button.press` successfully pushed current Bangkok time into inverter RTC, verified via `queryDeviceLastData` returning `'2026-11-03 12:28:52'`.

---

## 10. EM11000 Secondary Priority Scheduling & Overnight Battery Balancing (Nov 2026)

- **Dess Solar API Timeout Hardening:**
  - custom_components/dess_solar/api.py line 564 patched from default 15s to timeout_seconds=40.
  - Root cause: Eybond Wi-Fi data logger cloud round-trip for ctrlDevice parameter changes requires 15-25 seconds. 15s timeout was triggering false HTTP 500 errors.
- **Overnight Grid Pre-Charge Configuration (2026-11-03 Night):**
  - Configured EM11000 Secondary Slot via HA service calls:
    - Secondary Output Priority: SUB (Start 21:00:00, End 06:30:00)
    - Secondary Charging Priority: SNU (Start 21:00:00, End 06:30:00)
    - Charging current: 60A (~3.0 kW), Grid load: ~5.2 kW.
  - Objective: Bring 8-pack Huawei ESM bank from drifted 24% SOC up to ~75-80% before morning, enabling Nov 4 solar PV to reach 100% (54.0V) and complete cell top-balancing.
- **HA One-Shot Morning Automation (06:32 AM):**
  - Entity: automation.solar_cchbkaarchaarcchaebtfuuenfuut_nklaangkhuuen_06_32_n (in automations.yaml).
  - Sequence: 
    1. Secondary Output Priority -> OFF
    2. Delay 25s
    3. Secondary Charging Priority -> OFF
    4. Delay 25s
    5. Charger Source Priority -> OSO (Only Solar)
    6. Delay 25s
    7. Main Output Priority -> SBU
    8. Send rich push notification to mobile devices and create persistent notification in HA with final SOC, remaining Ah, and voltage.
    9. Self-disables via automation.turn_off.
  - Dual redundancy: Agent watchdog background timer (task-10384) set for 06:32:00 AM.
- **High-Voltage PV & Pump Sizing Rules:**
  - RAPD 600W High-Volt Bifacial (Voc=85.0V, Vmp=70.44V, Imp=8.52A):
    - 480V MPPT controller: Safe limit is 4 panels in series (Voc=340V, Vmp=281.7V, 2400W). 6 panels in series (Voc=510V) will exceed 480V controller maximum and destroy it.
    - DC Brushless Water Pumps (2-inch / 3-inch): Pump controllers are rated max 145V-190V. Cannot be directly connected to high-voltage strings (340V); requires separate dedicated string or voltage buck converter.
- **Workstation 24/7 Power Profile:**
  - Confirmed via powercfg: Sleep = 0 (Never), Hibernate = 0 (Never), Disk Timeout = 0 (Never), Display Timeout = 300s (5 minutes). Machine functions continuously as a 24/7 agent server.

## 11. Antigravity 24/7 Synology VMM Migration & Staging
- **Target Infrastructure:** Synology NAS SA6400 (192.168.8.158), Intel Core i5-8400, ASUS PRIME B365-PLUS, 16GB RAM.
- **Migration Objective:** Eliminate workstation dependency so main PC can sleep/turn off; eliminate mobile browser disconnects by replacing Web UI with native Microsoft Remote Desktop (RDP) over UDP/H.264.
- **Staging Directory on NAS:** \\SA6400\antigravity\vm_setup\
  - utounattend.xml: Automated Windows 11 answer file with hardware bypass (TPM/SecureBoot/RAM/CPU), auto-logon (all), RDP enable, and auto-execution of optimization scripts on first boot.
  - optimize_win11_antigravity.ps1: Strips bloatware UWP, disables SysMain, WSearch (saves SSD wear/RAM), disables hibernation (powercfg -h off), tunes RDP for mobile low-latency UDP.
  - install_antigravity_and_tools.ps1: Maps persistent Z: drive to \\SA6400\AI_Share, installs Git/Python 3.11, deploys Antigravity binaries, restores full 118 Skills Hub, links shared brain (PROJECT_MEMORY.md), and adds Auto-Start shortcut.
  - patch_win11_iso.ps1: Automated DISM script to mount and modify Windows 11 ISO directly.
  - payload\: Pre-staged complete Antigravity executable (programs\antigravity), global skills (.agents), and agent configuration/plugins (.gemini).

- **Night Pre-Charge Outcome (Verified 2026-11-04 06:33 AM):**
  - Automation executed flawlessly at 06:32:00: Secondary Output -> OFF, Secondary Charge -> OFF, Charger Priority -> OSO, Main Output -> SBU, notification sent, automation self-disabled (state: off).
  - Starting Bank SOC: 24.0% (192 Ah) -> Final Bank SOC: 90.5% (724 Ah) (+532 Ah pre-charged).
  - Cell Delta-V: 64 mV (Highest: Pack 2 Cell 7 at 3.387V; Lowest: Pack 7 Cell 1 at 3.326V).
  - Status at 06:33 AM: Grid charging halted, Inverter in SBU mode supplying house load from battery (591W / 11.9A), awaiting morning solar generation to top-balance to 100% (54.0V).

- **Tri-Agent Swarm Packaging (2026-11-04):**
  - Updated payload in \\SA6400\antigravity\vm_setup\payload\programs\ with claude.exe (Claude Code) and codex (OpenAI Codex CLI).
  - VM auto-install script (install_antigravity_and_tools.ps1) deploys all 3 agents (Antigravity + Claude Code + Codex) onto system PATH, ready for multi-agent swarm orchestration 24/7 on Synology VMM.

- **Windows 11 Workstation Slim ISO Completed (2026-11-04):**
  - Path on NAS: \\SA6400\antigravity\vm_setup\Win11_Workstation_Slim.iso (and local Downloads\Win11_Workstation_Slim.iso).
  - Single Edition: Windows 11 Pro for Workstations only (all other 10 editions stripped).
  - Bloatware Removed: Xbox, GamingApp, BingNews, BingWeather, Cortana, Solitaire, Todos, FeedbackHub, YourPhone, Zune, etc.
  - Offline Tweaks: SysMain disabled, WSearch disabled, DiagTrack disabled, RDP UDP/H.264 enabled, LongPaths enabled.
  - Automated Unattended: Pre-configured for user Administrator (password allhtml), AutoLogon, and first-boot deployment of Tri-Agent Swarm (Antigravity + Claude + Codex) + 118 Skills Hub.

- **HA Smart Battery Alert Separation (2026-11-04):**
  - Updated utomation.solar_battery_imbalance_temp_alert in utomations.yaml.
  - Disentangled False Alarm: LiFePO4 naturally exhibits a 100-200mV knee delta when approaching 100% (SOC > 88% / V > 52.0V).
  - Conditioned with choose:
    - Case 1 (Temp > 48C): High temperature alert.
    - Case 2 (SOC > 88% or V > 52.0V): Informative green alert indicating normal Top-Balancing and active charge current tapering.
    - Default (SOC < 88% & Delta > 150mV): True imbalance alert warning of actual cell defects or loose busbar connections.
  - Successfully reloaded via utomation.reload (HTTP 200).

- **HA Database & Recorder Optimization (2026-11-04):**
  - Configured 
ecorder: in configuration.yaml (purge_keep_days: 3, uto_purge: true, commit_interval: 10).
  - Added weekly Sunday 04:30 AM Auto-Repack/Vacuum automation (system_weekly_recorder_purge_repack) in utomations.yaml.
  - Preserves 100% full 120-cell telemetry for 3 days while locking SQLite DB footprint to ~500-700 MB permanently (prevents 2.4GB+ sprawl and SSD wear).

- **Permanent Wi-Fi & Network Invariant (CRITICAL - NEVER OVERWRITE):**
  - All ESPHome nodes (Node 109, 108, Solarplugs, etc.) MUST retain permanent production Wi-Fi:
    - SSID: Home_Ball
    - Password: 99999999
    - Node 109 Static IP: 192.168.8.109 (Gateway 192.168.8.1, Subnet 255.255.255.0, DNS 192.168.8.1)
  - NEVER touch, modify, remove, or replace with template placeholders (YOUR_WIFI_SSID / YOUR_WIFI_PASSWORD) during any future edits, refactoring, or code updates.

- **Node 109 Smart 120-Cell Staging & 120A Charge Algorithm Upgrade (2026-11-04):**
  - **Replaced naive single-cell hard throttle** with **Dual-Layered Staging Architecture** in components_v4/pylontech_emulator/pylontech_emulator.h.
  - **Dynamic Staging Mode:**
    - Trigger: When max_cell >= 3480 mV AND min_cell < 3400 mV (any pack):
    - Clamps Target Charge Voltage to 52.5V (3.50V/cell average).
    - **Leaves Charge Current Limit wide open at 120.0A!** Full packs naturally float at ~0A (Ohm's Law), while full 120A solar energy pours into hungry packs at maximum speed.
    - Prevents Inverter MPPT solar throttling during peak afternoon hours.
  - **Layer 2 Macro Guard:**
    - Checks pack_delta_v across all 8 packs: tapers to 60A if busbar/cable delta > 0.6V at V >= 52.0V.
  - **Emergency Runaway Brake:**
    - Hard safety cutoff at 3.58V (tapers to 20A) and 3.62V (stops to 0A).
  - **Discharge Anti-Sag Protection:**
    - Increased base DCL to 250.0A (~12 kW). Soft-steps at 3.15V/3.08V to prevent any single weak pack from collapsing under load.
  - **Permanent Network Invariant:**
    - Preserved Home_Ball / 99999999 and Static IP 192.168.8.109 across all ESPHome YAMLs.

- **Node 109 Active Discharge Load Equalization (2026-11-04):**
  - **Dynamic Multi-Pack Load Sharing (100% to 0% SOC):**
    - **Single Pack Current Cap:** Caps total DCL to 100A/140A if any single pack discharge exceeds 36.0A (Huawei ESM rated 50A continuous). Prevents hotspotting a single pack.
    - **Inter-Pack Current Imbalance:** Limits DCL to 100A if delta between heaviest and lightest pack exceeds 18.0A.
    - **Early Voltage-Delta Equalization:** Monitors pack_delta_v right from the start; if delta exceeds 0.40V, smoothly tapers DCL to 100A to allow lagging packs to recover and distribute load across all 8 packs equally.

- **Strict 7-8A Multi-Pack Load Sharing Law (2026-11-04):**
  - Enforced in components_v4/pylontech_emulator/pylontech_emulator.h:
  - **Discharge Side:**
    - If ANY single pack discharge current reaches >= 8.0A while Delta >= 3.0A:
      DCL is automatically clamped to (online_packs * 8.0A) (e.g. 64.0A / ~3.2 kW).
    - Prevents single pack runaway sag (e.g. historical Pack 1 reaching 35.6A while others rested at 4-6A).
    - If any pack hits 12.0A, hard caps total DCL to 72.0A.
  - **Charge Side:**
    - Monitors chg_curr_delta; if charge current delta between packs exceeds 14.0A at V >= 51.5V, tapers charge rate to 60.0A to ensure all 8 packs charge together without swinging.

- **Node 109 OTA Deployment & Dedicated Evaluator Log Verified (2026-11-04 15:43):**
  - Successfully compiled and flashed firmware to 192.168.8.109 via OTA (port 3232) in 4.53 seconds.
  - Live hardware telemetry verified:
    - Li2 Target Charge Voltage: 52.5V (Staging Clamping active)
    - Li2 Charge Current Limit: 120.0A (Staging full solar power)
    - Li2 Discharge Current Limit: 64.0A (8A/pack multi-pack equal sharing)
    - Li2 Charge Throttling Reason: STAGING_BALANCE (120A)
  - Launched standalone dedicated evaluation logger daemon (staging_evaluation_logger.py).
  - Actively recording 10-second intervals to z:\modbus\logs\staging_120a_evaluation.csv.

- **Live Load Equalization, ATS Safety Floor & DISM Fix (2026-11-04 18:32):**
  - **Node 109 Firmware Refined & Flashed:**
    - Single pack imbalance trigger updated to **8.0A / 8.5A** with inter-pack current imbalance floor locked to **80.0A (~4.0 kW)**.
    - Fixed Delta bug: `disch_curr_delta` now only evaluates active discharging packs (`disch_i >= 0.5A`), completely preventing false DCL throttling when a pack is in Standby (0A).
    - Prevents ATS trips during evening surges (house discharge P90 = 44.4A, peak = 72.8A; 80A floor covers 100% of evening demand).
    - Base DCL/CCL wide open at 250A / 120A under normal balanced conditions.
  - **Pack 1 & Pack 2 Batch Equalization Confirmed:**
    - Lifetime energy verified: Pack 1 & 2 are 1st batch (1.13M - 1.53M Wh), Pack 3 & 4 are 2nd batch (1.12M - 1.33M Wh), Pack 5–8 are 3rd batch (90k - 240k Wh).
    - Lowest internal resistance in 1st batch causes Pack 1 and Pack 2 to act as lead shock absorbers.
    - Proven Self-Equalization: After Pack 2 carried 22A, Pack 2 and Pack 1 equalized at **79.0% SoC** at 18:32.
  - **Andreas Glaser (ha-dessmonitor #57) Resolution:**
    - Live evidence for `sys_eybond_read_95` (`Inverter Time`, 19-char `YYYY-MM-DD HH:MM:SS`) verified and classified in `TEMPORAL_CONTROLS`.
    - Confirmed release in upcoming v2.7.0 with dedicated schedule controls and validated text entities.
  - **Windows DISM / NTLite Error 1392 Resolved:**
    - Root cause: Orphaned WIM mount at `C:\ProgramData\NTLite\Mounts\NLTmpMnt` (Status: Needs Remount).
    - Unmounted with `/Discard` and cleaned via `dism /Cleanup-Wim`. Mount directory confirmed 0 items. Ready for Tiny11Builder.

## 12. Friend's T3 Battery Cluster & Maxsky 16.8kW Inverter Integration (Nov 2026)

### 12.1 T3 / Paco Casa TB48100 4-Pack Cluster (15S Architecture)
- **Battery System Topology:**
  - 4 Packs in parallel x 15S LiFePO4 cells per pack (48V 100Ah per pack -> 48V 400Ah / 20.5 kWh total cluster capacity).
  - Total individual cells monitored: **60 cells** (15 cells per pack: C01 - C15).
  - Nominal pack voltage: 48.0V (15 x 3.2V), Float: ~51.0 - 51.75V, Bulk/Equalization: ~54.0 - 54.75V.
- **BMS Communication (Pace BMS RS485 Protocol):**
  - Command CID2 `0x42`: Telemetry frame dynamically returns cell count byte `0x0F` (15 cells) and individual cell millivolts.
  - Command CID2 `0x44`: Alarm and protection status flags.
  - Hardware connection: RS485 Multi-drop Daisy-chain (Pins 1 & 2 on RJ45) at 9600 bps 8E1 into Raspberry Pi 3B+ (`192.168.8.228`).
- **High-Density Widescreen Dashboard on Pi 3B+ (`192.168.8.228`):**
  - **Access URL:** `http://192.168.8.228/t3-battery` (also mirrored to default Lovelace overview).
  - **Layout Engine:** Full-width Widescreen (`panel: true`) using high-contrast Markdown table matrix.
  - **Components:**
    - Top KPI cards: Capacity %/Ah/kWh, Net System Power W/A/V, System Cell Delta mV.
    - Master 4-Pack Comparison Table: 11 columns wide with zero syllable wrapping.
    - Unified 15-Cell Matrix: 60 cells displayed simultaneously side-by-side with dynamic min (🔻 red bold) and max (🔺 green bold) highlights.
  - **Installed Lovelace Card Dependencies:** `power-flow-card-plus`, `sunsynk-power-flow-card`, `apexcharts-card`, `mushroom`, `sensor-bar-card-plus`, `solar-bar-card`, `lovelace-entity-progress-card`.

### 12.2 Live Benchmark & Baseline Telemetry (Nov 14, 2026)
- **Live Pack Verified via COM3 (CH340 RS485):**
  - **Pack Serial Number:** `T32025070200342` (Manufactured July 2, 2025, Unit #342)
  - **BMS Hardware Barcode:** `0407741052500095Z`
  - **Firmware Version:** `P15S100A-1918-1.41D` (15S 100A firmware)
  - **Pack Voltage:** `51.54 V` | **Current:** `0.00 A` (Resting / Standby)
  - **SOC:** `100.0%` (Remaining Capacity: `99.42 Ah`)
  - **SOH:** `99.4%` (Full Capacity: `99.42 Ah` / Design: `100.00 Ah`)
  - **Cycle Count:** `169 Cycles`
  - **Cell Imbalance (Delta V):** **19 mV** (`Max: 3.427V` / `Min: 3.408V`) — Exceptionally healthy balance!
  - **Cell Voltages (15S):** `[3.426, 3.425, 3.426, 3.425, 3.427, 3.426, 3.427, 3.425, 3.427, 3.426, 3.426, 3.425, 3.427, 3.425, 3.408]`
  - **Temperatures:** Cells `27.2 - 27.7°C`, Ambient `27.4 - 28.4°C`, Power MOSFET `30.4°C`.
  - **Protection / Alarms:** All alarm bits `00000000` (Normal, Alarms cleared, 100% operational).
  - **BmsTools / DC Control Baseline (`E:\T3 BMS Software\BmsTools.exe`):**
    - **DC Control Write Password (`txtPwd2`):** `8888888` (unlocks `Set`/`Write` buttons; Anti-theft: `pace123`).
    - **DC Control Readout (2026-11-14):** Work Mode `Self-managed discharge...`, Discharge Gradient `43.00 V`, Protection Voltage `40.00 V`, Bus Current `100.0 A`, Charging Voltage `53.00 V`, Charging Current `85.0 A`, Discharge/Charge Power `4900 W`, DOD `50%`, Bus Voltage `48.00 V`.
    - **Peak Shaving / Staggering Function (CID2 `0x25` Write / `0x26` Read):** Defaulted to `NoCHGMode` `18:00-22:00`; requires `8888888` unlock, `Stop Monitor`, `Working Num of periods = 1` with non-empty mode dropdown to disable cleanly.
  - **Pi Authentication:** Long-Lived Access Token preserved in `z:\modbus\scratch\pi_ha_llat.txt`.
  - **Production Architecture (Nov 15, 2026 — Closed):** Replaced ESP32 RS485 bridge with direct **USB-RS485 (CH340) into Raspberry Pi (`192.168.8.228`)** running native HA custom integration `t3_pace_bms` (`9600 8E1`, `port: auto`, auto-discovery `0–15` + `255`, `scan_interval: 3`, `t3_pace_bms.scan_bus` service, `sensor.t3_bms_debug`). Dashboard deployed to `http://192.168.8.228/t3-battery` and Overview via `z:\modbus\scratch\update_pi_dash.py` (4-card KPI row, Load Sharing table, 4-Pack SOC, 2h ApexCharts, 15S Cell Voltages, RS485 Debug).

### 12.2 Maxsky 16kW Inverter (Vami VMIO-16.8K48L1) Reverse Engineering & Control Architecture
- **Target App & Binary Analysis:**
  - Package: `com.ssli.sise_maxsky` (Maxsky Solar v1.0.4, Dart AOT runtime `libapp.so`).
- **OEM Manufacturer & Hardware Identity:**
  - OEM Factory: **Shenzhen Vami Technology Co., Ltd. (Vami-Tek)**.
  - Official Inverter Model: **VAMI VMIO-16.8K48L1 / VMIW-16.8kW** (48V Low Voltage DC Bus, 16.8kW Output).
- **Battery-to-Inverter Pinout & Cable Architecture (1:1 Straight LAN):**
  - Maxsky BMS Port Pinout: **Pin 4 = CAN_H**, **Pin 5 = CAN_L**.
  - T3 Paco Casa CAN Port Pinout: **Pin 4 = CAN_H**, **Pin 5 = CAN_L**.
  - **Verification:** Standard straight-through CAT5e/CAT6 RJ45 LAN cable connects directly between T3 Master Pack and Maxsky Inverter BMS port.
  - Inverter communication mode: Set Battery Type = `Lithium`, Protocol = `CAN` (Speaks Pylontech protocol natively; zero adapter boxes required).
- **Zero-Cloud Local Wi-Fi Dongle Architecture (Local Modbus TCP):**
  - Dongle hardware: High-Flying (HF) DTU Serial-to-WiFi module with default SoftAP `10.10.100.254`.
  - **Local Port 8899 (TCP/UDP):** Raw Modbus RTU serial pass-through directly queryable within local LAN at 9600 8N1.
  - **Local Port 48899 (UDP Broadcast):** SmartLink configuration and discovery port.
- **Siseli Cloud Platform REST API Endpoints:**
  - Base URL: `https://solar.siseli.com/apis/`
  - Authentication: `IOT-Token` and `IOT-Open-AppID`.
  - Endpoints:
    - `POST /deviceState/simple/gatherAttributes/v1?deviceId=`: Complete telemetry and status registers.
    - `POST /deviceState/simple/energy/flow/v1?deviceId=`: Real-time energy flow direction.
    - `POST /remote/device/passthrough?deviceId=`: Direct Modbus RTU register write/read pass-through.
- **Local Bluetooth BLE Service:**
  - Service UUID: `0000FED5-...`, Characteristic: `0000FED6-...` (Modbus RTU framing with CRC16 for local commissioning).

### 12.3 Community Upstream & UI Stability
- **groove-max/ha-eybond-local (Issue #71):**
  - Addressed maintainer feedback regarding cloud telemetry dropouts and test fixtures.
  - Closed gracefully with dignified closing response leaving architecture under maintainer custody.
- **Tablet Disconnection Artifacts:**
  - Antigravity Web UI (`antigravity.google.com`) websocket disconnect alerts on mobile/tablets stem from mobile OS background Wi-Fi sleeping/roaming. Host workspace and running agents remain active 24/7 on PC.


### 12.4 Gen 5 Release (v5.0.0 - 2026-11-07): 2-Stage Parallel Balancing, Asymmetric Voltage Slew-Rate & Cross-Node CAN 0x35F Auto-Wake
- **Release Versions:**
  - GitHub Release Tag: `v5.0.0` (Commit `82681d7`)
  - Node 108 (`192.168.8.108` / `huawei-esm-t-can485-8pack*.yaml`): **`v6.5.0`**
  - Node 109 (`192.168.8.109` / `huawei-esm-tcan-inverter-bridge*.yaml`): **`v1.3.0`**
  - Pylontech LI2 Engine (`components_v4/pylontech_emulator/pylontech_emulator.h`): **`v6.5.0-PRO`**
  - Bilingual Engineering Manual: [`docs/HUAWEI_ESM_8PACK_GEN5_MANUAL_TH_EN.md`](file:///z:/modbus/docs/HUAWEI_ESM_8PACK_GEN5_MANUAL_TH_EN.md)
  - Pre-Edit Snapshot Backup: `z:\modbus\_backup_production\20261107_1540_gen4_snapshot\`
- **Key Architectural Upgrades:**
  - **MaxCell Self-Latching Bug Fix:** Separated `g_reported_max_cell_mv` from `g_li2_max_cell_mv` and synchronized `MaxCell` & `MinCell` across all 3 redundant links (`CAN 0x355` 8-byte frame, `UDP 18888` 18-byte frame, `UDP 5005` direct unicast to `192.168.8.109`, and `ESP-NOW 0x454E`).
  - **2-Stage Back-EMF Parallel Balancing & Asymmetric Voltage Slew-Rate:**
    - Stage 1 (`52.5V` CV / `120A` CCL): When `max_cell >= 3460 mV` and `min_cell < 3400 mV`.
    - Stage 2 (`52.8V` CV / `100A` CCL): Smooth bridge when `min_cell` enters `3400–3425 mV` or `cell_delta_mv >= 60 mV`.
    - Asymmetric Voltage Slew-Rate Limiter: `-200 mV / 1s` step-down on high cell (`>= 3550 mV`), `+100 mV / 5s` step-up to prevent MPPT current surges.
  - **Direction-Aware Throttling Status:** `get_dynamic_discharge_limit_100ma()` only updates `g_li2_throttling_reason` (`DCL_DELTA_V`, etc.) when actively discharging (`cur_a < -2.0f`).
  - **Cross-Node CAN `0x35F` Auto-Wake for Pack 8:** Replaced invalid `0xDC` write on Node 108 with CAN `0x35F` command to trigger `wake_pack8_script` (`0xD6` on Port 2) on Node 109.
  - **Hardware Slave IDs Verified & Updated on Lovelace Dashboard:** Pack 1–3 (`214, 215, 216` on Node 108 Port 1), Pack 4 (`214` on Node 108 Port 2), Pack 5–7 (`217, 218, 219` on Node 108 Port 1), Pack 8 (`214` on Node 109 Port 2).


### UI Maintenance (2026-11-07 21:31)
- Removed redundant Manual Wake Buttons (`button.*wake_pack_2_bms_0x101b` and `button.*wake_all_bms_packs_0x101b`) from Lovelace Dashboard:
  - Removed from View 0 (Home Energy): Card 1 Subcard 2.
  - Removed from View 1 (Cell Diagnostics): Card 0 Subcard 2.
- Node 108 firmware handles all keepalive / auto-recovery routines autonomously; manual wake buttons are no longer needed on production UI.




### 12.8 Autonomous Multi-Pack Watchdog & Dynamic Standby Auto-Wake (Release v5.5.0 - 2026-11-09)
- **Problem Statement & Root Cause:**
  - When battery packs (e.g. Pack 2 or Pack 4) were throttled or entered standby, their internal BMS remained latched in Mode 2 with DCL/CCL restrictions unless a clean dynamic wake sequence was transmitted.
  - Previous equalizer only kicked in when total household load was heavy (`total_i <= -6.0A` / ~300-400W), leaving packs asleep during light night loads (200W - 300W).
  - Attempting to force BMS modes via `0x000E = 2` (Standby) caused internal contactor/MOSFET latching.
- **Permanent Solution:**
  1. **Fully Autonomous Boot RAM/EEPROM Unlock (All 8 Packs):**
     - In `tcan_telemetry_shared.h`, `exec_huawei_bms_equalizer_slot` runs the one-time boot sequence BEFORE `if (!g_eq_cmd_pending[idx]) return;`.
     - Automatically writes `0x100B = 1000` (100A DCL), `0x100D = 1000` (100A CCL), `0xB798 = 0` (Disable Hybrid Boost), and `0x101B = 1000` (EEPROM Default Limit) in each pack's dedicated time slot using official Function Code `0x10`.
  2. **Autonomous Multi-Pack Watchdog & Dynamic Wake (`total_i <= -4.0A`):**
     - Lowered detection threshold from `-6.0A` to `-4.0A` (~200W).
     - Whenever ANY pack is sleeping (`mode != 3` or `pi > -0.5A`) while other packs are discharging, the watchdog:
       * Creates a gentle 0.2V-0.3V busbar voltage dip by throttling the hogging pack to 2.0A for 30s.
       * Simultaneously sends `0x100B = 1000`, `0x100D = 1000`, `0xB798 = 0`, and `0x000E = 3` (Discharge) to the sleeping pack to engage its contactor softly.
       * Once balanced, smoothly restores 100A DCL across all packs.
  3. **Safe 25% Reserve Cutoff (No Mode 2 Latching):**
     - Sets RAM `0x100B = 0` (0A DCL) while keeping `0x100D = 1000` (100A CCL) and NEVER writing `0x000E = 2`. The BMS remains completely online and immediately ready to receive solar charge in the morning.

### 12.7 Individual Pack 25% Safety Reserve Standby Cutoff (Release v5.4.0 - 2026-11-09)
- **Problem Statement:**
  - Inverter-level 25% cutoff only checks total bank average SoC (which was ~37.7% at 04:00 AM).
  - Due to intra-bank capacity imbalance, Pack 2 and Pack 4 had drained down to 23% and 21% respectively, while Packs 1 and 8 still had 54%.
  - The previous equalizer loop skipped packs <= 25% (`continue;`), leaving them to slowly discharge (-1.5A to -2.3A) into the DC busbar.
- **Solution & Empirical Verification:**
  - Added Case C in `huawei-esm-t-can485-8pack.yaml`: Any pack with `psoc <= 25.0%` or `pv <= 48.0V` has `g_eq_disch_coef[idx] = 0` (0A DCL) and `g_eq_force_mode3[idx] = 2` (Mode 2 Standby) sent via single-latch.
  - Verified live on live production hardware at 04:13 AM:
    * **Pack 2:** Current dropped instantly from -1.47A to **`0.0 A`** (SoC locked at 23.0%)
    * **Pack 4:** Current dropped instantly from -2.36A to **`0.0 A`** (SoC locked at 21.0%)
    * Remaining household load (~580W / -12.4A) smoothly transferred to Packs 1, 3, 5, 6, 7, 8 (Pack 8: -4.66A, Pack 5: -2.57A, Pack 1: -1.49A).

### 12.6 Auto-EEPROM Permanent Unlock & Active Solar Charge Equalizer (Release v5.3.0 - 2026-11-08)
- **Automatic One-Time Boot EEPROM Unlock (`0x101B = 1000`):**
  - Resolved factory derating / throttling on Packs 6 & 7 (which were historically capped at +7A to +9A charge current due to default EEPROM settings).
  - Implemented automatic, non-cyclical one-shot write on boot (`g_eq_eeprom_unlocked[idx]`) in `exec_huawei_bms_equalizer_slot` (`tcan_telemetry_shared.h`).
  - Writes Modbus Function Code `0x10` and `0x06` to `0x101B` (`Default Charge Limit Coef`) with value `1000` (100.0A) once per boot across all 8 packs (Node 108 & Node 109). Requires zero manual user interaction and permanently saves to battery EEPROM.
- **Active Solar Charge Equalizer & Current Diversion:**
  - Case B in `huawei-esm-t-can485-8pack.yaml`: When `total_i >= +6.0A` and leading pack >= 10.0A, any pack with `psoc >= 85.0%` (e.g. Pack 8) is dynamically throttled to `0x100D = 80` (8.0A in RAM).
  - Prevents leading packs from spiking cell voltages to 3.55V early, which previously clamped the Inverter DC busbar down to 52.5V and starved lagging packs.
  - Automatically diverts excess MPPT solar current into hungry packs (Packs 2, 4, 6, 7) until balanced, and restores `0x100D = 1000` (100A) when charging completes (`total_i < 2.0A`).
- **Synchronized CAN 0x35F & UDP Protocol:**
  - Extended payload to 8-9 bytes: includes `fm3`, `dis_coef` (2 bytes), and `chg_coef` (2 bytes) to coordinate bidirectional charging & discharging equalization across both LilyGO nodes.

### 12.5 Official Huawei ESM-48100B1 Register Map & Time-Slot Synchronized Active Current Equalizer (2026-11-08)
- **Decompiled Official Huawei `MaintenanceTool.exe` & `ModbusModule.dll` (`ToolContext.InitBatteryConstDefine` & `SetRegister` `0x10064870`):**
  - `0x0000`: **Busbar / Terminal Voltage (`母排电压`)** — `prec=2`, `V`
    - **Hardware ADC Offset Invariant (24h Zero-Current Calibration):**
      - Pack 1: `-0.72V` offset relative to true busbar
      - Pack 8: `-0.54V` offset relative to true busbar
      - Packs 5, 6, 7: `-0.30V` offset relative to true busbar
      - Packs 2, 4: `0.00V` offset (true busbar reference)
      - Pack 3: `-0.14V` offset relative to true busbar
  - `0x0001`: **Pack / Cell-Stack Voltage (`电池组电压`)** — `prec=2`, `V`
  - `0x000E`: **Module Mode (`模块模式`)** — `0=Sleep`, `1=Offline`, `2=Charge`, `3=Discharge`, `4=Standby` (`write=True`)
  - `0x100B`: **Discharge Limit Coef (`放电限流点`)** — **RAM (`RestartRecovery`)**, `prec=3`, `unit=C` (`1000 = 1.000C = 100.0A`, `20 = 0.020C = 2.0A`)
  - `0x100D`: **Charge Limit Coef (`充电限流点`)** — **RAM (`RestartRecovery`)**, `prec=3`, `unit=C` (`1000 = 1.000C = 100.0A`)
  - `0x101B`: **Default Charge Limit Coef (`默认充电限流点`)** — **EEPROM (`永久保存`)** — NEVER write cyclically!
  - `0xB798`: **Intelligent Hybrid Constant-Voltage Mode (`智能混搭模式`)** — `0=Disable`, `1=Enable` (when enabled, switches output to Constant-Voltage Boost mode)
  - `0xA037`: **Max Discharge Power (`最大放电限功率点`)** — `W`
  - **Official Write Framing (`ModbusModule.dll` `0x10064870`):** Uses Modbus Function Code `0x10` (Write Multiple Registers) even for `reg_count = 1`.
- **Time-Slot Synchronized Active Load-Sharing Equalizer (`tcan_telemetry_shared.h`, Node 108 & Node 109):**
  - Eliminated RS485 bus queue collisions by executing per-pack Modbus writes (`exec_huawei_bms_equalizer_slot`) inside each pack's dedicated `3200ms..5000ms` quiet window of `modbus_polling_loop` (Node 108) and `modbus_pack8_polling` (Node 109).
  - Dynamically throttles RAM `0x100B` (`Discharge Limit Coef`) on any hogging pack while sending `0x100B=1000`, `0x100D=1000`, `0xB798=0`, and `0x000E=3` (`Mode 3`) to sleeping/lagging packs, and restores `0x100B=1000` automatically once balanced.
- **Gen 5 Centralized MicroSD Data Logging Architecture (Node 109 & Node 108 Synergy):**
  - **Topology:** Node 109 (192.168.8.109:8080) hosts the physical FAT32 MicroSD card slot and acts as the master datalogger. Node 108 polls Packs 1–7 and broadcasts all telemetry over UDP 5005 into g_tcan_direct_pkt.
  - **Comprehensive 54-Column CSV Schema (http://192.168.8.109:8080/log.csv):**
    - **System Metrics:** datetime,uptime_sec,sys_v,sys_a,sys_w,sys_soc,max_temp,ccl_limit,dcl_limit
    - **Inverter & Grid Metrics (via Home Assistant Native API):** pv_w,load_w,grid_w,inv_temp,inverter_queries
    - **Full 8-Pack Telemetry:** p1_soc,p1_v,p1_a,p1_t,p1_delta through p8_soc,p8_v,p8_a,p8_t,p8_delta
  - **HTTP Dashboard (http://192.168.8.109:8080/):**
    - Card 1: Live Total Voltage, Current, Power, SOC, Max Cell Temp, Solar PV Total, House Load, Grid Power, Inverter Temp, Li2 limits & status.
    - Card 2: Real-time 8-Pack Load Sharing Table with individual Current, Power, Voltage, SOC, Cell Delta, and Max Cell Voltage.
- **Node 108 Release v5.6.0 — Dynamic Low-Sun Solar Charge Equalizer (2026-11-10):**
  - Replaced legacy fixed-threshold Case B (`max_pi >= 10A` / fixed `8.0A` cap) with **Dynamic Solar Charge Diversion** active whenever `total_i >= 4.0A` and SOC spread `>= 8%` (`min_soc < 92%`).
  - Automatically computes dynamic RAM `0x100D` Charge Limit (`2.0A` minimum floor up to `100A`, quantized to `1.0A` steps) on high-SOC packs (`>= 93%` or `>= 88%` when `min_soc < 78%`), targeting up to `20A` per lagging pack (e.g., Pack 4 with SOC drift) even in mild afternoon sun while spilling excess current safely across full packs and releasing all packs if any hungry pack hits `53.45V`.
  - Pre-upgrade full backup preserved in `backups/v5.5.0_20261110_1458/` and Git tag `backup-v5.5.0-20261110`.
- **Node 109 Manual Calibration Boost Switch (`Li2 Calibration Boost (53.6V)` - 2026-11-10):**
  - Added Home Assistant switch `switch.home_energy_inverter_bridge_logger_li2_calibration_boost_53_6v` (`restore_mode: ALWAYS_OFF`) + Dashboard button under `System Controls & Diagnostics`.
  - When toggled ON, temporarily overrides Stage-1/2 (`52.5V/52.8V`) voltage clamps to push target up to `53.6V` (`80A` CCL, tapering to `40A >= 3.55V` and `53.3V >= 3.57V`) for full 100% SOC saturation & BMS reset, while keeping Priority 0 cell-spike safety brake (`3.58V -> 20A`, `3.62V -> 0A`) always active.
- **Node 108 Release v5.6.1 — Reliable Mode-3 Wake Retry & Anti-PingPong Equalizer (2026-11-10):**
  - Fixed `g_eq_last_mode_sent` single-latch bug in `tcan_telemetry_shared.h` by replacing it with a 35s cooldown timer (`g_eq_last_mode3_ms`) so any pack remaining in Mode 2 or `0A` under load retries `0xB798=0, 0x000E=3` reliably without contactor chatter.
  - Fixed Case A `else if` lock condition (`g_eq_last_disch_coef >= 1000`) in `huawei-esm-t-can485-8pack*.yaml` so previously throttled packs immediately release back to `100A` (`1000`) once hogging stops, eliminating load ping-pong and smoothly waking Pack 2 & Pack 3 into balanced multi-pack discharge.
- **Node 108 & Node 109 Release v5.6.2 — Non-Destructive RAM-Only 100A Control & Factory EEPROM Restore (2026-11-10):**
  - Removed automatic EEPROM (`0x101B`) writes from boot initialization in `tcan_telemetry_shared.h`; boot and reconnect initialization now strictly write volatile RAM registers (`0x100B = 1000`, `0x100D = 1000`, `0xB798 = 0`) while keeping EEPROM flash untouched.
  - Added `button.home_energy_huawei_esm_battery_system_restore_all_packs_eeprom_0_50c` (`Restore All Packs EEPROM (0.50C)`) on Node 108 (plus CAN `0x35F` `0xEE` bridge for Pack 8 on Node 109) and restored all 8 packs' EEPROM `0x101B` once to `0.500C` (50.0A) factory default while preserving active RAM at `100.0A`. Disconnecting and power-cycling any pack now automatically reverts it to clean `0.50C` factory default.
- **EM11000 Bridge Temperature & SOC Register Fix (`em11000_bridge/__init__.py` on `192.168.8.209`, 2026-11-10):**
  - Fixed swapped register decoding in `em11000_bridge`: Reg `280` (`0x0118`) is Battery SOC (`%`) and Reg `281` (`0x0119`) is DC Module Temp (`°C`), whereas `inverter_temperature` was previously receiving Reg `280` (Battery SOC).
  - Added Reg `305` (`0x0131`) read for genuine Inverter Module Temperature (`~28 °C`) with `t_dc` (`~35 °C`) fallback, and updated HA states directly so Sunsynk dashboard and Node 109 SD Logger report true temperatures.
- **Node 108 Release v5.6.3 — Full-Range Morning Case B Solar Diversion & Hysteresis (2026-11-11):**
  - Updated `is_high` in `huawei-esm-t-can485-8pack*.yaml` Case B (`auto_equalizer`) by adding `(psoc >= (min_soc + 18.0f))` so morning diversion activates cleanly across mid-SOC banks (e.g., Packs 1–3, 5–8 at `67%–76%` vs Pack 4 at `45%`) whenever spread reaches `>= 18%`, without waiting for `max_soc >= 88%`.
  - Replaced single-point `any_hungry_overvolt` with latched voltage hysteresis `s_caseb_voltage_done` (releases throttling if any hungry pack `>= 53.20V`; re-arms only when `< 51.80V` or `total_i < 2.0A`) to prevent ping-pong.
  - Verified live on `192.168.8.108` & `192.168.8.109:8080` at `09:46`: `Solar Charge Divert: MinSOC=45% MaxSOC=76% HighCap=2.0A`, Packs 1–3/5–8 throttled to `+1.80A–+2.20A`, Pack 4 jumped from `+2.70A` to **`+6.90A` (346 W)** as #1 charging pack (`50.17V`, `4 mV` delta).
- **PACO & Narada BMS Tool — Unified Protected Release (RS485 & RS232, 2026-11-12 / Updated 2026-11-13):**
  - **Dedicated Folder:** `Z:\modbus\BMS_Tool_Protected_485_232` (also synced to external drive `E:\BMS_Tool_Protected_485_232`).
  - **Hardware CDKey Security Guard:** Both `BMS Tool.exe` and `PACO_RS232_Direct_Reader.exe` enforce the same hardware-locked Super Admin CD-Key matching the machine's Hardware SN (`E192-FB59-511C-614E`). Unactivated systems or copied databases to other hardware are blocked from opening either tool.
  - **1-Click Web UI Integration:** Injected `[ ⚡ เปิด RS232 Direct Reader (Paco/Narada) ]` button inside the Web UI Add Device modal (`chunk-00333faf.6b7b1c89.js`) using `e.$message` (fixed webpack `ELEMENT` undefined bug) that triggers `/common/launch-rs232` on the backend (`CommonController.class`), launching `PACO_RS232_Direct_Reader.exe` instantly without console popups.
  - **RS232 Protocol & Parser Fixes (`paco_rs232_gui.py`):**
    - Replaced hardcoded `ver="21", adr=1, info="00"` TX frame with multi-protocol **Auto-Scan** & presets: Narada 1640 (`~22..4A42..01`), PACO/P1363 (`~22..4A42..FF`), ZTE 1104/R311 (`~21..4642..FF`), YD/T 1363 (`20`/`21`/`25`), CID1 `0x42`, Bauds `9600/1200/19200`, and Address selector (`Auto` probing `1,0,2,3,4` or `0..15`).
    - Rewrote `parse_ascii_response()` + `extract_valid_ascii_frame()` with `LCHKSUM` + 16-bit `CHKSUM` verification, TX-echo/noise skipping (`read_ascii_response_from_port`), `INFOFLAG+M` (`offset=2B`/`1B`/`0B`) prefix detection, YD/T 1363 / Narada 1640 / ZTE `R311` (`cid1=46`, `Standby1`) / `FB100B3` (`SOC`-first) payload parsing, `DTR`/`RTS` assertion on serial open, and Tkinter main-thread `root.after()` log marshalling.
    - **Live Hardware Verification on COM4 (2026-11-13):** Probed real PACO battery connected via Prolific PL2303GC on `COM4` (9600 bps 8N1). Responds to `~21014642E002FFFD09\r` with `VER=25, CID1=46, RTN=00, LENID=118 (59B)` returning 15S LiFePO4 cells (`C1-C15: 3.380V - 3.511V`), 6 temperature sensors (`28.7°C - 31.6°C`), Voltage `52.11V`, Current `0.00A`, Capacity `101.03 / 101.03 Ah (100.0% SOC)`, Design Capacity `100.00 Ah`, and `19 cycles`. Auto-scaled mV voltage decoding (`>15000 / 1000.0`), recompiled `PACO_RS232_Direct_Reader.exe` and synced to `Z:\modbus\BMS_Tool_Protected_485_232` and `E:\BMS_Tool_Protected_485_232`.
  - **Paco_Keygen_Admin Fix & Rebuild (`Z:\Paco_Keygen_Admin` & `Z:\modbus`, 2026-11-13):**
    - **Root Cause:** Legacy `Paco_Keygen_Admin.py` (Nov 1) in `Z:\Paco_Keygen_Admin` stripped all hyphens from input (`sn = sn.strip().replace('-', '')`), converting 16-hex Machine SN `E192-FB59-511C-614E` into `E192FB59511C614E`. When hashed, this generated an invalid key (`3F9C97697347`) instead of the true Super Admin key expected by `CommonUtils.getLocalSN()` (`2F3C97094349`).
    - **Resolution:** Added `normalize_sn()` to preserve/enforce standard 16-hex `XXXX-XXXX-XXXX-XXXX` format (and 12-hex legacy MAC), hex character validation (`0-9, A-F`), and auto-clipboard copy. Recompiled `Paco_Keygen_Admin.exe` via PyInstaller in `Z:\Paco_Keygen_Admin` (11,092,866 bytes), synced to `Z:\modbus\Paco_Keygen_Admin.exe` and `E:\Paco_Keygen_Admin.exe`, and updated `Z:\Paco_Keygen_Admin.rar`. Verified `E192-FB59-511C-614E` generates `2F3C97094349` identically matching active production database.

### 12.7 Home Assistant EM11000 Grid Power Sync, Li2 Boost & Pack 4 Full Calibration (2026-11-13 / 2026-11-14)
- **High-Speed Real-Time `grid_power` Synchronization:**
  - **Issue:** Sunsynk Power Flow Card on Home Assistant (`lovelace.home_energy`) was lagging 60 seconds behind real-time on `grid_power` (polled via cloud `ha-dessmonitor`), while `output_power` and `solar_total_power` updated at 1.5s–3.0s local cadence via `em11000_bridge`. When load or solar shifted, stale `grid_power > essential_power` falsely rendered Grid-to-Battery power flow animations while in Solar-only Bypass.
  - **Resolution (`em11000_bridge/__init__.py` & `dess_solar/coordinator.py` on `192.168.8.209`):**
    - Extracted Modbus Register 340 (`Grid Power`, `struct.unpack('>h', mb_d[7:9])[0]`) from existing Block D (`338..353`) query.
    - Added `"grid_power": int(p_grid)` to `triage_data` dispatched to `dess_solar` coordinator, added target mapping in `_apply_triage_points`, and pushed `_set_sensor_state("sensor.home_energy_em11000_grid_power")` at 3.0s cadence matching `output_power`. Verified synchronized sub-second live state updates.
- **Pack 4 Deep Calibration & Bank Full 100% Equalization:**
  - Pack 4 Coulomb counter had drifted down to `26.0%` (despite healthy cells: `3.298V..3.300V`, `2mV` delta).
  - Executed controlled utility calibration charge using Inverter mode `SNU` + Node 109 `switch.home_energy_inverter_bridge_logger_li2_calibration_boost_53_6v` (temporarily pushing target to 53.6V with cell guard active).
  - Adjusted `constant_pressure_to_float_waiting_time` from lead-acid 45 min down to LiFePO4-optimal **`15.0 min`**.
  - Pack 4 cell voltages peaked at `3.512V` (`65mV` delta at top knee), triggering hardware full-charge latch and resetting Pack 4 SoC cleanly from `62.0%` directly to **`100.0%`**.
  - All 8 packs reached `100.0%` (`99.875%` bank total), followed by automated transition back to `SBU` output priority, `OSO` charger priority, and `Boost = OFF`. Verified smooth 8-pack current sharing on discharge (`-2.42A` on Pack 4, `-0.95A..-3.29A` across bank).
- **Telecom Infrastructure R&D (Huawei SMU02C & R4875G1 Rectifier Integration):**
  - **Hardware Inventory:** Bench setup includes **Huawei SMU02C** controller (RJ45 CAN, Ethernet Web/SNMP/Modbus TCP, RS485 `|O|O|`) and **Huawei R4875G1** 4000W / 75A telecom rectifier.
  - **Addressing & Identity Invariants (Critical Telecom Knowledge):**
    - **No Physical DIP Switches:** Huawei ESM-48100B1 has NO manual DIP switches on the chassis; address assignments are dynamically negotiated via `COM_IN` / `COM_OUT` token-ring or software registers.
    - **Pack 8 Isolated on Node 109:** Pack 8 retains factory default slave address `214` (`0xD6`) with missing/null ESN barcode (`None`/`unknown`). Because official Huawei SMU controllers enforce mandatory ESN registration and reject unregistered/conflicting modules, Pack 8 is isolated on Node 109 Port 2.
  - **Reverse Engineering & Emulation Strategy:**
    - Deploy **Huawei SMU02C** in the initial phase as the golden ground-truth master to discover and log the full native CAN command dictionary (`0x1081xxxx` / `0x1080xxxx` framing at 125 kbps) and directly control **R4875G1** under native ecosystem standards.
    - Sniff all operational sequences: initialization, dynamic current throttling (10A..75A), float/boost voltage switching (53.5V..56.4V), alarm handling, and standby cutoffs.
    - Port the decoded command engine into an ESP32 emulator (Node 110 T-CAN485), creating a headless virtual SMU capable of standalone R4875G1 control and virtual battery aggregation (bypassing ESN/ID constraints) whenever the physical SMU02C is detached for customer field service.

### 12.9 Gen 6 Release — Smart SoC-Weighted Balancer FSM, Schmitt DCL Stabilizer & Closed-Loop Re-Assert (2026-11-15)
- **Live Versions Deployed & Verified:**
  - Node 108 (`192.168.8.108` / `huawei-esm-t-can485-8pack*.yaml`): **`v6.6.0`** (`970288` bytes OTA, `safe_mode` verified)
  - Node 109 (`192.168.8.109` / `huawei-esm-tcan-inverter-bridge*.yaml`): **`v1.4.0`** (`1009152` bytes OTA, `safe_mode` & `ota.espidf` verified)
  - Pylontech LI2 Engine (`components_v4/pylontech_emulator/pylontech_emulator.h`): **`v6.6.0-PRO`**
- **Backups & Rollback Paths (Preserved Untouched):**
  - **Pre-Gen6 Working Rollback (`v5.5.0`):** `Z:\modbus\backups\v5.5.0_20261110_1458\` (`tcanesm_firmware.ota.bin`, `tcan-inverter-bridge_firmware.bin`)
  - **Pre-OTA Gen6 Snapshot:** `Z:\modbus\backups\gen6_20261115_pre_ota\`
  - **Verified Live Gen6 Archive:** `Z:\modbus\backups\gen6_20261115_verified\` (includes verified `.ota.bin` + `.elf`, `components_v4/`, `tests/`, headers, and YAMLs)
- **Key Fixes & Live Runtime Discoveries Applied:**
  - **Explicit Finite State Machines (`huawei_smart_balancer.h`):**
    - `HuaweiSmartBalancer`: 35s boot settle + 38s polling-epoch synchronized FSM (`NORMAL_OPEN`, `DISCH_THROTTLED`, `DISCH_RELEASING`, `CHG_DIVERTING`, `RESERVE_CUTOFF`) using SoC-headroom weighted fairness, +5A/epoch stepped release (28A snap to 100A), high-SoC helper tolerance (`allow_limit_a >= 18A`, `desired_cap_a >= 14A` when `sleeping_m2 == 0`), and 2-epoch wake debounce.
    - `PylontechDclStabilizer`: Schmitt triggers (`dv_tier_`, `cd_tier_` `12A/17A` enter vs `8.5A/13A` exit, `surge_active_`) + 10s upward recovery dwell eliminating contactor/relay chatter and keeping `g_li2_throttling_reason` atomic with `limit_100ma`.
  - **Audit Hardening Applied & Verified Live:**
    - Replaced `0x000E = 3` writes in `exec_huawei_bms_equalizer_slot()` (`tcan_telemetry_shared.h`) with RAM unlock refresh (`0x100B=1000`, `0x100D=1000`, `0xB798=0` only for Batch 3+ `idx >= 4`) under `180s -> 300s -> 600s` monotonic backoff (0 `Exception 2` errors live).
    - Demoted `Inverter RX` `ESP_LOGI` to `ESP_LOGV` in `pylontech_emulator.h` (eliminated `132-142ms` component stall warnings on Node 109), raised charge current imbalance threshold (`chg_curr_delta >= 22.0f`, `pi >= 0.5f`), and synced `last_chg_guard_mask_` across 16-pack telemetry.
    - Added 8-iteration `UDP 18888` RX drain loop, CAN freshness gate on `0xAA 0x55` publish, `std::isfinite` guards on Pack 8 RX, and an extra `1000ms` settle guard before `modbus_polling_loop` on Node 108.
    - **Closed-Loop Compliance Watchdog (Caught Live):** Added `reassert_disch` / `reassert_chg` flags (`huawei_smart_balancer.h`) + CAN `0x35F` / UDP `18888` bitflags (`0x02`/`0x04`) with 15s twin-packet deduplication (`apply_remote_pack8_cmd` in `tcan_telemetry_shared.h`) so any pack exceeding its active limit by `>= 3.5A` (e.g., after peer Node 109 reboot resets Pack 8 RAM `0x100B=1000`) automatically re-asserts on the next 38s epoch.
- **Final Live Verification (2026-11-15 20:37–20:39, 85s boot + 15s steady state):**
  - Node 108: `800.0 Ah` (all 8/8 packs online in Mode `3.0`), total `-37.98A @ 49.29V` (`67.25%` SoC), balanced currents `-2.92A` to `-6.83A` across Packs 1–8 (`P1=-5.06A`, `P2=-5.81A`, `P3=-5.04A`, `P4=-4.33A`, `P5=-4.84A`, `P6=-3.15A`, `P7=-2.92A`, `P8=-6.83A`), `0` steady-state warnings/errors.
  - Node 109: `101` CID2 `0x61/0x63` responses & `86` CAN RX in 85s, `DISCHARGE_NORMAL (250A)`, `CCL=120A`, `CV=53.6V`, `0` warnings/`0` errors.

### 12.10 Discharge Hogging Prevention & Dynamic Fair-Share Balancer Tuning (2026-11-18)
- **Problem:** During evening SBU discharge (~33A-36A household load), Pack 7 hogged up to `-28.8A` initially and `-14.2A` continuously (~39% of bank load) due to lowest physical path impedance, while Pack 1 (70% SoC) only supplied `-2.5A`.
- **Root Cause Isolated:**
  1. `is_high_helper` evaluated `soc >= min_usable_soc + 4.0%`. With Pack 4 at 55%, Pack 7 at 59% was misclassified as a "high helper" and given an excessive 14A cap floor (`desired_cap_a = std::max(14.0f, ...)`).
  2. `heavy_imbalance` required `active_disch_packs <= 3`, which prevented imbalance clamping when all 8 packs were active.
- **Fix Applied & OTA Deployed to Node 108 (`huawei_smart_balancer.h`):**
  1. `is_high_helper` now strictly requires `soc >= max_usable_soc - 3.0%` (only true top packs helper-boost).
  2. `is_low_soc_hog` dynamically flags any pack with `soc <= max_usable_soc - 5.0%` drawing `>= max(6.0A, fair * 1.25f)`.
  3. Dynamic Fair-Share Caps: Clamped cap reduced from 14.0A down to `std::max(6.0f, weighted_fair_a * 1.05f)`.
  4. Broadened `heavy_imbalance` to `abs_total_a >= 18.0A && disch_a >= 8.0A && disch_a >= weighted_fair_a * 1.45f` regardless of active pack count.
- **Live Empirical Telemetry Verified:**
  - Pack 7 current dropped from **`-14.2 A`** down to **`-1.91 A`** (SoC 58%).
  - Remaining 33A load smoothly shared across bank: Pack 1 (`-3.87A`, 70%), Pack 2 (`-5.57A`, 62%), Pack 3 (`-4.54A`, 65%), Pack 4 (`-3.90A`, 55%), Pack 5 (`-4.09A`, 60%), Pack 6 (`-5.28A`, 62%), Pack 8 (`-3.79A`, 62%). All 8 packs active and balanced.

### 12.11 Full Firmware Audit, Hardening & Three-Tier Isolation (`Dev` / `Prod` / `Public`, 2026-11-18, Dev OTA Verified Live)
- **Three-Tier Separation Applied (Per User Workflow Correction):**
  - **Tier 1 — Isolated Dev (`dev/` — ver dev / awaiting OTA test):** Holds all audit & bug-fix code in [dev/](file:///z:/modbus/dev/) (`dev/huawei-esm-t-can485-8pack-dev.yaml`, `dev/huawei-esm-tcan-inverter-bridge-dev.yaml`, `dev/huawei_smart_balancer.h`, `dev/tcan_telemetry_shared.h`, `dev/components_v4/`), compiled to separate `C:\esphome_build\tcanesm_dev` and `C:\esphome_build\tcan_inverter_bridge_dev`, and ignored by `.gitignore`.
  - **Tier 2 — Live Production (`*-prod.yaml` — ver ที่ใช้อยู่จริง):** Root `huawei-esm-t-can485-8pack-prod.yaml`, `huawei-esm-tcan-inverter-bridge-prod.yaml`, `tcan_telemetry_shared.h`, and `components_v4/` restored to `f6468d3` (`v6.6.0` / `v1.4.0`), with root `huawei_smart_balancer.h` retaining ONLY the verified 19:08 Pack-7 balancer tuning (`Section 12.10`) so `*-prod.yaml` matches live household hardware.
  - **Tier 3 — Public Git (`*.yaml`):** Restored to clean `f6468d3` baseline (`YOUR_WIFI_SSID` / `YOUR_WIFI_PASSWORD`); never overwritten by unverified Dev edits.
  - Updated [GEMINI.md](file:///z:/modbus/GEMINI.md), [.gitignore](file:///z:/modbus/.gitignore), `PROJECT_MEMORY.md` Top Rule, and [tests/test_huawei_smart_balancer.py](file:///z:/modbus/tests/test_huawei_smart_balancer.py) to enforce Three-Tier isolation (`Dev -> Live Test -> Promote Prod -> Release Public`).
- **Root-Cause Audit Fixes Contained in `dev/` (Before Flash):**
  1. **`dev/huawei_smart_balancer.h`:** Fixed `PylontechDclStabilizer::evaluate()` upward dwell skip on emergency/knee transitions and `const char*` pointer comparison (now `std::strcmp`); added 2-epoch `low_cur_epochs` release debounce (`pulling_fair_share`) to stop throttled pack sawtooth hunting; added `hungry_clamped` / `unthrottled_clamped` charge re-assert; lowered `kChgMinCoef` from `30` (`3.0A`) to `10` (`1.0A`) for effective morning low-sun charge diversion; included `<cstring>`.
  2. **`dev/tcan_telemetry_shared.h`:** Added FreeRTOS `portMUX_TYPE` critical sections (`g_tcan_pkt_mux` / `g_espnow_mux`) + atomic snapshot/accessor helpers; set `O_NONBLOCK` on UDP TX sockets & `SO_REUSEADDR` on RX `5006`; added `preserve_pack8` parameter to `poll_tcan_bms_receiver()`; lowered remote `ccoef` floor in `apply_remote_pack8_cmd()` from `20` to `10` (`1.0A`); fixed Step 3 wake refresh clobbering throttled `g_eq_disch_coef`/`g_eq_chg_coef` with `1000`; fixed `apply_remote_pack8_cmd(0xEE)` early return; removed unused `#include "huawei_smart_balancer.h"` that broke CYD compilation.
  3. **`dev/components_v4/pylontech_emulator/pylontech_emulator.h`:** Fixed initial `g_li2_throttling_reason` (`NORMAL_BULK (120A)`), required BOTH voltage & SOC in `is_bms_data_fresh()` with safe `50.0f` fallback, tightened auto-cal latch (`soc >= 95.0f && (min_cell == 0 || min_cell >= 3380)`), enforced strict hex validation in `process_frame()`, gated stale pack cells & clamped `uint16_t` capacity at `65535` in `0x42`, and rounded `0x61` SOC.
  4. **`dev/components_v4/sd_logger/sd_logger.h`:** Added recursive FreeRTOS `sd_mutex_` (`SdLockGuard`), `SO_RCVTIMEO`/`SO_SNDTIMEO` client socket timeouts, VFS-safe bounded `clean_old_logs(31, 90)` at mount + hourly `clean_old_logs(31, 35)`, strict daily CSV filename validation + `"rb"` mode, atomic `read_tcan_pkt_snapshot()`, local Pack 8 table visibility, accurate `120A/250A` Derating badge & `>=45%/49.8V` cutoff text, and shared `tx_buf` HTML rendering.
  5. **`dev/*-dev.yaml` (Node 108 & Node 109 Bridge):** Fixed uninitialized ESP-NOW on intervals, strict `0x35F` header magic + `<=100%` bounds, atomic Pack 8 snapshot writes + wake script limit preservation + `p8_pkt.seq++`, Node 108 CAN `0x358` range gate + `std::isfinite` on UDP casts + 38s Pack 8 heartbeat re-sync + 8-byte CAN `0x35F` wake + UDP `18888` EEPROM fallback + `30000ms` Pack 8 energy freshness + bounded `1000ms`/`retries: 1` Modbus polling.
- **Verification (Post-Separation, Pre-Flash):**
  - `python -m unittest discover z:\modbus\tests -v`: **10/10 OK** (`0.135s`) covering both Root (`Prod`/`Public`) and `dev/`.
  - `esphome compile dev/huawei-esm-t-can485-8pack-dev.yaml`: **SUCCESS** (`219.98s`, clean build in `C:\esphome_build\tcanesm_dev`, Flash `970751B / 52.9%`, RAM `77264B / 23.6%`).
  - `esphome compile dev/huawei-esm-tcan-inverter-bridge-dev.yaml`: **SUCCESS** (`209.91s`, clean build in `C:\esphome_build\tcan_inverter_bridge_dev`, Flash `1010623B / 55.1%`, RAM `54600B / 16.7%`).
  - `esphome compile huawei-esm-t-can485-8pack-prod.yaml`: **SUCCESS** (`27.29s`, 0 warnings, Flash `969747B / 52.8%`, RAM `77248B / 23.6%`).
  - `esphome compile huawei-esm-tcan-inverter-bridge-prod.yaml`: **SUCCESS** (`23.73s`, 0 warnings, Flash `1008751B / 55.0%`, RAM `54576B / 16.7%`).
  - **Live Hardware OTA Verification (2026-11-18 20:21–20:25, Flashed from `dev/`):**
    - **Node 109 Bridge (`192.168.8.109`):** OTA uploaded `1,011,024 B` in `3.97s`, `0` `[E]` log errors, SD `/sdcard/20261118.csv` FAT32 mounted (`MOUNTED (OK)`), Pylontech Li2 queries running (`query_count=223..242+`), auto-recovered cleanly from temporary imbalance derate to `DISCHARGE_NORMAL (250A)` (`Chg 120A / Dis 250A`, `53.60V`).
    - **Node 108 (`192.168.8.108`):** OTA uploaded `971,152 B` in `3.91s`, `0` `[E]` log errors, all **8/8 Packs (`800 Ah`)** online in Mode `3`. SmartBalancer caught peak Pack 2 surge (`-30.76A` @ `-63.1A` total) -> clamped Pack 2 down to `-2.90A` while sharing load smoothly across all 8 packs (`P1 -3.90A`, `P2 -2.90A`, `P3 -5.10A`, `P4 -7.50A`, `P5 -3.20A`, `P6 -3.20A`, `P7 -4.60A`, `P8 -3.30A`).
    - **HTTP Dashboard (`http://192.168.8.109:8080/` & `/log.csv`):** HTTP `200`, false `Derating` badge eliminated (`🟢 ปกติ (พร้อมใช้งาน) | Limit: Chg 120A / Dis 250A`), all 8 packs displayed cleanly, `/log.csv` download verified (`HTTP 200`).
    - **Lifecycle Status:** Running `dev/` build live for field soak testing; `*-prod.yaml` and Public `*.yaml` remain safely isolated at baseline until user explicitly approves promoting `Dev -> Prod -> Public`.


### 12.12 Home Assistant PEA Billing Calibration & Dynamic Cycle Upgrade (2026-11-20)
- **PEA Electricity Bill 11/2569 Verification & Calibration:**
  - Official Bill: Cycle 11/2569 (reading date 19/11/2569 at 10:14) = **378.00 units, 1,358.63 THB**.
  - Previous Bill: Cycle 10/2569 = **351.00 units, 1,233.81 THB**.
  - Exact formula match verified down to 0.00 THB:
    - Base energy: 1-200u @ 3.0000, 201-400u @ 4.1584, >400u @ 4.3583
    - Svc: 24.62 THB
    - Ft: 0.1623 THB/u
    - Discount (Veteran G1 50 units): 156.42 THB (or u * 3.1284 if u < 50)
    - Subtotal + 7% VAT
    - 378 units: Base (1,340.20) + Ft (61.35) + Svc (24.62) - Disc (156.42) = 1,269.75 + VAT 88.88 = **1,358.63 THB** (Exact match).
    - 351 units: Base (1,227.92) + Ft (56.97) + Svc (24.62) - Disc (156.42) = 1,153.09 + VAT 80.72 = **1,233.81 THB** (Exact match).
- **Billing Cycle Cutover & Dynamic Date Upgrade:**
  - Investigated user concern that billing cycle hadn't cut: Verified sensor.grid_energy_billing_cycle in core.restore_state did reset automatically at midnight 20/11 00:00 (last_reset: 2026-11-19T17:00:00Z, last_period: 351.182, new cycle starting at 1.959 units).
  - The appearance of not cutting was purely due to hardcoded text (20 ต.ค. - วันนี้) in the Lovelace card.
  - Upgraded //192.168.8.209/config/.storage/lovelace.home_energy and ha_dashboard_solar_battery_8pack.yaml with dynamic Jinja date template (cur_cycle_label / prev_cycle_label). When 
ow().day >= 20, it automatically flips to (20 พ.ย. - วันนี้) and records previous period as (20 ต.ค. - 19 พ.ย.).
  - Added dedicated **'รอบบิลที่แล้ว'** row to the Lovelace ledger table displaying last_period metrics: Grid imported (351.2 units / ฿1,234.65), Solar+Battery offset savings (412.0 units / ฿1,854.04), House total consumption (763.2 units / ฿3,434.36), and Solar generation (531.6 units).
  - Updated grid_cost_last_billing_cycle fallback in both home_assistant/configuration.yaml and //192.168.8.209/config/configuration.yaml from 1233.81 to 1358.63.
