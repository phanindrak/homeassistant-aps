"""Sensor platform for APS Energy — per-address sensor matrix."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_DOLLAR, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_ADDRESS,
    ATTR_BILLING_DAYS,
    ATTR_DUE_DATE,
    ATTR_IS_ACTIVE,
    ATTR_IS_TOU,
    ATTR_LAST_PAYMENT_AMOUNT,
    ATTR_LAST_PAYMENT_DATE,
    ATTR_OFF_PEAK_COST,
    ATTR_OFF_PEAK_KWH,
    ATTR_ON_PEAK_COST,
    ATTR_ON_PEAK_KWH,
    ATTR_PLAN_EFF_DATE,
    ATTR_RATE_PLAN,
    ATTR_RATE_PLAN_CODE,
    ATTR_SA_STATUS,
    ATTR_SUPER_OFF_PEAK_KWH,
    CONF_ACCOUNT_ID,
    CONF_ADDRESS,
    CONF_FRIENDLY_NAME,
    CONF_IS_ACTIVE,
    CONF_MONITORED_ADDRESSES,
    CONF_SA_ID,
    DOMAIN,
)
from .coordinator import APSAddressCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up APS Energy sensor platform."""
    coordinators: list[APSAddressCoordinator] = hass.data[DOMAIN][entry.entry_id]
    account_id: str = entry.data.get(CONF_ACCOUNT_ID, "")
    monitored: list[dict] = entry.data.get(CONF_MONITORED_ADDRESSES, [])

    entities: list[SensorEntity] = []

    # Account-level sensors (one set, attached to account device)
    if coordinators:
        primary = coordinators[0]
        entities.append(APSCurrentBalanceSensor(primary, account_id))

    # Per-address sensors
    for coordinator in coordinators:
        addr_conf = next(
            (a for a in monitored if a[CONF_SA_ID] == coordinator.sa_id), {}
        )
        entities += _create_address_sensors(coordinator, account_id, addr_conf)

    async_add_entities(entities)


def _create_address_sensors(
    coordinator: APSAddressCoordinator,
    account_id: str,
    addr_conf: dict[str, Any],
) -> list[SensorEntity]:
    """Create the full set of sensors for one service address."""
    entities: list[SensorEntity] = [
        APSServiceAddressSensor(coordinator, account_id),
        APSServiceStatusSensor(coordinator, account_id),
        APSCurrentRatePlanSensor(coordinator, account_id),
        APSLatestBillSensor(coordinator, account_id),
        APSEstimatedChargesSensor(coordinator, account_id),
        APSDailyUsageSensor(coordinator, account_id),
        APSMonthlyUsageSensor(coordinator, account_id),
        APSOnPeakUsageSensor(coordinator, account_id),
        APSOffPeakUsageSensor(coordinator, account_id),
        APSSuperOffPeakUsageSensor(coordinator, account_id),
        APSOnPeakCostSensor(coordinator, account_id),
        APSOffPeakCostSensor(coordinator, account_id),
    ]
    return entities


# ---------------------------------------------------------------------------
# Base sensor
# ---------------------------------------------------------------------------

