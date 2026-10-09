# ai-generated: 90% - assistant implemented METRIC-SPEC.md R-01..R-17; practice fixture is the published answer key
"""DORA metric computation. A pure function of the request body. METRIC-SPEC.md wins over folklore."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from svcdesk.clock import format_instant, parse_instant

SPEC_VERSION = "1.0.0"


class LogError(ValueError):
    """The event log or the window is not acceptable. The API turns this into 422."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise LogError(message)


def _as_instant(value, label: str) -> datetime:
    try:
        return parse_instant(value)
    except ValueError as exc:
        raise LogError(f"{label} is not an RFC 3339 instant") from exc


def _dedupe(events: list) -> list:
    seen: set[str] = set()
    kept = []
    for event in events:
        _require(isinstance(event, dict), "event is not an object")
        event_id = event.get("event_id")
        _require(isinstance(event_id, str) and 1 <= len(event_id) <= 64, "event_id must be 1..64 characters")
        if event_id in seen:
            continue
        seen.add(event_id)
        kept.append(event)
    return kept


def _validate_and_index(events: list) -> tuple[list, list, list]:
    commits = []
    deployments = []
    incidents = []
    for event in events:
        kind = event.get("type")
        _require(kind in ("commit", "deployment", "incident"), "event type is not commit, deployment or incident")
        at = _as_instant(event.get("at"), "at")
        if kind == "commit":
            sha = event.get("sha")
            branch = event.get("branch")
            reverts = event.get("reverts")
            change_id = event.get("change_id")
            _require(isinstance(sha, str) and sha, "commit sha is missing")
            _require(isinstance(branch, str), "commit branch is missing")
            _require(reverts is None or (isinstance(reverts, str) and reverts), "reverts must be a sha or null")
            if reverts is None:
                _require(isinstance(change_id, str) and change_id, "change_id is required when reverts is null")
            else:
                _require(change_id is None, "a revert commit must not carry its own change_id")
            commits.append({
                "sha": sha,
                "branch": branch,
                "at": at,
                "reverts": reverts,
                "change_id": change_id,
            })
        elif kind == "deployment":
            deployment_id = event.get("deployment_id")
            environment = event.get("environment")
            outcome = event.get("outcome")
            commit_list = event.get("commits")
            unplanned = event.get("unplanned")
            caused_by = event.get("caused_by")
            _require(isinstance(deployment_id, str) and deployment_id, "deployment_id is missing")
            _require(isinstance(environment, str) and environment, "environment is missing")
            _require(outcome in ("success", "failure"), "outcome must be success or failure")
            _require(isinstance(commit_list, list), "commits must be an array")
            _require(all(isinstance(item, str) and item for item in commit_list), "commits must be shas")
            _require(isinstance(unplanned, bool), "unplanned must be a boolean")
            _require(caused_by is None or (isinstance(caused_by, str) and caused_by), "caused_by must be an incident id or null")
            deployments.append({
                "deployment_id": deployment_id,
                "environment": environment,
                "outcome": outcome,
                "at": at,
                "commits": list(dict.fromkeys(commit_list)),
                "unplanned": unplanned,
                "caused_by": caused_by,
            })
        else:
            incident_id = event.get("incident_id")
            phase = event.get("phase")
            linked = event.get("deployments")
            _require(isinstance(incident_id, str) and incident_id, "incident_id is missing")
            _require(phase in ("opened", "resolved"), "phase must be opened or resolved")
            _require(isinstance(linked, list), "incident deployments must be an array")
            _require(all(isinstance(item, str) and item for item in linked), "incident deployments must be ids")
            incidents.append({
                "incident_id": incident_id,
                "phase": phase,
                "at": at,
                "deployments": list(linked),
            })

    shas = [item["sha"] for item in commits]
    _require(len(shas) == len(set(shas)), "commit sha is not unique")
    sha_set = set(shas)
    deployment_ids = {item["deployment_id"] for item in deployments}
    by_sha = {item["sha"]: item for item in commits}

    for item in commits:
        if item["reverts"] is not None:
            _require(item["reverts"] in sha_set, "reverts names a sha that is not in the log")
    for item in deployments:
        for sha in item["commits"]:
            _require(sha in sha_set, "deployment commits name a sha that is not in the log")
        if item["caused_by"] is not None:
            _require(
                any(inc["incident_id"] == item["caused_by"] for inc in incidents),
                "caused_by names an incident that is not in the log",
            )
    for item in incidents:
        for deployment_id in item["deployments"]:
            _require(deployment_id in deployment_ids, "incident names a deployment that is not in the log")

    # Transitive revert resolution. A cycle, or a revert of a missing sha, is malformed.
    resolved: dict[str, str] = {}

    def change_of(sha: str, stack: tuple[str, ...]) -> str:
        if sha in resolved:
            return resolved[sha]
        _require(sha not in stack, "revert chain is cyclic")
        commit = by_sha[sha]
        if commit["reverts"] is None:
            resolved[sha] = commit["change_id"]
            return commit["change_id"]
        resolved[sha] = change_of(commit["reverts"], stack + (sha,))
        return resolved[sha]

    for sha in shas:
        change_of(sha, ())

    opened: dict[str, datetime] = {}
    resolved_at: dict[str, datetime] = {}
    covers: dict[str, list[str]] = {}
    for item in incidents:
        incident_id = item["incident_id"]
        covers.setdefault(incident_id, [])
        if item["phase"] == "opened":
            _require(incident_id not in opened, "incident opened more than once")
            opened[incident_id] = item["at"]
            covers[incident_id] = item["deployments"]
        else:
            _require(incident_id not in resolved_at, "incident resolved more than once")
            resolved_at[incident_id] = item["at"]
            if item["deployments"]:
                covers[incident_id] = item["deployments"]
    for incident_id in resolved_at:
        _require(incident_id in opened, "incident resolved without being opened")

    incident_rows = []
    for incident_id, opened_at in opened.items():
        incident_rows.append({
            "incident_id": incident_id,
            "opened": opened_at,
            "resolved": resolved_at.get(incident_id),
            "deployments": covers.get(incident_id, []),
        })

    for commit in commits:
        commit["change"] = resolved[commit["sha"]]
    return commits, deployments, incident_rows


