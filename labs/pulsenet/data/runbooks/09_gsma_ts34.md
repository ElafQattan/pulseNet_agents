---
id: GSMA-TS34
title: GSMA TS.34 IoT Device Connection Efficiency Guidelines (excerpts)
title_ar: إرشادات GSMA TS.34 لكفاءة اتصال أجهزة إنترنت الأشياء (مقتطفات)
keywords_ar: GSMA، إرشادات رسمية، توقيت عشوائي، تجنب الاتصال المتزامن، عاصفة إشارات، back-off
source: GSMA TS.34 v12.0 (5 May 2025), Copyright © 2025 GSM Association, via huggingface.co/datasets/GSMA/gsma
---
# GSMA TS.34 IoT Device Connection Efficiency Guidelines (excerpts)

Short quotations from the official GSMA guideline, kept word for word, for citation. Full document: GSMA TS.34
v12.0, 5 May 2025.

## Why it matters (section 1.1, Problem Statement)
> "When deployed on a mass scale such devices can cause network signalling traffic to increase to a level which
> impacts network services for all users of the mobile network. In the worst cases the mass deployment of such IoT
> Devices can disable a mobile network completely."

> "IoT Devices overusing the mobile network can affect not only the devices causing the incident but also other
> devices on the same IoT Service Platform or those devices of other End Customers."

## Randomised reconnection (TS.34_4.0_REQ_003)
> "For the regular activation of IoT Devices, for regular application messaging, or even after a service
> interruption, the IoT Device Application SHOULD employ a randomized timer to trigger network connection requests.
> Note: It is important to avoid that devices in close proximity to each other communicate simultaneously because
> of a system-wide failure situation (e.g., regional power outage) or for their initial activation […]."

## Platforms must not synchronise devices (TS.34_6.0_REQ_001)
> "If permissible for the IoT Service, any IoT Service Platform which communicates to multiple IoT Devices SHALL
> avoid synchronized behaviour and employ a randomized pattern for accessing the IoT Devices within the IoT Service
> Platform's domain."

## Spreading activity in time (Annex, Figure 8)
> "IoT Device Application developers are recommended to avoid, as much as possible, using exact times for an IoT
> Device Application's network activities, and to use randomisation design techniques to spread network activity
> timings across different IoT Devices."

## A real incident (Annex A.1, Use of Unintelligent Error Handling Mechanisms)
About 375,000 IoT devices lost their server, all fell back to the mobile network and ended up rebooting their modems
"every minute or so". The signalling load overloaded the operator's core network, roaming destinations had to be
shut down, and recovery took about 48 hours:
> "If the devices had implemented an intelligent 'back-off' mechanism […] when loss of connectivity to the server
> had been detected then this problem would not have occurred."
