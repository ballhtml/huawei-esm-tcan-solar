"""Platform for DessMonitor Solar Universal button entities."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
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
    """Set up DessMonitor Solar Universal button entities."""
    coordinator: DessSolarCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    if not coordinator.data:
        return

    entities: list[ButtonEntity] = []

    for sn, dev_entry in coordinator.data.items():
        device_meta = dev_entry.get("device", {})
        collector_meta = dev_entry.get("collector", {})
        ctrl_fields = dev_entry.get("ctrl_fields", [])

        # 1. Add Refresh Telemetry button for every inverter
        entities.append(
            DessSolarRefreshButton(
                coordinator=coordinator,
                device_sn=sn,
                device_meta=device_meta,
                collector_meta=collector_meta,
            )
        )
        # 2. Add Dump Debug JSON button
        entities.append(
            DessSolarDumpDebugButton(
                coordinator=coordinator,
                device_sn=sn,
                device_meta=device_meta,
                collector_meta=collector_meta,
            )
        )

        # 2. Add single-action command buttons from ctrl_fields (e.g. Exit Fault Mode)
        for field in ctrl_fields:
            if not isinstance(field, dict):
                continue
            items = field.get("item")
            field_id = field.get("id")
            field_name = field.get("name")
            if items and len(items) == 1 and field_id and field_name:
                item = items[0]
                action_key = str(item.get("key", "1"))
                action_name = str(item.get("val", field_name))
                entities.append(
                    DessSolarActionButton(
                        coordinator=coordinator,
                        device_sn=sn,
                        device_meta=device_meta,
                        collector_meta=collector_meta,
                        field=field,
                        action_key=action_key,
                        action_name=action_name,
                    )
                )

    if entities:
        async_add_entities(entities)
        _LOGGER.info("Added %d button entities for %s", len(entities), config_entry.title)


class DessSolarRefreshButton(CoordinatorEntity[DessSolarCoordinator], ButtonEntity):
    """Button to manually refresh telemetry from cloud."""

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
        self._attr_unique_id = f"{DOMAIN}_{device_sn}_refresh_telemetry"
        self._attr_name = "Refresh Telemetry"
        dev_alias = resolve_device_alias(device_meta, device_sn)
        self._attr_icon = "mdi:refresh"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

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

    async def async_press(self) -> None:
        """Handle button press to refresh coordinator data."""
        _LOGGER.debug("Manual refresh requested for %s", self.device_sn)
        await self.coordinator.async_request_refresh()


class DessSolarActionButton(CoordinatorEntity[DessSolarCoordinator], ButtonEntity):
    """Button to execute a one-shot command or action on the inverter."""

    def __init__(
        self,
        coordinator: DessSolarCoordinator,
        device_sn: str,
        device_meta: dict[str, Any],
        collector_meta: dict[str, Any],
        field: dict[str, Any],
        action_key: str,
        action_name: str,
    ) -> None:
        super().__init__(coordinator)
        self.device_sn = device_sn
        self.device_meta = device_meta
        self.collector_meta = collector_meta
        self.field = field
        self.field_id = str(field.get("id"))
        self.action_key = action_key
        self.action_name = action_name

        self._attr_has_entity_name = True
        self._attr_unique_id = f"{DOMAIN}_{device_sn}_btn_{self.field_id}"
        self._attr_name = action_name
        dev_alias = resolve_device_alias(device_meta, device_sn)
        self._attr_icon = "mdi:play-circle-outline"
        self._attr_entity_category = EntityCategory.CONFIG

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

    async def async_press(self) -> None:
        """Handle execution of inverter action."""
        pn = self.collector_meta.get("pn")
        devcode = self.device_meta.get("devcode")
        devaddr = self.device_meta.get("devaddr", 1)

        _LOGGER.info(
            "Executing action %s (%s) for inverter %s",
            self.action_name,
            self.field_id,
            self.device_sn,
        )

        await self.coordinator.async_execute_control(
            pn=pn,
            devcode=devcode,
            devaddr=devaddr,
            sn=self.device_sn,
            field_id=self.field_id,
            value=self.action_key,
        )


class DessSolarDumpDebugButton(CoordinatorEntity[DessSolarCoordinator], ButtonEntity):
    """Button to manually dump diagnostics JSON file to HA config directory."""

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
        self._attr_unique_id = f"{DOMAIN}_{device_sn}_dump_debug_json"
        self._attr_name = "Dump Debug JSON"
        dev_alias = resolve_device_alias(device_meta, device_sn)
        self._attr_icon = "mdi:file-code-outline"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

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

    async def async_press(self) -> None:
        """Handle button press to write diagnostics file."""
        path = await self.coordinator.async_dump_debug_file()
        _LOGGER.info("Diagnostics dump button pressed: written to %s", path)

