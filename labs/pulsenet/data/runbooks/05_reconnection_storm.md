---
id: RB-05
title: Reconnection storm after an outage
keywords: connection storm, too many connections, platform overloaded, broker cpu, power restored, retry timer, back-off, jitter
---
# Reconnection storm after an outage

## Symptoms
- `CENTER-MQTT` reports connect attempts per minute far above its baseline (more than 10×) and high CPU.
- A group of devices shows `degraded` with hundreds of reconnects per hour.
- The logs show the devices retrying **together**, at the same fixed interval (`reconnect_strategy=fixed_5s`),
  usually right after a power or network outage in one district.

## Why it happens
Devices that retry on a fixed timer stay synchronised: they all lose the connection together, retry together,
overload the broker together, and time out together. The broker never recovers while they keep retrying. GSMA
TS.34 describes this failure and its fix (see GSMA-TS34: requirement TS.34_4.0_REQ_003 and Annex A.1).

## Fix
- `update_config` on the affected devices with setting `reconnect_strategy`, value `exponential_jitter`: each device
  waits a random, growing delay before retrying, so the attempts spread out and the broker recovers within minutes.
  One call can take several device IDs. **Needs the technician's approval** (RB-08).
- **Do not reboot the broker.** A broker restart disconnects every client in the city at once and makes the storm
  worse.
- Do not reboot the devices: they come back with the same fixed timer.
- Priority `high` while the broker is degraded, because every district depends on it.
