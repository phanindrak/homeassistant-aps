"""Historical data backfill for APS Energy using HA's external statistics API.

When a user chooses "Import all available history" during setup, this module
runs a background task that fetches all historical billing and usage data from
the APS API and injects it into Home Assistant's long-term statistics database
using async_add_external_statistics.

Statistics appear in the Energy Dashboard and History graphs just like live data.
The backfill is idempotent — safe to re-run; existing values are overwritten.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .api import APSClient
from .const import (
    CONF_BACKFILL_COMPLETE,
    CONF_MONITORED_ADDRESSES,
    CONF_SA_ID,
    CONF_SP_ID,
    CONF_FRIENDLY_NAME,
    CONF_IS_ACTIVE,
    CONF_IMPORT_MODE,
    DOMAIN,
    IMPORT_MODE_FULL,
)

_LOGGER = logging.getLogger(__name__)

# How many seconds to wait between API calls to be polite
API_THROTTLE_SECONDS = 1

# How far back to request history (API typically has 2-3 years)
HISTORY_YEARS = 15


def _statistic_id(friendly_name: str, metric: str) -> str:
    """Return a statistic_id for external statistics.

    Format: <domain>:<friendly_name_lower>_<metric>
    Example: aps_energy:peoria_daily_kwh
    """
    slug = friendly_name.lower().replace(" ", "_")
    return f"{DOMAIN}:{slug}_{metric}"


def _make_meta(
    statistic_id: str, name: str, unit: str, has_mean: bool, has_sum: bool
) -> StatisticMetaData:
    """Build StatisticMetaData."""
    return StatisticMetaData(
        source=DOMAIN,
        statistic_id=statistic_id,
        name=name,
        unit_of_measurement=unit,
        has_mean=has_mean,
        has_sum=has_sum,
    )


def _date_to_utc_datetime(d: date) -> datetime:
    """Convert a date to midnight UTC datetime."""
    local_midnight = datetime(d.year, d.month, d.day, 0, 0, 0)
    return dt_util.as_utc(local_midnight)


async def backfill_address(
    hass: HomeAssistant,
    client: APSClient,
    sa_id: str,
    sp_id: str,
    friendly_name: str,
) -> None:
    """Fetch and inject all available historical data for one service address.

    This coroutine is expected to run in the background. It:
    1. Fetches billed usage history (monthly cycle summaries)
    2. For each billing cycle, fetches daily usage breakdown
    3. Injects statistics into HA via async_add_external_statistics
    """
    _LOGGER.info("Starting historical backfill for %s (sa_id=%s)", friendly_name, sa_id)

    today = date.today()
    start = today.replace(year=today.year - HISTORY_YEARS, month=1, day=1)

    # --- Step 1: Fetch billed usage history ---
    try:
        history_resp = await client.get_billed_usage_history(sa_id, start, today)
    except Exception as exc:  # pylint: disable=broad-except
        _LOGGER.error("Backfill: failed to fetch billed history for %s: %s", friendly_name, exc)
        return

    billing_cycles = _parse_billing_cycles(history_resp)
    _LOGGER.info(
        "Backfill: %s — found %d billing cycles to process",
        friendly_name, len(billing_cycles)
    )

    # Cumulative energy sum across all time (required for has_sum=True statistics)
    cumulative_kwh = 0.0
    cumulative_cost = 0.0
    cumulative_on_peak = 0.0
    cumulative_off_peak = 0.0
    cumulative_super_off_peak = 0.0

    daily_kwh_stats: list[StatisticData] = []
    daily_cost_stats: list[StatisticData] = []
    on_peak_stats: list[StatisticData] = []
    off_peak_stats: list[StatisticData] = []
    super_off_peak_stats: list[StatisticData] = []

    for cycle in billing_cycles:
        cycle_start: date = cycle["start_date"]
        cycle_end: date = cycle["end_date"]

        # Throttle between API calls
        await asyncio.sleep(API_THROTTLE_SECONDS)

        # --- Step 2: Fetch daily usage for this billing cycle ---
        try:
            daily_resp = await client.get_daily_usage(sa_id, sp_id, cycle_start, cycle_end)
            daily_readings = _parse_daily_readings(daily_resp)
        except Exception as exc:  # pylint: disable=broad-except
            _LOGGER.warning(
                "Backfill: could not fetch daily usage for %s cycle %s–%s: %s",
                friendly_name, cycle_start, cycle_end, exc,
            )
            daily_readings = []

        if not daily_readings:
            # Fallback: evenly distribute the monthly total across the days in the cycle
            cycle_days = (cycle_end - cycle_start).days
            if cycle_days > 0:
                _LOGGER.info(
                    "Backfill: %s — falling back to synthetic daily average for cycle %s–%s",
                    friendly_name, cycle_start, cycle_end
                )
                total = cycle.get("total_kwh", 0.0)
                daily_avg_kwh = total / cycle_days
                for day_offset in range(cycle_days):
                    synthetic_date = cycle_start + timedelta(days=day_offset)
                    daily_readings.append({
                        "date": synthetic_date,
                        "kwh": daily_avg_kwh,
                        "cost": 0.0,
                        "on_peak_kwh": 0.0,
                        "off_peak_kwh": 0.0,
                        "super_off_peak_kwh": 0.0,
                    })

        for reading in daily_readings:
            period_start = _date_to_utc_datetime(reading["date"])

            kwh = reading.get("kwh", 0.0) or 0.0
            cost = reading.get("cost", 0.0) or 0.0
            on_peak = reading.get("on_peak_kwh", 0.0) or 0.0
            off_peak = reading.get("off_peak_kwh", 0.0) or 0.0
            super_op = reading.get("super_off_peak_kwh", 0.0) or 0.0

            cumulative_kwh += kwh
            cumulative_cost += cost
            cumulative_on_peak += on_peak
            cumulative_off_peak += off_peak
            cumulative_super_off_peak += super_op

            daily_kwh_stats.append(StatisticData(start=period_start, sum=cumulative_kwh, state=kwh))
            daily_cost_stats.append(StatisticData(start=period_start, sum=cumulative_cost, state=cost))
            if on_peak or off_peak:
                on_peak_stats.append(StatisticData(start=period_start, sum=cumulative_on_peak, state=on_peak))
                off_peak_stats.append(StatisticData(start=period_start, sum=cumulative_off_peak, state=off_peak))
            if super_op:
                super_off_peak_stats.append(StatisticData(start=period_start, sum=cumulative_super_off_peak, state=super_op))

        _LOGGER.debug(
            "Backfill: %s — processed cycle %s–%s (%d daily readings)",
            friendly_name, cycle_start, cycle_end, len(daily_readings),
        )

    # --- Step 3: Write statistics to HA recorder ---
    _LOGGER.info(
        "Backfill: %s — writing %d daily kWh records to HA statistics",
        friendly_name, len(daily_kwh_stats),
    )

    def _write_stats() -> None:
        if daily_kwh_stats:
            async_add_external_statistics(
                hass,
                _make_meta(
                    _statistic_id(friendly_name, "daily_kwh"),
                    f"APS {friendly_name} Daily Usage",
                    UnitOfEnergy.KILO_WATT_HOUR,
                    has_mean=False,
                    has_sum=True,
                ),
                daily_kwh_stats,
            )
        if daily_cost_stats:
            async_add_external_statistics(
                hass,
                _make_meta(
                    _statistic_id(friendly_name, "daily_cost"),
                    f"APS {friendly_name} Daily Cost",
                    "USD",
                    has_mean=False,
                    has_sum=True,
                ),
                daily_cost_stats,
            )
        if on_peak_stats:
            async_add_external_statistics(
                hass,
                _make_meta(
                    _statistic_id(friendly_name, "on_peak_kwh"),
                    f"APS {friendly_name} On-Peak Usage",
                    UnitOfEnergy.KILO_WATT_HOUR,
                    has_mean=False,
                    has_sum=True,
                ),
                on_peak_stats,
            )
        if off_peak_stats:
            async_add_external_statistics(
                hass,
                _make_meta(
                    _statistic_id(friendly_name, "off_peak_kwh"),
                    f"APS {friendly_name} Off-Peak Usage",
                    UnitOfEnergy.KILO_WATT_HOUR,
                    has_mean=False,
                    has_sum=True,
                ),
                off_peak_stats,
            )
        if super_off_peak_stats:
            async_add_external_statistics(
                hass,
                _make_meta(
                    _statistic_id(friendly_name, "super_off_peak_kwh"),
                    f"APS {friendly_name} Super Off-Peak Usage",
                    UnitOfEnergy.KILO_WATT_HOUR,
                    has_mean=False,
                    has_sum=True,
                ),
                super_off_peak_stats,
            )

    # async_add_external_statistics must be called from the recorder thread
    await get_instance(hass).async_add_executor_job(_write_stats)

    _LOGGER.info("Backfill complete for %s — %.1f kWh total backfilled", friendly_name, cumulative_kwh)


# ---------------------------------------------------------------------------
# Response parsers — adapt these when actual API response shapes are confirmed
# ---------------------------------------------------------------------------

def _parse_billing_cycles(history_resp: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse billing cycle date ranges from getbilledusagehistory response.

    Returns list of dicts with 'start_date', 'end_date', 'total_kwh'.
    """
    cycles = []
    try:
        data = (
            history_resp
            .get("getBilledUsageHistoryResponse", {})
            .get("getBilledUsageHistoryRes", {})
        )
        for entry in data.get("bills", []):
            start_str = entry.get("billCycleStartDate")
            end_str = entry.get("billCycleEndDate")
            if start_str and end_str:
                try:
                    cycles.append({
                        "start_date": date.fromisoformat(start_str[:10]),
                        "end_date": date.fromisoformat(end_str[:10]),
                        "total_kwh": float(entry.get("totalUsg") or 0),
                    })
                except (ValueError, TypeError):
                    pass
    except (KeyError, TypeError, AttributeError) as exc:
        _LOGGER.debug("Could not parse billing cycles: %s", exc)
    return sorted(cycles, key=lambda c: c["start_date"])


