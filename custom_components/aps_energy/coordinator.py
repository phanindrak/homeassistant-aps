"""Per-address DataUpdateCoordinator for APS Energy."""

from datetime import date, timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import APSAuthError, APSClient, APSConnectionError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Active addresses poll more frequently (usage data updates ~hourly)
ACTIVE_SCAN_INTERVAL = timedelta(minutes=30)
# Inactive addresses only have historical data — daily refresh is enough
INACTIVE_SCAN_INTERVAL = timedelta(hours=24)


def _billing_cycle_start(estimated_charges: dict[str, Any], today: date) -> date:
    """Return the start date of the current billing cycle.

    Calculates the start date using the 'billingDays' field from the
    estimated charges response. Falls back to the 1st of the current month
    if unavailable.
    """
    try:
        # The getEstimatedCharges response wraps data under these keys
        res = (
            estimated_charges
            .get("getEstimatedChargesResponse", estimated_charges)
            .get("getEstimatedChargesRes", estimated_charges)
        )
        billing_days_str = res.get("billingDays")
        if billing_days_str:
            billing_days = int(billing_days_str)
            if billing_days > 0:
                # If we are 5 days into the billing period including today, start date was 4 days ago
                return today - timedelta(days=billing_days - 1)
    except (AttributeError, ValueError, TypeError):
        pass
    # Safe fallback: 1st of the current month
    return today.replace(day=1)


class APSAddressCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for a single monitored APS service address."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: APSClient,
        sa_id: str,
        sp_id: str,
        friendly_name: str,
        is_active: bool,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        self.sa_id = sa_id
        self.sp_id = sp_id
        self.friendly_name = friendly_name
        self.is_active = is_active

        interval = ACTIVE_SCAN_INTERVAL if is_active else INACTIVE_SCAN_INTERVAL

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{sa_id}",
            update_interval=interval,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch fresh data for this service address."""
        try:
            # Re-authenticate if token may have expired (best-effort; client caches it)
            user_details = await self.client.get_account_details()

            # Parse current rate plan and status for this address from user details
            address_meta: dict[str, Any] = {}
            from .api import parse_service_addresses
            all_addrs = parse_service_addresses(user_details)
            for addr in all_addrs:
                if addr["sa_id"] == self.sa_id:
                    address_meta = addr
                    break

            # Estimated charges — only meaningful for active addresses.
            # Fetch this first so we can derive the billing cycle start date.
            estimated_charges: dict[str, Any] = {}
            if self.is_active:
                try:
                    estimated_charges = await self.client.get_estimated_charges(
                        self.sa_id, self.sp_id
                    )
                except Exception as exc:  # pylint: disable=broad-except
                    _LOGGER.warning(
                        "Could not fetch estimated charges for %s: %s",
                        self.friendly_name, exc,
                    )

            # Daily usage — must stay within the current billing cycle.
            # The APS getdailyusagecharges API returns 500 when the requested
            # date range spans more than one billing period. We derive the
            # cycle start from the estimated charges payload; if that is not
            # available we fall back to the 1st of the current month.
            today = date.today()
            cycle_start = _billing_cycle_start(estimated_charges, today)
            daily_usage: dict[str, Any] = {}
            try:
                daily_usage = await self.client.get_daily_usage(
                    self.sa_id, self.sp_id, cycle_start, today
                )
            except Exception as exc:  # pylint: disable=broad-except
                _LOGGER.warning(
                    "Could not fetch daily usage for %s: %s",
                    self.friendly_name, exc,
                )

            # Billed history — last 13 months
            thirteen_months_ago = today.replace(day=1) - timedelta(days=365)
            billed_history: dict[str, Any] = {}
            try:
                billed_history = await self.client.get_billed_usage_history(
                    self.sa_id, thirteen_months_ago, today
                )
            except Exception as exc:  # pylint: disable=broad-except
                _LOGGER.warning(
                    "Could not fetch billed history for %s: %s",
                    self.friendly_name, exc,
                )

            return {
                "address_meta": address_meta,
                "user_details": user_details,
                "estimated_charges": estimated_charges,
                "daily_usage": daily_usage,
                "billed_history": billed_history,
            }

        except APSAuthError as exc:
            raise UpdateFailed(f"Authentication failed: {exc}") from exc
        except APSConnectionError as exc:
            raise UpdateFailed(f"Error communicating with APS: {exc}") from exc
        except UpdateFailed:
            raise
        except Exception as exc:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected error updating APS data for %s", self.friendly_name)
            raise UpdateFailed(f"Unexpected error: {exc}") from exc
