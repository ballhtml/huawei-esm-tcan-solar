"""DessMonitor Solar Universal integration entry point."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .api import DessSolarAPI
from .const import CONF_COMPANY_KEY, CONF_PASSWORD, CONF_USERNAME, DEFAULT_COMPANY_KEY, DOMAIN
from .coordinator import DessSolarCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.BUTTON,
    Platform.BINARY_SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up DessMonitor Solar Universal from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    company_key = entry.data.get(CONF_COMPANY_KEY, DEFAULT_COMPANY_KEY)

    session = async_get_clientsession(hass)
    store = Store(hass, 1, f"{DOMAIN}_{entry.entry_id}_auth")

    api = DessSolarAPI(
        username=username,
        password=password,
        company_key=company_key,
        session=session,
        store=store,
    )

    if not await api.load_saved_token():
        await api.authenticate()

    coordinator = DessSolarCoordinator(hass, api, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: DessSolarCoordinator | None = hass.data[DOMAIN].pop(entry.entry_id, None)
        if coordinator:
            await coordinator.api.close()
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
