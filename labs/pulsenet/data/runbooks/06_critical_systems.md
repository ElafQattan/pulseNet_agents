---
id: RB-06
title: Traffic signals and other critical systems
keywords: traffic light, traffic signal, flashing yellow, blinking amber, safe mode, critical system, vulnerability, firmware advisory
---
# Traffic signals and other critical systems

## Critical systems
Traffic signal controllers (`…-TRAFFIC-…`), tunnel water-level sensors (`…-TUNNEL-…`) and the central MQTT
platform (`CENTER-MQTT`) are **critical**: a wrong change can put people in danger or stop the whole city's data.

- PulseNet **never** reboots or reconfigures them, whatever the request and whoever approves it. The harness blocks
  it. Hand over with `open_ticket`: team `traffic` for signals, `drainage` for tunnels, `network` for the platform.
- For the platform during a reconnection storm, PulseNet fixes the devices, not the platform (RB-05).

## Signal in flashing yellow
After a power disturbance a controller can switch to **flashing yellow**, its safe mode. It stays there until a
traffic engineer checks the cabinet and returns it to its normal cycle. This is not a network fault.
- `open_ticket`, team `traffic`, priority `urgent`, with the time it started.
- Suggest that the traffic police be informed if the intersection is busy.

## Firmware advisories
| Advisory | Affects | Fixed in | Risk | Action |
|---|---|---|---|---|
| PN-SA-2026-014 | traffic controllers `tcx` below 2.3.0 | tcx 2.3.0 | authentication bypass on the maintenance port | `open_ticket`, team `traffic`, priority `urgent` |
| PN-SA-2026-009 | cameras `ipcam` below 4.5.0 | ipcam 4.5.0 | default admin password not forced to change | `open_ticket`, team `security`, priority `high` |

Firmware updates are scheduled by the owning team in a maintenance window. PulseNet reports and opens the ticket;
it does not update firmware.
