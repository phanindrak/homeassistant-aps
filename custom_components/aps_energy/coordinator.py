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
            update_interval=timedelta(hours=6), # APS data doesn't update very often
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            # We might need to re-authenticate if the session expired
            # For now, get_account_details should work if cookies are valid
            data = await self.client.get_account_details()
            # Also fetch estimated charges
            data["estimated_charges"] = await self.client.get_estimated_charges()
            return data
        except APSAuthError:
            _LOGGER.warning("Authentication expired, re-authenticating")
            await self.client.authenticate()
            data = await self.client.get_account_details()
            data["estimated_charges"] = await self.client.get_estimated_charges()
            return data
        except APSConnectionError as err:
            raise UpdateFailed(f"Error communicating with APS: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error: {err}") from err
