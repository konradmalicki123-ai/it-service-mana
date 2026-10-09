---
svcdesk_decisions:
  C1: wallclock
  C2: immutable
  C3: vip
---
<!-- ai-generated: 80% - assistant drafted the prose from the three resolutions already chosen in specs/spec.md; the choices themselves were fixed before this text -->

# Decisions

## C1 - SLA clock for P1

**Decision:** P1 acknowledgement and resolution both run on the wall clock. P2, P3 and P4 stay on the business-hours clock, Monday to Friday 08:00-16:00 Europe/Warsaw.

**Rejected alternative:** Putting P1 on the business-hours clock as well, which is the other admissible value, C1 = business. That reading pauses a Friday-evening P1 until Monday 08:00.

**Reason:** R-13 says every SLA clock pauses outside business hours. R-14 says a P1 raised on Friday evening is late fifteen minutes later, not on Monday morning. Both sentences cannot be true of P1 at once. An organisation-wide outage does not pause because the office closed, so the wall clock is the reading that matches the sentence the desk would actually say. The business-hours pause remains for P2 to P4, which is where R-13 still has a meaning that does not collide with R-14. The published vector T3 is the witness: under this choice the Friday 17:00 local P1 is due at 15:15Z and 19:00Z the same day.

**Service owner:** The service owner of the service desk. They own the promise about how fast a stopped organisation is answered, and they are the role who would have to explain a Monday breach on a Friday-night P1.

**Customer outcome:** A reporter who raises a P1 on Friday evening gets an acknowledgement target fifteen minutes later the same evening, and a resolution target four hours later, including through the night and the weekend. The people affected by an organisation-wide outage are not told to wait until Monday morning.

## C2 - Closed tickets and reopening

**Decision:** A closed ticket cannot be reopened. Reopen is accepted only from resolved, and only while now is at most seven days after resolved_at. The ticket returns to in_progress and the original resolution target does not move.

**Rejected alternative:** Allowing reopen from closed within seven days of closed_at, which is C2 = reopen. That keeps R-10's second clause and gives up R-09's immutability.

**Reason:** R-09 says a closed ticket is immutable and that further work is a new ticket linked with related_to. R-10 also says a reporter may reopen a resolved or closed ticket within seven days. Closure is the moment the reporter has confirmed the fix, so rewriting that record would erase the confirmation the Monday report relies on. The seven-day reopen stays available while the ticket is only resolved, which is before that confirmation. After close, the path R-09 names is the one this service implements: a new ticket, not an edited one.

**Service owner:** The service owner of the service desk. Closure is their audit point. They are the role that signs off the policy that a confirmed ticket is not edited in place.

**Customer outcome:** A reporter who disagrees before confirming can still reopen a resolved ticket for seven days and send it back to in_progress, without resetting the resolution target. A reporter who already confirmed, and then finds the fix failed, opens a new ticket that points at the closed one. They do one extra step. In return the original closure time stays trustworthy for anyone reading the record later.

## C3 - VIP reporters and the priority matrix

**Decision:** The matrix runs first. A VIP reporter whose matrix result is P3 or P4 is then raised to P2. A VIP who is already P1 or P2 is left unchanged. A priority field in the request body is ignored for everyone.

**Rejected alternative:** Letting the matrix stand alone and storing reporter.vip without using it, which is C3 = matrix. A cosmetic VIP issue would then be P4.

**Reason:** R-05 says priority comes from the matrix and from nothing else. R-06 says a VIP ticket is never lower than P2, whatever the matrix says. A client cannot type a priority: that field is still discarded, so R-05's ban on a requested priority holds. The vip flag is data about the reporter, the same kind of input as impact, and R-06 is explicit that an executive issue must be visible to the desk immediately. Raising only P3 and P4 to P2 is the smallest change that makes R-06 true. Check 2.46 is the witness, and 2.47 keeps a VIP P1 at P1.

**Service owner:** The service owner of the service desk. Queue order is their policy, because they are accountable for which ticket the agents see first when they start the day.

**Customer outcome:** A VIP whose impact and urgency would have been P4 is queued as P2, so the acknowledgement target is one business hour rather than eight. A non-VIP P2 is not pushed down by a VIP who was already P2, and a VIP P1 stays P1. The cost sits with non-VIP P3 work, which can wait behind a cosmetic VIP issue that this rule lifted.
