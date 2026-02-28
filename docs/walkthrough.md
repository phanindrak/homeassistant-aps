# APS Energy Integration Walkthrough

This integration provides Home Assistant sensors for Arizona Public Service (APS) energy data.

## Phase 0: Research and Discovery
We used Playwright to capture network traffic from the APS Portal. This revealed:
- **Authentication**: Uses a POST request with an RSA-encrypted password.
- **Account Details**: `GetAllUserDetails` returns a comprehensive JSON with account IDs and billing info.
- **Cost Estimation**: `GetEstimatedCharges` provides real-time month-to-date costs for AMI-equipped meters.

## Phase 1: Python Client (`api.py`)
- Implemented `APSClient` to handle stateful authentication and API calls.
- Mimicked the browser's RSA encryption using the `cryptography` library.
- Added logic to automatically discover the active service address (status "20").

## Phase 2: Home Assistant Integration
- **`manifest.json`**: Defined integration meta-data and dependencies (`aiohttp`, `cryptography`).
- **`coordinator.py`**: Implemented a `DataUpdateCoordinator` to fetch data every hour and share it among sensors.
- **`sensor.py`**: Created sensors for:
    - **Current Balance**: Outstanding amount due.
    - **Latest Bill**: Details of the most recent month's billing.
    - **Estimated Charges**: Real-time cost estimates with detailed attributes (on-peak, off-peak, etc.).
- **`config_flow.py`**: Guided setup UI with credential validation.

## Technical Details
- **RSA Key**: Dynamically extracted from `aps-apscom.js` during authentication.
- **B2C Token**: Extracted from `GetAllUserDetails` and used as a Bearer token for protected Service APIs.
- **Status Codes**: Prioritizes service addresses with status "20" to avoid legacy/closed accounts.
