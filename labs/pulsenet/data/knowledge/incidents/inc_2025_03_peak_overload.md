---
id: INC-2025-03
title: Evening peak overload after a ring segment was left down all day
keywords: past incident, postmortem, evening peak, overload, ring, utilisation, backup wavelength, packet loss, Ramadan
---
# INC-2025-03: evening peak overload after a ring segment was left down all day

**What happened.** A ring segment failed at 10:00. Service was fine in the morning, so the backup wavelength was not
enabled. At 21:00 the protection path reached 108 % and two districts had 3 % packet loss for 50 minutes.

**Lesson.** When a segment is down, forecast the evening peak in the morning and enable the backup wavelength before
utilisation passes 70 %. It takes 2 minutes to enable and costs nothing while idle.