def _median(values: list[Decimal]) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    count = len(ordered)
    if count % 2 == 1:
        raw = ordered[count // 2]
    else:
        raw = (ordered[count // 2 - 1] + ordered[count // 2]) / Decimal(2)
    return int(raw.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    quantized = (Decimal(numerator) / Decimal(denominator)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    return float(quantized)


def _seconds(later: datetime, earlier: datetime) -> Decimal:
    delta = later - earlier
    return (
        Decimal(delta.days) * Decimal(86400)
        + Decimal(delta.seconds)
        + (Decimal(delta.microseconds) / Decimal(1_000_000))
    )


def compute_metrics(window: dict, events: list) -> dict:
    """Return the metric object defined in METRIC-SPEC.md section 6."""
    _require(isinstance(window, dict), "window is missing")
    if "from" not in window or "to" not in window:
        raise LogError("window is missing")
    start = _as_instant(window.get("from"), "window.from")
    end = _as_instant(window.get("to"), "window.to")
    _require(end > start, "window to must be after from")
    _require(isinstance(events, list), "events must be an array")
    commits, deployments, incidents = _validate_and_index(_dedupe(events))

    window_days = _seconds(end, start) / Decimal(86400)
    production = [item for item in deployments if item["environment"] == "production" and start <= item["at"] < end]
    successes = [item for item in production if item["outcome"] == "success"]
    failures = [item for item in production if item["outcome"] == "failure"]

    by_sha = {item["sha"]: item for item in commits}
    # Earliest successful in-window deployment of each sha (R-08). Ties break on deployment_id.
    first_success: dict[str, dict] = {}
    for deployment in sorted(successes, key=lambda item: (item["at"], item["deployment_id"])):
        for sha in deployment["commits"]:
            first_success.setdefault(sha, deployment)

    lead_times: list[Decimal] = []
    negative_pairs = 0
    for sha, deployment in first_success.items():
        raw = _seconds(deployment["at"], by_sha[sha]["at"])
        if raw < 0:
            negative_pairs += 1
            raw = Decimal(0)
        lead_times.append(raw)

    off_main: set[str] = set()
    for deployment in production:
        for sha in deployment["commits"]:
            if by_sha[sha]["branch"] != "main":
                off_main.add(sha)

    # Covering incident: earliest opened, then lowest incident_id (R-12).
    recovered: list[Decimal] = []
    open_failures = 0
    for deployment in failures:
        candidates = [inc for inc in incidents if deployment["deployment_id"] in inc["deployments"]]
        if not candidates:
            open_failures += 1
            continue
        candidates.sort(key=lambda inc: (inc["opened"], inc["incident_id"]))
        cover = candidates[0]
        if cover["resolved"] is None:
            open_failures += 1
            continue
        raw = _seconds(cover["resolved"], deployment["at"])
        if raw < 0:
            raw = Decimal(0)
        recovered.append(raw)

    # Overlapping incidents, unordered pairs, half-open intervals (R-13).
    intervals = []
    for inc in incidents:
        intervals.append((inc["opened"], inc["resolved"] if inc["resolved"] is not None else end))
    overlapping = 0
    for left in range(len(intervals)):
        opened_a, end_a = intervals[left]
        for right in range(left + 1, len(intervals)):
            opened_b, end_b = intervals[right]
            if opened_a < end_b and opened_b < end_a:
                overlapping += 1

    changes: dict[str, list] = {}
    for commit in commits:
        changes.setdefault(commit["change"], []).append(commit)

    delivered_at: dict[str, datetime] = {}
    for deployment in successes:
        for sha in deployment["commits"]:
            change_id = by_sha[sha]["change"]
            previous = delivered_at.get(change_id)
            if previous is None or deployment["at"] < previous:
                delivered_at[change_id] = deployment["at"]

    true_lead: list[Decimal] = []
    for change_id, deployed_at in delivered_at.items():
        first_commit = min(item["at"] for item in changes[change_id])
        raw = _seconds(deployed_at, first_commit)
        if raw < 0:
            raw = Decimal(0)
        true_lead.append(raw)

    deployment_count = len(production)
    frequency = float(
        (Decimal(deployment_count) / window_days).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    )
    rework = sum(1 for item in production if item["unplanned"] and item["caused_by"] is not None)

    return {
        "spec_version": SPEC_VERSION,
        "window": {"from": format_instant(start), "to": format_instant(end)},
        "deployment_frequency_per_day": frequency,
        "change_lead_time_seconds_p50": _median(lead_times),
        "failed_deployment_recovery_time_seconds_p50": _median(recovered),
        "change_fail_rate": _rate(len(failures), deployment_count),
        "deployment_rework_rate": _rate(rework, deployment_count),
        "counts": {
            "deployments": deployment_count,
            "successful_deployments": len(successes),
            "failed_deployments": len(failures),
            "recovered_failures": len(recovered),
            "open_failures": open_failures,
            "rework_deployments": rework,
            "lead_time_pairs": len(lead_times),
            "changes": len(changes),
        },
        "anomalies": {
            "negative_lead_time_pairs": negative_pairs,
            "deployments_without_commits": sum(1 for item in production if not item["commits"]),
            "commits_never_on_main": len(off_main),
            "revert_chains_collapsed": sum(1 for item in commits if item["reverts"] is not None),
            "overlapping_incident_pairs": overlapping,
        },
        "ground_truth": {
            "changes_delivered": len(delivered_at),
            "true_change_lead_time_seconds_p50": _median(true_lead),
        },
    }
