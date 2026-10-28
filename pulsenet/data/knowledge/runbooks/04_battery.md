---
id: RB-04
title: Cell site on battery after a power cut
keywords: power cut, mains lost, battery, backup power, generator, energy saving, minutes left, utility outage
---
# Cell site on battery after a power cut

Each site has batteries for about three hours at normal load. The time left depends on the load.

1. `get_asset`: `battery_pct` and `battery_minutes_left`. Compare with the expected repair time of the utility.
2. If less than 120 minutes are left, enable **energy saving**: `update_config`, setting `energy_saving`, value
   `enabled`. The site switches off its capacity layer and keeps coverage; the battery lasts about three times
   longer. Users notice lower peak speeds, not loss of service. **Needs the engineer's approval.**
3. `open_ticket`, team `power`, priority `urgent` if less than 90 minutes are left (a mobile generator takes about
   60 minutes to arrive), otherwise `high`.
4. Never restart a site that runs on battery: the restart draws extra power.
