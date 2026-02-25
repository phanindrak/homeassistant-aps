# Tech Context: APS Energy Integration

## Technologies Used
- **Language**: Python 3.10+
- **HTTP Client**: `aiohttp` for primary API interaction.
- **Encryption**: `cryptography` (RSA-PKCS1v15) for password security.
- **Automation (Discovery)**: `playwright` for capturing browser network traffic.
- **Framework**: Home Assistant Core (Custom Integration).
- **Persistence**: HA Recorder (Long-term statistics API).

## APIs Discovered & Utilized
- **www.aps.com**: Sitecore authenticated endpoints for account and service details.
- **mobi.aps.com**: Granular JSON APIs for daily/hourly usage and billed history.
  - Requirement: Bearer Token + `ocp-apim-subscription-key` + `x-correlation-id`.

## Development Tools
- `capture_traffic.py`: Uses Playwright to intercept real portal traffic and discover API keys/endpoints.
- `probe_usage.py`: Authenticates and tests various API endpoint permutations.

## Technical Constraints
- **MFA/Bot Detection**: APS triggers security blocks if login behavior is suspicious. Mimicking the browser flow (RSA encryption) is required.
- **Rate Limiting**: Backfill tasks must be throttled (e.g., 0.75s per call) to avoid API bans.
- **Data Latency**: Historical daily usage is typically not available for the current day until the following morning.
- **Translation Caching**: HA requires a full restart and browser cache clear to reflect changes in `strings.json` / `en.json`.
