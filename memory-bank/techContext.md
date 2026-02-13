# Tech Context: APS Energy Integration

## Technologies Used
- **Language**: Python 3.10+
- **Dependency Management**: Poetry
- **HTTP Client**: `aiohttp`
- **Encryption**: `cryptography` (RSA-PKCS1v15)
- **Environment**: `python-dotenv` for local credential testing.
- **Framework**: Home Assistant Core (Custom Integration).

## Development Setup
- `poetry install`: Install dependencies.
- `.env`: Stores `APS_USERNAME` and `APS_PASSWORD` for local testing.
- `pytest`: Used for logic verification (especially rate engine).

## Technical Constraints
- **APS MFA/Forbidden Errors**: APS might throttle or block standard headless logins. Authentication mimics browser behavior using RSA encryption.
- **Data Delay**: APS data typically lags by 24-48 hours on the portal.
- **Sitecore CMS**: Backend architecture requires handling specific cookie/header state.
