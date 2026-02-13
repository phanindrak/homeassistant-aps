# APS Energy Integration

A Home Assistant custom integration for monitoring energy usage and billing data from Arizona Public Service (APS).

## Features

- **Current Balance**: Monitor your outstanding account balance.
- **Latest Bill Sensors**: Tracks your most recent bill amount, date, and billing period.
- **Estimated Charges**: Real-time month-to-date cost estimates (for accounts with AMI meters), including on-peak and off-peak breakdowns.
- **Secure Authentication**: Uses native RSA encryption to communicate directly with APS Portal APIs.
- **Auto-Discovery**: Automatically identifies active service addresses and account details during setup.

## Project Structure

```text
.
├── custom_components/
│   └── aps_energy/        # Core Home Assistant integration
├── docs/                 # Detailed documentation and test guides
├── docker-compose.yml    # Standalone test environment
├── pyproject.toml        # Dependency management (Poetry)
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

The integration reverse-engineers the following APS Portal endpoints:
- `GetAllUserDetails`: For account and SASP (Service Agreement Service Point) discovery.
- `GetEstimatedCharges`: For real-time billing period cost estimates.
- Sitecore JSS Layout: For parsing account hierarchy and rate plan descriptions.
