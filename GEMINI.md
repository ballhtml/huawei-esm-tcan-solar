# Project Guidelines: Modbus Solar & Battery System

## Operating Mode: Poteto Mode
Follow the rules defined in [.agents/rules/poteto-mode.md](file:///.agents/rules/poteto-mode.md):
- **Verify with Evidence:** Prove every assertion on live hardware / telemetry before declaring done.
- **Laziness Protocol:** Minimal diff, clean removals, no unnecessary speculative code layers.
- **Model the Domain:** Clean data models and structured telemetry mappings.
- **Unslopped Communication:** Code and findings first; zero cheerleading.

## Domain Constraints (Critical)
- **Battery Bank State:** All 8 Packs (800 Ah / 38.4 kWh / 120 cells) are fully connected to the main DC busbar and in active production use.
- **Huawei ESM-48100B1 Batteries:** Never instruct or require the user to change DIP switches on active packs without explicit consent.
- **RS485 Bus & Pin Isolation:** Keep Pack 4 on its isolated bus to prevent address collisions (ID 214) and eliminate noise loops.
- **T-CAN485 Hardware:** Prefer isolated external modules (Red/Black) for battery lines; use onboard CAN bus for Inverter Pylontech protocol.
- **EM11000 RS232 Inverter Bridge (`192.168.8.111`):**
  - Use direct 3.3V/GND power from ESP32 to MAX3232 (no `B0505S` without optocouplers).
  - Keep UART fixed at `9600` baud `8N1`; never use runtime `load_settings()` loops or `register_count > 1` gap-bridging on 16-bit sensors in `modbus_controller`.
