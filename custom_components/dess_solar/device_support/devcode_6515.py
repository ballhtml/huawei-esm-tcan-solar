"""Devcode 6515 Profile: ANENJI ANJ-HHS-11KW-48V-WIFI."""

from __future__ import annotations

DEVICE_INFO = {
    "name": "Home Energy EM11000",
    "description": "ANENJI 11kW / Maxsky EM11000 Solar Inverter (devcode 6515, Protocol 4)",
    "manufacturer": "ANENJI",
    "model": "EM11000",
    "supported_features": [
        "dual_mppt_tracking",
        "battery_management",
        "real_time_telemetry",
        "dynamic_parameter_control",
        "energy_tracking",
    ],
}

OUTPUT_PRIORITY_MAPPING: dict[str, str] = {
    "SUB": "Solar → Utility → Battery",
    "SBU": "Solar → Battery → Utility",
    "SUF": "Solar → Utility First",
}

CHARGER_PRIORITY_MAPPING: dict[str, str] = {
    "SOF": "Solar First",
    "SNU": "Solar and Utility",
    "OSO": "Only Solar",
    "SOR": "Solar or Utility",
}

OPERATING_MODE_MAPPING: dict[str, str] = {
    "OffgridMode": "Off-grid Mode",
    "Bypass Mode": "Grid Mode",
    "Line Mode": "Grid Mode",
    "Mains Mode": "Grid Mode",
    "Battery Mode": "Battery Mode",
    "Inverter Mode": "Off-grid Mode",
    "Standby": "Standby",
    "Fault": "Fault",
}

# Map raw API parameter and last_data titles to canonical names
SENSOR_TITLE_MAPPINGS: dict[str, str] = {
    # Fix OEM Typos
    "INV Module Termperature": "Inverter Temperature",
    "DC Module Termperature": "DC Module Temperature",
    "Output Aparent Power": "Output Apparent Power",
    "Devise serial number": "Device Serial Number",
    "Output frequency": "Output Frequency",
    # Solar Strings (PV1, PV2, Total)
    "PV1 Voltage": "PV1 Voltage",
    "PV1 Power": "PV1 Charger Power",
    "PV1 Current": "PV1 Charger Current",
    "PV2 Voltage": "PV2 Voltage",
    "PV2 Power": "PV2 Charger Power",
    "PV2 Current": "PV2 Charger Current",
    "Total PV Power": "PV Power",
    "Total PV Charging Power": "PV Total Charger Power",
    "Total PV Charging Current": "PV Charging Current",
    "PV temperature": "PV Temperature",
    # Energy Sensors & Deduplication
    "Daily PV energy generation": "Energy Today",
    "Today generation": "Energy Today",
    "Total PV energy generation": "Energy Total",
    "Total generation": "Energy Total",
    # Priority Sensor Standardizations
    "Main Output Priority": "Main Output Priority",
    "Output priority": "Main Output Priority",
    "Current output priority": "Main Output Priority",
    "bse_eybond_read_50": "Main Output Priority",
    "bc_output_source_priority": "Main Output Priority",
    "Current charging priority": "Charger Source Priority",
    "bat_eybond_read_59": "Charger Source Priority",
    "Charger Source Priority": "Charger Source Priority",
    "Charge Priority": "Charger Source Priority",
    # Energy flow & hardware IDs
    "pv_output_power": "PV Power",
    "battery_active_power": "Battery Power",
    "load_active_power": "Load Power",
    "grid_active_power": "Grid Power",
    "bt_battery_capacity": "SOC",
    "soh": "Battery SOH",
    "SOH": "Battery SOH",
    "battery_soh": "Battery SOH",
    "Battery SOH": "Battery SOH",
    "State of Health": "Battery SOH",
    "bt_soh": "Battery SOH",
    "Battery Rated Capacity": "Battery Rated Capacity",
    "Battery Current Direction": "Battery Current Direction",
    "Battery Remaining Energy Wh": "Battery Remaining Energy Wh",
    "Day Battery Charge": "Day Battery Charge",
    "Day Battery Discharge": "Day Battery Discharge",
    "Battery Charge Power": "Battery Charge Power",
    "Battery Discharge Power": "Battery Discharge Power",
    "energy_today": "Energy Today",
    "eybond_read_24": "Battery Voltage",
    "eybond_read_25": "Battery Current",
    "eybond_read_43": "PV1 Voltage",
    "eybond_read_45": "PV1 Charger Power",
    "eybond_read_46": "PV2 Voltage",
    "eybond_read_48": "PV2 Charger Power",
    # Apparent Power, Output Current and Load Percentage
    "Output Current": "Output Current",
    "Output current": "Output Current",
    "AC Output Current": "Output Current",
    "ac_output_current": "Output Current",
    "output_current": "Output Current",
    "inv_output_current": "Output Current",
    "Total Output Current": "Output Current",
    "Load Current": "Output Current",
    "Output Apparent Power": "Output Apparent Power",
    "AC Output Apparent Power": "Output Apparent Power",
    "bc_eybond_read_27": "Output Apparent Power",
    "bt_ac_output_apparent_power": "Output Apparent Power",
    "bc_output_apparent_power": "Output Apparent Power",
    "Load Percentage": "Load Percentage",
    "Load Percent": "Load Percentage",
    "Output Load Percent": "Load Percentage",
    "bt_output_load_percent": "Load Percentage",
    "bc_load_percent": "Load Percentage",
    "bc_eybond_read_37": "Load Percentage",
}

VALUE_TRANSFORMATIONS: dict = {}

# Parameters to fetch via queryDeviceParsEs in parallel with last_data
PARAMETER_SENSOR_NAMES: set[str] = {
    "Battery Voltage",
    "Battery Current",
    "PV1 Voltage",
    "PV1 Power",
    "PV2 Voltage",
    "PV2 Power",
    "Total PV Power",
    "Daily PV energy generation",
    "Output Apparent Power",
    "Load Percent",
    "Load Percentage",
    "Output Voltage",
    "Output Current",
    "Output frequency",
    "Output Active Power",
    # Internal Eybond hardware IDs
    "eybond_read_24",
    "eybond_read_25",
    "eybond_read_43",
    "eybond_read_45",
    "eybond_read_46",
    "eybond_read_48",
    "bc_eybond_read_27",
    "bc_eybond_read_37",
    "bse_eybond_read_50",
    "pv_output_power",
    "energy_today",
}

DEVCODE_CONFIG = {
    "device_info": DEVICE_INFO,
    "output_priority_mapping": OUTPUT_PRIORITY_MAPPING,
    "charger_priority_mapping": CHARGER_PRIORITY_MAPPING,
    "operating_mode_mapping": OPERATING_MODE_MAPPING,
    "sensor_title_mappings": SENSOR_TITLE_MAPPINGS,
    "value_transformations": VALUE_TRANSFORMATIONS,
    "parameter_sensor_names": PARAMETER_SENSOR_NAMES,
}