def _parse_daily_readings(daily_resp: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse daily usage readings from getdailyusagecharges response.

    Returns list of dicts: date, kwh, cost, on_peak_kwh, off_peak_kwh, super_off_peak_kwh.
    NOTE: Update key paths below once the real API response is inspected.
    """
    readings = []
    try:
        data = daily_resp
        for key in ("getDailyUsageChargesResponse", "dailyUsage", "usage"):
            if key in data:
                data = data[key]
                break

        items = data if isinstance(data, list) else data.get("dailyReadings", data.get("days", []))
        for entry in items:
            date_str = entry.get("date") or entry.get("usageDate") or entry.get("readDate")
            if not date_str:
                continue
            try:
                readings.append({
                    "date": date.fromisoformat(date_str[:10]),
                    "kwh": float(entry.get("totalKwh") or entry.get("kwh") or entry.get("usage") or 0),
                    "cost": float(entry.get("totalCost") or entry.get("cost") or entry.get("charge") or 0),
                    "on_peak_kwh": float(entry.get("onPeakKwh") or entry.get("onPeakUsage") or 0),
                    "off_peak_kwh": float(entry.get("offPeakKwh") or entry.get("offPeakUsage") or 0),
                    "super_off_peak_kwh": float(entry.get("superOffPeakKwh") or entry.get("superOffPeakUsage") or 0),
                })
            except (ValueError, TypeError):
                pass
    except (KeyError, TypeError, AttributeError) as exc:
        _LOGGER.debug("Could not parse daily readings: %s", exc)
    return sorted(readings, key=lambda r: r["date"])


async def maybe_start_backfill(
    hass: HomeAssistant,
    config_entry_id: str,
    client: APSClient,
    addresses: list[dict[str, Any]],
    options: dict[str, Any],
) -> None:
    """Start backfill tasks for any addresses that need it."""
    for addr in addresses:
        if addr.get(CONF_IMPORT_MODE) != IMPORT_MODE_FULL:
            continue
        sa_id = addr[CONF_SA_ID]
        backfill_key = f"backfill_complete_{sa_id}"
        if options.get(backfill_key):
            _LOGGER.debug("Backfill already complete for %s — skipping", addr[CONF_FRIENDLY_NAME])
            continue

        _LOGGER.info("Scheduling background backfill for %s", addr[CONF_FRIENDLY_NAME])

        async def _run_and_mark(addr: dict[str, Any] = addr) -> None:
            try:
                await backfill_address(
                    hass,
                    client,
                    addr[CONF_SA_ID],
                    addr[CONF_SP_ID],
                    addr[CONF_FRIENDLY_NAME],
                )
                # Mark complete so we don't re-run on next restart
                from homeassistant.config_entries import current_entry  # noqa: PLC0415
                entry = hass.config_entries.async_get_entry(config_entry_id)
                if entry:
                    new_opts = dict(entry.options)
                    new_opts[f"backfill_complete_{addr[CONF_SA_ID]}"] = True
                    hass.config_entries.async_update_entry(entry, options=new_opts)
            except Exception as exc:  # pylint: disable=broad-except
                _LOGGER.error(
                    "Background backfill failed for %s: %s",
                    addr[CONF_FRIENDLY_NAME], exc,
                )

        hass.async_create_task(_run_and_mark())
