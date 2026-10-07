---
description: Validate and audit ESPHome solar/battery configuration files for common Modbus timing, memory leaks, and grounding issues.
---

Perform a comprehensive review and validation of the ESPHome YAML configuration file for solar battery systems:

1. **Check UART & Modbus Settings:**
   - Ensure `mode: INPUT_PULLUP` is present on all RS485 RX pins.
   - Verify that `parity: EVEN`, `baud_rate: 9600`, and `stop_bits: 1` match the target BMS specifications.
   - Confirm `send_wait_time` is at least 1500ms to avoid overloading slow battery controllers.

2. **Check Architecture & Bus Safety:**
   - Detect if duplicate slave IDs exist on the same UART bus.
   - Ensure external isolated modules are designated for battery and inverter connections instead of raw onboard transceivers.

3. **Check Heap & Polling Strategy:**
   - Ensure polling intervals are staggered or use sequential Time-Division Multiplexing (TDM) script loops instead of simultaneous updates.
   - Flag any potential memory bloat or unbounded batching.

4. **Summarize Findings:**
   - Report errors (high risk), warnings (medium risk), and optimizations (performance/clarity).
