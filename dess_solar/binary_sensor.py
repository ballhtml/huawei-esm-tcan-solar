"""Platform for DessMonitor Solar Universal binary sensors."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DessSolarCoordinator
from .device_support import get_devcode_config, map_operating_mode, resolve_device_alias

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DessMonitor Solar Universal binary sensors."""
    coordinator: DessSolarCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    if not coordinator.data:
        return

    entities: list[BinarySensorEntity] = []

    for sn, dev_entry in coordinator.data.items():
        device_meta = dev_entry.get("device", {})
        collector_meta = dev_entry.get("collector", {})

        # Status / Online
        entities.append(
            DessSolarStatusBinarySensor(
                coordinator=coordinator,
                device_sn=sn,
                device_meta=device_meta,
                collector_meta=collector_meta,
            )
        )
        # Grid Connected
        entities.append(
            DessSolarGridBinarySensor(
                coordinator=coordinator,
                device_sn=sn,
                device_meta=device_meta,
                collector_meta=collector_meta,
            )
        )
        # Fault Alert
        entities.append(
            DessSolarFaultBinarySensor(
                coordinator=coordinator,
                device_sn=sn,
                device_meta=device_meta,
                collector_meta=collector_meta,
            )
        )
        # Battery Charging
        entities.append(
            DessSolarBatteryChargingBinarySensor(
                coordinator=coordinator,
                device_sn=sn,
                device_meta=device_meta,
                collector_meta=collector_meta,
            )
        )

    if entities:
        async_add_entities(entities)
        _LOGGER.info("Added %d binary sensor entities for %s", len(entities), config_entry.title)


class _DessSolarBinaryBase(CoordinatorEntity[DessSolarCoordinator], BinarySensorEntity):
    """Base class for DessSolar binary sensors."""

    def __init__(
        self,
        coordinator: DessSolarCoordinator,
        device_sn: str,
        device_meta: dict[str, Any],
        collector_meta: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self.device_sn = device_sn
        self.device_meta = device_meta
        self.collector_meta = collector_meta

        self._attr_has_entity_name = True
        dev_alias = resolve_device_alias(device_meta, device_sn)
        self._dev_alias = dev_alias

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

    def _get_point_value(self, titles: set[str]) -> Any:
        """Helper to extract a value from coordinator data by candidate titles."""
        dev_entry = self.coordinator.data.get(self.device_sn)
        if not dev_entry:
            return None
        for pt in dev_entry.get("data", []):
            if pt.get("title") in titles:
                return pt.get("val")
        return None


class DessSolarStatusBinarySensor(_DessSolarBinaryBase):
    """Binary sensor indicating if the inverter is communicating."""

    def __init__(self, coordinator, device_sn, device_meta, collector_meta):
        super().__init__(coordinator, device_sn, device_meta, collector_meta)
        self._attr_unique_id = f"{DOMAIN}_{device_sn}_status"
        self._attr_name = "Status"
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        self._attr_icon = "mdi:lan-connect"

    @property
    def is_on(self) -> bool:
        """Return true if device has recent data."""
        dev_entry = self.coordinator.data.get(self.device_sn)
        return bool(dev_entry and dev_entry.get("data"))


class DessSolarGridBinarySensor(_DessSolarBinaryBase):
    """Binary sensor indicating whether AC Grid power is present."""

    def __init__(self, coordinator, device_sn, device_meta, collector_meta):
        super().__init__(coordinator, device_sn, device_meta, collector_meta)
        self._attr_unique_id = f"{DOMAIN}_{device_sn}_grid_connected"
        self._attr_name = "Grid Connected"
        self._attr_device_class = BinarySensorDeviceClass.POWER
        self._attr_icon = "mdi:transmission-tower"

    @property
    def is_on(self) -> bool:
        """Return true if Grid Voltage > 50V or Grid Frequency > 40Hz."""
        v = self._get_point_value({"Grid Voltage", "Grid voltage", "grid_voltage", "AC Input Voltage"})
        try:
            if v is not None and float(v) > 50.0:
                return True
        except (ValueError, TypeError):
            pass

        hz = self._get_point_value({"Grid Frequency", "Grid frequency", "grid_frequency"})
        try:
            if hz is not None and float(hz) > 40.0:
                return True
        except (ValueError, TypeError):
            pass

        return False


class DessSolarFaultBinarySensor(_DessSolarBinaryBase):
    """Binary sensor indicating if an inverter fault has occurred."""

    def __init__(self, coordinator, device_sn, device_meta, collector_meta):
        super().__init__(coordinator, device_sn, device_meta, collector_meta)
        self._attr_unique_id = f"{DOMAIN}_{device_sn}_fault"
        self._attr_name = "Fault"
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        self._attr_icon = "mdi:alert-circle"

    @property
    def is_on(self) -> bool:
        """Return true if Operating Mode is Fault or fault code is reported."""
        mode_raw = self._get_point_value({"Operating Mode", "Operating mode", "Device state", "Machine state"})
        devcode = self.device_meta.get("devcode")
        if mode_raw is not None:
            mode_str = map_operating_mode(devcode, str(mode_raw)).lower()
            if "fault" in mode_str:
                return True

        fault_code = self._get_point_value({"Fault code", "Fault Code", "Error code"})
        try:
            if fault_code is not None and float(fault_code) > 0:
                return True
        except (ValueError, TypeError):
            if fault_code and str(fault_code).strip() not in ("0", "None", ""):
                return True

        return False


class DessSolarBatteryChargingBinarySensor(_DessSolarBinaryBase):
    """Binary sensor indicating if battery is actively receiving charge."""

    def __init__(self, coordinator, device_sn, device_meta, collector_meta):
        super().__init__(coordinator, device_sn, device_meta, collector_meta)
        self._attr_unique_id = f"{DOMAIN}_{device_sn}_battery_charging"
        self._attr_name = "Battery Charging"
        self._attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING
        self._attr_icon = "mdi:battery-charging"

    @property
    def is_on(self) -> bool:
        """Return true if charging current > 0.5A or charging power > 10W."""
        charge_curr = self._get_point_value({"Battery Charging Current", "Battery charging current", "Charging Current"})
        try:
            if charge_curr is not None and float(charge_curr) > 0.5:
                return True
        except (ValueError, TypeError):
            pass

        p = self._get_point_value({"AC Charging Power", "Solar Total Power", "PV Total Charging Power"})
        batt_p = self._get_point_value({"Battery Power", "battery_power"})
        try:
            if batt_p is not None and float(batt_p) > 10.0:
                return True
        except (ValueError, TypeError):
            pass

        return False
