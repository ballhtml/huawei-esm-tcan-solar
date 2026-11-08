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
| **Synology NAS (SA6400)** | Intel i5-8400 / 16GB RAM | `192.168.8.158` | LAN DSM Port 5000 / Web IDE 8443 | XPEnology DSM 7.2 (Arc Loader), 24/7 Agent Server, Open WebUI (3000), Transmission (9091) |
| **Workstation PC** | Windows 11 PC | `192.168.8.161` | LAN 2.5G | Local dev station, ESPHome compilation, Antigravity harness |

### Battery Bank Constraints & Specs (8x Huawei ESM-48100B1)
- **Total Capacity:** 800 Ah / 38.4 kWh (15 LiFePO4 cells per pack = 120 individual cells monitored).
- **Current Operational Status (Active Standard):**
  - **All 8 packs are fully active and online in parallel** on heavy-duty DC copper busbars (Total: **800 Ah / 800A nominal capacity**).
  - **CRITICAL AGENT INVARIANT:** NEVER refer to the home ESS as 300 Ah, 3 packs, or 400 Ah in any calculations, sizing, or discussions. Earlier 3-pack and 4-pack references were temporary bench tests during firmware debugging; the live household system is strictly **800 Ah (8x 100 Ah packs)**.
- **Physical Connection:** All 8 packs permanently connected in parallel to common heavy-duty DC copper busbars.
- **Geographic Location (Permanent):** จังหวัดเลย (Mueang Loei District, Lat: 17.59768, Lon: 101.71790). Solar forecasts must always query Loei coordinates, NOT Bangkok.
- **Dual-Version File Standard (Permanent Rule):**
  - **Set 1 (Production - สำหรับใช้เอง):** `*-prod.yaml` (e.g. `huawei-esm-t-can485-8pack-prod.yaml`, `huawei-esm-tcan-inverter-bridge-prod.yaml`, `cyd-solar-display-prod.yaml`). Fully populated with `Home_Ball` / `99999999` and static IPs (`192.168.8.108`, `109`, `110`). Flashed via `flash_node*.bat` scripts. Protected by `.gitignore`.
  - **Set 2 (Public / GitHub - สำหรับแจก):** `*.yaml` (e.g. `huawei-esm-t-can485-8pack.yaml`, `huawei-esm-tcan-inverter-bridge.yaml`, `cyd-solar-display.yaml`). Sanitized with `YOUR_WIFI_SSID` / `YOUR_WIFI_PASSWORD`. Safe for open-source publication.
  - **Rule:** Every modification must be mirrored across both sets. Git operations must never overwrite production files.
- **Autonomous Equalizer (Node 108):** If Pack 2 discharges > 6.0A while other packs discharge < 2.0A, Node 108 automatically pulses wake frames (0x101B = 100A, 300ms delays) to Packs 1, 3, 4, 5, 6, 7, 8 (cooldown 60s) to eliminate single-pack runaway without user manual intervention.
- **Manual Wake Buttons Policy:** Both wake_pack2_bms / wake_all_bms scripts and buttons on Node 108 are permanently remarked out (#) to prevent accidental manual gate runaway.
- **Critical Safety Rules:**
  - **NEVER** instruct or require changing DIP switches on active packs without explicit user consent.
  - **Pack 4 Isolation:** Pack 4 hardware address is `214` (`0xD6`). Kept on dedicated isolated RS485 UART channel on Node 108 to eliminate bus collisions with standard IDs (1, 2, 3, 5, 6, 7, 8).
- **Safety Standby Reserve & Cutoff Floor (Synchronized across Firmware & HA - Nov 2026):**
  - **Standby Cutoff Floor:** Raised to 25.0% SoC and 48.0V across ESPHome Node 108 & 109 (usable_disch condition) to eliminate sag/surge drops during high-power kitchen spikes.
  - **HA Usable Reserve Calculation:** sensor.battery_shutdown_soc_setting = 25%, usable formula = (soc - 25) / 100 * total_kwh, emergency reserve = 25% (9.6 kWh out of 38.4 kWh).
  - **HA Lovelace Cards:** custom:sunsynk-power-flow-card shutdown_soc = 25, custom:solar-bar-card = พร้อมจ่าย (หัก 25% สำรอง), mushroom card = พลังงานพร้อมจ่าย (ถึง 25% สำรอง).
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

- **Host Machine:** Intel Core i5-8400 (6 Cores, 2.80GHz - 4.00GHz), 16GB DDR4 RAM, 750W PSU.
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
  - `ha-dessmonitor` v2.6.0: Custom integration polling EM11000 inverter and syncing battery bank states.
  - Lovelace Dashboard: High-density solar cards displaying real-time 8-pack telemetry and 120-cell bar charts.
- **Xiaomi / Mi Smart Home Ecosystem:**
  - Integration Method: `Xiaomi Miot Auto` via HACS.
  - Controls: Fans, air purifiers, smart plugs, air conditioning units, and environmental sensors.
- **Network Routing & Automation:**
  - Network Router: Cudy Router (`192.168.8.1`) managed via `Z:\cudy\router.py`.
  - Active Port Forwards on Cudy:
    - `5000-5001` -> Synology DSM (`192.168.8.158`)
    - `8123` -> Home Assistant (`192.168.8.209`)
    - `9091` -> Transmission Torrent (`192.168.8.158`)
    - `8443` -> Antigravity Web IDE (`192.168.8.158`)
  - Primary Wi-Fi SSID: `Home_Ball` / Password: `99999999`
  - Fallback APs (Emergency recovery only):
    - SSID: `tcan-bridge-ap` / Password: `bms_setup_password`
    - SSID: `tcanesm-ap` / Password: `bms_setup_password`

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
- **Target Infrastructure:** Synology NAS SA6400 (192.168.8.158), Intel Core i5-8400, 16GB RAM.
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
  - **Pi Authentication:** Long-Lived Access Token preserved in `z:\modbus\scratch\pi_ha_llat.txt`.

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
