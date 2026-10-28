---
id: INC-2025-08
title: Edge data center cooling failure and late migration
keywords: past incident, postmortem, data center, cooling failure, CRAC, temperature, migration, shutdown
---
# INC-2025-08: edge data center cooling failure and late migration

**What happened.** One of two cooling units failed. The team waited for the technician; at 34 C the migration
started, and three servers shut down at 35 C before it finished.

**Lesson.** Start migrating at about 30-31 C, not 34 C. Migration takes about 10 minutes and the temperature rises
about 0.6 C every 10 minutes with one unit down.
