"""Config flow for APS Energy integration — multi-address, looping config."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import APSClient, APSAuthError, APSConnectionError
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
    IMPORT_MODE_FULL,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


def _address_label(addr: dict[str, Any]) -> str:
    """Build a human-readable label for the address selector."""
    status = "Active" if addr["is_active"] else "Inactive"
    return f"{addr['address']}  [{status}]"


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for APS Energy — multi-address."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize flow state."""
        self._username: str = ""
        self._password: str = ""
        self._account_id: str = ""
        self._all_addresses: list[dict[str, Any]] = []
        self._address_queue: list[dict[str, Any]] = []
        self._monitored_addresses: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Step 1 – Credentials
    # ------------------------------------------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle credential entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = APSClient(user_input[CONF_USERNAME], user_input[CONF_PASSWORD], session)
            try:
                await client.authenticate()
                self._username = user_input[CONF_USERNAME]
                self._password = user_input[CONF_PASSWORD]
                self._account_id = client.account_id
                self._all_addresses = await client.get_service_addresses()
                return await self.async_step_select_addresses()
            except APSAuthError:
                errors["base"] = "invalid_auth"
            except APSConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected error during authentication")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Step 2 – Address Selection
    # ------------------------------------------------------------------

    async def async_step_select_addresses(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle address multi-selection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected_ids = user_input.get("selected_addresses", [])
            if not selected_ids:
                errors["selected_addresses"] = "select_one_address"
            else:
                # Build the queue of addresses to configure
                self._address_queue = [
                    addr for addr in self._all_addresses if addr["sa_id"] in selected_ids
                ]
                return await self.async_step_configure_address()

        options = [
            SelectOptionDict(value=addr["sa_id"], label=_address_label(addr))
            for addr in self._all_addresses
        ]

        return self.async_show_form(
            step_id="select_addresses",
            data_schema=vol.Schema(
                {
                    vol.Required("selected_addresses"): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            multiple=True,
                            mode=SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
            description_placeholders={"count": str(len(self._all_addresses))},
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Step 3 – Address Configuration (Loop)
    # ------------------------------------------------------------------

    async def async_step_configure_address(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure a single service address."""
        if not self._address_queue:
            # Done configuring all addresses, create the entry
            entry_data = {
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                CONF_ACCOUNT_ID: self._account_id,
                CONF_MONITORED_ADDRESSES: self._monitored_addresses,
            }
            return self.async_create_entry(
                title=f"APS Account {self._account_id}", data=entry_data
            )

        current_address = self._address_queue[0]
        errors: dict[str, str] = {}

        if user_input is not None:
            friendly_name = user_input[CONF_FRIENDLY_NAME].strip()
            # Uniqueness check against other addresses in THIS entry
            if any(
                a[CONF_FRIENDLY_NAME].lower() == friendly_name.lower()
                for a in self._monitored_addresses
            ):
                errors[CONF_FRIENDLY_NAME] = "name_conflict"
            else:
                # Add to finished list and move to next in queue
                self._monitored_addresses.append({
                    CONF_SA_ID: current_address["sa_id"],
                    CONF_SP_ID: current_address["sp_id"],
                    CONF_ADDRESS: current_address["address"],
                    CONF_FRIENDLY_NAME: friendly_name,
                    CONF_IS_ACTIVE: current_address["is_active"],
                    CONF_IMPORT_MODE: user_input[CONF_IMPORT_MODE],
                })
                self._address_queue.pop(0)
                return await self.async_step_configure_address()

        data_schema = vol.Schema({
            vol.Required(
                CONF_FRIENDLY_NAME,
                default=current_address["suggested_friendly_name"]
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            vol.Required(
                CONF_IMPORT_MODE,
                default=IMPORT_MODE_CURRENT
            ): SelectSelector(SelectSelectorConfig(
                options=[
                    SelectOptionDict(value=IMPORT_MODE_CURRENT, label="Current billing cycle only"),
                    SelectOptionDict(value=IMPORT_MODE_FULL, label="Import all available history (background)"),
                ],
                mode=SelectSelectorMode.LIST,
            )),
        })

        current_idx = len(self._monitored_addresses) + 1
        total_count = len(self._monitored_addresses) + len(self._address_queue)

        return self.async_show_form(
            step_id="configure_address",
            data_schema=data_schema,
            description_placeholders={
                "address": current_address["address"],
                "current": str(current_idx),
                "total": str(total_count),
            },
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Options Flow
    # ------------------------------------------------------------------

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Return the options flow handler."""
        return APSOptionsFlow(config_entry)


class APSOptionsFlow(config_entries.OptionsFlow):
    """Options flow: change friendly names or add/remove addresses."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._entry = config_entry
        self._all_addresses: list[dict[str, Any]] = []
        self._address_queue: list[dict[str, Any]] = []
        self._monitored_addresses: list[dict[str, Any]] = []
        self._existing_map: dict[str, dict[str, Any]] = {
            a[CONF_SA_ID]: a
            for a in config_entry.data.get(CONF_MONITORED_ADDRESSES, [])
        }

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Re-authenticate to get fresh address list then show address picker."""
        session = async_get_clientsession(self.hass)
        client = APSClient(
            self._entry.data[CONF_USERNAME],
            self._entry.data[CONF_PASSWORD],
            session,
        )
        try:
            await client.authenticate()
            self._all_addresses = await client.get_service_addresses()
        except (APSAuthError, APSConnectionError) as exc:
            return self.async_abort(reason="cannot_connect")

        return await self.async_step_select_addresses()

    async def async_step_select_addresses(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Address multi-selection."""
        errors: dict[str, str] = {}
        existing_ids = list(self._existing_map.keys())

        if user_input is not None:
            selected_ids = user_input.get("selected_addresses", [])
            if not selected_ids:
                errors["selected_addresses"] = "select_one_address"
            else:
                self._address_queue = [
                    addr for addr in self._all_addresses if addr["sa_id"] in selected_ids
                ]
                return await self.async_step_configure_address()

        options = [
            SelectOptionDict(value=a["sa_id"], label=_address_label(a))
            for a in self._all_addresses
        ]

        return self.async_show_form(
            step_id="select_addresses",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "selected_addresses", default=existing_ids
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=options, multiple=True, mode=SelectSelectorMode.LIST
                        )
                    )
                }
            ),
            description_placeholders={"count": str(len(self._all_addresses))},
            errors=errors,
        )

    async def async_step_configure_address(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure a single service address (Options)."""
        if not self._address_queue:
            # Done, update the entry
            new_data = dict(self._entry.data)
            new_data[CONF_MONITORED_ADDRESSES] = self._monitored_addresses
            self.hass.config_entries.async_update_entry(self._entry, data=new_data)
            return self.async_create_entry(title="", data={})

        current_address = self._address_queue[0]
        existing = self._existing_map.get(current_address["sa_id"], {})
        errors: dict[str, str] = {}

        if user_input is not None:
            friendly_name = user_input[CONF_FRIENDLY_NAME].strip()
            if any(
                a[CONF_FRIENDLY_NAME].lower() == friendly_name.lower()
                for a in self._monitored_addresses
            ):
                errors[CONF_FRIENDLY_NAME] = "name_conflict"
            else:
                self._monitored_addresses.append({
                    CONF_SA_ID: current_address["sa_id"],
                    CONF_SP_ID: current_address["sp_id"],
                    CONF_ADDRESS: current_address["address"],
                    CONF_FRIENDLY_NAME: friendly_name,
                    CONF_IS_ACTIVE: current_address["is_active"],
                    CONF_IMPORT_MODE: user_input.get(
                        CONF_IMPORT_MODE, existing.get(CONF_IMPORT_MODE, IMPORT_MODE_CURRENT)
                    ),
                })
                self._address_queue.pop(0)
                return await self.async_step_configure_address()

        fields: dict[Any, Any] = {
            vol.Required(
                CONF_FRIENDLY_NAME,
                default=existing.get(CONF_FRIENDLY_NAME, current_address["suggested_friendly_name"])
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
        }
        # Only ask about import mode for NEWLY added addresses
        if current_address["sa_id"] not in self._existing_map:
            fields[vol.Required(CONF_IMPORT_MODE, default=IMPORT_MODE_CURRENT)] = SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(value=IMPORT_MODE_CURRENT, label="Current billing cycle only"),
                        SelectOptionDict(value=IMPORT_MODE_FULL, label="Import all available history (background)"),
                    ],
                    mode=SelectSelectorMode.LIST,
                )
            )

        # Options flow index calculation (for newly added addresses during this flow)
        # To keep it simple, we just count how many we processed in THIS flow + what's left
        current_idx = len(self._monitored_addresses) + 1
        total_count = len(self._monitored_addresses) + len(self._address_queue)

        return self.async_show_form(
            step_id="configure_address",
            data_schema=vol.Schema(fields),
            description_placeholders={
                "address": current_address["address"],
                "current": str(current_idx),
                "total": str(total_count),
            },
            errors=errors,
        )
