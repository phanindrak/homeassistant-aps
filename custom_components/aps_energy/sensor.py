"""Sensor platform for APS Energy."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import CURRENCY_DOLLAR, UnitOfTime
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    ATTR_LAST_PAYMENT_AMOUNT,
    ATTR_LAST_PAYMENT_DATE,
    ATTR_DUE_DATE,
    ATTR_RATE_PLAN,
    ATTR_BILLING_DAYS,
)
from .coordinator import APSEnergyDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator: APSEnergyDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = [
        APSCurrentBalanceSensor(coordinator),
        APSLatestBillSensor(coordinator),
        APSEstimatedChargesSensor(coordinator),
    ]
    
    async_add_entities(entities)


class APSBaseSensor(CoordinatorEntity[APSEnergyDataUpdateCoordinator], SensorEntity):
    """Base class for APS sensors."""

    def __init__(self, coordinator: APSEnergyDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.client.account_id)},
            "name": f"APS Account {coordinator.client.account_id}",
            "manufacturer": "Arizona Public Service",
        }


class APSCurrentBalanceSensor(APSBaseSensor):
    """Sensor for the current outstanding balance."""

    _attr_name = "APS Current Balance"
    _attr_native_unit_of_measurement = CURRENCY_DOLLAR
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.coordinator.client.account_id}_balance"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        try:
            return float(self.coordinator.data["Details"]["profileData"]["OutstandingBillAmount"])
        except (KeyError, ValueError, TypeError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        try:
            profile = self.coordinator.data["Details"]["profileData"]
            financial = self.coordinator.data["Details"]["AccountDetails"]["getAccountDetailsResponse"]["getAccountDetailsRes"]["getAccountFinancialDetails"]
            return {
                ATTR_DUE_DATE: profile.get("DueDate"),
                ATTR_LAST_PAYMENT_AMOUNT: financial.get("lastPayAmt"),
                ATTR_LAST_PAYMENT_DATE: financial.get("lastPayDt"),
            }
        except (KeyError, TypeError):
            return {}


class APSLatestBillSensor(APSBaseSensor):
    """Sensor for the latest bill amount."""

    _attr_name = "APS Latest Bill"
    _attr_native_unit_of_measurement = CURRENCY_DOLLAR
    _attr_device_class = SensorDeviceClass.MONETARY

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.coordinator.client.account_id}_latest_bill"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        try:
            bill = self.coordinator.data["Details"]["AccountDetails"]["getAccountDetailsResponse"]["getAccountDetailsRes"]["getSASPListByAccountID"]["latestBillDetails"]
            return float(bill["billTotalCurrentChargesAmount"])
        except (KeyError, ValueError, TypeError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        try:
            # We need to find the specific SASP detail that has the rate plan
            # For simplicity, we'll take the first one or the one matching the service address ID
            details = self.coordinator.data["Details"]["AccountDetails"]["getAccountDetailsResponse"]["getAccountDetailsRes"]
            bill = details["getSASPListByAccountID"]["latestBillDetails"]
            
            rate_plan = "Unknown"
            premise_list = details.get("getSASPListByAccountID", {}).get("premiseDetailsList", [])
            for premise in premise_list:
                for sasp in premise.get("sASPDetails", []):
                    if str(sasp.get("sAID")) == self.coordinator.client.service_address_id:
                        rate_plan = sasp.get("sARatePlanDescription", "Unknown")
                        break
            
            return {
                "bill_date": bill.get("billDate"),
                "bill_due_date": bill.get("billDueDate"),
                ATTR_BILLING_DAYS: bill.get("billPeriodbillingDays"),
                ATTR_RATE_PLAN: rate_plan,
            }
        except (KeyError, TypeError):
            return {}


class APSEstimatedChargesSensor(APSBaseSensor):
    """Sensor for estimated charges."""

    _attr_name = "APS Estimated Charges"
    _attr_native_unit_of_measurement = CURRENCY_DOLLAR
    _attr_device_class = SensorDeviceClass.MONETARY

    def __init__(self, coordinator: APSEnergyDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._estimated_data: dict[str, Any] = {}

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.coordinator.client.account_id}_estimated_charges"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        # This data comes from a different endpoint in a real scenario
        # But we saw it in the captured traffic. For now, we'll try to find it
        # in the coordinator data if we add a call to fetch it.
        try:
            # Check if we have estimated charges data
            # (Note: we need to update the coordinator to fetch this too)
            charges = self.coordinator.data.get("estimated_charges", {})
            return float(charges.get("totalChargeAmt", 0))
        except (KeyError, ValueError, TypeError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        try:
            charges = self.coordinator.data.get("estimated_charges", {}).get("getEstimatedChargesResponse", {}).get("getEstimatedChargesRes", {})
            return {
                "billing_days": charges.get("billingDays"),
                "on_peak_cost": charges.get("onPeakEnergyChargeAmt"),
                "off_peak_cost": charges.get("offPeakEnergyChargeAmt"),
                "super_off_peak_cost": charges.get("superOffPeakEnergyChargeAmt"),
                "demand_charge": charges.get("demandChargeAmt"),
                "tax_charge": charges.get("taxChargeAmt"),
                "basic_service_charge": charges.get("basicServiceChargeAmt"),
                "adjustors_amount": charges.get("adjustorsAmt"),
                "average_daily_cost": charges.get("avgDailyChargeAmt"),
            }
        except (KeyError, TypeError):
            return {}
