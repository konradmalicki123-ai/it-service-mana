# ai-generated: 90% - assistant drafted the HTTP API from API.md; C1=wallclock, C2=immutable, C3=vip match specs/spec.md; Lab 3 adds /kb/search and the histogram
"""svcdesk HTTP API. Laboratory 1 ticketing, laboratory 2 DORA, laboratory 3 kb-index."""

from __future__ import annotations

import asyncio
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from svcdesk.clock import due_instants, format_instant, in_business_hours, parse_instant
from svcdesk.dora import LogError, compute_metrics
from svcdesk.metrics import METRICS_CONTENT_TYPE, REQUEST_DURATION, render_metrics, route_template
from svcdesk.store import get_store

# Decision C1. P1 uses the wall clock; P2-P4 use business hours. See DECISIONS.md.
P1_WALLCLOCK = True

MATRIX = {
    (1, 1): "P1",
    (1, 2): "P2",
    (1, 3): "P3",
    (2, 1): "P2",
    (2, 2): "P3",
    (2, 3): "P4",
    (3, 1): "P3",
    (3, 2): "P4",
    (3, 3): "P4",
}

app = FastAPI()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect is not a second search. Surface it as the upstream status."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


# Passing the subclass replaces the default redirect handler, so open() does one GET.
_KB_OPENER = urllib.request.build_opener(_NoRedirect)


def error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@app.exception_handler(404)
async def not_found(_request: Request, _exc: Exception) -> JSONResponse:
    return error(404, "not_found", "not found")


def test_clock_enabled() -> bool:
    return os.environ.get("SVCDESK_TEST_CLOCK", "").strip().lower() in {"1", "true"}


def request_now(request: Request) -> datetime:
    header = request.headers.get("x-test-clock")
    if test_clock_enabled() and header is not None:
        return parse_instant(header)
    return datetime.now(timezone.utc)


def priority_for(impact: int, urgency: int, vip: bool) -> str:
    priority = MATRIX[(impact, urgency)]
    # Decision C3 = vip. A VIP ticket below P2 is raised to P2. P1 and P2 stay.
    if vip and priority in {"P3", "P4"}:
        return "P2"
    return priority


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def validate_create(body: dict) -> JSONResponse | None:
    title = body.get("title", None)
    if not isinstance(title, str) or not 1 <= len(title) <= 200:
        return error(422, "validation", "title is required and must be 1..200 characters")
    if "description" in body and body["description"] is not None:
        if not isinstance(body["description"], str) or len(body["description"]) > 4000:
            return error(422, "validation", "description must be at most 4000 characters")
    reporter = body.get("reporter")
    if not isinstance(reporter, dict):
        return error(422, "validation", "reporter is required")
    name = reporter.get("name")
    if not isinstance(name, str) or not 1 <= len(name) <= 100:
        return error(422, "validation", "reporter.name is required and must be 1..100 characters")
    if "email" in reporter and reporter["email"] is not None and not isinstance(reporter["email"], str):
        return error(422, "validation", "reporter.email must be a string or null")
    if "vip" in reporter and not isinstance(reporter["vip"], bool):
        return error(422, "validation", "reporter.vip must be a boolean")
    if not _is_int(body.get("impact")) or body["impact"] not in (1, 2, 3):
        return error(422, "validation", "impact must be an integer from 1 to 3")
    if not _is_int(body.get("urgency")) or body["urgency"] not in (1, 2, 3):
        return error(422, "validation", "urgency must be an integer from 1 to 3")
    if "related_to" in body and body["related_to"] is not None and not isinstance(body["related_to"], str):
        return error(422, "validation", "related_to must be a string or null")
    return None


def sla_view(ticket: dict, now: datetime) -> dict:
    ack_due = parse_instant(ticket["sla"]["ack_due_at"])
    resolve_due = parse_instant(ticket["sla"]["resolve_due_at"])
    acknowledged = ticket["acknowledged_at"]
    resolved = ticket["resolved_at"]
    if acknowledged is None:
        ack_breached = now > ack_due
    else:
        ack_breached = parse_instant(acknowledged) > ack_due
    if resolved is None:
        resolve_breached = now > resolve_due
    else:
        resolve_breached = parse_instant(resolved) > resolve_due
    business_resolution = ticket["priority"] != "P1" or not P1_WALLCLOCK
    open_ticket = ticket["state"] not in {"resolved", "closed"}
    paused = open_ticket and business_resolution and not in_business_hours(now)
    return {
        "priority": ticket["priority"],
        "ack_due_at": ticket["sla"]["ack_due_at"],
        "resolve_due_at": ticket["sla"]["resolve_due_at"],
        "ack_breached": ack_breached,
        "resolve_breached": resolve_breached,
        "paused": paused,
    }


