---
name: Home Energy & Battery Storage Design System
description: Industrial-grade, high-density telemetry and energy management interface for Home Assistant
colors:
  primary: "#10b981"
  primary-hover: "#059669"
  warning: "#f59e0b"
  danger: "#ef4444"
  info: "#3b82f6"
  accent-purple: "#8b5cf6"
  surface-card: "rgba(255, 255, 255, 0.04)"
  surface-hover: "rgba(255, 255, 255, 0.08)"
  border-subtle: "rgba(255, 255, 255, 0.08)"
  divider: "rgba(127, 127, 127, 0.18)"
  text-primary: "var(--primary-text-color, #ffffff)"
  text-secondary: "var(--secondary-text-color, #9ca3af)"
typography:
  display:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "2rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.02em"
  title:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "-0.01em"
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "0em"
  data-numeric:
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace"
    fontSize: "0.875rem"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "0em"
rounded:
  sm: "6px"
  md: "10px"
  lg: "12px"
  pill: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
components:
  card-glass:
    backgroundColor: "{colors.surface-card}"
    rounded: "{rounded.lg}"
    padding: "16px"
  badge-healthy:
    backgroundColor: "rgba(16, 185, 129, 0.12)"
    textColor: "{colors.primary}"
    rounded: "{rounded.pill}"
    padding: "2px 8px"
  badge-caution:
    backgroundColor: "rgba(245, 158, 11, 0.12)"
    textColor: "{colors.warning}"
    rounded: "{rounded.pill}"
    padding: "2px 8px"
  badge-alert:
    backgroundColor: "rgba(239, 68, 68, 0.12)"
    textColor: "{colors.danger}"
    rounded: "{rounded.pill}"
    padding: "2px 8px"
---

## Overview

The Home Energy & Battery Storage design system governs the visual hierarchy, component architecture, and interaction states across all Home Assistant solar views (`/home-energy`, `/home-energy/cells`, and `/home-energy/inverter-setup`). Designed strictly in the `Operate` mode, the interface prioritizes high-density telemetry, instant scanability under all ambient lighting conditions, and strict tabular numeric alignment for electrical and financial calculations.

## Colors

The palette employs a purposeful, semantic role structure calibrated for electrical and solar domains:

- **Primary / Battery Healthy (`#10b981` Emerald):** Represents balanced cells, nominal SOH, charging states, and verified electrical safety.
- **Solar & Caution (`#f59e0b` Amber):** Represents live PV generation power, battery discharging state, and minor cell drift ($21\text{--}40\text{ mV}$).
- **Grid & Utility (`#3b82f6` Blue):** Represents PEA utility grid connection, AC voltage, and standard billing liabilities.
- **Critical & Alarm (`#ef4444` Crimson):** High cell drift ($> 40\text{ mV}$), inverter overload proximity, or communication timeouts.
- **Financial Benefit (`#8b5cf6` Purple):** Government 50-unit discount incentives and cumulative bill offset.
- **Backgrounds & Dividers:** Subtle translucent overlays (`rgba(255, 255, 255, 0.04)` on dark mode, `rgba(0, 0, 0, 0.02)` on light mode) with `1px` subtle boundary borders (`rgba(255, 255, 255, 0.08)`). Hard offset shadows and decorative neon glows are strictly refused.

## Typography

Typography balances clean humanist UI labels with strict tabular monospace numeric alignment:

- **Tabular Numerals (`font-variant-numeric: tabular-nums`):** Mandatory on all tables, cell matrix voltages, currencies, and percentages to eliminate visual wobble during 1-second live streaming.
- **Monospace Precision (`ui-monospace, Consolas`):** Applied to individual cell voltages (`3.228 V`), pack currents, and Modbus hexadecimal registers (`0x0042`, `0x0005`).
- **Hierarchy:**
  - **Screen Titles (H2):** 20px, Semi-bold (600), `-0.01em` tracking.
  - **Card Headers (H3):** 16px, Medium (500).
  - **Metric Labels:** 11–12px, Muted (`var(--secondary-text-color)`), uppercase when abbreviating electrical units.
  - **Metric Values:** 18–24px, Bold (700) with integrated 12px unit symbols.

## Layout

- **3-Tab Master/Detail Surface:**
  - **Tab 1: Home Energy (`/home-energy`):** Intuitive non-technical layout: Top navigation chips, compact Solar Bar overview, hero animated Sunsynk power flow, detailed financial ledger. Column 2 is dedicated to Battery Bank telemetry (Active Discharging/Charging banner, real-time 8-pack Load Sharing ranking, core metrics, 8-pack SOC bars). Column 3 hosts 24h & 7d energy balance charts, and System Controls & Diagnostics with one-touch navigation (120-Cell Diagnostics & Inverter Setup) plus inverter priority toggles.
  - **Tab 2: Cell Diagnostics (`/home-energy/cells`):** Deep 120-cell telemetry matrix ($15\text{ Cells} \times 8\text{ Packs}$), min/max cell comparison, and hardware SOH/thermal registry.
  - **Tab 3: Inverter Setup (`/home-energy/inverter-setup`):** Priority controls (SBU/SUB), current limits, 15S cut-off voltage configuration, and one-touch profile triggers.
- **Responsive Breakpoints:**
  - **Mobile (< 600px):** Single vertical stack; 120-cell table wrapped in horizontal scroll container (`min-width: 620px; overflow-x: auto`) to prevent text squeezing.
  - **Tablet (600px – 1024px):** 2-column balanced grid; sticky table headers.
  - **Desktop (> 1024px):** 3-column panoramic layout with multi-pack load distribution graphs.

## Elevation & Depth

- Elevation is achieved purely through translucent tonal layering (`rgba(255, 255, 255, 0.04)`) and `1px` crisp hairline borders.
- Zero-blur block shadows and heavy drop-shadows are excluded.
- Interactive cards elevate subtly on hover (`transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15); transition: all 0.15s ease-out`).

## Shapes

- **Card Enclosures:** `border-radius: 12px` (`{rounded.lg}`).
- **Input & Select Dropdowns:** `border-radius: 8px` (`{rounded.md}`).
- **Status Badges & Pills:** `border-radius: 9999px` (`{rounded.pill}`).
- **Table Cells:** `border-radius: 4px` on highlighted min/max cell outliers.

## Components

1. **Mushroom Chip Bar:** Positioned at the top of every tab for instant situational awareness and 1-click cross-tab navigation.
2. **Sunsynk Power Flow Card:** Displays active solar generation, grid import/export, battery charge/discharge, and house consumption with animated flow dots.
3. **Financial Ledger Table:** Displays PEA billing cycle totals (20th to 20th), unit consumption, standard cost, government discount deduction, and net liability.
4. **120-Cell Matrix:** $15\times 8$ real-time grid rendering cell voltages with min/max delta calculation.
5. **Inverter Parameter Controls:** Mushroom Select Cards paired with numeric sliders for safe threshold adjustment without physical hardware intervention.

## Do's and Don'ts

### Do
- Always enforce `font-variant-numeric: tabular-nums` on any table displaying electrical metrics or money.
- Always provide bidirectional navigation buttons on all tabs.
- Always guard Jinja2 templates with default fallbacks: `states(...) | float(0)`.
- Use soft pill badges (`rgba` background + 1px border) for semantic status cues.

### Don't
- Never use decorative 4px `border-left` or `border-right` on callouts or alert cards.
- Never hardcode fixed pixel widths that break on 360px mobile displays.
- Never omit unit symbols or round cell voltages to less than 3 decimal places (`0.001 V` precision required).
- Never send Modbus write commands to ESM batteries without explicit user authorization.
