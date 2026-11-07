"""Constants for the DessMonitor Solar Universal integration."""

from typing import Final

DOMAIN: Final = "dess_solar"
VERSION: Final = "1.0.0"

# Configuration keys
CONF_USERNAME: Final = "username"
CONF_PASSWORD: Final = "password"
CONF_COMPANY_KEY: Final = "company_key"
CONF_UPDATE_INTERVAL: Final = "update_interval"
CONF_LOCAL_MODE: Final = "local_mode"

DEFAULT_COMPANY_KEY: Final = "bnrl_frRFjEz8Mkn"
DEFAULT_UPDATE_INTERVAL: Final = 7
MIN_UPDATE_INTERVAL: Final = 3
MAX_UPDATE_INTERVAL: Final = 3600

UPDATE_INTERVAL_OPTIONS: Final = {
    3: "3 seconds (Ultra-Fast Live)",
    5: "5 seconds (Exact 5s Cloud Feed)",
    7: "7 seconds (Optimal: Cloud Buffer Safe - Recommended)",
    10: "10 seconds (Standard Fast)",
    15: "15 seconds",
    30: "30 seconds",
    60: "1 minute (Standard)",
    300: "5 minutes (Low API Usage)",
    600: "10 minutes",
    1800: "30 minutes",
    3600: "1 hour",
}

LOCAL_MODE_DISABLED: Final = "disabled"
LOCAL_MODE_PREFER_LOCAL: Final = "prefer_local"
LOCAL_MODE_OPTIONS: Final = {
    LOCAL_MODE_DISABLED: "Cloud only",
    LOCAL_MODE_PREFER_LOCAL: "Prefer local, fall back to cloud",
}

API_BASE_URL: Final = "https://api.dessmonitor.com/public/"
APP_ID: Final = "ha-dess-solar"
APP_VERSION: Final = "1.0.0"

UNITS: Final = {
    "POWER": "W",
    "POWER_KW": "kW",
    "APPARENT_POWER": "VA",
    "ENERGY": "kWh",
    "VOLTAGE": "V",
    "CURRENT": "A",
    "FREQUENCY": "Hz",
    "TEMPERATURE": "°C",
    "PERCENTAGE": "%",
}

OUTPUT_PRIORITIES = [
    "SBU",
    "SUB",
    "UTI",
    "SOL",
    "SUF",
    "Solar → Battery → Utility",
    "Solar → Utility → Battery",
    "Solar → Utility First",
    "Utility First",
    "Solar First",
    "Unknown",
]

CHARGER_PRIORITIES = [
    "SOF",
    "SNU",
    "OSO",
    "SOR",
    "Utility First",
    "PV First",
    "Solar and Utility",
    "Only PV",
    "Only Solar",
    "Solar First",
    "Solar or Utility",
    "Unknown",
]

OPERATING_MODES = [
    "Power On",
    "Standby",
    "Line Mode",
    "Battery Mode",
    "Fault",
    "Off-grid Mode",
    "Grid Mode",
    "Hybrid Mode",
    "Bypass Mode",
    "OffgridMode",
    "Line",
    "Battery",
    "Unknown",
]


