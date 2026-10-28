---
id: RB-05
title: Sleeping cell
keywords: sleeping cell, silent failure, zero traffic, no users, no alarm, sector, KPI anomaly, neighbour overload
---
# Sleeping cell

A sleeping cell is a sector that looks healthy (no alarm) but carries **no users**. Phones near it fall back to
neighbouring sites, which become busier than usual. It often follows a software restart.

## Detect
- One sector with 0 users during the day while the other sectors of the same site carry hundreds.
- A neighbouring site busier than its usual level for the hour.
- The logs often show a baseband or software restart just before the traffic stopped.

## Fix
- `restart_asset` on the site: the sector is re-initialised and picks up users within about two minutes.
  **Needs the engineer's approval.** Do this outside the evening peak if possible.
- If the sector is still empty after the restart, `open_ticket`, team `ran`, priority `high`.
