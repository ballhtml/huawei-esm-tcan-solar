---
name: esphome-modbus
description: Expert runbook for configuring, validating, and troubleshooting ESPHome Modbus RTU and CAN Bus communication with solar inverters and lithium BMS batteries (e.g. Huawei ESM-48100B1, Pylontech).
---

# ESPHome Modbus & CAN Bus Engineering Skill

This skill guides the creation, optimization, and debugging of ESPHome firmware interfacing with solar batteries and inverters over Modbus RTU (RS485) and CAN Bus (TWAI).

## 1. Modbus Configuration Pattern

### UART Setup
```yaml
uart:
  - id: uart_bms
    tx_pin: GPIO33
    rx_pin:
      number: GPIO32
      mode: INPUT_PULLUP
    baud_rate: 9600
    parity: EVEN
    stop_bits: 1
    rx_timeout: 90
    rx_buffer_size: 512
```

### Controller & Time-Division Polling
To avoid overwhelming the ESP32 heap and bus collisions, avoid simultaneous polling. Use sequential script loops:

```yaml
script:
  - id: modbus_polling_loop
    mode: restart
    then:
      - while:
          condition:
            lambda: 'return true;'
          then:
            - lambda: 'id(pack1_controller).update();'
            - delay: 3000ms
            - lambda: 'id(pack2_controller).update();'
            - delay: 3000ms
```

## 2. CAN Bus Interconnect Pattern

When linking two ESP32 / T-CAN485 boards or talking to inverters:

```yaml
canbus:
  - platform: esp32_can
    id: can_bus
    tx_pin: GPIO27
    rx_pin: GPIO26
    can_id: 0
    bit_rate: 500kbps
```

### Transmitting Pylontech Telemetry
- `0x351`: Charge/Discharge Voltage & Current Limits
- `0x355`: SOC & SOH (uint16_t each)
- `0x356`: Voltage (0.01V), Current (0.1A signed), Temperature (0.1°C signed)

## 3. Grounding & Noise Troubleshooting Checklist
1. **Timeouts during AC/Solar Charging:**
   - Verify if isolated RS485 module terminal `GND` is connected to battery RJ45 pin 3 or 6.
   - Never float the RS485 signal ground; tie it to the battery BMS reference ground to clamp common-mode voltage.
2. **ESP32 Reset / Latchup:**
   - Power ESP32 from a clean DC supply (e.g. high-grade Glink 5V 2A adapter or battery DC-DC step-down) instead of generic phone chargers affected by inverter Y-capacitor leakage.
