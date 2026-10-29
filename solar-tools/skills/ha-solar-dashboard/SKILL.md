---
name: ha-solar-dashboard
description: Runbook and templates for designing high-density Home Assistant Lovelace dashboards, energy cards, and automations for solar inverters and lithium battery systems.
---

# Home Assistant Solar & Battery Dashboard Skill

This skill provides best practices, templates, and patterns for building responsive, high-density Home Assistant Lovelace dashboards and automations for solar batteries and inverters.

## 1. Core Visual Hierarchy

Organize dashboards into 3 intuitive layers:
1. **System Health & Overview:** Total SOC gauge, System Voltage, Real-time Power (Charging in green, Discharging in amber/red).
2. **Individual Battery Packs:** Pack comparison cards showing SOC, Voltage, Current, SOH, and Temperature.
3. **Deep Telemetry & Cell Voltages:** Expandable or tabbed view showing individual 15-cell or 16-cell voltages with min/max delta highlight.

## 2. Lovelace Card Patterns

### Energy & Battery Overview Card
```yaml
type: vertical-stack
cards:
  - type: custom:mushroom-title-card
    title: Solar Battery Storage
    subtitle: System Overview
  - type: grid
    columns: 2
    square: false
    cards:
      - type: custom:mushroom-entity-card
        entity: sensor.total_battery_system_soc
        name: Battery SOC
        icon: mdi:battery-high
        icon_color: green
      - type: custom:mushroom-entity-card
        entity: sensor.total_battery_system_power
        name: Battery Power
        icon: mdi:flash
```

### Multi-pack Bar Card
```yaml
type: custom:bar-card
title: Battery Packs SOC
entities:
  - entity: sensor.pack1_state_of_charge
    name: Pack 1
  - entity: sensor.pack2_state_of_charge
    name: Pack 2
  - entity: sensor.pack3_state_of_charge
    name: Pack 3
  - entity: sensor.pack4_state_of_charge
    name: Pack 4
positions:
  icon: 'inside'
  indicator: 'inside'
severity:
  - color: '#e74c3c'
    from: 0
    to: 20
  - color: '#f39c12'
    from: 21
    to: 50
  - color: '#2ecc71'
    from: 51
    to: 100
```

## 3. Automation Patterns
- **High Temperature Throttling:** Alert if `max_battery_cell_temp` > 45°C.
- **Cell Delta Alarm:** Calculate `max_cell_voltage - min_cell_voltage` and trigger notification if delta > 50mV during absorption.
