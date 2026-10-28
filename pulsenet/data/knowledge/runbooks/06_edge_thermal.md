---
id: RB-06
title: Edge data center overheating
keywords: data center, temperature, overheating, cooling failure, CRAC, inlet temperature, thermal, migrate workloads, servers
---
# Edge data center overheating

Inlet temperature should stay at or below **27 C** (intent INT-3). Servers shut themselves down at **35 C**.

1. `get_asset`: inlet temperature, its trend and the cooling units.
2. With one cooling unit down and the temperature rising, **move the workloads** to the other edge data center
   before it reaches 33 C: `update_config` on the hot data center, setting `migrate_to`, value the target data
   center (`EDGE-DC-QUBA` or `EDGE-DC-UYUN`). Check the target has free capacity. Live migration takes about 10
   minutes and the heat load drops by about 70 %. **Needs the engineer's approval.**
3. `open_ticket`, team `facilities`, priority `urgent`, for the cooling unit.
