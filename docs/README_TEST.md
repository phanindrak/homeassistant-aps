# Testing APS Energy Integration

This directory contains a standalone Home Assistant test environment.

## How to use

1. **Start the container**:
   ```bash
   docker-compose up -d
   ```

2. **Access Home Assistant**:
   Open [http://localhost:8123](http://localhost:8123) in your browser.

3. **Initial Setup**:
   - Create a test account (standard HA onboarding).
   - Go to **Settings** > **Devices & Services**.
   - Click **Add Integration**.
   - Search for **APS Energy**.
   - Enter your credentials.

4. **Debugging**:
   - View logs in real-time:
     ```bash
     docker logs -f homeassistant-test
     ```
   - The integration logs are set to `DEBUG` level in `test_config/configuration.yaml`.

5. **Stop and Cleanup**:
   ```bash
   docker-compose down
   ```

## Folder Structure
- `test_config/`: Contains the HA configuration, database, and logs.
- `custom_components/aps_energy/`: Mounted directly from your development directory. Changes to the code will require a Home Assistant restart (inside the container) to take effect.
