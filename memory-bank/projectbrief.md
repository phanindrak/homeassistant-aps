# Project Brief: APS Energy Integration for Home Assistant

## Core Requirements
- Integrate Arizona Public Service (APS) energy data into Home Assistant.
- Provide sensors for:
    - Hourly/Daily/Monthly energy consumption (kWh).
    - Current billing period costs and usage.
    - Forecasted costs and usage.
    - Real-time energy rates (Time-of-Use periods).
- Compatible with Home Assistant's Energy Dashboard.
- Automate data retrieval from APS customer portal.

## Goals
- Stable and resilient data extraction from APS (direct API/portal access since Opower is no longer supported).
- Precise tracking of APS-specific rate plans (TOU 4-7, etc.).
- Easy installation as a Home Assistant Custom Integration.

## Success Criteria
- Successful authentication to APS portal using user credentials.
- Discovery of valid API endpoints for usage and billing data.
- Implementation of an HA sensor platform that updates regularly.
- Correct integration with the HA Energy Dashboard (proper device/state classes).
