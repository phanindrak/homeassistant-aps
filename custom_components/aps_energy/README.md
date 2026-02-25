# APS Energy Home Assistant Integration

This custom integration fetches energy data from Arizona Public Service (APS) by directly interacting with the APS Portal and Mobi APIs.

## Features

- **Multi-Address Support**: Configure and monitor all properties on your APS account individually.
- **Energy Dashboard Ready**: Sensors for daily usage, cost, and historical backfill into long-term statistics.
- **Time-of-Use (ToU) Breakdown**: Separate sensors for On-Peak, Off-Peak, and Super Off-Peak usage/cost for compatible plans.
- **Billing Details**: Monitor current balance, latest bill amount, and estimated charges for the current cycle.
- **Service Info**: Tracks service status (Active/Inactive) and current rate plan details.

## Sensors

Each monitored service address provides a suite of sensors, including:

- `sensor.aps_<friendly_name>_daily_usage_kwh`
- `sensor.aps_<friendly_name>_monthly_usage_kwh`
- `sensor.aps_<friendly_name>_estimated_charges`
- `sensor.aps_<friendly_name>_latest_bill_amount`
- `sensor.aps_<friendly_name>_current_rate_plan`
- `sensor.aps_<friendly_name>_service_address`
- `sensor.aps_<friendly_name>_service_status`
- Plus account-level: `sensor.aps_current_balance`

## Installation

1. Copy the `custom_components/aps_energy` directory to your Home Assistant `custom_components` folder.
2. Restart Home Assistant.
3. In the Home Assistant UI, go to **Settings** > **Devices & Services**.
4. Click **Add Integration** and search for **APS Energy**.
5. Enter your APS Portal credentials (email and password).
6. Select the service addresses you wish to monitor.
7. Assign a friendly name and choose a data import strategy (Full history vs. Current cycle only) for each address.

## Development

The integration uses the following APS APIs:
- `GetAllUserDetails`: For account and service address discovery.
- `GetEstimatedCharges`: For real-time cost estimation.
- `mobi.aps.com`: Advanced JSON APIs for daily consumption, hourly usage, and billed history.

Password encryption is handled using RSA PKCS1v15 padding to match the APS client-side security flow. Historical data is injected using Home Assistant's `async_add_external_statistics` API.
