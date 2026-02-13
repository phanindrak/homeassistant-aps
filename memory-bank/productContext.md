# Product Context: APS Energy Integration

## Why this project exists
Arizona Public Service (APS) customers lack a native or well-supported integration for Home Assistant to monitor their energy usage and costs. While some legacy tools existed (Opower integration), support for APS has been removed or restricted. This integration fills that gap, allowing users to automate their energy management based on actual utility data.

## Problems it solves
- **Visibility**: Provides real-time and historical views of energy spend.
- **Cost Management**: Helps users shift energy usage to off-peak hours by providing live rate information.
- **Planning**: Forecasts bill totals based on current month performance.
- **Automation**: Enables HA to trigger appliances or batteries during super-off-peak or off-peak periods.

## Core Workflows
1. **Setup**: User enters APS credentials and selects their rate plan via HA UI.
2. **Data Fetching**: Integration polls APS portal APIs every 4 hours.
3. **Processing**: Raw usage values are categorized into peak/off-peak periods.
4. **Visualization**: Data is presented in HA sensors and the Energy Dashboard.
