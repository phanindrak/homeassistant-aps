# Future Release To-Do List

## Research
- [ ] Optimization of backfill for inactive addresses.
  - [ ] Investigate if there is a way to find the last date the address was active to use as a start point instead of the current date.
- [ ] Plan-specific rate lookups (per kWh).
  - [ ] Research if the API provides rates (per kWH) for the plan, including on-peak, off-peak, and super off-peak variations.

## New Sensors & Features
- [ ] Billing Period Tracking.
  - [ ] Sensor for number of days into the current billing period.
  - [ ] Sensor for estimated number of days until the next billing period.
- [ ] Billing History.
  - [ ] Fetch and display billing and payment history.
- [ ] Advanced Estimated Billing Detail.
  - [ ] Capture and expose additional data elements from `GetEstimatedCharges`:
    - Energy Usage Cost
    - Energy Cost
    - On-Peak Energy Cost
    - Off-Peak Energy Cost
    - Super Off-Peak Energy Cost
    - Adjustors
    - Taxes, Fees and Other Charges
    - Basic Service and Other Charges
    - Taxes and Fees
    - Days in Billing Period
    - Average Daily Cost
    - Estimated Total Cost
