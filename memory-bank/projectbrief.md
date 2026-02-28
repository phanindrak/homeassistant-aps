# Project Brief: APS Energy Integration for Home Assistant

## Core Requirements
- Integrate Arizona Public Service (APS) energy data into Home Assistant.
- Provide sensors for:
    - Service Address information and status (Active/Inactive).
    - Current rate plan details.
    - Hourly/Daily/Monthly energy consumption (kWh).
    - Current billing period costs and usage.
    - Historical billing and usage data.
    - Real-time energy rates and periods (Time-of-Use).
- Support for **accounts with multiple service addresses**.
- Automated **backfill of historical data** into Home Assistant's long-term statistics.
- Precise tracking of APS-specific rate plans (TOU 4-7, etc.).
- Compatible with Home Assistant's Energy Dashboard.

## Goals
- Stable and resilient data extraction from APS portal/mobi APIs.
- User-friendly configuration flow with friendly labels and multi-address selection.
- Real-time awareness of utility rate periods via a local rate engine.
- Easy installation as a Home Assistant Custom Integration.

## Success Criteria
- Successful authentication and extraction of multiple service addresses.
- Discovery and implementation of `mobi.aps.com` usage APIs.
- Successful backfill of 2-3 years of history into HA statistics.
- Correct integration with the HA Energy Dashboard.
- Accurate real-time ToU period tracking (On-Peak/Off-Peak).
