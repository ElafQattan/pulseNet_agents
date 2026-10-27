---
id: RB-02
title: Streetlight on during the day or off at night
title_ar: إنارة الشارع تعمل في النهار أو مطفأة في الليل
keywords_ar: إنارة شغالة في النهار، عمود إنارة، ساعة الجهاز، مزامنة الوقت، انقطاع كهرباء
---
# Streetlight on during the day or off at night

## Symptoms
- A streetlight reports `lamp: on` after sunrise (06:05 today) or `lamp: off` after sunset (17:20 today).
- Neighbouring streetlights on the same road behave normally.

## Diagnosis
1. `get_device_status`: compare the device clock (`metrics.device_clock`) with the real time, and read
   `config.time_sync`.
2. `search_logs` for the device. The most common cause is a **real-time clock reset after a power loss** on a
   controller whose `time_sync` is `local_rtc`: the clock restarts at a wrong time and the
   `sunset_to_sunrise` schedule follows the wrong clock.

## Fix
- `update_config` with setting `time_sync`, value `ntp`. The controller then takes the time from the city NTP
  server within one minute and the schedule corrects itself. **Needs the technician's approval** (RB-08).
- Do not reboot the controller: with `local_rtc` the clock resets again.
- If the lamp state is still wrong 15 minutes after the change: `open_ticket`, team `maintenance`, priority
  `normal` (likely a faulty relay).