SENSOR_TYPES = {
    # Data Provenance
    "Data Source": {
        "name": "Data Source",
        "unit": "",
        "device_class": "enum",
        "options": ["Cloud", "Cached Cloud", "Local"],
        "icon": "mdi:source-branch",
    },
    # Inverter / System Power
    "Output Active Power": {
        "name": "Output Power",
        "unit": UNITS["POWER"],
        "device_class": "power",
        "state_class": "measurement",
        "icon": "mdi:flash",
    },
    "Output Apparent Power": {
        "name": "Output Apparent Power",
        "unit": UNITS["APPARENT_POWER"],
        "device_class": "apparent_power",
        "state_class": "measurement",
        "icon": "mdi:flash",
    },
    "Output Aparent Power": {
        "name": "Output Apparent Power",
        "unit": UNITS["APPARENT_POWER"],
        "device_class": "apparent_power",
        "state_class": "measurement",
        "icon": "mdi:flash",
    },
    "Output Current": {
        "name": "Output Current",
        "unit": UNITS["CURRENT"],
        "device_class": "current",
        "state_class": "measurement",
        "icon": "mdi:current-ac",
    },
    "Output current": {
        "name": "Output Current",
        "unit": UNITS["CURRENT"],
        "device_class": "current",
        "state_class": "measurement",
        "icon": "mdi:current-ac",
    },
    "ac_output_current": {
        "name": "Output Current",
        "unit": UNITS["CURRENT"],
        "device_class": "current",
        "state_class": "measurement",
        "icon": "mdi:current-ac",
    },
    "Load Power": {
        "name": "Load Power",
        "unit": UNITS["POWER"],
        "device_class": "power",
        "state_class": "measurement",
        "icon": "mdi:home-lightning-bolt",
    },
    "Load Percentage": {
        "name": "Load Percentage",
        "unit": UNITS["PERCENTAGE"],
        "state_class": "measurement",
        "icon": "mdi:gauge",
    },
    "Load Percent": {
        "name": "Load Percentage",
        "unit": UNITS["PERCENTAGE"],
        "state_class": "measurement",
        "icon": "mdi:gauge",
    },
    "Grid Power": {
        "name": "Grid Power",
        "unit": UNITS["POWER"],
        "device_class": "power",
        "state_class": "measurement",
        "icon": "mdi:transmission-tower",
    },
    # PV Power & Voltages
    "PV Power": {
        "name": "Solar Total Power",
        "unit": UNITS["POWER"],
        "device_class": "power",
        "state_class": "measurement",
        "icon": "mdi:solar-power",
    },
    "PV1 Charger Power": {
        "name": "PV1 Power",
        "unit": UNITS["POWER"],
        "device_class": "power",
        "state_class": "measurement",
        "icon": "mdi:solar-power-variant",
    },
    "PV2 Charger Power": {
        "name": "PV2 Power",
        "unit": UNITS["POWER"],
        "device_class": "power",
        "state_class": "measurement",
        "icon": "mdi:solar-power-variant",
    },
    "PV Total Charger Power": {
        "name": "PV Total Charging Power",
        "unit": UNITS["POWER"],
        "device_class": "power",
        "state_class": "measurement",
        "icon": "mdi:solar-power",
    },
    "PV Voltage": {
        "name": "Solar Voltage",
        "unit": UNITS["VOLTAGE"],
        "device_class": "voltage",
        "state_class": "measurement",
        "icon": "mdi:solar-power",
    },
    "PV1 Voltage": {
        "name": "PV1 Voltage",
        "unit": UNITS["VOLTAGE"],
        "device_class": "voltage",
        "state_class": "measurement",
        "icon": "mdi:solar-power-variant",
    },
    "PV2 Voltage": {
        "name": "PV2 Voltage",
        "unit": UNITS["VOLTAGE"],
        "device_class": "voltage",
        "state_class": "measurement",
        "icon": "mdi:solar-power-variant",
    },
    "PV1 Charger Current": {
        "name": "PV1 Current",
        "unit": UNITS["CURRENT"],
        "device_class": "current",
        "state_class": "measurement",
        "icon": "mdi:current-dc",
    },
    "PV2 Charger Current": {
        "name": "PV2 Current",
        "unit": UNITS["CURRENT"],
        "device_class": "current",
        "state_class": "measurement",
        "icon": "mdi:current-dc",
    },
    # Battery Metrics
    "Battery Voltage": {
        "name": "Battery Voltage",
        "unit": UNITS["VOLTAGE"],
        "device_class": "voltage",
        "state_class": "measurement",
        "icon": "mdi:battery",
    },
    "Battery Current": {
        "name": "Battery Current",
        "unit": UNITS["CURRENT"],
        "device_class": "current",
        "state_class": "measurement",
        "icon": "mdi:battery",
    },
    "Battery Power": {
        "name": "Battery Power",
        "unit": UNITS["POWER"],
        "device_class": "power",
        "state_class": "measurement",
        "icon": "mdi:battery",
    },
    "Battery Charging Current": {
        "name": "Battery Charging Current",
        "unit": UNITS["CURRENT"],
        "device_class": "current",
        "state_class": "measurement",
        "icon": "mdi:battery-charging",
    },
    "Battery Discharge Current": {
        "name": "Battery Discharge Current",
        "unit": UNITS["CURRENT"],
        "device_class": "current",
        "state_class": "measurement",
        "icon": "mdi:battery-arrow-down",
    },
    "AC Charging Power": {
        "name": "AC Charging Power",
        "unit": UNITS["POWER"],
        "device_class": "power",
        "state_class": "measurement",
        "icon": "mdi:battery-charging",
    },
    "State of Charge": {
        "name": "Battery SOC",
        "unit": UNITS["PERCENTAGE"],
        "device_class": "battery",
        "state_class": "measurement",
        "icon": "mdi:battery-high",
    },
    "SOC": {
        "name": "Battery SOC",
        "unit": UNITS["PERCENTAGE"],
        "device_class": "battery",
        "state_class": "measurement",
        "icon": "mdi:battery-high",
    },
    "Battery SOH": {
        "name": "Battery SOH",
        "unit": UNITS["PERCENTAGE"],
        "device_class": "battery",
        "state_class": "measurement",
        "icon": "mdi:heart-pulse",
    },
    "SOH": {
        "name": "Battery SOH",
        "unit": UNITS["PERCENTAGE"],
        "device_class": "battery",
        "state_class": "measurement",
        "icon": "mdi:heart-pulse",
    },
    "State of Health": {
        "name": "Battery SOH",
        "unit": UNITS["PERCENTAGE"],
        "device_class": "battery",
        "state_class": "measurement",
        "icon": "mdi:heart-pulse",
    },
    "Battery Rated Capacity": {
        "name": "Battery Rated Capacity",
        "unit": "Ah",
        "state_class": "measurement",
        "icon": "mdi:battery-check",
    },
    "Battery Current Direction": {
        "name": "Battery Current Direction",
        "unit": "",
        "device_class": "enum",
        "options": ["Charging", "Discharging", "Idle"],
        "icon": "mdi:swap-horizontal-bold",
    },
    "Battery Remaining Energy Wh": {
        "name": "Battery Remaining Energy Wh",
        "unit": "Wh",
        "device_class": "energy_storage",
        "state_class": "measurement",
        "icon": "mdi:battery-heart-variant",
    },
    "Day Battery Charge": {
        "name": "Day Battery Charge",
        "unit": UNITS["ENERGY"],
        "device_class": "energy",
        "state_class": "total_increasing",
        "icon": "mdi:battery-charging",
    },
    "Day Battery Discharge": {
        "name": "Day Battery Discharge",
        "unit": UNITS["ENERGY"],
        "device_class": "energy",
        "state_class": "total_increasing",
        "icon": "mdi:battery-arrow-down",
    },
    "Battery Charge Power": {
        "name": "Battery Charge Power",
        "unit": UNITS["POWER"],
        "device_class": "power",
        "state_class": "measurement",
        "icon": "mdi:battery-charging",
    },
    "Battery Discharge Power": {
        "name": "Battery Discharge Power",
        "unit": UNITS["POWER"],
        "device_class": "power",
        "state_class": "measurement",
        "icon": "mdi:battery-arrow-down",
    },
    # Grid & Output Voltages / Frequencies
    "Grid Voltage": {
        "name": "Grid Voltage",
        "unit": UNITS["VOLTAGE"],
        "device_class": "voltage",
        "state_class": "measurement",
        "icon": "mdi:transmission-tower",
    },
    "Grid Frequency": {
        "name": "Grid Frequency",
        "unit": UNITS["FREQUENCY"],
        "device_class": "frequency",
        "state_class": "measurement",
        "icon": "mdi:sine-wave",
    },
    "Output Voltage": {
        "name": "Output Voltage",
        "unit": UNITS["VOLTAGE"],
        "device_class": "voltage",
        "state_class": "measurement",
        "icon": "mdi:flash",
    },
    "Output Frequency": {
        "name": "Output Frequency",
        "unit": UNITS["FREQUENCY"],
        "device_class": "frequency",
        "state_class": "measurement",
        "icon": "mdi:sine-wave",
    },
    # Temperatures
    "Inverter Temperature": {
        "name": "Inverter Temperature",
        "unit": UNITS["TEMPERATURE"],
        "device_class": "temperature",
        "state_class": "measurement",
        "icon": "mdi:thermometer",
    },
    "DC Module Temperature": {
        "name": "DC Module Temperature",
        "unit": UNITS["TEMPERATURE"],
        "device_class": "temperature",
        "state_class": "measurement",
        "icon": "mdi:thermometer",
    },
    "PV Temperature": {
        "name": "PV Temperature",
        "unit": UNITS["TEMPERATURE"],
        "device_class": "temperature",
        "state_class": "measurement",
        "icon": "mdi:thermometer",
    },
    # Energy Counters (HA Energy Dashboard compatible)
    "Energy Today": {
        "name": "Energy Today",
        "unit": UNITS["ENERGY"],
        "device_class": "energy",
        "state_class": "total_increasing",
        "icon": "mdi:solar-power",
    },
    "Energy Total": {
        "name": "Energy Total",
        "unit": UNITS["ENERGY"],
        "device_class": "energy",
        "state_class": "total_increasing",
        "icon": "mdi:counter",
    },
    # Operational Status
    "Operating Mode": {
        "name": "Operating Mode",
        "unit": "",
        "device_class": "enum",
        "options": OPERATING_MODES,
        "icon": "mdi:power-settings",
    },
    "Main Output Priority": {
        "name": "Main Output Priority",
        "unit": "",
        "device_class": "enum",
        "options": OUTPUT_PRIORITIES,
        "icon": "mdi:swap-horizontal",
    },
    "Output priority": {
        "name": "Main Output Priority",
        "unit": "",
        "device_class": "enum",
        "options": OUTPUT_PRIORITIES,
        "icon": "mdi:swap-horizontal",
    },
    "Charger Source Priority": {
        "name": "Charger Source Priority",
        "unit": "",
        "device_class": "enum",
        "options": CHARGER_PRIORITIES,
        "icon": "mdi:battery-charging-wireless",
    },
    "Charge Priority": {
        "name": "Charger Source Priority",
        "unit": "",
        "device_class": "enum",
        "options": CHARGER_PRIORITIES,
        "icon": "mdi:battery-charging-wireless",
    },
}
