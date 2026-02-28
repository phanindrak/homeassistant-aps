# Active Context: APS Energy Integration

## Current Status
- **Phase 2 (Multi-address & Backfill)** is complete. 
- Integration supports multiple service addresses per account.
- Per-address sensors (Usage, Rate Plan, Cost, Status) are implemented.
- Historical backfill of daily usage and costs into HA long-term statistics is implemented.
- **Phase 2 Bugfixes** (Missing translations and looping UI sequence indicators) are resolved.

## Recent Changes
- Refactored `config_flow.py` to a looping pattern for configuring multiple addresses.
- Fixed UI text loading by creating `translations/en.json`.
- Added `(current of total)` indicators to config flow titles for better UX.
- Implemented `backfill.py` using `async_add_external_statistics`.
- Updated `sensor.py` with 13 distinct sensor classes per address plus account-level balance.

## In Progress
- Transitioning to **Phase 3 (Local Rate Engine)**.

## Next Steps
- [ ] Create `rate_engine.py` to calculate ToU periods locally.
- [ ] Implement real-time ToU sensors (`current_rate_period`, `next_rate_change`).
- [ ] Verify ToU calculation against all 14 APS holidays and seasonal boundaries.
- [ ] Finalize documentation for end-users.
 
+## Future Roadmap Added
+- [ ] **Phase 4 (Billing & Analytics)**: New items added to the roadmap from user requests (see `TODO.md` and `memory-bank/progress.md`).
+  - Research: Optimized backfill start dates for inactive addresses.
+  - Research: Plan-specific rate lookups (per kWh).
+  - New Sensors: Billing period tracking and payment history.
+  - Enhanced Data Capture: Capturing all fields from `GetEstimatedCharges`.
+
