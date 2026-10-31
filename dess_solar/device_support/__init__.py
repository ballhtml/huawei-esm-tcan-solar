"""Device support module for DessMonitor Solar Universal."""

from .device_registry import (
    get_devcode_config,
    get_parameter_sensor_names,
    is_devcode_supported,
    map_charger_priority,
    map_operating_mode,
    map_output_priority,
    map_sensor_title,
    needs_parameter_fetch,
    register_devcode,
    resolve_device_alias,
)

__all__ = [
    "get_devcode_config",
    "get_parameter_sensor_names",
    "is_devcode_supported",
    "map_charger_priority",
    "map_operating_mode",
    "map_output_priority",
    "map_sensor_title",
    "needs_parameter_fetch",
    "register_devcode",
    "resolve_device_alias",
]
