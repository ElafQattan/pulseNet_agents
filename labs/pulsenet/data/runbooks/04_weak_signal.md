---
id: RB-04
title: Weak radio signal (LoRaWAN and NB-IoT)
title_ar: إشارة لاسلكية ضعيفة (LoRaWAN و NB-IoT)
keywords_ar: إشارة ضعيفة، قراءات متأخرة، إعادة إرسال، عداد مياه، تغطية، هوائي
---
# Weak radio signal (LoRaWAN and NB-IoT)

## Symptoms
- Late or missing readings from one device while its neighbours are fine.
- Many retries or retransmissions in the logs (`RRC connection setup failed`, `retry`).

## Thresholds
| Connectivity | Healthy | Weak: act |
|---|---|---|
| LoRaWAN | RSSI above −115 dBm and SNR above −7 dB | RSSI −115 dBm or below, or SNR −7 dB or below |
| NB-IoT | RSRP above −115 dBm, coverage class CE0 or CE1 | RSRP −120 dBm or below, or coverage class CE2 |

Coverage class CE2 means the device repeats every transmission many times to be heard: it works, but slowly and
at a high battery cost.

## Fix
- A weak signal is a physical problem. **Rebooting or changing the configuration does not help.**
- `open_ticket`, team `maintenance`, priority `normal`, asking for an external antenna or for the device to be
  moved (underground valve chambers are a common cause for water meters).
- Priority `high` if the device has not reported for more than 12 hours.
