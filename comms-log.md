---
lab4_comms:
  awareness: 2026-10-12T06:41:00Z
  detection: 2026-10-12T06:39:19Z
  classification: 2026-10-12T06:50:00Z
  nis2:
    early_warning_due: 2026-10-13T06:41:00Z
    notification_due: 2026-10-15T06:41:00Z
    notification_sent: 2026-10-12T09:00:00Z
    final_report_due: 2026-11-12T09:00:00Z
  ksc:
    early_warning_due: 2026-10-13T06:39:19Z
    notification_due: 2026-10-15T06:39:19Z
    notification_sent: 2026-10-12T09:00:00Z
    final_report_due: 2026-11-12T09:00:00Z
  dora:
    initial_due: 2026-10-12T10:50:00Z
    initial_sent: 2026-10-12T10:00:00Z
    intermediate_due: 2026-10-15T10:00:00Z
    intermediate_sent: 2026-10-15T09:00:00Z
    final_due: 2026-11-15T09:00:00Z
  log:
    - {at: 2026-10-12T09:00:00Z, to: the CSIRT, what: NIS2 incident notification and KSC incident notification}
    - {at: 2026-10-12T10:00:00Z, to: the financial supervisor, what: DORA initial notification of a major ICT-related incident}
    - {at: 2026-10-15T09:00:00Z, to: the financial supervisor, what: DORA intermediate report}
---
<!-- ai-generated: 20% - an assistant checked the deadline arithmetic; the instants and why each clock starts there are mine -->

# Communications log: the regulators' clocks

The shop is treated, for this exercise, as an entity in scope for NIS2, the Polish KSC act and DORA, and this incident is taken as significant under the first two and major under the third. Every instant below is UTC. 12 October 2026 is a Monday, so none of these deadlines falls across the weekend relief, and that relief is ignored anyway.

## The three instants you defend

Detection, for KSC, is the detecting alert. ShopCheckoutErrors began firing at 2026-10-12T06:39:19Z. That is the earliest moment the on-call's paging path can be said to have detected the incident, and it is the same instant the postmortem calls detection. KSC counts from "the moment of detection", so the early warning is due at 2026-10-13T06:39:19Z and the incident notification at 2026-10-15T06:39:19Z.

Awareness, for NIS2, is later than that page. At 06:39:19Z the on-call knew a checkout symptom had crossed a threshold, not yet that the incident was significant. By 2026-10-12T06:41:00Z the ticket was acknowledged, the charge error ratio had been read, and it was clear that orders were failing rather than a single noisy span. That is the moment of becoming aware of a significant incident. The early warning is due 24 hours later, at 2026-10-13T06:41:00Z, and the notification 72 hours later, at 2026-10-15T06:41:00Z.

Classification, for DORA, is when the incident was classified as a major ICT-related incident. At 2026-10-12T06:50:00Z the on-call had both identified flags, the fault series was already back at 0, and the customer impact (failed charges, not a full outage) was clear enough to call it major. Classification is 9 minutes after awareness, inside the 24 hour cap, so the initial notification is due at classification plus 4 hours, 2026-10-12T10:50:00Z, which is earlier than awareness plus 24 hours.

## The log

The NIS2 notification and the KSC notification would go out together at 2026-10-12T09:00:00Z, to the CSIRT. That is after awareness and after detection, inside both 72 hour notification deadlines, and well after the early-warning window has opened. One calendar month after that send is 2026-11-12T09:00:00Z, which is the final-report deadline for both NIS2 and KSC.

The DORA initial notification would go to the financial supervisor at 2026-10-12T10:00:00Z, after classification and 50 minutes before the initial deadline. The intermediate report is due 72 hours after that send, at 2026-10-15T10:00:00Z. It would be sent at 2026-10-15T09:00:00Z. One calendar month after that intermediate send is 2026-11-15T09:00:00Z, the DORA final report.

| at (UTC) | to | what | clock |
|---|---|---|---|
| 2026-10-12T09:00:00Z | the CSIRT | NIS2 incident notification and KSC incident notification | NIS2 notification, KSC notification |
| 2026-10-12T10:00:00Z | the financial supervisor | DORA initial notification of a major ICT-related incident | DORA initial |
| 2026-10-15T09:00:00Z | the financial supervisor | DORA intermediate report | DORA intermediate |
