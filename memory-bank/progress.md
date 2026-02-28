# Progress Tracker: APS Energy Integration

## Phases

### [x] Planning & Research
- [x] Research APS data access methods.
- [x] Define feature set and implementation strategy.
- [x] Select direct portal and mobi API access.

### [x] Phase 0: API Discovery
- [x] Project structure set up.
- [x] RSA Authentication client implemented.
- [x] Account/Service info extraction verified.
- [x] Playwright traffic capture tool implemented.
- [x] `mobi.aps.com` usage/billing endpoints discovered and verified.

### [x] Phase 1: Core HA Integration
- [x] Integration scaffold (`manifest.json`, `__init__.py`).
- [x] Configuration Flow (Credentials setup).
- [x] DataUpdateCoordinator.
- [x] Basic Cost sensors (Balance, Bill).

### [x] Phase 2: Multi-Address & Usage
- [x] Looping Multi-Address selection UI.
- [x] Historical data backfill into HA Statistics.
- [x] Per-address sensor matrix (Daily/Monthly kWh, ToU splits).
- [x] UI/UX Bugfixes (Translations + Sequence counts).

### [ ] Phase 3: Local Rate Engine
- [ ] `rate_engine.py` implementation (Local ToU logic).
- [ ] Current Rate / Period real-time sensors.
- [ ] Countdown to next rate changes.

### [ ] Phase 4: Billing Improvements & Analytics
- [ ] Research: Optimization of backfill date for inactive addresses.
- [ ] Research: API rate lookup (On-Peak/Off-Peak/Super-Off-Peak per kWh).
- [ ] Tracking of billing period dates and duration.
- [ ] Billing & account payment history retrieval.
- [ ] Capture additional `GetEstimatedCharges` data elements (Adjustors, Taxes, etc.).

## Status Summary
- **Total Progress**: ~80%
- **Core Platform**: Complete ✅
- **Historical Data**: Integrated ✅
- **Real-time ToU**: In Planning 🛠️
- **Future Enhancements**: Queued 📋
