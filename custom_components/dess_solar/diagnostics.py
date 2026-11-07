"""Diagnostics support for DessMonitor Solar Universal."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_PASSWORD, CONF_USERNAME, DOMAIN
from .coordinator import DessSolarCoordinator

TO_REDACT = {
    CONF_PASSWORD,
    CONF_USERNAME,
    "usr",
    "token",
    "secret",
    "password",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: DessSolarCoordinator | None = hass.data.get(DOMAIN, {}).get(entry.entry_id)

    diag: dict[str, Any] = {
        "config_entry": {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
    }

    if coordinator:
        diag["coordinator"] = {
            "name": coordinator.name,
            "last_update_success": coordinator.last_update_success,
            "devices_metadata": async_redact_data(coordinator._devices_metadata, TO_REDACT),
            "collectors_metadata": async_redact_data(coordinator._collectors_metadata, TO_REDACT),
            "cached_ctrl_fields": coordinator._cached_ctrl_fields,
            "cached_ctrl_values": coordinator._cached_ctrl_values,
            "data": coordinator.data,
            "raw_api_responses": async_redact_data(coordinator.api.last_raw_responses, TO_REDACT),
            "last_error": coordinator.diagnostics_dump.get("last_error"),
        }
    else:
        diag["coordinator"] = "not_initialized"

    return diag
