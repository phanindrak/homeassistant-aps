# Active Context: APS Energy Integration

## Current Status
- **Phase 0 (API Discovery)** is active.
- Authentication flow is fully implemented and verified.
- Account and Service Address details are being retrieved successfully.

## Recent Changes
- Implemented `APSClient` with RSA password encryption.
- Added `.env` support for credentials.
- Switched to **Poetry** for dependency management.
- Discovered 16+ API endpoints; found they return maintenance pages without correct parameters.
- **Added Playwright-based traffic capture tool** (`capture_traffic.py`) to intercept real portal requests.

## In Progress
- Running `capture_traffic.py` to observe real API payloads for usage and billing history.
- Investigating the specific payload/params required for usage data endpoints.

## Next Steps
- [ ] Inspect browser network traffic when viewing usage on `aps.com`.
- [ ] Determine required parameters for usage data POST/GET requests.
- [ ] Extract hourly usage data samples.
- [ ] Begin Phase 1: Building the `custom_components` skeleton.
