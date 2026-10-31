"""Platform for DessMonitor Solar Universal dynamic select entities."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
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
    """Set up DessMonitor Solar Universal select entities."""
    coordinator: DessSolarCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    if not coordinator.data:
        return

    entities: list[DessSolarSelect] = []

    for sn, dev_entry in coordinator.data.items():
        device_meta = dev_entry.get("device", {})
        collector_meta = dev_entry.get("collector", {})
        ctrl_fields = dev_entry.get("ctrl_fields", [])

        for field in ctrl_fields:
            if not isinstance(field, dict):
                continue
            items = field.get("item")
            field_id = field.get("id")
            field_name = field.get("name")
            if items and field_id and field_name:
                entities.append(
                    DessSolarSelect(
                        coordinator=coordinator,
                        device_sn=sn,
                        device_meta=device_meta,
                        collector_meta=collector_meta,
                        field=field,
                    )
                )

    if entities:
        async_add_entities(entities)
        _LOGGER.info("Added %d select control entities for %s", len(entities), config_entry.title)


class DessSolarSelect(CoordinatorEntity[DessSolarCoordinator], SelectEntity):
    """Dynamic select entity representing an inverter configuration option."""

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
        self._attr_unique_id = f"{DOMAIN}_{device_sn}_select_{self.field_id}"
        self._attr_name = raw_name
        dev_alias = resolve_device_alias(device_meta, device_sn)
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_icon = "mdi:tune"

        # Build options mapping
        items = field.get("item", [])
        self._key_to_option: dict[str, str] = {}
        self._option_to_key: dict[str, str] = {}
        options_list = []

        for it in items:
            k = str(it.get("key"))
            val = str(it.get("val", k))
            self._key_to_option[k] = val
            self._option_to_key[val] = k
            options_list.append(val)

        self._attr_options = options_list

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
    def current_option(self) -> str | None:
        """Return the current selected option."""
        dev_entry = self.coordinator.data.get(self.device_sn)
        if not dev_entry:
            return None

        ctrl_values = dev_entry.get("ctrl_values", {})
        active_key = ctrl_values.get(self.field_id)

        if active_key is not None:
            active_str = str(active_key)
            if active_str in self._key_to_option:
                return self._key_to_option[active_str]

        # Fallback to telemetry data points if active control poll hasn't populated this field yet
        raw_name = str(self.field.get("name", "")).strip().lower()
        for pt in dev_entry.get("data", []):
            pt_title = str(pt.get("title", "")).strip().lower()
            if pt_title and (pt_title == raw_name or raw_name in pt_title):
                val = str(pt.get("val", "")).strip()
                if val in self._key_to_option:
                    return self._key_to_option[val]
                if val in self._option_to_key:
                    return val

        return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option on the physical inverter."""
        key = self._option_to_key.get(option)
        if key is None:
            _LOGGER.error("Unknown option '%s' for field %s", option, self.field_id)
            return

        pn = self.collector_meta.get("pn")
        devcode = self.device_meta.get("devcode")
        devaddr = self.device_meta.get("devaddr", 1)

        success = await self.coordinator.async_execute_control(
            pn=pn,
            devcode=devcode,
            devaddr=devaddr,
            sn=self.device_sn,
            field_id=self.field_id,
            value=key,
        )

        if success:
            _LOGGER.info(
                "Successfully set '%s' to '%s' (key=%s) on %s",
                self.name,
                option,
                key,
                self.device_sn,
            )
        else:
            _LOGGER.error("Failed setting '%s' to '%s' on %s", self.name, option, self.device_sn)
