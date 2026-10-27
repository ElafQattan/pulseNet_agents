---
id: RB-11
title: Streetlight power cabinet tripped
keywords: short circuit, electrical fault, earth leakage, ground fault, breaker tripped, power cabinet, lights off, water in cabinet, rain
---
# Streetlight power cabinet tripped

Streetlights are powered from roadside cabinets (`…-CABINET-…`). Each light's `cabinet_id` says which one.

## Symptoms
- Several lights on the same road go `offline` at the **same** time, while their gateway is online and other lights
  on the same gateway are fine. (If the gateway is offline too, see RB-01 instead.)
- Their cabinet shows `breaker: open`.

## Earth leakage trip (water in the cabinet)
- `trip_reason: earth_leakage` means current was leaking to ground, almost always because rain water reached a
  cable joint or the cabinet. With standing water this is an **electric shock risk** for people nearby.
- **Never reset it remotely.** Closing the breaker on a wet fault can electrify the pole or the cabinet. The tool
  refuses it.
- `open_ticket`, team `electrical`, priority `urgent`, with the trip time and the leakage value. The electricians
  dry and test the circuit on site before closing the breaker.

## Overload trip
- `trip_reason: overload` with no water around and low earth leakage: a remote reset with approval is allowed
  once. If it trips again, `open_ticket`, team `electrical`, priority `high`.
