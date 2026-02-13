# APS Energy Home Assistant Integration

This custom integration fetches energy data from Arizona Public Service (APS) by directly interacting with the APS Portal APIs.

## Features

- **Outstanding Balance**: Monitor your current outstanding balance with APS.
- **Latest Bill**: View the amount and date of your most recent bill.
- **Estimated Charges**: Real-time estimate of your current billing period charges (for accounts with AMI meters).
- **Auto-Discovery**: Automatically finds your account and active service addresses.

## Installation

1. Copy the `custom_components/aps_energy` directory to your Home Assistant `custom_components` folder.
2. Restart Home Assistant.
3. In the Home Assistant UI, go to **Settings** > **Devices & Services**.
4. Click **Add Integration** and search for **APS Energy**.
5. Enter your APS Portal credentials (email and password).

## Development

The integration uses the following APS APIs:
- `GetAllUserDetails`: For account and service address discovery.
- `GetEstimatedCharges`: For real-time cost estimation.
- Sitecore JSS Layout: For overall account structure.

Password encryption is handled using RSA PKCS1v15 padding to match the APS client-side security flow.
