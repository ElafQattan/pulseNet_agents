---
id: RB-01
title: Fiber cut on the backbone ring
keywords: fiber cut, loss of signal, LOS, ring, backbone, protection switch, single-homed, roadworks, excavation, duct, OTDR
---
# Fiber cut on the backbone ring

The five districts are connected by a 100G fiber ring. When one segment is cut, the ring protection switch sends
the traffic the other way round within 50 ms. Service survives, but the network is now **unprotected** (a second
cut would isolate districts) and the remaining segments carry more traffic.

## Confirm
1. `get_asset` on the segment: `loss_of_signal` at both ends and the OTDR distance to the fault.
2. `search_logs` around the time: roadworks or excavation notices near the same duct confirm a physical cut.
3. Look for **shared-risk links**: anything else in the same duct (spurs to cell sites) is cut at the same moment.

## Restore protection and capacity
1. `forecast` the remaining segments at the evening peak (21:00). If any is above 70 % (intent INT-2), enable the
   leased backup wavelength: `update_config` on `BACKUP-WAVE-1`, setting `state`, value `enabled`. It carries the
   affected district over a different duct and gives it a second path again. **Needs the engineer's approval.**
2. `open_ticket`, team `fiber`, priority `urgent`: duct, distance to fault, the roadworks location.
3. Do not touch the core routers or the aggregation routers: the protection already worked.
