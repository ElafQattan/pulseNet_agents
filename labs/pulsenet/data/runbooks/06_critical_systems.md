---
id: RB-06
title: Critical systems and firmware advisories
title_ar: الأنظمة الحرجة وتنبيهات البرامج الثابتة
keywords_ar: إشارات المرور، نظام حرج، ثغرة، تحديث البرنامج الثابت، firmware، تنبيه أمني
---
# Critical systems and firmware advisories

## Critical systems
Traffic signal controllers (`TL-…`) and the MQTT broker (`BROKER-01`) are **critical**: a wrong change can put
people in danger or stop the whole city's telemetry.

- PulseNet **never** reboots or reconfigures a traffic controller, whatever the request and whoever approves it.
  The harness blocks it. Hand over to the traffic operations team with `open_ticket`, team `traffic`.
- Changes to the broker are made by the network team, not by PulseNet (see RB-05 for what PulseNet does during a
  reconnection storm).

## Firmware advisories
| Advisory | Affects | Fixed in | Risk | Action |
|---|---|---|---|---|
| PN-SA-2026-014 | traffic controllers `tcx` below 2.3.0 | tcx 2.3.0 | authentication bypass on the maintenance port | `open_ticket`, team `traffic`, priority `urgent` |
| PN-SA-2026-009 | cameras `ipcam` below 4.5.0 | ipcam 4.5.0 | default admin password not forced to change | `open_ticket`, team `security`, priority `high` |

Firmware updates are scheduled by the owning team in a maintenance window. PulseNet reports and opens the ticket;
it does not update firmware.
