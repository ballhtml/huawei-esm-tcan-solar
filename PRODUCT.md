# Product

<!-- impeccable:product-schema 1 -->

## Platform

Home Assistant (Lovelace Dashboard) & Web (Desktop, Tablet, Mobile, ESP32 CYD Display)

## Users

Home solar system owner and operator (Khun Ball) managing a high-capacity hybrid energy storage system in Bangkok, Thailand. The user monitors real-time solar generation, grid consumption, billing cycle ROI, 8-pack battery bank health, individual cell balancing (120 cells), and inverter operational mode settings.

## Product Purpose

Provide an industrial-grade, responsive, 100% local-first monitoring and control dashboard in Home Assistant that surfaces mission-critical solar and battery metrics with high visual hierarchy, tabular numeric precision, and zero fluff. It empowers the homeowner to verify daily savings, track PEA utility bill net liabilities (with government discount deductions), audit 120 individual cell voltages across 8 Huawei ESM packs, and safely calibrate inverter charge/discharge cutoffs without touching high-voltage hardware.

## Positioning

Unlike generic cloud portals (DessMonitor, SolarMAN) that suffer from network latency, rate limits, and packet drops, this unified Home Assistant system combines direct edge hardware bridges (ESPHome T-CAN485 controllers) and hardened local integration to deliver sub-second telemetry, real-time cell matrix visualization, and automated financial accounting on the local home network.

## Operating Context

- **Environment:** Local network, accessible 24/7 via Home Assistant companion app, iPad wall tablet, PC workstation, and 2.8" CYD desktop monitor.
- **Physical System:** 8x Huawei ESM-48100B1 48V 100Ah LiFePO4 battery packs in parallel (800 Ah / 38.4 kWh total capacity), ANENJI EM11000 11kW hybrid inverter, PEA single-phase grid connection, dual ESP32 T-CAN485 controllers with isolated RS485 and CAN buses.
- **Rituals:** Morning PV ramp verification, peak afternoon charge taper and cell balance audit, evening off-grid battery discharge monitoring, and monthly PEA billing reconciliation on the 20th.

## Capabilities and Constraints

- **3-Tab Master/Detail Surface Architecture:**
  1. **Tab 1: Home Energy (`/home-energy`):**
     - Financial KPI chips (Today's PEA cost, Billing cycle net liability, Solar load offset savings).
     - Live animated Sunsynk power flow diagram.
     - Financial ROI & Energy Ledger table (4.50 THB/kWh baseline, 50-unit government tier deduction).
     - 8-Pack bank health & active SOC distribution.
  2. **Tab 2: Cell Diagnostics (`/home-energy/cells`):**
     - Bank Overview table with live cell drift $\Delta\text{mV}$ and balance badges.
     - 120-Cell Real-Time Matrix (15 cells $\times$ 8 packs) with instant cell outlier highlighting.
     - Hardware & Cumulative Energy registry ($0\text{x}0042$ lifetime discharged kWh, $0\text{x}0005$ max temperatures, SOH).
  3. **Tab 3: Inverter Setup (`/home-energy/inverter-setup`):**
     - Output priority (SBU / SUB / Utility First) and Charger priority controls.
     - Charging current limits (Utility, Total) and 15S LiFePO4 voltage protection cutoffs.
     - 1-click User Mode Profile activation button and telemetry refresh trigger.
- **Constraints:**
  - Zero unsolicited Modbus writes to ESM packs to eliminate BMS anti-theft lockout risk.
  - Responsive layouts must maintain table legibility across 360px mobile viewports up to 4K desktop screens.
  - All template sensors must handle `unavailable` or `unknown` inputs gracefully with fallback states.

## Brand & Design Commitments

- **Tone & Voice:** Engineering-grade, authoritative, mathematically precise, uncluttered.
- **Operating Mode:** `Operate` (immediate scanability, high data density, zero decorative distraction).
- **Typography Scale:** Tabular monospace digits (`font-variant-numeric: tabular-nums`) for all electrical and monetary values.
- **Color Dosage:** Purposeful semantic palette (Solar: Amber/Gold, Battery: Emerald Green, Grid: Crisp Blue/Red, Faults: Crimson).

## Evidence on Hand

- Board 108: Master Battery Controller & Aggregator (`huawei-esm-t-can485-8pack.yaml`).
- Board 109: Inverter Pylontech Bridge & Pack 8 (`huawei-esm-tcan-inverter-bridge.yaml`).
- Home Assistant Server (`lovelace.home_energy`).
- Verified zero Modbus Exception 2 errors and hardened cloud coordinator fallback.
