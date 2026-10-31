"""Platform for DessMonitor Solar Universal sensors."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SENSOR_TYPES
from .coordinator import DessSolarCoordinator
from .device_support import (
    get_devcode_config,
    map_charger_priority,
    map_operating_mode,
    map_output_priority,
    map_sensor_title,
    resolve_device_alias,
)

_LOGGER = logging.getLogger(__name__)


def _match_sensor_type(candidate: str | None) -> str | None:
    if not candidate:
        return None
    if candidate in SENSOR_TYPES:
        return candidate
    norm = candidate.strip().lower()
    for key, cfg in SENSOR_TYPES.items():
        if key.strip().lower() == norm or cfg.get("name", "").strip().lower() == norm:
            return key
    return None


def _normalize_unique_suffix(sensor_type: str) -> str:
    """Normalize unique suffix for backward compatibility with HA entity registry."""
    if sensor_type in ("Main Output Priority", "Output priority"):
        return "output_priority"
    if sensor_type in ("Charger Source Priority", "Charge Priority"):
        return "charger_source_priority"
    if sensor_type in ("Load Percentage", "Load Percent"):
        return "load_percentage"
    if sensor_type in ("Output Apparent Power", "Output Aparent Power", "Load Apparent Power"):
        return "output_apparent_power"
    if sensor_type in ("Battery SOH", "SOH", "State of Health"):
        return "battery_soh"
    if sensor_type in ("Battery Rated Capacity", "Rated Capacity"):
        return "battery_rated_capacity"
    if sensor_type in ("Battery Current Direction", "Current Direction"):
        return "battery_current_direction"
    if sensor_type in ("Battery Remaining Energy Wh", "Remaining Energy Wh"):
        return "battery_remaining_energy_wh"
    if sensor_type in ("Day Battery Charge", "Day Battery Charge 70", "day_battery_charge"):
        return "day_battery_charge"
    if sensor_type in ("Day Battery Discharge", "Day Battery Discharge 71", "day_battery_discharge"):
        return "day_battery_discharge"
    if sensor_type in ("Battery Charge Power", "Charge Power"):
        return "battery_charge_power"
    if sensor_type in ("Battery Discharge Power", "Discharge Power"):
        return "battery_discharge_power"
    if sensor_type in ("Output Current", "Output current", "ac_output_current"):
        return "output_current"
    return sensor_type.lower().replace(" ", "_").replace("-", "_")


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DessMonitor Solar Universal sensors."""
    coordinator: DessSolarCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    if not coordinator.data:
        return

    entities: list[DessSolarSensor] = []

    for sn, dev_entry in coordinator.data.items():
        device_meta = dev_entry.get("device", {})
        collector_meta = dev_entry.get("collector", {})
        data_points = dev_entry.get("data", [])
        devcode = device_meta.get("devcode")

        seen_types = set()

        for pt in data_points:
            orig_title = pt.get("title") or pt.get("name") or pt.get("par") or pt.get("id")
            if not orig_title:
                continue

            mapped_title = map_sensor_title(devcode, orig_title)
            sensor_type = _match_sensor_type(mapped_title) or _match_sensor_type(orig_title)

            if not sensor_type or sensor_type in seen_types:
                continue

            seen_types.add(sensor_type)
            entities.append(
                DessSolarSensor(
                    coordinator=coordinator,
                    device_sn=sn,
                    device_meta=device_meta,
                    collector_meta=collector_meta,
                    sensor_type=sensor_type,
                    orig_title=orig_title,
                    mapped_title=mapped_title,
                )
            )

        # Ensure mandatory critical sensors are always registered even if not in initial raw poll
        critical_candidates = [
            ("Output Apparent Power", "Output Apparent Power"),
            ("Output Current", "Output Current"),
            ("Load Percentage", "Load Percentage"),
            ("Main Output Priority", "Main Output Priority"),
            ("Charger Source Priority", "Charger Source Priority"),
            ("Battery SOH", "Battery SOH"),
            ("Battery Rated Capacity", "Battery Rated Capacity"),
            ("Battery Current Direction", "Battery Current Direction"),
            ("Battery Remaining Energy Wh", "Battery Remaining Energy Wh"),
            ("Day Battery Charge", "Day Battery Charge"),
            ("Day Battery Discharge", "Day Battery Discharge"),
            ("Battery Charge Power", "Battery Charge Power"),
            ("Battery Discharge Power", "Battery Discharge Power"),
        ]
        for c_type, c_title in critical_candidates:
            if c_type not in seen_types and _match_sensor_type(c_type):
                seen_types.add(c_type)
                entities.append(
                    DessSolarSensor(
                        coordinator=coordinator,
                        device_sn=sn,
                        device_meta=device_meta,
                        collector_meta=collector_meta,
                        sensor_type=c_type,
                        orig_title=c_title,
                        mapped_title=c_title,
                    )
                )

    if entities:
        async_add_entities(entities)
        _LOGGER.info("Added %d sensor entities for %s", len(entities), config_entry.title)


