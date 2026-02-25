# APS Energy Integration — Phase 2 Implementation Plan

## Background

Phase 1 implemented 3 sensors (balance, latest bill, estimated charges) against a single hardcoded service address. Phase 2 will:

- Support accounts with **multiple service addresses** (premises)
- Let the user **select which addresses to monitor** and assign **friendly names**
- Expose a full set of sensors **per address** including kWh usage and rate plan
- Backfill **historical usage and billing data** into HA's long-term statistics

> [!IMPORTANT]
> `ConfigFlow.VERSION` must be bumped to `2` and `async_migrate_entry` added to upgrade existing v1 entries automatically.

---

## What the API Provides

### Account-Level `FriendlyName` (profileData)
The API has a single `FriendlyName` on the account, not per-premise. For the test account it is `"Phoenix and Peoria"` — useful as context but not a per-address label.

**Default friendly name strategy:** Extract the **city** from the `premiseAddress` string (e.g., `"25226 N 131ST DR, PEORIA, AZ, 85383"` → `"Peoria"`). This becomes the pre-filled default the user can change.

### Per-Address Fields (inside each `sASPDetails` entry)

| Field | Example | Usage |
|-------|---------|-------|
| `sAID` | `3942113360` | Service Address ID — key for all API calls |
| `sPID` | `3941131360` | Service Point ID — required by mobi.aps.com endpoints |
| `sAStatus` | `"20"` / `"60"` | `20` = active, `60` = inactive |
| `premiseAddress` | `"25226 N 131ST DR, PEORIA, AZ, 85383"` | Full address string |
| `sARatePlanDescription` | `"Time-of-Use 4pm-7pm Weekdays"` | Plan name — changes per billing cycle |
| `sARatePlancCode` | `"RTOUE47"` | Machine-readable plan code |
| `sARatePlanEffDate` | `"2025-05-22"` | Current plan start date |
| `sAStartDate` / `sAEndDate` | `"2025-05-22"` / `""` | Service dates (`sAEndDate` empty = currently active) |

---

## Data Sources

| API | Host | What it provides |
|-----|------|-----------------|
| `GetAllUserDetails` | `www.aps.com` | Token, all premises, rate plans, status |
| `GetEstimatedCharges` | `www.aps.com` | Current-cycle estimated bill (per SA) |
| `getdailyusagecharges` | `mobi.aps.com` | Daily kWh + charges + ToU splits |
| `gethourlyusagecharges` | `mobi.aps.com` | Hourly kWh + charges for one date |
| `getbilledusagehistory` | `mobi.aps.com` | Monthly historical kWh per billing cycle |

---

## Proposed Changes

### Config Flow

#### [MODIFY] [config_flow.py](file:///home/phani/code/antigravity-test/homeassistant-aps/custom_components/aps_energy/config_flow.py)

**Four-step flow:**

**Step 1 – Credentials**
Username + password. On success: authenticate, load all premises.

**Step 2 – Address Selection**
Multi-select addresses using `SelectSelector(mode=MULTIPLE)`. Each option displays:
```
25226 N 131ST DR, PEORIA, AZ 85383   [Active]
18250 N 25 AVE APT 2038, PHOENIX, AZ 85023   [Inactive]
```
Key = `sAID`. Require at least one selection.

