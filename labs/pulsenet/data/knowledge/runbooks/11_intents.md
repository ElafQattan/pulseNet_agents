---
id: RB-11
title: The operator's intents for the city network
keywords: intent, goals, targets, SLA, availability, protection, utilisation, temperature, battery, compliance
---
# The operator's intents for the city network

Intents are goals, not commands: PulseNet decides how to meet them and the engineer approves.

| Intent | Goal | Typical fix when violated |
|---|---|---|
| INT-1 | 5G availability at least 99.5 % in every district | restore the site (RB-02, RB-05), protect neighbours (RB-03) |
| INT-2 | two independent paths per district; no backbone link above 70 % at the evening peak | backup wavelength (RB-01) |
| INT-3 | edge data center inlet at or below 27 C | migrate workloads, fix cooling (RB-06) |
| INT-4 | no cell site runs out of battery | energy saving, generator (RB-04) |
| INT-5 | critical services always protected | restore protection (RB-01), inform city-services (RB-07) |
