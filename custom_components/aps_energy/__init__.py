"""The APS Energy integration — multi-address orchestration and migration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import APSClient, extract_city
from .backfill import maybe_start_backfill
from .const import (
    CONF_ACCOUNT_ID,
    CONF_ADDRESS,
    CONF_FRIENDLY_NAME,
    CONF_IMPORT_MODE,
    CONF_IS_ACTIVE,
    CONF_MONITORED_ADDRESSES,
    CONF_SA_ID,
    CONF_SP_ID,
    DOMAIN,
    IMPORT_MODE_CURRENT,
)
from .coordinator import APSAddressCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up APS Energy from a config entry."""
    session = async_get_clientsession(hass)
    client = APSClient(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        session,
    )

    # Authenticate once — token is cached in the client for all coordinators to share
    await client.authenticate()

    monitored: list[dict] = entry.data.get(CONF_MONITORED_ADDRESSES, [])

    # Create one coordinator per monitored address
    coordinators: list[APSAddressCoordinator] = []
    for addr in monitored:
        coord = APSAddressCoordinator(
            hass=hass,
            client=client,
            sa_id=addr[CONF_SA_ID],
            sp_id=addr[CONF_SP_ID],
            friendly_name=addr[CONF_FRIENDLY_NAME],
            is_active=addr.get(CONF_IS_ACTIVE, True),
        )
        await coord.async_config_entry_first_refresh()
        coordinators.append(coord)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Start background backfill tasks for any address that requested full history
    hass.async_create_task(
        maybe_start_backfill(
            hass,
            entry.entry_id,
            client,
            monitored,
            dict(entry.options),
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate v1 single-address entries to v2 multi-address format."""
    _LOGGER.debug(
        "Migrating APS Energy config entry from version %s to 2",
        config_entry.version,
    )

    if config_entry.version == 1:
        old_data = dict(config_entry.data)
        session = async_get_clientsession(hass)
        client = APSClient(
            old_data[CONF_USERNAME],
            old_data[CONF_PASSWORD],
            session,
        )

        # Re-authenticate to get full address details for the single old SA
        try:
            await client.authenticate()
            addresses = await client.get_service_addresses()
        except Exception as exc:  # pylint: disable=broad-except
            _LOGGER.error("Migration failed — could not fetch addresses: %s", exc)
            return False

        old_sa_id = str(old_data.get("service_address_id", ""))
        matched = next(
            (a for a in addresses if a["sa_id"] == old_sa_id),
            addresses[0] if addresses else None,
        )

        if matched is None:
            _LOGGER.error("Migration failed — no service address found")
            return False

        monitored_addresses = [
            {
                CONF_SA_ID: matched["sa_id"],
                CONF_SP_ID: matched["sp_id"],
                CONF_ADDRESS: matched["address"],
                CONF_FRIENDLY_NAME: extract_city(matched["address"]),
                CONF_IS_ACTIVE: matched["is_active"],
                # Don't trigger backfill on migration — data up to now was already "live"
                CONF_IMPORT_MODE: IMPORT_MODE_CURRENT,
            }
        ]

        new_data = {
            CONF_USERNAME: old_data[CONF_USERNAME],
            CONF_PASSWORD: old_data[CONF_PASSWORD],
            CONF_ACCOUNT_ID: client.account_id,
            CONF_MONITORED_ADDRESSES: monitored_addresses,
        }

        hass.config_entries.async_update_entry(
            config_entry, data=new_data, version=2
        )
        _LOGGER.info(
            "Successfully migrated APS Energy entry to v2 with address: %s",
            matched["address"],
        )

    return True
