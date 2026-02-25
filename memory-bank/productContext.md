# Product Context: APS Energy Integration

## Why this project exists
Arizona Public Service (APS) customers lack a native or well-supported integration for Home Assistant to monitor their energy usage and costs. This integration fills that gap, allowing users to automate their energy management based on actual utility data, rates, and historical performance.

## Problems it solves
- **Visibility**: Provides real-time and historical views of energy spend for one or more properties.
- **Cost Management**: Helps users shift energy usage to off-peak hours by providing live rate information via a local rate engine.
- **Planning**: Forecasts bill totals and provides historical context via long-term statistics.
- **Automation**: Enables HA to trigger appliances or batteries during super-off-peak or off-peak periods.
- **Multi-Property Support**: Handles users with multiple APS accounts or service addresses in a single integration entry.

## Core Workflows
1. **Setup**:
   - User enters credentials.
   - User selects one or more discovered service addresses (active or inactive).
   - User assigns a friendly name to each address (to prefix sensors).
   - User chooses a data import strategy (Full history vs. Current cycle only).
2. **Data Fetching**:
   - Shared authenticated client fetches account-level details.
   - Per-address coordinators poll for granular usage and billing data (30m interval for active, 24h for inactive).
3. **Historical Backfill**:
   - A background task retrieves years of historical daily usage and billing data and writes it to HA long-term statistics.
4. **Real-time Processing**:
   - A local rate engine determines the current ToU period (On-Peak/Off-Peak) and estimated current cost.
5. **Visualization**:
   - Data is presented in HA sensors and automatically populates the Energy Dashboard.
