"""Platform for DessMonitor Solar Universal dynamic number slider entities."""

from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
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
    """Set up DessMonitor Solar Universal number entities."""
    coordinator: DessSolarCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    if not coordinator.data:
        return

    entities: list[DessSolarNumber] = []

    for sn, dev_entry in coordinator.data.items():
        device_meta = dev_entry.get("device", {})
        collector_meta = dev_entry.get("collector", {})
        ctrl_fields = dev_entry.get("ctrl_fields", [])

        for field in ctrl_fields:
            if not isinstance(field, dict):
                continue
            # Fields without 'item' but with a unit or recognized numeric id
            items = field.get("item")
            field_id = field.get("id")
            field_name = field.get("name")
            unit = field.get("unit")

            if not items and field_id and field_name and (unit or any(w in field_id for w in ["volt", "curr", "time", "soc"])):
                entities.append(
                    DessSolarNumber(
                        coordinator=coordinator,
                        device_sn=sn,
                        device_meta=device_meta,
                        collector_meta=collector_meta,
                        field=field,
                    )
                )

    if entities:
        async_add_entities(entities)
        _LOGGER.info("Added %d number control entities for %s", len(entities), config_entry.title)


class DessSolarNumber(CoordinatorEntity[DessSolarCoordinator], NumberEntity):
    """Dynamic number entity representing a numeric inverter threshold or limit."""

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
        self._attr_unique_id = f"{DOMAIN}_{device_sn}_number_{self.field_id}"
        self._attr_name = raw_name
        dev_alias = resolve_device_alias(device_meta, device_sn)
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_mode = NumberMode.BOX

        unit = field.get("unit", "")
        self._attr_native_unit_of_measurement = unit if unit else None

        # Determine reasonable bounds from hint or units
        hint = field.get("hint")
        parsed_lo, parsed_hi = self._parse_hint_range(hint) if hint else (None, None)

        unit_lower = unit.lower() if unit else ""
        if "v" in unit_lower:
            self._attr_native_min_value = parsed_lo if parsed_lo is not None else 10.0
            self._attr_native_max_value = parsed_hi if parsed_hi is not None else 70.0
            self._attr_native_step = 0.1
            self._attr_icon = "mdi:sine-wave"
        elif "a" in unit_lower:
            self._attr_native_min_value = parsed_lo if parsed_lo is not None else 0.0
            self._attr_native_max_value = parsed_hi if parsed_hi is not None else 200.0
            self._attr_native_step = 0.1 if parsed_lo is not None and "." in str(hint) else 1.0
            self._attr_icon = "mdi:current-dc"
        elif "%" in unit_lower:
            self._attr_native_min_value = parsed_lo if parsed_lo is not None else 0.0
            self._attr_native_max_value = parsed_hi if parsed_hi is not None else 100.0
            self._attr_native_step = 1.0
            self._attr_icon = "mdi:percent"
        elif "min" in unit_lower or "day" in unit_lower:
            self._attr_native_min_value = parsed_lo if parsed_lo is not None else 0.0
            self._attr_native_max_value = parsed_hi if parsed_hi is not None else 1440.0
            self._attr_native_step = 1.0
            self._attr_icon = "mdi:timer-outline"
        else:
            self._attr_native_min_value = parsed_lo if parsed_lo is not None else 0.0
            self._attr_native_max_value = parsed_hi if parsed_hi is not None else 1000.0
            self._attr_native_step = 1.0
            self._attr_icon = "mdi:numeric"

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
    def native_value(self) -> float | None:
        """Return the current threshold value."""
        dev_entry = self.coordinator.data.get(self.device_sn)
        if not dev_entry:
            return None

        ctrl_values = dev_entry.get("ctrl_values", {})
        active = ctrl_values.get(self.field_id)

        if active is not None and active != "":
            try:
                return float(active)
            except ValueError:
                pass
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Send updated value to inverter."""
        pn = self.collector_meta.get("pn")
        devcode = self.device_meta.get("devcode")
        devaddr = self.device_meta.get("devaddr", 1)

        val_str = f"{value:.1f}" if self._attr_native_step == 0.1 else f"{int(value)}"

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
        else:
            _LOGGER.error("Failed updating '%s' to %s on %s", self.name, val_str, self.device_sn)

    @staticmethod
    def _parse_hint_range(hint: str) -> tuple[float | None, float | None]:
        """Parse min/max from hint string like '60.0~66V' or '0-900min'."""
        numbers = re.findall(r"[\d.]+", str(hint))
        if len(numbers) >= 2:
            try:
                a, b = float(numbers[0]), float(numbers[1])
                return (min(a, b), max(a, b))
            except ValueError:
                pass
        return None, None