class APSAddressBaseSensor(CoordinatorEntity[APSAddressCoordinator], SensorEntity):
    """Base sensor scoped to one service address."""

    def __init__(self, coordinator: APSAddressCoordinator, account_id: str) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._account_id = account_id
        self._sa_id = coordinator.sa_id
        self._friendly = coordinator.friendly_name

    @property
    def device_info(self) -> DeviceInfo:
        """Per-address Device in HA device registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._sa_id)},
            name=f"APS {self._friendly}",
            manufacturer="Arizona Public Service",
            model=f"Service Address {self._sa_id}",
            via_device=(DOMAIN, self._account_id),
        )

    def _address_meta(self) -> dict[str, Any]:
        """Shortcut to address_meta in coordinator data."""
        return (self.coordinator.data or {}).get("address_meta", {})

    def _estimated_charges(self) -> dict[str, Any]:
        charges = (self.coordinator.data or {}).get("estimated_charges", {})
        return (
            charges.get("getEstimatedChargesResponse", {})
            .get("getEstimatedChargesRes", {})
        )

    def _daily_usage_entries(self) -> list[dict[str, Any]]:
        data = (self.coordinator.data or {}).get("daily_usage", {})
        # Unwrap common response envelope — adapt once actual shapes are confirmed
        for key in ("getDailyUsageChargesResponse", "dailyUsage", "usage"):
            if key in data:
                data = data[key]
                break
        return data if isinstance(data, list) else data.get("dailyReadings", data.get("days", []))

    def _latest_daily(self) -> dict[str, Any]:
        entries = self._daily_usage_entries()
        return entries[-1] if entries else {}

    def _is_tou(self) -> bool:
        from .api import is_tou_plan
        return is_tou_plan(self._address_meta().get("rate_plan_code", ""))


# ---------------------------------------------------------------------------
# Account-level sensors
# ---------------------------------------------------------------------------

class APSCurrentBalanceSensor(APSAddressBaseSensor):
    """Current outstanding balance — account-level, lives on the primary address device."""

    _attr_name = "Current Balance"
    _attr_native_unit_of_measurement = CURRENCY_DOLLAR
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL

    @property
    def unique_id(self) -> str:
        return f"{self._account_id}_balance"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._account_id)},
            name=f"APS Account {self._account_id}",
            manufacturer="Arizona Public Service",
        )

    @property
    def native_value(self) -> float | None:
        try:
            return float(
                self.coordinator.data["user_details"]["Details"]["profileData"][
                    "OutstandingBillAmount"
                ]
            )
        except (KeyError, ValueError, TypeError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        try:
            profile = self.coordinator.data["user_details"]["Details"]["profileData"]
            financial = (
                self.coordinator.data["user_details"]["Details"]["AccountDetails"]
                ["getAccountDetailsResponse"]["getAccountDetailsRes"]
                ["getAccountFinancialDetails"]
            )
            return {
                ATTR_DUE_DATE: profile.get("DueDate"),
                ATTR_LAST_PAYMENT_AMOUNT: financial.get("lastPayAmt"),
                ATTR_LAST_PAYMENT_DATE: financial.get("lastPayDt"),
            }
        except (KeyError, TypeError):
            return {}


# ---------------------------------------------------------------------------
# Per-address sensors
# ---------------------------------------------------------------------------

class APSServiceAddressSensor(APSAddressBaseSensor):
    """Full premise address string as a text sensor."""

    @property
    def unique_id(self) -> str:
        return f"{self._sa_id}_address"

    @property
    def name(self) -> str:
        return f"APS {self._friendly} Service Address"

    @property
    def native_value(self) -> str | None:
        return self._address_meta().get("address") or self.coordinator.data.get("address_meta", {}).get("address")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        meta = self._address_meta()
        return {
            CONF_SA_ID: self._sa_id,
            "sp_id": self.coordinator.sp_id,
            "start_date": meta.get("start_date"),
            "end_date": meta.get("end_date"),
        }


class APSServiceStatusSensor(APSAddressBaseSensor):
    """Active / Inactive status of this service address."""

    @property
    def unique_id(self) -> str:
        return f"{self._sa_id}_status"

    @property
    def name(self) -> str:
        return f"APS {self._friendly} Service Status"

    @property
    def native_value(self) -> str:
        meta = self._address_meta()
        # Live status from latest API response
        is_active = meta.get("is_active", self.coordinator.is_active)
        return "active" if is_active else "inactive"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        meta = self._address_meta()
        return {
            ATTR_SA_STATUS: meta.get("sa_status"),
            "start_date": meta.get("start_date"),
            "end_date": meta.get("end_date"),
        }


class APSCurrentRatePlanSensor(APSAddressBaseSensor):
    """Current rate plan name as a text sensor."""

    @property
    def unique_id(self) -> str:
        return f"{self._sa_id}_rate_plan"

    @property
    def name(self) -> str:
        return f"APS {self._friendly} Rate Plan"

    @property
    def native_value(self) -> str | None:
        return self._address_meta().get("rate_plan")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        meta = self._address_meta()
        return {
            ATTR_RATE_PLAN_CODE: meta.get("rate_plan_code"),
            ATTR_PLAN_EFF_DATE: meta.get("rate_plan_eff_date"),
            ATTR_IS_TOU: meta.get("is_tou", False),
        }


class APSLatestBillSensor(APSAddressBaseSensor):
    """Latest billed amount for this address."""

    _attr_native_unit_of_measurement = CURRENCY_DOLLAR
    _attr_device_class = SensorDeviceClass.MONETARY

    @property
    def unique_id(self) -> str:
        return f"{self._sa_id}_latest_bill"

    @property
    def name(self) -> str:
        return f"APS {self._friendly} Latest Bill"

    @property
    def native_value(self) -> float | None:
        try:
            return float(self._address_meta().get("totalElectricChargeAmount") or 0)
        except (ValueError, TypeError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        try:
            details = (
                self.coordinator.data["user_details"]["Details"]["AccountDetails"]
                ["getAccountDetailsResponse"]["getAccountDetailsRes"]
            )
            bill = details["getSASPListByAccountID"]["latestBillDetails"]
            return {
                "bill_date": bill.get("billDate"),
                ATTR_DUE_DATE: bill.get("billDueDate"),
                ATTR_BILLING_DAYS: bill.get("billPeriodbillingDays"),
                ATTR_RATE_PLAN: self._address_meta().get("rate_plan"),
                "total_payment_amount": bill.get("billTotalPaymentAmount"),
                "ending_balance": bill.get("billEndingBalanceAmount"),
            }
        except (KeyError, TypeError):
            return {ATTR_RATE_PLAN: self._address_meta().get("rate_plan")}


class APSEstimatedChargesSensor(APSAddressBaseSensor):
    """Estimated charges for the current billing cycle."""

    _attr_native_unit_of_measurement = CURRENCY_DOLLAR
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL

    @property
    def unique_id(self) -> str:
        return f"{self._sa_id}_estimated_charges"

    @property
    def name(self) -> str:
        return f"APS {self._friendly} Estimated Charges"

    @property
    def available(self) -> bool:
        return self.coordinator.is_active and super().available

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.is_active:
            return None
        try:
            return float(self._estimated_charges().get("totalChargeAmt", 0))
        except (ValueError, TypeError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        charges = self._estimated_charges()
        return {
            ATTR_BILLING_DAYS: charges.get("billingDays"),
            ATTR_ON_PEAK_COST: charges.get("onPeakEnergyChargeAmt"),
            ATTR_OFF_PEAK_COST: charges.get("offPeakEnergyChargeAmt"),
            "super_off_peak_cost": charges.get("superOffPeakEnergyChargeAmt"),
            "demand_charge": charges.get("demandChargeAmt"),
            "tax_charge": charges.get("taxChargeAmt"),
            "basic_service_charge": charges.get("basicServiceChargeAmt"),
            "adjustors_amount": charges.get("adjustorsAmt"),
            "average_daily_cost": charges.get("avgDailyChargeAmt"),
            "energy_charge_amount": charges.get("energyChargeAmount"),
        }


class APSDailyUsageSensor(APSAddressBaseSensor):
    """Total kWh for the most recent complete day."""

    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def unique_id(self) -> str:
        return f"{self._sa_id}_daily_usage_kwh"

    @property
    def name(self) -> str:
        return f"APS {self._friendly} Daily Usage"

    @property
    def native_value(self) -> float | None:
        entry = self._latest_daily()
        if not entry:
            return None
        try:
            return float(entry.get("totalKwh") or entry.get("kwh") or entry.get("usage") or 0)
        except (ValueError, TypeError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        entry = self._latest_daily()
        return {
            "date": entry.get("date") or entry.get("usageDate"),
            "avg_temperature": entry.get("avgTemperature"),
        }


class APSMonthlyUsageSensor(APSAddressBaseSensor):
    """Total kWh for the current / most recent billing cycle."""

    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def unique_id(self) -> str:
        return f"{self._sa_id}_monthly_usage_kwh"

    @property
    def name(self) -> str:
        return f"APS {self._friendly} Monthly Usage"

    @property
    def native_value(self) -> float | None:
        entries = self._daily_usage_entries()
        if not entries:
            return None
        try:
            total = sum(
                float(e.get("totalKwh") or e.get("kwh") or e.get("usage") or 0)
                for e in entries
            )
            return total
        except (ValueError, TypeError):
            return None


class APSOnPeakUsageSensor(APSAddressBaseSensor):
    """On-peak kWh for current billing period — ToU plans only."""

    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def unique_id(self) -> str:
        return f"{self._sa_id}_on_peak_kwh"

    @property
    def name(self) -> str:
        return f"APS {self._friendly} On-Peak Usage"

    @property
    def available(self) -> bool:
        return self._is_tou() and super().available

    @property
    def native_value(self) -> float | None:
        if not self._is_tou():
            return None
        try:
            entries = self._daily_usage_entries()
            return sum(
                float(e.get("onPeakKwh") or e.get("onPeakUsage") or 0) for e in entries
            )
        except (ValueError, TypeError):
            return None


class APSOffPeakUsageSensor(APSAddressBaseSensor):
    """Off-peak kWh for current billing period — ToU plans only."""

    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def unique_id(self) -> str:
        return f"{self._sa_id}_off_peak_kwh"

    @property
    def name(self) -> str:
        return f"APS {self._friendly} Off-Peak Usage"

    @property
    def available(self) -> bool:
        return self._is_tou() and super().available

    @property
    def native_value(self) -> float | None:
        if not self._is_tou():
            return None
        try:
            entries = self._daily_usage_entries()
            return sum(
                float(e.get("offPeakKwh") or e.get("offPeakUsage") or 0) for e in entries
            )
        except (ValueError, TypeError):
            return None


class APSSuperOffPeakUsageSensor(APSAddressBaseSensor):
    """Super off-peak kWh — ToU plans with super-off-peak tier only."""

    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def unique_id(self) -> str:
        return f"{self._sa_id}_super_off_peak_kwh"

    @property
    def name(self) -> str:
        return f"APS {self._friendly} Super Off-Peak Usage"

    @property
    def available(self) -> bool:
        return self._is_tou() and super().available

    @property
    def native_value(self) -> float | None:
        if not self._is_tou():
            return None
        try:
            entries = self._daily_usage_entries()
            total = sum(
                float(e.get("superOffPeakKwh") or e.get("superOffPeakUsage") or 0)
                for e in entries
            )
            return total if total > 0 else None
        except (ValueError, TypeError):
            return None


class APSOnPeakCostSensor(APSAddressBaseSensor):
    """On-peak cost from estimated charges — ToU plans only."""

    _attr_native_unit_of_measurement = CURRENCY_DOLLAR
    _attr_device_class = SensorDeviceClass.MONETARY

    @property
    def unique_id(self) -> str:
        return f"{self._sa_id}_on_peak_cost"

    @property
    def name(self) -> str:
        return f"APS {self._friendly} On-Peak Cost"

    @property
    def available(self) -> bool:
        return self._is_tou() and self.coordinator.is_active and super().available

    @property
    def native_value(self) -> float | None:
        if not (self._is_tou() and self.coordinator.is_active):
            return None
        try:
            return float(self._estimated_charges().get("onPeakEnergyChargeAmt") or 0)
        except (ValueError, TypeError):
            return None


class APSOffPeakCostSensor(APSAddressBaseSensor):
    """Off-peak cost from estimated charges — ToU plans only."""

    _attr_native_unit_of_measurement = CURRENCY_DOLLAR
    _attr_device_class = SensorDeviceClass.MONETARY

    @property
    def unique_id(self) -> str:
        return f"{self._sa_id}_off_peak_cost"

    @property
    def name(self) -> str:
        return f"APS {self._friendly} Off-Peak Cost"

    @property
    def available(self) -> bool:
        return self._is_tou() and self.coordinator.is_active and super().available

    @property
    def native_value(self) -> float | None:
        if not (self._is_tou() and self.coordinator.is_active):
            return None
        try:
            return float(self._estimated_charges().get("offPeakEnergyChargeAmt") or 0)
        except (ValueError, TypeError):
            return None
