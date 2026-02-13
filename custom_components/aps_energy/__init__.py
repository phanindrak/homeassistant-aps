"""The APS Energy integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import APSClient
from .const import DOMAIN
from .coordinator import APSEnergyDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up APS Energy from a config entry."""
    
    session = async_get_clientsession(hass)
    client = APSClient(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        session
    )
    
    # Authenticate to get account_id and initial data
    await client.authenticate()
    
    coordinator = APSEnergyDataUpdateCoordinator(hass, client)
    
    # Fetch initial data so we have data before setting up platforms
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
