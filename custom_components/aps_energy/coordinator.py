"""DataUpdateCoordinator for APS Energy."""

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import APSClient, APSAuthError, APSConnectionError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class APSEnergyDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching APS Energy data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: APSClient,
    ) -> None:
        """Initialize."""
        self.client = client
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=12), # APS data updates daily, be conservative to avoid blocks
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            # We might need to re-authenticate if the session expired
            try:
                data = await self.client.get_account_details()
            except APSAuthError:
                _LOGGER.info("Session expired, re-authenticating")
                await self.client.authenticate()
                data = await self.client.get_account_details()
            
            # Fetch estimated charges (cost sensor data)
            # This requires the account details to be loaded first (for IDs and tokens)
            estimated_charges = await self.client.get_estimated_charges()
            data["estimated_charges"] = estimated_charges
            
            return data
        except APSAuthError as err:
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except APSConnectionError as err:
            raise UpdateFailed(f"Error communicating with APS: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error updating APS data")
            raise UpdateFailed(f"Unexpected error: {err}") from err
