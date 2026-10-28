---
id: INC-2024-12
title: Sleeping cell unnoticed for nine hours
keywords: past incident, postmortem, sleeping cell, zero users, no alarm, watchdog restart, neighbour congestion
---
# INC-2024-12: sleeping cell unnoticed for nine hours

**What happened.** After a watchdog restart a sector came back "in service" but served nobody. There was no alarm.
Customers complained about slow data near the neighbouring site, which was overloaded.

**Lesson.** A sector with zero users in the daytime is a sleeping cell even without an alarm. A site restart fixed
it in two minutes. A KPI rule now flags it.
