# APS Energy Integration

A Home Assistant custom integration for monitoring energy usage, billing data, and real-time Time-of-Use periods from Arizona Public Service (APS).

## Features

- **Multi-Address Support**: Automatically discover and monitor multiple service addresses (active and inactive) from a single APS account.
- **Granular Energy Usage**: Sensor data for daily and monthly kWh consumption.
- **Time-of-Use (ToU) Intelligence**:
    - Automatic detection of ToU rate plans.
    - Energy and cost breakdowns for On-Peak, Off-Peak, and Super Off-Peak periods.
    - (Planned) Real-time ToU period sensors via local rate engine.
- **Historical Data Backfill**: Automatically imports years of historical daily usage and billing data into Home Assistant's long-term statistics for display in the Energy Dashboard.
- **Detailed Billing Info**:
    - **Current Balance**: Monitor your outstanding account balance.
    - **Latest Bill Sensors**: Tracks your most recent bill amount and date per service address.
    - **Estimated Charges**: Real-time month-to-date cost estimates (for accounts with AMI meters).
- **Premium UI Experience**: User-friendly multi-step configuration flow with friendly name assignment and descriptive instructions.
- **Secure Authentication**: Uses native RSA encryption to communicate directly with APS Portal APIs.

## Project Structure

```text
.
├── custom_components/
│   └── aps_energy/        # Core Home Assistant integration
├── docs/                 # Detailed documentation and test guides
├── docker-compose.yml    # Standalone test environment
├── pyproject.yml         # Dependency management (Poetry)
└── poetry.lock
```

## Getting Started

### 1. Development Environment
This project uses [Poetry](https://python-poetry.org/) for dependency management.
```bash
poetry install
```

### 2. Testing with Home Assistant
You can run a standalone test instance of Home Assistant pre-loaded with this integration using Docker Compose:
```bash
docker-compose up -d
```
Access the test instance at [http://localhost:8123](http://localhost:8123). See [docs/README_TEST.md](docs/README_TEST.md) for more details.

### 3. Manual Installation
To use this in your main Home Assistant instance:
1. Copy the `custom_components/aps_energy/` folder into your Home Assistant's `custom_components` directory.
2. Restart Home Assistant.
3. Add the integration via **Settings** > **Devices & Services** > **Add Integration** and search for **APS Energy**.

## Documentation

- [Walkthrough](docs/walkthrough.md): Detailed explanation of the technical implementation.
- [Testing Guide](docs/README_TEST.md): How to use the Docker-based test environment.
- [Integration Details](custom_components/aps_energy/README.md): Specific sensors and configuration details.

## Implementation Details

The integration reverse-engineers the following APS APIs:
- `GetAllUserDetails`: For account and SASP (Service Agreement Service Point) discovery.
- `GetEstimatedCharges`: For real-time billing period cost estimates.
- `mobi.aps.com`: Granular usage and historical billing APIs.
- `async_add_external_statistics`: For historical data ingestion.