async def read_body(request: Request) -> dict | JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return error(422, "validation", "body must be a JSON object")
    if not isinstance(body, dict):
        return error(422, "validation", "body must be a JSON object")
    return body


@app.middleware("http")
async def record_request_duration(request: Request, call_next):
    # One observation per request, after routing, so http_route is the template.
    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        REQUEST_DURATION.labels(
            http_request_method=request.method,
            http_route=route_template(request.scope),
            http_response_status_code=str(status_code),
        ).observe(time.perf_counter() - started)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "svcdesk"}


@app.get("/metrics")
def metrics() -> Response:
    return Response(content=render_metrics(), media_type=METRICS_CONTENT_TYPE)


def kb_index_base() -> str:
    return os.environ.get("KB_INDEX_URL", "http://kb-index:8080").rstrip("/")


def _kb_get(url: str, timeout: float) -> tuple[int, bytes]:
    # Exactly one request. HTTPError is the upstream's non-200 response, not a retry.
    request = urllib.request.Request(url, method="GET")
    try:
        with _KB_OPENER.open(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


@app.get("/kb/search")
async def kb_search(q: str | None = None):
    if q is None or not 1 <= len(q) <= 200:
        return error(422, "validation", "q is required and must be 1..200 characters")
    # q is URL-encoded. Timeout is 5 s, above the 2 s minimum. No cache and no retry.
    url = kb_index_base() + "/search?q=" + urllib.parse.quote(q, safe="")
    try:
        status, raw = await asyncio.to_thread(_kb_get, url, 5.0)
    except Exception:
        return error(502, "upstream_unavailable", "kb-index did not answer")
    if status != 200:
        return error(502, "upstream_unavailable", "kb-index did not answer")
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeError):
        return error(502, "upstream_unavailable", "kb-index did not answer")
    if not isinstance(payload, dict) or "hits" not in payload:
        return error(502, "upstream_unavailable", "kb-index did not answer")
    return {"query": q, "hits": payload["hits"]}


@app.post("/tickets")
async def create_ticket(request: Request):
    try:
        now = request_now(request)
    except ValueError:
        return error(422, "validation", "X-Test-Clock is not an RFC 3339 instant")
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    invalid = validate_create(body)
    if invalid is not None:
        return invalid
    reporter_in = body["reporter"]
    vip = bool(reporter_in.get("vip", False))
    priority = priority_for(body["impact"], body["urgency"], vip)
    ack_due, resolve_due, _business = due_instants(now, priority, P1_WALLCLOCK)
    description = body.get("description") or ""
    related = body.get("related_to")
    ticket = {
        "id": str(uuid.uuid4()),
        "title": body["title"],
        "description": description,
        "reporter": {
            "name": reporter_in["name"],
            "email": reporter_in.get("email"),
            "vip": vip,
        },
        "impact": body["impact"],
        "urgency": body["urgency"],
        "priority": priority,
        "state": "new",
        "created_at": format_instant(now),
        "acknowledged_at": None,
        "resolved_at": None,
        "closed_at": None,
        "related_to": related if isinstance(related, str) else None,
        "sla": {
            "ack_due_at": format_instant(ack_due),
            "resolve_due_at": format_instant(resolve_due),
        },
    }
    get_store().insert(ticket)
    return JSONResponse(status_code=201, content=ticket)


@app.get("/tickets")
async def list_tickets(state: str | None = None, priority: str | None = None) -> list:
    tickets = get_store().list_all()
    if state is not None:
        tickets = [item for item in tickets if item["state"] == state]
    if priority is not None:
        tickets = [item for item in tickets if item["priority"] == priority]
    return tickets


@app.get("/tickets/{ticket_id}")
async def get_ticket(ticket_id: str):
    ticket = get_store().get(ticket_id)
    if ticket is None:
        return error(404, "not_found", "ticket not found")
    return ticket


