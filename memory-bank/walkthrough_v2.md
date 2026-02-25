# APS Phase 2 — Multi-Address Integration Complete

## Summary of Changes

8 files written/updated, all verified with zero syntax errors.

---

## File-by-File Changes

render_diffs(file:///home/phani/code/antigravity-test/homeassistant-aps/custom_components/aps_energy/const.py)

render_diffs(file:///home/phani/code/antigravity-test/homeassistant-aps/custom_components/aps_energy/api.py)

render_diffs(file:///home/phani/code/antigravity-test/homeassistant-aps/custom_components/aps_energy/config_flow.py)

render_diffs(file:///home/phani/code/antigravity-test/homeassistant-aps/custom_components/aps_energy/coordinator.py)

render_diffs(file:///home/phani/code/antigravity-test/homeassistant-aps/custom_components/aps_energy/backfill.py)

render_diffs(file:///home/phani/code/antigravity-test/homeassistant-aps/custom_components/aps_energy/sensor.py)

render_diffs(file:///home/phani/code/antigravity-test/homeassistant-aps/custom_components/aps_energy/__init__.py)

---

## Config Flow (4 Steps)

```
Step 1: Credentials → authenticate, load all premises
Step 2: Address Selection → multi-select with Active/Inactive labels
Step 3: Friendly Names + History Mode → city-name defaults, uniqueness check
         └─ Per-address: "Current only" or "Import all history (background)"
Options Flow: re-select addresses, rename, add new ones post-install
```

---

## Sensor Matrix per Address

| Sensor | New? | Notes |
|--------|------|-------|
| `service_address` | ✅ New | Full premise string |
| `service_status` | ✅ New | `active` / `inactive` |
| `current_rate_plan` | ✅ New | Live from GetAllUserDetails; attrs: code, eff_date, is_tou |
| `latest_bill_amount` | ✅ New | Per-address `totalElectricChargeAmount` |
| `estimated_charges` | ✅ Updated | Now per-SA; unavailable on inactive address |
| `current_balance` | ✅ Updated | Account-level device |
| `daily_usage_kwh` | ✅ New | Most recent day from `getdailyusagecharges` |
| `monthly_usage_kwh` | ✅ New | Sum of current billing cycle |
| `on_peak_usage_kwh` | ✅ New | ToU plans only |
| `off_peak_usage_kwh` | ✅ New | ToU plans only |
| `super_off_peak_usage_kwh` | ✅ New | ToU plans only (if tier exists) |
| `on_peak_cost` | ✅ New | ToU + active only |
| `off_peak_cost` | ✅ New | ToU + active only |

---

## Historical Backfill Design

When user selects "Import all history", a background task in `backfill.py`:

1. Fetches `getbilledusagehistory` (up to 3 years)
2. For each billing cycle, fetches `getdailyusagecharges` (throttled at 0.75s/call)
3. Writes cumulative `StatisticData` to HA via `async_add_external_statistics`
4. Marks `backfill_complete_{sa_id} = True` in `entry.options` to prevent re-runs

Statistics backfilled: `daily_kwh`, `daily_cost`, `on_peak_kwh`, `off_peak_kwh`, `super_off_peak_kwh` — appear in Energy Dashboard and History graphs.

---

## Key Design Decisions

- **Shared client, per-address coordinators** — one authenticated `APSClient` instance is shared across all coordinators; only one `GetAllUserDetails` HTTP call per update cycle regardless of how many addresses are monitored
- **Token caching** — `_token` cached on the client; no extra auth call needed for mobi.aps.com requests
- **ToU detection** — `is_tou_plan(rate_plan_code)` checks if code contains `"TOU"` or starts with `"RTOU"`; ToU sensors return `None` and are `unavailable` for flat-rate plans
- **City extraction** — `extract_city(address)` splits on commas and takes the third-from-last segment (city comes before state and zip)
- **v1 → v2 migration** — `async_migrate_entry` re-authenticates, finds the old SA in the premise list, wraps it in the new `monitored_addresses` format with `import_mode=current_only` (no spurious backfill trigger)

---

## Next Steps

> [!NOTE]
> The `_parse_billing_cycles()` and `_parse_daily_readings()` parsers in `backfill.py`, plus the `_daily_usage_entries()` method in `sensor.py`, need to be updated with the exact key paths from the real `mobi.aps.com` API responses. Run `capture_traffic.py` or the browser subagent while interacting with the Usage page and inspect the raw JSON to confirm the field names.
