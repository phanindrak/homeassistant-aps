"""Constants for the APS Energy integration."""

DOMAIN = "aps_energy"

# --- Config entry keys ---
CONF_ACCOUNT_ID = "account_id"
CONF_MONITORED_ADDRESSES = "monitored_addresses"
CONF_SA_ID = "sa_id"
CONF_SP_ID = "sp_id"
CONF_FRIENDLY_NAME = "friendly_name"
CONF_ADDRESS = "address"
CONF_IS_ACTIVE = "is_active"
CONF_IMPORT_MODE = "import_mode"

IMPORT_MODE_CURRENT = "current_only"
IMPORT_MODE_FULL = "full_history"

# --- Options / runtime keys ---
CONF_BACKFILL_COMPLETE = "backfill_complete"

# --- Sensor attributes ---
ATTR_LAST_PAYMENT_AMOUNT = "last_payment_amount"
ATTR_LAST_PAYMENT_DATE = "last_payment_date"
ATTR_DUE_DATE = "due_date"
ATTR_RATE_PLAN = "rate_plan"
ATTR_RATE_PLAN_CODE = "rate_plan_code"
ATTR_RATE_PLAN_EFF_DATE = "rate_plan_effective_date"
ATTR_BILLING_DAYS = "billing_days"
ATTR_IS_TOU = "is_time_of_use"
ATTR_IS_ACTIVE = "is_active_service"
ATTR_ADDRESS = "address"
ATTR_ON_PEAK_KWH = "on_peak_kwh"
ATTR_OFF_PEAK_KWH = "off_peak_kwh"
ATTR_SUPER_OFF_PEAK_KWH = "super_off_peak_kwh"
ATTR_ON_PEAK_COST = "on_peak_cost"
ATTR_OFF_PEAK_COST = "off_peak_cost"
ATTR_SUPER_OFF_PEAK_COST = "super_off_peak_cost"
ATTR_SA_STATUS = "sa_status"
ATTR_PLAN_EFF_DATE = "plan_effective_date"
