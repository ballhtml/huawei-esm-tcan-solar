"""Platform for DessMonitor Solar Universal dynamic time entities."""

from __future__ import annotations

import datetime
import logging
from typing import Any

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DessSolarCoordinator
from .device_support import get_devcode_config, resolve_device_alias

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DessMonitor Solar Universal time entities."""
    coordinator: DessSolarCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    if not coordinator.data:
        return

    entities: list[DessSolarTime] = []

    for sn, dev_entry in coordinator.data.items():
        device_meta = dev_entry.get("device", {})
        collector_meta = dev_entry.get("collector", {})
        ctrl_fields = dev_entry.get("ctrl_fields", [])

        for field in ctrl_fields:
            if not isinstance(field, dict):
                continue
            items = field.get("item")
            field_id = str(field.get("id", ""))
            field_name = str(field.get("name", "")).strip()

            # Identify time-of-day configuration fields (HH:MM)
            if not items and field_id and field_name:
                name_lower = field_name.lower()
                if (
                    ("start time" in name_lower or "end time" in name_lower or "time slot" in name_lower)
                    or field_id in ["bse_eybond_read_52", "bse_eybond_read_53", "bat_eybond_read_61", "bat_eybond_read_62"]
                ):
                    entities.append(
                        DessSolarTime(
                            coordinator=coordinator,
                            device_sn=sn,
                            device_meta=device_meta,
                            collector_meta=collector_meta,
                            field=field,
                        )
                    )

    if entities:
        async_add_entities(entities)
        _LOGGER.info("Added %d time control entities for %s", len(entities), config_entry.title)


class DessSolarTime(CoordinatorEntity[DessSolarCoordinator], TimeEntity):
    """Dynamic time entity for inverter schedule configuration (HH:MM)."""

    def __init__(
        self,
        coordinator: DessSolarCoordinator,
        device_sn: str,
        device_meta: dict[str, Any],
        collector_meta: dict[str, Any],
        field: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self.device_sn = device_sn
        self.device_meta = device_meta
        self.collector_meta = collector_meta
        self.field = field

        self.field_id: str = str(field.get("id"))
        raw_name: str = str(field.get("name", self.field_id)).strip()

        self._attr_has_entity_name = True
        self._attr_unique_id = f"{DOMAIN}_{device_sn}_time_{self.field_id}"
        self._attr_name = raw_name
        dev_alias = resolve_device_alias(device_meta, device_sn)
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_icon = "mdi:clock-outline"

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

    @property
    def native_value(self) -> datetime.time | None:
        """Return the current time value."""
        dev_entry = self.coordinator.data.get(self.device_sn)
        if not dev_entry:
            return None

        ctrl_values = dev_entry.get("ctrl_values", {})
        active = ctrl_values.get(self.field_id)

        if active is not None and isinstance(active, str) and ":" in active:
            try:
                parts = active.strip().split(":")
                return datetime.time(int(parts[0]), int(parts[1]))
            except Exception:
                pass
        return None

    async def async_set_value(self, value: datetime.time) -> None:
        """Send updated time (HH:MM) to inverter."""
        pn = self.collector_meta.get("pn")
        devcode = self.device_meta.get("devcode")
        devaddr = self.device_meta.get("devaddr", 1)

        val_str = f"{value.hour:02d}:{value.minute:02d}"

        success = await self.coordinator.async_execute_control(
            pn=pn,
            devcode=devcode,
            devaddr=devaddr,
            sn=self.device_sn,
            field_id=self.field_id,
            value=val_str,
        )

        if success:
            _LOGGER.info("Successfully updated '%s' = %s on %s", self.name, val_str, self.device_sn)
            # Update cache immediately
            if self.coordinator.data and self.device_sn in self.coordinator.data:
                self.coordinator.data[self.device_sn].setdefault("ctrl_values", {})[self.field_id] = val_str
                self.async_write_ha_state()
        else:
            _LOGGER.error("Failed updating '%s' to %s on %s", self.name, val_str, self.device_sn)
