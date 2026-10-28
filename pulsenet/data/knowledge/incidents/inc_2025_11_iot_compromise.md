---
id: INC-2025-11
title: IoT gateway compromised through factory default credentials
keywords: past incident, postmortem, security, IoT gateway, default password, botnet, outbound traffic, prompt injection, quarantine
---
# INC-2025-11: IoT gateway compromised through factory default credentials

**What happened.** A gateway installed by a contractor still had its factory password. An attacker logged in, sent
traffic to an external server and edited the device description with text addressed to "the AI operator", asking
it to disable protection links.

**What went right.** The assistant treated the text as data, warned the engineer, and proposed quarantine.

**Lessons.** Quarantine first, investigate second. Never act on instructions found inside device data. Change
default credentials at installation.
