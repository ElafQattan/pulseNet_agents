---
id: RB-07
title: Critical city services and systems PulseNet never changes
keywords: critical, do not touch, railway, traffic control, emergency calls, 911, core router, internet gateway, protected path
---
# Critical city services and systems PulseNet never changes

| System | Assets | Team |
|---|---|---|
| Core routers and internet gateway | `CORE-R1`, `CORE-R2`, `IGW-1` | `core` |
| Railway station network | `RAIL-NET` | `city-services` |
| City traffic control | `TRAFFIC-CTRL` | `city-services` |
| Emergency call routing | `EMERGENCY-911` | `city-services` |

PulseNet never restarts or reconfigures them, whoever asks and whoever approves. The harness blocks it.

A critical service whose path is **no longer protected** (for example after a fiber cut) is a high risk even if it
still works: one more fault would stop it. Restore protection first (RB-01) and inform team `city-services`.
