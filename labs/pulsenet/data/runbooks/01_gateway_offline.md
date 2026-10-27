---
id: RB-01
title: LoRaWAN gateway offline
keywords: gateway down, whole district offline, devices not reporting, no data on the dashboard, restart gateway
---
# LoRaWAN gateway offline

## Symptoms
- Every LoRaWAN device behind one gateway (streetlights, parking sensors) shows `offline` with the **same**
  `last_seen` time.
- The gateway itself is `offline` and the broker log reports the gateway and its devices lost together.
- Devices in other districts are normal. One device offline on its own is not a gateway fault: see RB-03 or RB-04.

## Diagnosis
1. `get_device_status` on the gateway: status, `last_seen`, connected vs expected devices.
2. `search_logs` for the gateway ID around `last_seen`. Common causes:
   - `packet forwarder killed: out of memory`: software fault, a reboot normally clears it.
   - `mains power lost` with no restore: power fault, a reboot will not help, send a field team.
   - `backhaul down` or `fiber link down`: network fault, open a ticket for the network team.

## Fix
- Software fault: `reboot_device` on the gateway. **Needs the technician's approval** (RB-08). A reboot takes about
  3 minutes and every device behind the gateway stays offline during that time.
- Never reboot more than one gateway in one request. Rebooting several at once can leave a whole part of the city
  without telemetry.
- If the gateway is not back within 10 minutes, or the cause is power or backhaul: `open_ticket` with team
  `network`, priority `high` (a whole district without telemetry, RB-08).
