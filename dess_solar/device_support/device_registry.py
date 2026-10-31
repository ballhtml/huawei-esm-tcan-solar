"""Device registry and model transformations for DessMonitor Solar Universal."""

from __future__ import annotations

import logging
from typing import Any

from .devcode_6515 import DEVCODE_CONFIG as config_6515

_LOGGER = logging.getLogger(__name__)

_DEVCODE_REGISTRY: dict[int, dict[str, Any]] = {
    6515: config_6515,
}


def register_devcode(devcode: int, config: dict[str, Any]) -> None:
    """Register custom devcode profile."""
    _DEVCODE_REGISTRY[devcode] = config


def get_devcode_config(devcode: int) -> dict[str, Any] | None:
    """Return configuration for devcode if supported."""
    return _DEVCODE_REGISTRY.get(devcode)


def is_devcode_supported(devcode: int) -> bool:
    """Check if devcode has profile registered."""
    return devcode in _DEVCODE_REGISTRY


def map_sensor_title(devcode: int | None, title: str | None) -> str | None:
    """Map raw title to standardized canonical title."""
    if not title or devcode is None:
        return title
    config = get_devcode_config(devcode)
    if not config:
        return title
    mappings = config.get("sensor_title_mappings", {})
    return mappings.get(title, title)


def get_parameter_sensor_names(devcode: int | None) -> set[str]:
    """Return set of wanted parameter names to fetch via queryDeviceParsEs."""
    if devcode is None:
        return set()
    config = get_devcode_config(devcode)
    if not config:
        return set()
    return config.get("parameter_sensor_names", set())


def needs_parameter_fetch(devcode: int | None) -> bool:
    """Check if devcode requires querying parameter registry."""
    return bool(get_parameter_sensor_names(devcode))


def map_operating_mode(devcode: int | None, raw_mode: str | None) -> str:
    """Map raw inverter operating mode string."""
    if not raw_mode:
        return "Unknown"
    if devcode is not None:
        config = get_devcode_config(devcode)
        if config:
            modes = config.get("operating_mode_mapping", {})
            if raw_mode in modes:
                return modes[raw_mode]
    return raw_mode


def map_output_priority(devcode: int | None, priority: str | None) -> str:
    """Map output priority (SBU, SUB, UTI, SOL)."""
    if not priority:
        return "Unknown"
    if devcode is not None:
        config = get_devcode_config(devcode)
        if config:
            priorities = config.get("output_priority_mapping", {})
            if priority in priorities:
                return priorities[priority]
    return priority


def map_charger_priority(devcode: int | None, priority: str | None) -> str:
    """Map charger source priority (SOF, SNU, OSO, SOR)."""
    if not priority:
        return "Unknown"
    if devcode is not None:
        config = get_devcode_config(devcode)
        if config:
            priorities = config.get("charger_priority_mapping", {})
            if priority in priorities:
                return priorities[priority]
    return priority


def resolve_device_alias(device_meta: dict[str, Any], device_sn: str) -> str:
    """Resolve clean device alias for Home Assistant device registry."""
    raw_alias = device_meta.get("devalias")
    if raw_alias and raw_alias != device_sn:
        return raw_alias
    devcode = device_meta.get("devcode")
    if devcode == 6515:
        return "Home Energy EM11000"
    dev_cfg = get_devcode_config(devcode) if devcode else None
    dev_info = dev_cfg.get("device_info", {}) if dev_cfg else {}
    return dev_info.get("name") or dev_info.get("model") or f"Inverter {device_sn[-6:]}"

