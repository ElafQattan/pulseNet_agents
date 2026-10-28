---
id: RB-03
title: Cell site congestion
keywords: congestion, slow mobile data, PRB, RRC reject, capacity, second carrier, overloaded site, too many users
---
# Cell site congestion

- `prb_dl_pct` above **90 %** or `rrc_reject_pct` above **2 %** means users are refused or very slow.
- Enable the second carrier: `update_config` on the site, setting `second_carrier`, value `enabled`. It adds
  about 40 % capacity within two minutes. **Needs the engineer's approval.**
- If the congestion comes from a neighbour site being down, also fix or ticket that root cause (RB-02).
