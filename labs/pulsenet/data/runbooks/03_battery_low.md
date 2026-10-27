---
id: RB-03
title: Low battery on battery-powered sensors
keywords: battery low, flat battery, replace battery, parking sensor, water meter, late reports
---
# Low battery on battery-powered sensors

Parking sensors and water meters run on batteries (`battery_pct`). Streetlights, cameras, gateways and traffic
controllers are mains-powered and have no battery value.

## Thresholds
| battery_pct | Action |
|---|---|
| 20 % or more | nothing |
| 10–19 % | plan a replacement in the next routine round |
| 5–9 % | `open_ticket`, team `maintenance`, priority `normal` |
| below 5 % | `open_ticket`, team `maintenance`, priority `high` (the sensor will stop within days) |

Below 5 % a sensor enters low-power mode and reports every 30 minutes instead of every 5, so its data looks late:
this is expected and not a network fault.

## Do not
- Do not reboot a battery-powered sensor to "fix" late reports: a reboot rejoins the network and drains the
  battery faster.
- Do not change `report_interval_s` to save battery without a ticket: the parking app depends on it.

Sensors in disabled-access bays are high priority at any battery level below 10 %.
