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

        # 3. Add One-Click USER Mode Profile Apply Button
        entities.append(
            DessSolarApplyUserProfileButton(
                coordinator=coordinator,
                device_sn=sn,
                device_meta=device_meta,
                collector_meta=collector_meta,
            )
        )
        # 4. Add One-Click Switch to Li2 Mode Button
        entities.append(
            DessSolarSwitchToLi2Button(
                coordinator=coordinator,
                device_sn=sn,
                device_meta=device_meta,
                collector_meta=collector_meta,
            )
        )
        # 5. Add Read All Settings Button
        entities.append(
            DessSolarReadAllSettingsButton(
                coordinator=coordinator,
                device_sn=sn,
                device_meta=device_meta,
                collector_meta=collector_meta,
            )
        )
        # 6. Add Sync Inverter Clock Button
        entities.append(
            DessSolarSyncClockButton(
                coordinator=coordinator,
                device_sn=sn,
                device_meta=device_meta,
                collector_meta=collector_meta,
            )
        )

    if entities:
        async_add_entities(entities)
        _LOGGER.info("Added %d button entities for %s", len(entities), config_entry.title)


class DessSolarApplyUserProfileButton(CoordinatorEntity[DessSolarCoordinator], ButtonEntity):
    """Button to apply the complete optimal 15S Huawei battery USER mode profile."""

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
        self._attr_unique_id = f"{DOMAIN}_{device_sn}_apply_user_mode_profile"
        self._attr_name = "Apply USER Mode Profile"
        dev_alias = resolve_device_alias(device_meta, device_sn)
        self._attr_icon = "mdi:tune-vertical"

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
        """Execute sequential batch setting for optimal 15S Huawei USER profile."""
        import asyncio

        pn = self.collector_meta.get("pn") or self.device_meta.get("pn")
        devcode = self.device_meta.get("devcode")
        devaddr = self.device_meta.get("devaddr", 1)

        profile_fields = [
            ("bat_eybond_read_57", "2"),      # Battery Type: USER (key 2)
            ("bse_eybond_read_50", "2"),      # Main Output Priority: SBU (key 2)
            ("bat_eybond_read_59", "3"),      # Charger Source Priority: OSO (key 3)
            ("bat_eybond_read_67", 120.0),    # Maximum charging current: 120.0 A
            ("bat_eybond_read_68", 60.0),     # Maximum mains charging current: 60.0 A
            ("bat_eybond_read_69", 300),      # Maximum discharge current protection: 300 A
            ("bat_eybond_read_64", 54.0),     # Maximum charging voltage (Bulk): 54.0 V
            ("bat_eybond_read_65", 53.2),     # Floating charge voltage: 53.2 V
            ("bat_eybond_read_66", 45),       # Constant pressure to float waiting time: 45 Min
            ("bat_eybond_read_70", 50.0),     # Mains mode battery discharge recovery point: 50.0 V
            ("bat_eybond_read_71", 46.2),     # Mains mode battery low voltage protection point: 46.2 V
            ("bat_eybond_read_72", 46.0),     # Off-grid mode battery low voltage protection point: 46.0 V
            ("bat_eybond_read_58", 55.0),     # Battery overvoltage protection point: 55.0 V
            ("bat_eybond_read_76", "0"),      # Battery Eq mode enable: Prohibit (key 0)
            ("bat_eybond_read_77", 53.5),     # Eq charging voltage: 53.5 V
            ("bat_eybond_read_78", 0),        # bat_eq_time: 0 Min
            ("bat_eybond_read_79", 0),        # Eq timeout exit: 0 Min
            ("bat_eybond_read_80", 30),       # Eq charging interval: 30 Day
            ("bat_eybond_read_60", "0"),      # Secondary Charging Priority: OFF (key 0)
        ]

        _LOGGER.info("Starting batch apply of 15S Huawei USER Mode Profile for inverter %s", self.device_sn)
        for field_id, value in profile_fields:
            try:
                await self.coordinator.api.execute_device_control(
                    pn=pn,
                    devcode=devcode,
                    devaddr=devaddr,
                    sn=self.device_sn,
                    field_id=field_id,
                    value=value,
                )
                if self.device_sn in self.coordinator._cached_ctrl_values:
                    self.coordinator._cached_ctrl_values[self.device_sn][field_id] = str(value)
                await asyncio.sleep(0.3)
            except Exception as err:
                _LOGGER.error("Failed setting field %s=%s: %s", field_id, value, err)

        await self.coordinator.async_request_refresh()
        _LOGGER.info("Completed batch apply of 15S Huawei USER Mode Profile for inverter %s", self.device_sn)


