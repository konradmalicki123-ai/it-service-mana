<!-- ai-generated: 55% - Claude drafted this from REQUIREMENTS.md and API.md, the author chose the
     three conflict resolutions and rewrote the reasoning sections -->
# svcdesk - specification

Source documents: `REQUIREMENTS.md` (R-01..R-25, what the desk wants), `API.md` (the exact HTTP
contract, the SLA vectors, the compose contract), `CHECKS.md` (the published conformance checks).
Where REQUIREMENTS.md and API.md differ in precision, API.md is the contract that is enforced;
this document is the author's reading of both, written and pushed before any file under `src/`.

## 1. Purpose

A small HTTP ticketing service for an internal service desk of about 400 people across three
offices (R-purpose). It must accept tickets, compute their priority deterministically, drive them
through a fixed state machine, keep two kinds of SLA clock, and report breach/pause state on
demand, so that a Monday-morning report can be produced with one `GET /tickets/{id}/sla` call per
ticket (R-15).

## 2. Interface

`GET /health` for liveness; `POST /tickets`, `GET /tickets` (with `state=` and `priority=` exact
filters), `GET /tickets/{id}` and `GET /tickets/{id}/sla` for reading; `POST /tickets/{id}/ack`,
`/start`, `/resolve`, `/close`, `/reopen` for the five transitions. Every body is JSON. Every
timestamp is an RFC 3339 instant, reported in UTC with a `Z` suffix (R-17). Every ticket id is
opaque, unique and server-assigned (R-18, a UUID here). Server-owned fields sent by a client
(`id`, `priority`, `state`, the four event timestamps, `sla`) and unknown fields are ignored, never
rejected (R-20).

## 3. Priority

Priority comes only from the impact/urgency matrix (R-04, R-05); a client can never request one.
Impact 1..3 (organisation/team/person), urgency 1..3 (stopped/degraded/cosmetic). See the matrix in
API.md section 3. VIP reporters are handled per decision C3 below.

## 4. State machine and reopening

`new -> acknowledged -> in_progress -> resolved -> closed`, one endpoint per transition, each
recording its own timestamp (R-07). Any other transition is `409` (R-08); an action on an unknown
id is `404`. A closed ticket is immutable in the sense that no further transition changes it except
possibly `reopen`, which is decision C2 below; further work on a closed issue normally means a new
ticket referencing it via `related_to` (R-09). A resolved or closed ticket may be reopened to
`in_progress` within 7 days of the event that ended it (R-10); outside that window reopening is
`409` (R-11), and reopening never moves the resolution target.

## 5. SLA

Each priority has an acknowledge target and a resolve target measured from `created_at` (R-12,
API.md section 4). Two clocks exist: a wall-clock target (`created_at + target`) and a
business-hours target that only counts Mon-Fri 08:00-16:00 Europe/Warsaw, pausing the rest of the
time (R-13). Which clock applies to P1 is decision C1 below; P2-P4 always use the business-hours
clock. `GET /tickets/{id}/sla` reports both due instants, whether each has been breached, and
whether the ticket is currently paused (R-15, R-16, API.md section 5).

## 6. The three conflicts and their resolutions

REQUIREMENTS.md contains three pairs of requirements that cannot both hold in full. Each is
resolved by rejecting the minimal conflicting part of one requirement while keeping the rest of
the pair; both sides are still exercised by the published checks, so the choice is a defended
design decision, not a bug fix. The full reasoning, in the required five-label structure, is in
`DECISIONS.md` at the repository root; this section only names the conflicting pairs and the
resolution this build exhibits, so that the two documents read consistently.

- **C1 - SLA clock for P1.** R-13 says every SLA clock pauses outside business hours; R-14 says P1
  must be acknowledged and resolved "around the clock", a P1 raised Friday evening is late at 15
  minutes past, not Monday morning. Both cannot hold for P1 at once. **This build resolves C1 as
  `wallclock`**: P1's two targets never pause, so R-14 holds exactly as written, and R-13's
  business-hours pause is understood to apply to P2-P4 (which is the only way both requirements
  read literally without contradicting each other for P1).
- **C2 - closed tickets and reopening.** R-09 says a closed ticket is immutable and further work
  needs a new ticket; R-10 says a reporter may reopen a resolved *or closed* ticket within 7 days.
  A closed ticket cannot be simultaneously immutable and reopenable. **This build resolves C2 as
  `immutable`**: reopen is only ever accepted from `resolved`; a closed ticket answers `409`
  regardless of age, and R-09's "new ticket via `related_to`" path is the one supported for closed
  issues.
- **C3 - VIP reporters and the priority matrix.** R-04/R-05 say priority comes from the matrix and
  "from nothing else"; R-06 says a VIP ticket is never lower than P2, whatever the matrix says.
  **This build resolves C3 as `vip`**: after the matrix is applied, a VIP ticket that landed at P3
  or P4 is raised to P2, so R-06 is honoured literally, and R-04/R-05's "nothing else" is read as
  "no client-supplied override", which the `vip` flag is not (it is part of the reporter, provided
  before the matrix runs, exactly like impact and urgency).

## 7. Validation and errors

`title` 1..200 chars required, `description` <=4000 chars optional, `reporter.name` 1..100 chars
required, `impact`/`urgency` required integers in 1..3; anything that violates this is `400` or
`422` with a top-level `error` object (R-20, R-03). Unknown ids and unknown paths are `404` with a
JSON body (R-25).

## 8. Test clock

When `SVCDESK_TEST_CLOCK` is `1` or `true`, a request may carry `X-Test-Clock` with an RFC 3339
instant used as `now` for that request only; a header that does not parse is `400`/`422` (R-21).
`GET /tickets` and `GET /tickets/{id}` do not depend on the clock, so the header is irrelevant
there.

## 9. Deployment

Docker Compose service `svcdesk`, built (not pulled) from the repository, listening on 8080 inside
the container, `SVCDESK_TEST_CLOCK` set, no host-path bind mounts, no network needed once the image
is built (R-22); `GET /health` answers within 120 s of `docker compose up` (R-24); tickets survive
a container restart via a named volume holding a SQLite file (R-23).