@app.get("/tickets/{ticket_id}/sla")
async def get_sla(ticket_id: str, request: Request):
    try:
        now = request_now(request)
    except ValueError:
        return error(422, "validation", "X-Test-Clock is not an RFC 3339 instant")
    ticket = get_store().get(ticket_id)
    if ticket is None:
        return error(404, "not_found", "ticket not found")
    return sla_view(ticket, now)


def _transition(ticket: dict, action: str, now: datetime) -> JSONResponse | dict:
    state = ticket["state"]
    if action == "ack":
        if state != "new":
            return error(409, "invalid_transition", "ack is only valid from new")
        ticket["state"] = "acknowledged"
        ticket["acknowledged_at"] = format_instant(now)
    elif action == "start":
        if state != "acknowledged":
            return error(409, "invalid_transition", "start is only valid from acknowledged")
        ticket["state"] = "in_progress"
    elif action == "resolve":
        if state != "in_progress":
            return error(409, "invalid_transition", "resolve is only valid from in_progress")
        ticket["state"] = "resolved"
        ticket["resolved_at"] = format_instant(now)
    elif action == "close":
        if state != "resolved":
            return error(409, "invalid_transition", "close is only valid from resolved")
        ticket["state"] = "closed"
        ticket["closed_at"] = format_instant(now)
    elif action == "reopen":
        # Decision C2 = immutable. Closed tickets stay closed.
        if state == "closed":
            return error(409, "ticket_closed", "a closed ticket is immutable")
        if state != "resolved":
            return error(409, "invalid_transition", "reopen is only valid from resolved")
        deadline = parse_instant(ticket["resolved_at"]) + timedelta(days=7)
        if now > deadline:
            return error(409, "reopen_window_expired", "reopen window of 7 days has passed")
        ticket["state"] = "in_progress"
        ticket["resolved_at"] = None
        ticket["closed_at"] = None
    else:
        return error(404, "not_found", "not found")
    get_store().save(ticket)
    return ticket


async def act(ticket_id: str, action: str, request: Request):
    try:
        now = request_now(request)
    except ValueError:
        return error(422, "validation", "X-Test-Clock is not an RFC 3339 instant")
    ticket = get_store().get(ticket_id)
    if ticket is None:
        return error(404, "not_found", "ticket not found")
    return _transition(ticket, action, now)


@app.post("/tickets/{ticket_id}/ack")
async def ack(ticket_id: str, request: Request):
    return await act(ticket_id, "ack", request)


@app.post("/tickets/{ticket_id}/start")
async def start(ticket_id: str, request: Request):
    return await act(ticket_id, "start", request)


@app.post("/tickets/{ticket_id}/resolve")
async def resolve(ticket_id: str, request: Request):
    return await act(ticket_id, "resolve", request)


@app.post("/tickets/{ticket_id}/close")
async def close(ticket_id: str, request: Request):
    return await act(ticket_id, "close", request)


@app.post("/tickets/{ticket_id}/reopen")
async def reopen(ticket_id: str, request: Request):
    return await act(ticket_id, "reopen", request)


@app.post("/dora/metrics")
async def dora_metrics(request: Request):
    try:
        body = await request.json()
    except Exception:
        return error(422, "validation", "body must be a JSON object")
    if not isinstance(body, dict):
        return error(422, "validation", "body must be a JSON object")
    if "window" not in body:
        return error(422, "validation", "window is missing")
    if "events" not in body or not isinstance(body["events"], list):
        return error(422, "validation", "events must be an array")
    try:
        return compute_metrics(body["window"], body["events"])
    except LogError as exc:
        return error(422, "validation", str(exc))


@app.get("/dora/ticket-events")
async def ticket_events() -> list:
    rows = []
    for ticket in get_store().list_all():
        phases = (
            ("created", "created_at", "new"),
            ("acknowledged", "acknowledged_at", "acknowledged"),
            ("resolved", "resolved_at", "resolved"),
            ("closed", "closed_at", "closed"),
        )
        for phase, field, state in phases:
            if ticket[field] is None:
                continue
            rows.append({
                "ticket_id": ticket["id"],
                "at": ticket[field],
                "phase": phase,
                "priority": ticket["priority"],
                "state": state,
            })
    rows.sort(key=lambda item: (item["at"], item["ticket_id"]))
    return rows
