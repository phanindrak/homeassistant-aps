# APS Granular Usage API Discovery (Re-do)

## Research & Analysis
- [x] Review existing research scripts (discover_apis.py, probe_usage.py, capture_traffic.py, aps_client.py)
- [x] Analyze captured_traffic.json — only dashboard visited, no Usage/kWh pages captured
- [x] Identify root cause: sitecore endpoints returned HTML (false positives), real API is under `/api/Services/`
- [x] Identify correct auth pattern: Bearer B2C token + ocp-apim-subscription-key header

## Script Updates
- [x] Update `probe_usage.py` — focus on /api/Services/ namespace with more endpoint variations
- [x] Update `capture_traffic.py` — ensure it navigates to energy usage/history pages (not just dashboard)

## Discovery Execution
- [x] Run updated `probe_usage.py` — all 27 guesses returned 404 (confirms names can't be guessed)
- [x] Run browser capture — auto-navigated to Usage/History pages and captured API calls
- [x] Analyze captured traffic — found 3 mobi.aps.com endpoints for kWh data

## Document Results
- [x] Write walkthrough summarizing what endpoints were found

## Phase 2 Implementation
- [x] Update `const.py` — add new constants
- [x] Update `api.py` — mobi.aps.com endpoints, spId extraction, per-address method signatures
- [x] Rewrite `config_flow.py` — 4-step flow (credentials, address select, friendly names, history mode)
- [x] Update `coordinator.py` — per-address APSAddressCoordinator
- [x] Create `backfill.py` — background historical data backfill via async_add_external_statistics
- [x] Rewrite `sensor.py` — full sensor matrix per address
- [x] Update `__init__.py` — per-address coordinator setup, v1→v2 migration
- [x] Update `strings.json` / translations for new config flow steps
- [x] Refactor `config_flow.py` — use looping address config for better labels

## Phase 2 Bugfixes
- [x] Create `translations/en.json` from `strings.json` so HA loads the UI strings
- [x] Update `config_flow.py` to show "Address X of Y" in the looping flow to clarify it is a multi-step process

## Phase 3: Local ToU Rate Engine (Context Recovered)
- [ ] Create `rate_engine.py` to locally calculate On-Peak / Off-Peak / Super Off-Peak periods based on APS schedules without API calls.
- [ ] Implement `sensor.aps_current_rate_period` to show the real-time ToU period for active plans.
- [ ] Implement `sensor.aps_next_rate_change` to show a countdown to the next ToU transition.
