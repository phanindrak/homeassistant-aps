"""APS API Client for Home Assistant integration."""

import asyncio
import base64
import json
import logging
import re
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Optional

import aiohttp
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding

_LOGGER = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

BASE_URL = "https://www.aps.com"
MOBI_BASE_URL = "https://mobi.aps.com"

JS_FILE_URL = f"{BASE_URL}/Assets/Js/aps-apscom.js"
AUTH_URL = f"{BASE_URL}/api/sitecore/SitecoreReactApi/UserAuthentication"
USER_DETAILS_URL = f"{BASE_URL}/api/sitecore/sitecorereactapi/GetAllUserDetails"
ESTIMATED_CHARGES_URL = f"{BASE_URL}/api/Services/Dashboard/GetEstimatedCharges"
HOURLY_USAGE_URL = f"{MOBI_BASE_URL}/ccb-billing/v1/gethourlyusagecharges"
DAILY_USAGE_URL = f"{MOBI_BASE_URL}/ccb-billing/v1/getdailyusagecharges"
BILLED_HISTORY_URL = f"{MOBI_BASE_URL}/customerhistoryservices/v1/getbilledusagehistory"

OCP_APIM_KEY = "d2e9aafca6d546cd9097a3e3072cd7a5"


class APSAuthError(Exception):
    """Authentication failed."""


class APSConnectionError(Exception):
    """Connection to APS failed."""


def extract_rsa_key(js_content: str) -> str:
    """Extract the RSA public key from the APS JavaScript file."""
    pattern = r'APSCOMWebPasswordpublicKey:"(-----BEGIN PUBLIC KEY-----.*?-----END PUBLIC KEY-----)"'
    match = re.search(pattern, js_content, re.DOTALL)
    if not match:
        raise APSConnectionError("RSA public key not found in JavaScript file")
    rsa_key = match.group(1)
    return re.sub(
        r"(-----BEGIN PUBLIC KEY-----)(.*)(-----END PUBLIC KEY-----)",
        r"\1\n\2\n\3",
        rsa_key,
        flags=re.DOTALL,
    )


def encrypt_password(rsa_key_text: str, password: str) -> str:
    """Encrypt password using RSA public key (mimics JavaScript encryption)."""
    public_key = serialization.load_pem_public_key(
        rsa_key_text.encode(), backend=default_backend()
    )
    encrypted = public_key.encrypt(password.encode(), padding.PKCS1v15())
    return base64.b64encode(encrypted).decode()


def extract_city(address: str) -> str:
    """Extract city name from a premise address string.

    Format: "STREET, CITY, STATE, ZIP"
    Returns the city segment, title-cased.
    """
    parts = [p.strip() for p in address.split(",")]
    # City is second-to-last before state and zip
    if len(parts) >= 3:
        return parts[-3].title()
    return parts[0].title() if parts else "Unknown"


def is_tou_plan(rate_plan_code: str) -> bool:
    """Return True if the rate plan code indicates a Time-of-Use plan."""
    code = (rate_plan_code or "").upper()
    return "TOU" in code or code.startswith("RTOU")


