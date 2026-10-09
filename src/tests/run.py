# ai-generated: 90% - assistant drafted the HTTP checks the compose tests profile runs against svcdesk
"""Own tests for the compose tests profile. Last stdout line is the ITSMLAB-TESTS summary."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = os.environ.get("SVCDESK_URL", "http://svcdesk:8080").rstrip("/")
PASSED = 0
FAILED = 0


def clock_header(instant: str) -> dict:
    return {"X-Test-Clock": instant, "Content-Type": "application/json"}


def request(method: str, path: str, body=None, headers=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read()
            parsed = json.loads(raw) if raw else None
            return response.status, parsed
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = None
        return exc.status, parsed


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"ok {name}")
    else:
        FAILED += 1
        print(f"FAIL {name} {detail}")


def wait_until_healthy() -> None:
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            status, payload = request("GET", "/health")
            if status == 200 and isinstance(payload, dict) and payload.get("status") == "ok":
                return
        except Exception:
            pass
        time.sleep(1)
    print("service did not answer /health")
    print("ITSMLAB-TESTS: passed=0 failed=1")
    sys.exit(1)


def fixture_events() -> list:
    candidates = [
        Path("/app/fixtures/events-practice.jsonl"),
        Path(__file__).resolve().parents[2] / "fixtures" / "events-practice.jsonl",
    ]
    for path in candidates:
        if path.is_file():
            return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return []


def main() -> None:
    wait_until_healthy()
    status, payload = request("GET", "/health")
    check("health", status == 200 and payload.get("service") == "svcdesk", str(payload))

    status, payload = request("GET", "/this-route-does-not-exist-9f3c")
    check("unknown route", status == 404 and isinstance(payload, dict) and "error" in payload, str(status))

    status, payload = request(
        "POST",
        "/tickets",
        {"reporter": {"name": "Ada"}, "impact": 1, "urgency": 1},
        clock_header("2026-10-14T10:00:00Z"),
    )
    check("missing title", status in (400, 422) and "error" in payload, str(payload))

    status, payload = request(
        "POST",
        "/tickets",
        {"title": "x", "reporter": {"name": "Ada"}, "impact": 5, "urgency": 1},
        clock_header("2026-10-14T10:00:00Z"),
    )
    check("impact 5", status in (400, 422), str(status))

    created_status, created = request(
        "POST",
        "/tickets",
        {"title": "Org down", "reporter": {"name": "Ada", "vip": False}, "impact": 1, "urgency": 1},
        clock_header("2026-10-14T10:00:00Z"),
    )
    check(
        "create P1",
        created_status == 201 and created["priority"] == "P1" and created["created_at"] == "2026-10-14T10:00:00Z",
        str(created),
    )

    status, vip = request(
        "POST",
        "/tickets",
        {
            "title": "Cosmetic for a VIP",
            "reporter": {"name": "Executive", "vip": True},
            "impact": 3,
            "urgency": 3,
            "priority": "P1",
        },
        clock_header("2026-10-14T10:00:00Z"),
    )
    check("vip raised to P2 and body priority ignored", status == 201 and vip["priority"] == "P2", str(vip))

    status, friday = request(
        "POST",
        "/tickets",
        {"title": "Friday night P1", "reporter": {"name": "Oncall"}, "impact": 1, "urgency": 1},
        clock_header("2026-10-16T15:00:00Z"),
    )
    check(
        "T3 wall clock",
        status == 201
        and friday["sla"]["ack_due_at"] == "2026-10-16T15:15:00Z"
        and friday["sla"]["resolve_due_at"] == "2026-10-16T19:00:00Z",
        str(friday.get("sla") if isinstance(friday, dict) else friday),
    )

    status, p3 = request(
        "POST",
        "/tickets",
        {"title": "Friday afternoon P3", "reporter": {"name": "Team"}, "impact": 2, "urgency": 2},
        clock_header("2026-10-16T13:30:00Z"),
    )
    check(
        "T2 business hours",
        status == 201
        and p3["priority"] == "P3"
        and p3["sla"]["ack_due_at"] == "2026-10-19T09:30:00Z"
        and p3["sla"]["resolve_due_at"] == "2026-10-21T13:30:00Z",
        str(p3.get("sla") if isinstance(p3, dict) else p3),
    )

    ticket_id = created["id"]
    status, acked = request("POST", f"/tickets/{ticket_id}/ack", {}, clock_header("2026-10-14T10:05:00Z"))
    status2, started = request("POST", f"/tickets/{ticket_id}/start", {}, clock_header("2026-10-14T10:06:00Z"))
    status3, resolved = request("POST", f"/tickets/{ticket_id}/resolve", {}, clock_header("2026-10-14T11:00:00Z"))
    status4, closed = request("POST", f"/tickets/{ticket_id}/close", {}, clock_header("2026-10-14T12:00:00Z"))
    check(
        "state machine to closed",
        status == 200 and status2 == 200 and status3 == 200 and status4 == 200 and closed["state"] == "closed",
        str((status, status2, status3, status4, closed.get("state") if isinstance(closed, dict) else closed)),
    )
    status, reopened = request("POST", f"/tickets/{ticket_id}/reopen", {}, clock_header("2026-10-15T12:00:00Z"))
    check("closed ticket stays immutable", status == 409 and "error" in reopened, str(status))

    status, fresh = request(
        "POST",
        "/tickets",
        {"title": "Will reopen", "reporter": {"name": "Ada"}, "impact": 1, "urgency": 1},
        clock_header("2026-10-01T10:00:00Z"),
    )
    fid = fresh["id"]
    request("POST", f"/tickets/{fid}/ack", {}, clock_header("2026-10-01T10:05:00Z"))
    request("POST", f"/tickets/{fid}/start", {}, clock_header("2026-10-01T10:06:00Z"))
    request("POST", f"/tickets/{fid}/resolve", {}, clock_header("2026-10-01T12:00:00Z"))
    status, again = request("POST", f"/tickets/{fid}/reopen", {}, clock_header("2026-10-07T12:00:00Z"))
    check(
        "reopen resolved within 6 days",
        status == 200 and again["state"] == "in_progress" and again["resolved_at"] is None,
        str(again),
    )

    status, listing = request("GET", "/tickets?priority=P1")
    ids = {item["id"] for item in listing} if isinstance(listing, list) else set()
    check("list filter keeps P1 and drops the VIP P2", status == 200 and ticket_id in ids and vip["id"] not in ids, str(status))

    status, bad_clock = request(
        "POST",
        "/tickets",
        {"title": "x", "reporter": {"name": "Ada"}, "impact": 1, "urgency": 1},
        clock_header("yesterday"),
    )
    check("malformed clock", status in (400, 422), str(status))

    status, sla = request("GET", f"/tickets/{p3['id']}/sla", headers=clock_header("2026-10-17T10:00:00Z"))
    status_b, sla_b = request("GET", f"/tickets/{p3['id']}/sla", headers=clock_header("2026-10-19T09:00:00Z"))
    check(
        "paused on Saturday but not Monday morning",
        status == 200 and sla["paused"] is True and sla_b["paused"] is False and sla_b["ack_breached"] is False,
        str((sla, sla_b)),
    )

    status, empty = request(
        "POST",
        "/dora/metrics",
        {"window": {"from": "2026-09-01T00:00:00Z", "to": "2026-09-22T00:00:00Z"}, "events": []},
    )
    check(
        "empty log",
        status == 200 and empty["deployment_frequency_per_day"] == 0.0 and empty["change_fail_rate"] is None,
        str(empty)[:300],
    )

    events = fixture_events()
    status, metrics = request(
        "POST",
        "/dora/metrics",
        {
            "window": {"from": "2026-09-01T00:00:00Z", "to": "2026-09-22T00:00:00Z"},
            "events": events,
        },
    )
    check(
        "practice fixture headline counts",
        status == 200
        and metrics["counts"]["deployments"] == 42
        and metrics["counts"]["changes"] == 86
        and metrics["anomalies"]["negative_lead_time_pairs"] == 3
        and metrics["anomalies"]["overlapping_incident_pairs"] == 11
        and metrics["ground_truth"]["changes_delivered"] == 65
        and metrics["change_lead_time_seconds_p50"] == 375643,
        str(metrics)[:500] if isinstance(metrics, dict) else str(status),
    )

    status, stream = request("GET", "/dora/ticket-events")
    created_rows = [row for row in stream if row["ticket_id"] == fid] if isinstance(stream, list) else []
    phases = [row["phase"] for row in created_rows]
    check(
        "ticket events for a reopened ticket",
        status == 200 and phases == ["created", "acknowledged"] and created_rows[0]["state"] == "new",
        str(phases),
    )

    # A resolved ticket that was not reopened still carries the resolved phase.
    status, done = request(
        "POST",
        "/tickets",
        {"title": "Short one", "reporter": {"name": "Ada"}, "impact": 3, "urgency": 3},
        clock_header("2026-10-14T10:00:00Z"),
    )
    did = done["id"]
    request("POST", f"/tickets/{did}/ack", {}, clock_header("2026-10-14T10:10:00Z"))
    request("POST", f"/tickets/{did}/start", {}, clock_header("2026-10-14T10:20:00Z"))
    request("POST", f"/tickets/{did}/resolve", {}, clock_header("2026-10-14T11:00:00Z"))
    status, stream = request("GET", "/dora/ticket-events")
    phases = [row["phase"] for row in stream if row["ticket_id"] == did]
    ordered = [row["at"] for row in stream]
    check(
        "resolved ticket exports three phases in order",
        phases == ["created", "acknowledged", "resolved"] and ordered == sorted(ordered),
        str(phases),
    )

    print(f"ITSMLAB-TESTS: passed={PASSED} failed={FAILED}")
    sys.exit(0 if FAILED == 0 else 1)


if __name__ == "__main__":
    main()
