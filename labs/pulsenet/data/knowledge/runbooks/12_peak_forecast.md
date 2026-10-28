---
id: RB-12
title: Forecasting the evening peak
keywords: forecast, prediction, evening peak, 21:00, traffic profile, capacity planning, what will happen tonight, utilisation later
---
# Forecasting the evening peak

City traffic peaks around **21:00**. In the morning traffic is about 60 % of the peak. `forecast` scales today's
readings with the 30-day hourly profile.

- A link at 72 % at 09:30 will be above 100 % at 21:00 unless something changes: packets will be dropped for
  every district on that path.
- Fix capacity problems in the morning; do not wait for the peak.
- Batteries and temperatures are forecast by their trend, not by the traffic profile.
