"""APS API Client for Home Assistant integration."""

import asyncio
import base64
import json
import logging
import re
from typing import Any, Optional

import aiohttp
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding

_LOGGER = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

BASE_URL = "https://www.aps.com"
JS_FILE_URL = f"{BASE_URL}/Assets/Js/aps-apscom.js"
AUTH_URL = f"{BASE_URL}/api/sitecore/SitecoreReactApi/UserAuthentication"
USER_DETAILS_URL = f"{BASE_URL}/api/sitecore/sitecorereactapi/GetAllUserDetails"
ESTIMATED_CHARGES_URL = f"{BASE_URL}/api/Services/Dashboard/GetEstimatedCharges"


class APSAuthError(Exception):
    """Authentication failed."""
    pass


class APSConnectionError(Exception):
    """Connection to APS failed."""
    pass


def extract_rsa_key(js_content: str) -> str:
    """Extract the RSA public key from the APS JavaScript file."""
    pattern = r'APSCOMWebPasswordpublicKey:"(-----BEGIN PUBLIC KEY-----.*?-----END PUBLIC KEY-----)"'
    match = re.search(pattern, js_content, re.DOTALL)
    
    if not match:
        raise APSConnectionError("RSA public key not found in JavaScript file")
    
    rsa_key = match.group(1)
    formatted_key = re.sub(
        r"(-----BEGIN PUBLIC KEY-----)(.*)(-----END PUBLIC KEY-----)",
        r"\1\n\2\n\3",
        rsa_key,
        flags=re.DOTALL,
    )
    return formatted_key


def encrypt_password(rsa_key_text: str, password: str) -> str:
    """Encrypt password using RSA public key (mimics JavaScript encryption)."""
    public_key = serialization.load_pem_public_key(
        rsa_key_text.encode(),
        backend=default_backend()
    )
    
    encrypted = public_key.encrypt(
        password.encode(),
        padding.PKCS1v15()
    )
    
    return base64.b64encode(encrypted).decode()


class APSClient:
    """Client for interacting with the APS API."""
    
    def __init__(self, username: str, password: str, session: Optional[aiohttp.ClientSession] = None):
        """Initialize the APS client."""
        self.username = username
        self.password = password
        self._session = session
        self._close_session = session is None
        self.account_id: Optional[str] = None
        self.service_address_id: Optional[str] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session."""
        if self._session is None:
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": USER_AGENT}
            )
        return self._session

    async def authenticate(self) -> dict[str, Any]:
        """Authenticate with APS and retrieve account details."""
        session = await self._get_session()
        
        _LOGGER.debug("Fetching RSA key")
        try:
            async with session.get(JS_FILE_URL) as resp:
                resp.raise_for_status()
                js_content = await resp.text()
        except aiohttp.ClientError as e:
            raise APSConnectionError(f"Failed to fetch RSA key: {e}")
            
        rsa_key = extract_rsa_key(js_content)
        encrypted_password = encrypt_password(rsa_key, self.password)
        
        auth_data = {
            "username": self.username,
            "password": encrypted_password,
        }
        
        _LOGGER.debug("Posting credentials")
        try:
            async with session.post(AUTH_URL, json=auth_data) as resp:
                resp.raise_for_status()
                # Use text() then loads() because of the mimetype issue mentioned in logs
                text = await resp.text()
                login_result = json.loads(text)
        except (aiohttp.ClientError, json.JSONDecodeError) as e:
            raise APSConnectionError(f"Authentication request failed: {e}")
            
        if not login_result.get("isLoginSuccess", False):
            raise APSAuthError("Username and password failed")
            
        return await self.get_account_details()

    async def get_account_details(self) -> dict[str, Any]:
        """Fetch full account details."""
        session = await self._get_session()
        
        _LOGGER.debug("Fetching account details")
        try:
            async with session.get(USER_DETAILS_URL) as resp:
                resp.raise_for_status()
                # Bypass mimetype validation for "application /json"
                user_details = await resp.json(content_type=None)
        except aiohttp.ClientError as e:
            raise APSConnectionError(f"Failed to fetch account details: {e}")
            
        try:
            details = user_details["Details"]["AccountDetails"]["getAccountDetailsResponse"]["getAccountDetailsRes"]
            self.account_id = details["getPersonDetails"]["accountID"]
            
            # Find service address ID
            premise_list = details.get("getSASPListByAccountID", {}).get("premiseDetailsList", [])
            
            # First pass: look for active service (status 20)
            for premise in premise_list:
                for sasp in premise.get("sASPDetails", []):
                    if sasp.get("sAStatus") == "20" and "sAID" in sasp:
                        self.service_address_id = str(sasp["sAID"])
                        break
                if self.service_address_id:
                    break
            
            # Fallback: take the first one if no status 20 found
            if not self.service_address_id and premise_list:
                for premise in premise_list:
                    sasp_details = premise.get("sASPDetails", [])
                    if sasp_details and "sAID" in sasp_details[0]:
                        self.service_address_id = str(sasp_details[0]["sAID"])
                        break
                    
        except (KeyError, TypeError) as e:
            _LOGGER.warning(f"Could not parse account/service IDs: {e}")
            
        return user_details

    async def get_estimated_charges(self) -> dict[str, Any]:
        """Fetch estimated charges."""
        if not self.account_id or not self.service_address_id:
            _LOGGER.warning("Missing account_id or service_address_id")
            return {}

        session = await self._get_session()
        
        # Get the B2C Access Token from the session cookies or previous response
        # In the captured traffic, it was in the 'authorization' header as 'Bearer <token>'
        # The token is actually returned in 'GetAllUserDetails' as 'B2C_AccessToken' or 'id_token'
        # Based on traffic analysis, it uses the B2C_AccessToken
        user_details = await self.get_account_details()
        profile_data = user_details.get("Details", {}).get("profileData", {})
        token = profile_data.get("B2C_AccessToken")
        
        if not token:
            _LOGGER.warning("No B2C Access Token found")
            return {}

        headers = {
            "authorization": f"Bearer {token}",
            "ocp-apim-subscription-key": "d2e9aafca6d546cd9097a3e3072cd7a5", # Found in traffic
            "x-correlation-id": "d5403e15-a418-4c52-b39a-888bf872d162", # Static for now, or generate UUID
        }
        
        params = {
            "account-id": self.account_id,
            "email-address": self.username,
            "user-name": self.username.split("@")[0], # Based on traffic
            "sa-id": self.service_address_id,
            "css-user": "APSCOM"
        }
        
        _LOGGER.debug(f"Fetching estimated charges from {ESTIMATED_CHARGES_URL}")
        try:
            async with session.get(ESTIMATED_CHARGES_URL, params=params, headers=headers) as resp:
                resp.raise_for_status()
                return await resp.json()
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Failed to fetch estimated charges: {e}")
            return {}
        
        return {} # Fallback

    async def close(self):
        """Close the session if we created it."""
        if self._close_session and self._session:
            await self._session.close()
            self._session = None