**Step 3 – Friendly Names**
For each selected address show a text input pre-populated with the **extracted city name** (parse the city segment from `premiseAddress` — it's the second-to-last comma-delimited word). Example: `"Peoria"`, `"Phoenix"`.

**Uniqueness validation:** Before proceeding, check that no two entered names are identical (case-insensitive). Surface a per-field error `"name_conflict"` if a duplicate is detected.

**Step 4 – History Import**
One question per address (or a global choice if all are being imported together):

> *Do you want to import all available historical data for "[friendly name]"?*
> - `current_only` — Start from today / current billing cycle only
> - `full_history` — Retrieve and store all available historical data in the background

Store this as `import_mode: "current_only" | "full_history"` in the per-address metadata.

**Config entry `data` format (v2):**
```python
{
    CONF_USERNAME: "...",
    CONF_PASSWORD: "...",
    "account_id": "3944770000",
    "monitored_addresses": [
        {
            "sa_id": "3942113360",
            "sp_id": "3941131360",
            "address": "18250 N 25 AVE APT 2038, PHOENIX, AZ 85023",
            "friendly_name": "Phoenix",
            "is_active": False,
            "import_mode": "full_history",
        },
        {
            "sa_id": "3943495177",
            "sp_id": "7838977357",
            "address": "25226 N 131ST DR, PEORIA, AZ 85383",
            "friendly_name": "Peoria",
            "is_active": True,
            "import_mode": "current_only",
        }
    ]
}
```

**Options Flow** — allow users to change friendly names or add/remove addresses later without removing the integration. Friendly name uniqueness validation must run in the options flow too.

---

### API Client

#### [MODIFY] [api.py](file:///home/phani/code/antigravity-test/homeassistant-aps/custom_components/aps_energy/api.py)

**New constants:**
```python
MOBI_BASE_URL       = "https://mobi.aps.com"
HOURLY_USAGE_URL    = f"{MOBI_BASE_URL}/ccb-billing/v1/gethourlyusagecharges"
DAILY_USAGE_URL     = f"{MOBI_BASE_URL}/ccb-billing/v1/getdailyusagecharges"
BILLED_HISTORY_URL  = f"{MOBI_BASE_URL}/customerhistoryservices/v1/getbilledusagehistory"
```

**New/updated methods:**
1. `get_all_service_addresses(user_details) → list[dict]` — parse all premises; extract city from address string.
2. `get_estimated_charges(sa_id, sp_id) → dict` — explicit `sa_id`/`sp_id` args.
3. `get_daily_usage(sa_id, sp_id, start_date, end_date) → dict`
4. `get_hourly_usage(sa_id, sp_id, date) → dict`
5. `get_billed_usage_history(sa_id, start_date, end_date) → dict`

---

### Coordinator

#### [MODIFY] [coordinator.py](file:///home/phani/code/antigravity-test/homeassistant-aps/custom_components/aps_energy/coordinator.py)

**One `APSAddressCoordinator` per monitored address.** Shared `GetAllUserDetails` call cached at the client level (one HTTP request regardless of how many coordinators).

Polling intervals:
- Active address: **30 minutes**
- Inactive address: **24 hours** (historical only)

`_async_update_data()` returns:
```python
{
    "address_details": { ... },    # full sASPDetails for this address
    "estimated_charges": { ... },  # None if inactive
    "daily_usage": { ... },        # current/last billing period
    "billed_history": { ... },     # last 13 months
}
```

---

### Historical Backfill

#### [NEW] `backfill.py`

When `import_mode = "full_history"`, a **one-time background task** runs after the entry is set up:

```python
async def async_backfill_address(hass, client, sa_config):
    """Backfill all available historical statistics for one address."""
```

**How it works using HA's Statistics API:**

```python
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    StatisticData,
    StatisticMetaData,
)
```

1. **Fetch all available billed usage history** via `getbilledusagehistory` (go back as far as the API allows — typically 2–3 years for the active address, full service period for inactive).
2. **Fetch daily usage** for each historical billing cycle via `getdailyusagecharges`.
3. **Construct `StatisticData` list** — one entry per hour (HA statistics are hourly resolution). Daily data is spread across the day's hours as a running sum.
4. **Register external statistics** with `async_add_external_statistics`:
   ```python
   statistic_id = f"aps_energy:{friendly_name.lower()}_daily_usage_kwh"
   meta = StatisticMetaData(
       source="aps_energy",
       statistic_id=statistic_id,
       name=f"APS {friendly_name} Daily Usage",
       unit_of_measurement="kWh",
       has_mean=False,
       has_sum=True,
   )
   stats = [StatisticData(start=period_start, sum=cumulative_kwh)]
   async_add_external_statistics(hass, meta, stats)
   ```
5. **Rate-limit the backfill** — use `asyncio.sleep(0.5)` between billing-cycle fetches to avoid hammering the API. The entire backfill may take 30–120 seconds and runs fully in the background.
6. **Mark complete** — store `backfill_complete: true` in the entry's `options` dict so the backfill doesn't re-run on HA restart.
7. **Re-runnable** — if a user wants to force a re-backfill (e.g., more history became available), clearing `backfill_complete` and reloading the entry re-triggers it.

**What gets backfilled (per address):**
| Statistic | Unit | Details |
|-----------|------|---------|
| `daily_usage_kwh` | kWh | Sum per billing cycle, spread to daily resolution |
| `daily_cost` | $ | Charges per day |
| `on_peak_kwh` | kWh | ToU plans only |
| `off_peak_kwh` | kWh | ToU plans only |
| `bill_total` | $ | One entry per billing cycle end date |

> [!NOTE]
> HA's `async_add_external_statistics` is idempotent — re-running overwrites existing values, so it's safe to call multiple times. Historical statistics appear in the Energy Dashboard and History graphs just like live sensor data.

---

### Sensors

#### [MODIFY] [sensor.py](file:///home/phani/code/antigravity-test/homeassistant-aps/custom_components/aps_energy/sensor.py)

**Full sensor matrix per address** (entity prefix = `sensor.aps_<friendly_name>_`):

| Sensor | Unit | Device Class | Active Only | Notes |
|--------|------|-------------|-------------|-------|
| `service_address` | — | — | No | State = full address string |
| `service_status` | — | — | No | State = `"active"` / `"inactive"` |
| `current_rate_plan` | — | — | No | State = plan name; attrs: code, eff_date, `is_tou` |
| `estimated_charges` | $ | monetary | Yes | Null when inactive |
| `current_balance` | $ | monetary | No | Account-level (same across all address devices) |
| `latest_bill_amount` | $ | monetary | No | Per-address `totalElectricChargeAmount` |
| `daily_usage_kwh` | kWh | energy | No | Most recent complete day total |
| `monthly_usage_kwh` | kWh | energy | No | Current / last billing cycle total |
| `on_peak_usage_kwh` | kWh | energy | No | ToU only; `None` for flat-rate plans |
| `off_peak_usage_kwh` | kWh | energy | No | ToU only |
| `super_off_peak_usage_kwh` | kWh | energy | No | ToU only (if plan has super-off-peak) |
| `on_peak_cost` | $ | monetary | No | ToU only |
| `off_peak_cost` | $ | monetary | No | ToU only |

**Device grouping:**
- Each address → its own HA Device (`identifiers={(DOMAIN, sa_id)}`)
- Account-level sensor (`current_balance`) → parent "APS Account" device
- Backfill statistics share the same `statistic_id` namespace as live sensors

**ToU detection:** `sARatePlancCode` starts with `RTOU` or contains `TOU`. Non-ToU sensors return `None`.

---

### Constants

#### [MODIFY] [const.py](file:///home/phani/code/antigravity-test/homeassistant-aps/custom_components/aps_energy/const.py)

Add:
```python
CONF_MONITORED_ADDRESSES = "monitored_addresses"
CONF_FRIENDLY_NAME = "friendly_name"
CONF_SA_ID = "sa_id"
CONF_SP_ID = "sp_id"
CONF_IMPORT_MODE = "import_mode"
IMPORT_MODE_CURRENT = "current_only"
IMPORT_MODE_FULL = "full_history"

ATTR_RATE_PLAN_CODE     = "rate_plan_code"
ATTR_RATE_PLAN_EFF_DATE = "rate_plan_effective_date"
ATTR_IS_TOU             = "is_time_of_use"
ATTR_ON_PEAK_KWH        = "on_peak_kwh"
ATTR_OFF_PEAK_KWH       = "off_peak_kwh"
ATTR_SUPER_OFF_PEAK_KWH = "super_off_peak_kwh"
ATTR_IS_ACTIVE          = "is_active_service"
ATTR_ADDRESS            = "address"
```

---

### Migration

#### [MODIFY] [__init__.py](file:///home/phani/code/antigravity-test/homeassistant-aps/custom_components/aps_energy/__init__.py)

`async_migrate_entry` (v1 → v2):
- Authenticate with saved credentials
- Look up full premise details for the previously stored `service_address_id`
- Build a `monitored_addresses` list with one entry
- Default `friendly_name` = city extracted from `premiseAddress`
- Default `import_mode = "current_only"` (don't trigger backfill on migration)
- Set `backfill_complete = True` to avoid spurious backfill of already-seen data

---

---

### Phase 2 Bugfixes (Translation & Flow UI)

1. **Fix Missing Translations:**
   - Home Assistant loads UI strings from the `translations/` directory at runtime, not `strings.json`.
   - **Action:** Create `translations/en.json` directly from `strings.json` so Home Assistant correctly localizes all configuration flow labels and instructions.

2. **Improve Looping Config Flow UX:**
   - When a user selects multiple addresses, the looping form shows them one by one. The UI currently doesn't indicate this is a sequence, leading users to believe subsequent addresses were dropped.
   - **Action:** Update `strings.json` and `translations/en.json` to change the `configure_address` step title to `"Configure {address} ({current} of {total})"`.
   - **Action:** Update `config_flow.py` to calculate `current` and `total` based on the `_monitored_addresses` and `_address_queue` arrays, passing them into `description_placeholders`.

---

### Phase 3 — Local Rate Engine (Context Recovered from Previous Workspace)

The original project brief included a pure-Python, zero-API local rate engine to determine real-time Time-of-Use periods. Since the API only returns usage data *after* the fact (e.g. daily totals), a local engine is required to show the *current* rate period and cost in real-time.

1. **Create `rate_engine.py`**:
   - Pure Python, no network calls, highly testable.
   - **Rules** (hardcoded from APS rate schedules):
     - **On-Peak:** 4 PM – 7 PM, Mon–Fri (year-round).
     - **Super Off-Peak:** 10 AM – 3 PM, Mon–Fri (winter only: Nov–Apr).
     - **Off-Peak:** All other hours, all weekends, 14 designated holidays.
   - Calculates the current rate period, current estimated $/kWh, and the time until the next rate transition based on the user's plan.
2. **Add Real-time ToU Sensors**:
   - `sensor.aps_current_rate_period`: Shows On-Peak / Off-Peak / Super Off-Peak.
   - `sensor.aps_current_rate`: Shows the estimated $/kWh right now.
   - `sensor.aps_next_rate_change`: Countdown to next rate transition.
   - `sensor.aps_season`: Summer (May–Oct) / Winter (Nov–Apr).

## Verification Plan

### Automated Checks

```bash
# Verify city extraction from address string
python3 -c "
addr = '25226 N 131ST DR, PEORIA, AZ, 85383'
city = addr.split(',')[-3].strip()  # third from end
print('City:', city)  # → PEORIA
"

# Confirm account JSON structure has all needed fields
cd research
python3 -c "
import json
data = json.load(open('aps_account_details.json'))
details = data['Details']['AccountDetails']['getAccountDetailsResponse']['getAccountDetailsRes']
for p in details['getSASPListByAccountID']['premiseDetailsList']:
    s = p['sASPDetails'][0]
    print(s['sAID'], s['sPID'], s['sAStatus'], s.get('sARatePlanDescription','?'))
"
```

### Manual Verification (Home Assistant)

1. Re-add integration → confirm 4-step flow: Credentials → Address Selection → Friendly Names (pre-filled with city) → History Import
2. Enter duplicate friendly names → confirm error shown before proceeding
3. Select `full_history` for one address → confirm backfill task logs activity; check Energy Dashboard for historical bars
4. Confirm `service_address` and `service_status` sensors appear for both addresses
5. Confirm ToU sensors (`on_peak_usage_kwh` etc.) appear for Peoria (ToU plan) and are absent/unavailable for Phoenix (Fixed plan)
6. Open Options Flow → change a friendly name → confirm sensor entity IDs update