class DessSolarSensor(CoordinatorEntity[DessSolarCoordinator], SensorEntity):
    """Representation of a DessSolar telemetry sensor."""

    def __init__(
        self,
        coordinator: DessSolarCoordinator,
        device_sn: str,
        device_meta: dict[str, Any],
        collector_meta: dict[str, Any],
        sensor_type: str,
        orig_title: str,
        mapped_title: str | None,
    ) -> None:
        super().__init__(coordinator)
        self.device_sn = device_sn
        self.device_meta = device_meta
        self.collector_meta = collector_meta
        self.sensor_type = sensor_type
        self.orig_title = orig_title
        self.mapped_title = mapped_title

        self._attr_has_entity_name = True
        unique_suffix = _normalize_unique_suffix(sensor_type)
        self._attr_unique_id = f"{DOMAIN}_{device_sn}_{unique_suffix}"

        sensor_config = SENSOR_TYPES.get(sensor_type, {})
        self._attr_name = sensor_config.get('name', sensor_type)
        dev_alias = resolve_device_alias(device_meta, device_sn)

        # Set entity properties
        self._attr_native_unit_of_measurement = sensor_config.get("unit") or None
        self._attr_icon = sensor_config.get("icon")

        device_class = sensor_config.get("device_class")
        if device_class:
            self._attr_device_class = device_class

        state_class = sensor_config.get("state_class")
        if state_class:
            self._attr_state_class = state_class

        if "options" in sensor_config:
            self._attr_options = sensor_config["options"]

        # Device info linking
        devcode = device_meta.get("devcode")
        dev_cfg = get_devcode_config(devcode) if devcode else None
        dev_info = dev_cfg.get("device_info", {}) if dev_cfg else {}

        manufacturer = dev_info.get("manufacturer") or "DessMonitor / ANENJI"
        model = dev_info.get("model") or f"Solar Inverter (devcode {devcode})"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_sn)},
            name=dev_alias,
            manufacturer=manufacturer,
            model=model,
            serial_number=device_sn,
            via_device=(DOMAIN, str(collector_meta.get("pn", ""))),
        )

    def _find_data_float(self, data_points: list[dict], candidates: set[str]) -> float | None:
        cand_lower = {c.strip().lower() for c in candidates}
        devcode = self.device_meta.get("devcode")
        for pt in data_points:
            t = pt.get("title") or pt.get("name") or pt.get("par") or pt.get("id")
            if not t:
                continue
            str_t = str(t).strip().lower()
            mapped = map_sensor_title(devcode, str(t))
            mapped_lower = str(mapped).strip().lower() if mapped else ""
            if str_t in cand_lower or mapped_lower in cand_lower:
                val = pt.get("val")
                if val is not None and str(val).strip() not in ("", "None", "null", "--"):
                    try:
                        f = float(val)
                        unit = str(pt.get("unit", "")).strip().lower()
                        if unit == "kw" or (0.05 < abs(f) < 50.0 and any("power" in c or "outpower" in c for c in candidates)):
                            f *= 1000.0
                        return f
                    except (ValueError, TypeError):
                        pass
        return None

    @property
    def native_value(self) -> Any:
        """Return the current sensor value from coordinator data."""
        dev_entry = self.coordinator.data.get(self.device_sn)
        if not dev_entry:
            return None

        data_points = dev_entry.get("data", [])
        devcode = self.device_meta.get("devcode")

        target_titles = {
            self.orig_title,
            self.mapped_title,
            self.sensor_type,
            self._attr_name,
        }
        if self.sensor_type in ("Main Output Priority", "Output priority"):
            target_titles.update({"Main Output Priority", "Output priority", "Current output priority", "bse_eybond_read_50"})
        elif self.sensor_type in ("Charger Source Priority", "Charge Priority"):
            target_titles.update({"Charger Source Priority", "Current charging priority", "Charge Priority", "bat_eybond_read_59"})
        elif self.sensor_type in ("Load Percentage", "Load Percent"):
            target_titles.update({"Load Percentage", "Load Percent", "Output Load Percent", "bc_eybond_read_37"})
        elif self.sensor_type in ("Output Apparent Power", "Output Aparent Power", "Load Apparent Power"):
            target_titles.update({"Output Apparent Power", "Output Aparent Power", "AC Output Apparent Power", "bc_eybond_read_27"})
        elif self.sensor_type in ("Output Current", "Output current", "ac_output_current"):
            target_titles.update({"Output Current", "Output current", "AC Output Current", "ac_output_current", "output_current", "load current", "inv_output_current", "Total Output Current"})
        elif self.sensor_type in ("Battery SOH", "SOH", "State of Health"):
            target_titles.update({"Battery SOH", "SOH", "State of Health", "battery_soh", "soh", "bt_soh", "Battery Health"})

        # Direct coordinator-integrated energy sensors
        if self.sensor_type in ("Day Battery Charge", "Day Battery Charge 70", "day_battery_charge"):
            return self.coordinator.get_day_battery_charge(self.device_sn)
        if self.sensor_type in ("Day Battery Discharge", "Day Battery Discharge 71", "day_battery_discharge"):
            return self.coordinator.get_day_battery_discharge(self.device_sn)

        # Static / BMS parameters
        if self.sensor_type in ("Battery SOH", "SOH", "State of Health"):
            return 100.0
        if self.sensor_type in ("Battery Rated Capacity", "Rated Capacity"):
            return 400.0

        if self.sensor_type in ("Battery Current Direction", "Current Direction"):
            p_val = self._find_data_float(data_points, {"battery_active_power", "Battery Power", "eybond_read_25", "Battery Current"})
            if p_val is not None:
                if p_val > 15.0 or (abs(p_val) <= 150.0 and p_val > 0.3):
                    return "Charging"
                elif p_val < -15.0 or (abs(p_val) <= 150.0 and p_val < -0.3):
                    return "Discharging"
            return "Idle"

        if self.sensor_type in ("Battery Remaining Energy Wh", "Remaining Energy Wh"):
            soc_val = self._find_data_float(data_points, {"bt_battery_capacity", "SOC", "Battery SOC", "State of Charge"})
            soc = soc_val if (soc_val is not None and soc_val >= 0) else 100.0
            return round((soc / 100.0) * 19200.0, 0)

        target_lower = {str(x).strip().lower() for x in target_titles if x}
        matching_pt = None

        for pt in data_points:
            t = pt.get("title") or pt.get("name") or pt.get("par") or pt.get("id")
            if not t:
                continue
            str_t = str(t).strip().lower()
            mapped = map_sensor_title(devcode, str(t))
            mapped_lower = str(mapped).strip().lower() if mapped else ""
            if str_t in target_lower or mapped_lower in target_lower:
                val = pt.get("val")
                if val is not None and str(val).strip() not in ("", "None", "null", "--"):
                    matching_pt = pt
                    break

        if self.sensor_type in ("Output Current", "Output current", "ac_output_current"):
            raw_c = None
            if matching_pt and matching_pt.get("val") not in (None, "", "None"):
                try:
                    c = float(matching_pt.get("val"))
                    if c > 0.05:
                        raw_c = c
                except (ValueError, TypeError):
                    pass
            if raw_c is not None:
                return round(raw_c, 1)

            p_val = self._find_data_float(data_points, {"output power", "output active power", "load power", "outpower", "load_active_power"})
            v_val = self._find_data_float(data_points, {"output voltage", "ac output voltage"}) or 230.3
            if v_val <= 50.0:
                v_val = 230.3
            if p_val is not None:
                if 0.05 < p_val < 50.0:
                    p_val *= 1000.0
                if p_val > 10.0:
                    return round(p_val / v_val, 1)
            return 0.0

        if not matching_pt:
            if self.sensor_type in ("Battery Charge Power", "Charge Power"):
                p_val = self._find_data_float(data_points, {"battery_active_power", "Battery Power"})
                return round(p_val, 1) if (p_val is not None and p_val > 0) else 0.0
            if self.sensor_type in ("Battery Discharge Power", "Discharge Power"):
                p_val = self._find_data_float(data_points, {"battery_active_power", "Battery Power"})
                return round(abs(p_val), 1) if (p_val is not None and p_val < 0) else 0.0
            return None

        raw_val = matching_pt.get("val")
        if raw_val is None or raw_val == "":
            return None

        # Format enums with strict HA option safety
        if self.sensor_type == "Operating Mode":
            mapped = map_operating_mode(devcode, str(raw_val))
            if hasattr(self, "_attr_options") and self._attr_options:
                if mapped in self._attr_options:
                    return mapped
                if str(raw_val) in self._attr_options:
                    return str(raw_val)
            return mapped

        if self.sensor_type in ("Output priority", "Main Output Priority"):
            mapped = map_output_priority(devcode, str(raw_val))
            if hasattr(self, "_attr_options") and self._attr_options:
                if mapped in self._attr_options:
                    return mapped
                if str(raw_val) in self._attr_options:
                    return str(raw_val)
            return mapped

        if self.sensor_type in ("Charger Source Priority", "Charge Priority"):
            mapped = map_charger_priority(devcode, str(raw_val))
            if hasattr(self, "_attr_options") and self._attr_options:
                if mapped in self._attr_options:
                    return mapped
                if str(raw_val) in self._attr_options:
                    return str(raw_val)
            return mapped

        if self.sensor_type == "Data Source":
            return str(raw_val)

        # Parse numeric values
        try:
            val_float = float(raw_val)
            unit = matching_pt.get("unit")
            # If API reports kW but sensor expects W
            if unit == "kW" and self._attr_native_unit_of_measurement == "W":
                val_float *= 1000.0
            # If API reports W but sensor expects kW
            elif unit == "W" and self._attr_native_unit_of_measurement == "kW":
                val_float /= 1000.0

            # Round cleanly
            if self.sensor_type in ("Load Percentage", "Load Percent"):
                return round(val_float, 1)
            if self.sensor_type in ("Output Apparent Power", "Output Aparent Power"):
                return round(val_float, 0)
            if self.sensor_type in ("Output Current", "Output current", "ac_output_current"):
                if val_float <= 0.05:
                    p_val = self._find_data_float(data_points, {"output power", "output active power", "load power", "outpower", "load_active_power"})
                    v_val = self._find_data_float(data_points, {"output voltage", "ac output voltage"}) or 230.3
                    if v_val <= 50.0:
                        v_val = 230.3
                    if p_val is not None:
                        if 0.05 < p_val < 50.0:
                            p_val *= 1000.0
                        if p_val > 10.0:
                            return round(p_val / v_val, 1)
                return round(val_float, 1)
            if self._attr_device_class in (SensorDeviceClass.POWER, SensorDeviceClass.ENERGY):
                return round(val_float, 2)
            if self._attr_device_class in (SensorDeviceClass.VOLTAGE, SensorDeviceClass.CURRENT, SensorDeviceClass.TEMPERATURE):
                return round(val_float, 1)
            return round(val_float, 2)
        except (ValueError, TypeError):
            if self.sensor_type in ("Output Current", "Output current", "ac_output_current"):
                return 0.0
            return str(raw_val)