def parse_service_addresses(user_details: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse all service addresses from GetAllUserDetails response.

    Returns a list of dicts, one per sASPDetails entry, containing all
    fields needed by the config flow and coordinators.
    """
    addresses: list[dict[str, Any]] = []
    try:
        details = (
            user_details["Details"]["AccountDetails"]
            ["getAccountDetailsResponse"]["getAccountDetailsRes"]
        )
        premises = details["getSASPListByAccountID"]["premiseDetailsList"]
        for premise in premises:
            for sasp in premise.get("sASPDetails", []):
                sa_id = str(sasp.get("sAID", ""))
                sp_id = str(sasp.get("sPID", ""))
                address = sasp.get("premiseAddress", "")
                status = str(sasp.get("sAStatus", ""))
                is_active = status == "20"
                plan_code = sasp.get("sARatePlancCode", "")
                addresses.append({
                    "sa_id": sa_id,
                    "sp_id": sp_id,
                    "address": address,
                    "is_active": is_active,
                    "sa_status": status,
                    "rate_plan": sasp.get("sARatePlanDescription", ""),
                    "rate_plan_code": plan_code,
                    "rate_plan_eff_date": sasp.get("sARatePlanEffDate", ""),
                    "is_tou": is_tou_plan(plan_code),
                    "start_date": sasp.get("sAStartDate", ""),
                    "end_date": sasp.get("sAEndDate", ""),
                    "suggested_friendly_name": extract_city(address),
                })
    except (KeyError, TypeError) as exc:
        _LOGGER.warning("Could not parse service addresses: %s", exc)
    return addresses


class APSClient:
    """Client for interacting with the APS API."""

    def __init__(
        self,
        username: str,
        password: str,
        session: Optional[aiohttp.ClientSession] = None,
    ) -> None:
        """Initialize the APS client."""
        self.username = username
        self.password = password
        self._session = session
        self._close_session = session is None
        self.account_id: Optional[str] = None
        # Cached user details to avoid repeated GetAllUserDetails calls
        self._user_details: Optional[dict[str, Any]] = None
        self._token: Optional[str] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session."""
        if self._session is None:
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": USER_AGENT}
            )
        return self._session

    def _mobi_headers(self) -> dict[str, str]:
        """Build authorization headers for mobi.aps.com calls."""
        return {
            "authorization": f"Bearer {self._token}",
            "ocp-apim-subscription-key": OCP_APIM_KEY,
            "x-correlation-id": str(uuid.uuid4()),
            "accept": "application/json",
        }

    def _dashboard_headers(self) -> dict[str, str]:
        """Build authorization headers for www.aps.com/api/Services calls."""
        return {
            "authorization": f"Bearer {self._token}",
            "ocp-apim-subscription-key": OCP_APIM_KEY,
            "x-correlation-id": str(uuid.uuid4()),
        }

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def authenticate(self) -> dict[str, Any]:
        """Authenticate with APS and retrieve account details."""
        session = await self._get_session()

        _LOGGER.debug("Fetching RSA key")
        try:
            async with session.get(JS_FILE_URL) as resp:
                resp.raise_for_status()
                js_content = await resp.text()
        except aiohttp.ClientError as exc:
            raise APSConnectionError(f"Failed to fetch RSA key: {exc}") from exc

        rsa_key = extract_rsa_key(js_content)
        encrypted_password = encrypt_password(rsa_key, self.password)

        _LOGGER.debug("Posting credentials")
        try:
            async with session.post(
                AUTH_URL, json={"username": self.username, "password": encrypted_password}
            ) as resp:
                resp.raise_for_status()
                text = await resp.text()
                login_result = json.loads(text)
        except (aiohttp.ClientError, json.JSONDecodeError) as exc:
            raise APSConnectionError(f"Authentication request failed: {exc}") from exc

        if not login_result.get("isLoginSuccess", False):
            raise APSAuthError("Username and password failed")

        user_details = await self._fetch_user_details()
        try:
            details = (
                user_details["Details"]["AccountDetails"]
                ["getAccountDetailsResponse"]["getAccountDetailsRes"]
            )
            self.account_id = details["getPersonDetails"]["accountID"]
        except (KeyError, TypeError) as exc:
            raise APSConnectionError(f"Failed to parse account ID: {exc}") from exc

        return user_details

    async def _fetch_user_details(self) -> dict[str, Any]:
        """Fetch GetAllUserDetails and cache token and details."""
        session = await self._get_session()
        try:
            async with session.get(USER_DETAILS_URL) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
        except aiohttp.ClientError as exc:
            raise APSConnectionError(f"Failed to fetch account details: {exc}") from exc

        # Cache the details and extract the B2C token
        self._user_details = data
        self._token = (
            data.get("Details", {})
            .get("profileData", {})
            .get("B2C_AccessToken")
        )
        return data

    async def get_account_details(self) -> dict[str, Any]:
        """Fetch fresh account details (invalidates cache)."""
        return await self._fetch_user_details()

    async def get_service_addresses(self) -> list[dict[str, Any]]:
        """Return list of all service addresses parsed from account details."""
        details = self._user_details or await self._fetch_user_details()
        return parse_service_addresses(details)

    # ------------------------------------------------------------------
    # Per-address data fetchers
    # ------------------------------------------------------------------

    def _base_params(self, sa_id: str) -> dict[str, str]:
        return {
            "account-id": self.account_id,
            "email-address": self.username,
            "user-name": self.username.split("@")[0],
            "sa-id": sa_id,
            "css-user": "APSCOM",
        }

    async def get_estimated_charges(self, sa_id: str, sp_id: str) -> dict[str, Any]:
        """Fetch estimated charges for a specific service address."""
        if not self.account_id or not self._token:
            _LOGGER.warning("Not authenticated — cannot fetch estimated charges")
            return {}

        session = await self._get_session()
        params = self._base_params(sa_id)

        try:
            async with session.get(
                ESTIMATED_CHARGES_URL,
                params=params,
                headers=self._dashboard_headers(),
            ) as resp:
                resp.raise_for_status()
                return await resp.json(content_type=None)
        except aiohttp.ClientError as exc:
            _LOGGER.error("Failed to fetch estimated charges for sa_id=%s: %s", sa_id, exc)
            return {}

    async def get_daily_usage(
        self,
        sa_id: str,
        sp_id: str,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        """Fetch daily kWh usage and charges for a date range."""
        if not self._token:
            return {}

        session = await self._get_session()
        params = {
            "startDate": start_date.strftime("%Y-%m-%d"),
            "endDate": end_date.strftime("%Y-%m-%d"),
            "accountNumber": self.account_id,
            "sAID": sa_id,
            "spId": sp_id,
        }
        try:
            async with session.get(
                DAILY_USAGE_URL,
                params=params,
                headers=self._mobi_headers(),
            ) as resp:
                resp.raise_for_status()
                return await resp.json(content_type=None)
        except aiohttp.ClientError as exc:
            _LOGGER.error("Failed to fetch daily usage for sa_id=%s: %s", sa_id, exc)
            return {}

    async def get_hourly_usage(
        self,
        sa_id: str,
        sp_id: str,
        usage_date: date,
    ) -> dict[str, Any]:
        """Fetch hourly kWh usage and charges for a single date."""
        if not self._token:
            return {}

        session = await self._get_session()
        params = {
            "date": usage_date.strftime("%Y-%m-%d"),
            "accountNumber": self.account_id,
            "sAID": sa_id,
            "spId": sp_id,
        }
        try:
            async with session.get(
                HOURLY_USAGE_URL,
                params=params,
                headers=self._mobi_headers(),
            ) as resp:
                resp.raise_for_status()
                return await resp.json(content_type=None)
        except aiohttp.ClientError as exc:
            _LOGGER.error("Failed to fetch hourly usage for sa_id=%s: %s", sa_id, exc)
            return {}

    async def get_billed_usage_history(
        self,
        sa_id: str,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        """Fetch historical monthly billing data including kWh per cycle."""
        if not self._token:
            return {}

        session = await self._get_session()
        params = {
            "account-id": self.account_id,
            "sa-id": sa_id,
            "start-date": start_date.strftime("%Y-%m-%d"),
            "end-date": end_date.strftime("%Y-%m-%d"),
        }
        try:
            async with session.get(
                BILLED_HISTORY_URL,
                params=params,
                headers=self._mobi_headers(),
            ) as resp:
                resp.raise_for_status()
                return await resp.json(content_type=None)
        except aiohttp.ClientError as exc:
            _LOGGER.error("Failed to fetch billed usage history for sa_id=%s: %s", sa_id, exc)
            return {}

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the session if we created it."""
        if self._close_session and self._session:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> "APSClient":
        await self._get_session()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
