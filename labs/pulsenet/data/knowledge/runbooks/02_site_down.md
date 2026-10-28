---
id: RB-02
title: Cell site down
keywords: site down, out of service, no coverage, backhaul lost, power, alarm, cell outage, neighbour sites
---
# Cell site down

## Find out why
`trace_path` from the site to the core. The first hop that is down is the cause.
| First hop down | Cause | Action |
|---|---|---|
| the site's fiber spur or microwave link | backhaul lost | nothing to do remotely; ticket team `fiber`, and protect the neighbours |
| none, but the site reports `power: battery` with 0 % | power | ticket team `power`, see RB-04 |
| none, and the site itself is down | equipment | `restart_asset` on the site once; if it fails, ticket team `ran` |

## Protect the neighbours
Users of a site that is down move to the neighbouring sites. Check their `prb_dl_pct`; above 90 % enable their
second carrier (RB-03).
