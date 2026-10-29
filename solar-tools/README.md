# solar-tools

A specialized Cursor plugin for designing, configuring, debugging, and validating **ESPHome** firmware (Modbus RTU, CAN Bus, Pylontech emulation) and **Home Assistant** solar/battery storage dashboards.

## Features

- **Rules (`solar-esphome-ha.mdc`):** Enforces industry best practices for Modbus timing, galvanic isolation, ground loop prevention, and heap safety.
- **Skills:**
  - `esphome-modbus`: Step-by-step procedures for writing robust Modbus RTU polling loops, multi-pack scaling, CAN bus interconnects, and noise mitigation.
  - `ha-solar-dashboard`: Templates and Lovelace UI patterns for high-density solar battery monitoring.
- **Commands:**
  - `/validate-esphome`: Audits ESPHome YAML configurations for timing issues, bus collisions, and hardware pitfalls.

## Installation

### Local Install (Current Machine)
This plugin is installed locally in your Cursor plugins directory:
`~/.cursor/plugins/local/solar-tools/`

## Supported Hardware & Protocols
- **Hardware:** LILYGO T-CAN485, ESP32 DevKit, CYD (ESP32-2432S028R), Isolated TTL-to-RS485 modules.
- **Protocols:** Modbus RTU, CAN TWAI (500kbps), Pylontech ASCII / CAN protocols.
- **Batteries:** Huawei ESM-48100B1, Pylontech US2000/US3000/US5000, and generic LiFePO4 BMS.