class DessSolarSwitchToLi2Button(CoordinatorEntity[DessSolarCoordinator], ButtonEntity):
    """Button to switch inverter battery mode to Li2 (Pylontech BMS)."""

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
        self._attr_unique_id = f"{DOMAIN}_{device_sn}_switch_to_li2_mode"
        self._attr_name = "Switch to Li2 Mode"
        dev_alias = resolve_device_alias(device_meta, device_sn)
        self._attr_icon = "mdi:battery-sync"

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
        """Execute switch to Li2 mode."""
        pn = self.collector_meta.get("pn") or self.device_meta.get("pn")
        devcode = self.device_meta.get("devcode")
        devaddr = self.device_meta.get("devaddr", 1)

        _LOGGER.info("Switching battery type to Li2 for inverter %s", self.device_sn)
        try:
            await self.coordinator.api.execute_device_control(
                pn=pn,
                devcode=devcode,
                devaddr=devaddr,
                sn=self.device_sn,
                field_id="bat_eybond_read_57",
                value="4",
            )
            if self.device_sn in self.coordinator._cached_ctrl_values:
                self.coordinator._cached_ctrl_values[self.device_sn]["bat_eybond_read_57"] = "4"
            await self.coordinator.async_request_refresh()
            _LOGGER.info("Successfully switched battery type to Li2 for inverter %s", self.device_sn)
        except Exception as err:
            _LOGGER.error("Failed switching to Li2: %s", err)


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


class DessSolarReadAllSettingsButton(CoordinatorEntity[DessSolarCoordinator], ButtonEntity):
    """Button to read and refresh all inverter configuration parameters."""

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
        self._attr_unique_id = f"{DOMAIN}_{device_sn}_read_all_settings"
        self._attr_name = "Read Inverter Settings Now"
        self._attr_icon = "mdi:book-sync"
        self._attr_entity_category = EntityCategory.CONFIG

        dev_alias = resolve_device_alias(device_meta, device_sn)
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
        """Fetch all configuration fields from inverter/cloud and refresh entity states."""
        _LOGGER.info("User requested reading all inverter settings for %s", self.device_sn)
        await self.coordinator.async_refresh_all_control_values(self.device_sn)
        _LOGGER.info("Completed reading all inverter settings for %s", self.device_sn)




class DessSolarSyncClockButton(CoordinatorEntity[DessSolarCoordinator], ButtonEntity):
    """Button to sync the inverter real-time clock with Home Assistant (Bangkok UTC+7)."""

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
        self._attr_unique_id = f"{DOMAIN}_{device_sn}_btn_sync_clock"
        self._attr_name = "Sync Inverter Clock"
        self._attr_icon = "mdi:clock-check-outline"
        self._attr_entity_category = EntityCategory.CONFIG

        dev_alias = resolve_device_alias(device_meta, device_sn)
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
        """Handle clock synchronization."""
        from datetime import datetime
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _LOGGER.info(
            "Syncing clock for inverter %s to %s",
            self.device_sn,
            now_str,
        )
        pn = self.collector_meta.get("pn")
        devcode = self.device_meta.get("devcode")
        devaddr = self.device_meta.get("devaddr", 1)

        success = await self.coordinator.async_execute_control(
            pn=pn,
            devcode=devcode,
            devaddr=devaddr,
            sn=self.device_sn,
            field_id="sys_eybond_read_95",
            value=now_str,
        )
        if success:
            _LOGGER.info("Successfully synced inverter %s clock to %s", self.device_sn, now_str)
        else:
            _LOGGER.error("Failed to sync clock for inverter %s", self.device_sn)
