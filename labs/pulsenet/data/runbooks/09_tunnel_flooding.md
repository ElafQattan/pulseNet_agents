---
id: RB-09
title: Underpass flooding and drainage pumps
keywords: tunnel flooded, water in the underpass, flooding, pump stopped, pump trip, water level, close the tunnel, rain
---
# Underpass flooding and drainage pumps

Each underpass has a water-level sensor (`…-TUNNEL-…`) at its lowest point and two drainage pumps (`…-PUMP-…`).
One pump alone cannot keep up with heavy rain run-off.

## Levels
| Water level | Meaning | Action |
|---|---|---|
| below 20 cm | normal | none |
| 20–39 cm | warning | check both pumps |
| 40 cm or more | **dangerous for cars** | the tunnel must be closed: `open_ticket`, team `traffic`, priority `urgent` (close the tunnel) **and** fix the pumps |

## Pump stopped
1. `get_device_status` on both pumps: `running`, `trip_reason`, `trips_last_24h`.
2. `trip_reason: undervoltage` with **one** trip in 24 h: the pump stopped because of a power dip (common in storms)
   and does not restart by itself. A remote reset is safe: `reboot_device` on the pump controller.
   **Needs the technician's approval** (RB-08).
3. `trip_reason: overcurrent` or `motor_overheat`, or more than one trip in 24 h: something is blocking the pump or
   the motor is damaged. **Do not reset remotely.** `open_ticket`, team `drainage`, priority `urgent`.
4. After a reset, check the tunnel sensor: the trend should change to `falling` within minutes.

Always report the water level and its trend first: it tells the technician how urgent the case is.
