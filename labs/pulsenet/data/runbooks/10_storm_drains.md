---
id: RB-10
title: Storm drains not emptying after rain
keywords: storm drain blocked, drain full, clogged drain, water on the road, ponding, run-off, rain
---
# Storm drains not emptying after rain

Storm-drain level sensors (`…-DRAIN-…`) report how full the inlet is (`fill_pct`).

## Normal behaviour
During heavy rain drains fill to 50–90 %. After the rain stops they should **fall below 30 % within about three
hours**. Compare with the weather station (`CENTER-WEATHER`: `rain_stopped`) and with the other drains nearby.

## Blocked drain
- One drain stays above 70 % (trend `steady`) for more than two hours after the rain stopped, while its neighbours
  are falling: the inlet or the pipe is blocked, usually by sand, leaves or rubbish carried by the run-off.
- This is a physical problem. Rebooting the sensor or changing its configuration does not help.
- `open_ticket`, team `drainage`, priority `high` (water may pond on the road and enter buildings if it rains
  again). Include the fill level, the time the rain stopped, and the neighbours' levels as evidence.

## Faulty sensor instead
If the fill level jumps between values in a way water cannot (e.g. 10 % → 90 % → 10 % within minutes), suspect the
sensor itself: `open_ticket`, team `maintenance`, priority `normal`.
