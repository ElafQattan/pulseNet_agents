---
id: RB-10
title: How PulseNet works an incident (closed loop)
keywords: closed loop, method, root cause, correlation, many alarms one cause, monitor analyse plan execute verify, autonomy level
---
# How PulseNet works an incident (closed loop)

PulseNet follows the closed-loop pattern used in autonomous network research (monitor, analyse, decide, execute,
verify), at **intelligence level L3** of ITU-T Y.3173: the system collects data and executes; analysis and decision
are shared with the engineer; the engineer sets the goals (the intents).

1. **Monitor:** `get_overview` (alarms by severity) and `check_intents` (which goals are violated).
2. **Analyse:** many alarms often have one cause. Correlate by **time** (alarms in the same minute), **place**
   (same duct, same power feeder) and **path** (`trace_path`). Name the root cause, not the symptoms.
3. **Decide:** search the knowledge base for the runbook and past incidents; `forecast` the next peak; check the
   blast radius (`impact_of`) of any change.
4. **Execute:** propose the change; it runs only after the engineer approves.
5. **Verify:** read the asset again and `check_intents`. Report what is fixed and what is still open.
