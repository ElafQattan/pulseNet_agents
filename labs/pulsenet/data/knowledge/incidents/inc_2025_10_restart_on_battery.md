---
id: INC-2025-10
title: Restarting a site on battery made the outage worse
keywords: past incident, postmortem, restart, battery, power, site down, mistake
---
# INC-2025-10: restarting a site on battery made the outage worse

**What happened.** A site on battery showed degraded throughput. An engineer restarted it; the restart peak drained
the weak battery and the site did not come back until the power returned.

**Lesson.** Never restart a site that runs on battery. Use energy saving and send a generator.
