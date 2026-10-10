# ai-generated: 90% - assistant chose the histogram name, labels and ladder and wired the exposition
"""Request histogram for Laboratory 3.

One histogram, in seconds, with the three OpenTelemetry HTTP labels in their
Prometheus form. The ladder is a geometric sequence of ratio 1.16 from 0.03 s
to 2.22 s (30 finite boundaries). Every latency inside that span falls in a
bucket no wider than 16 percent of the bucket's lower edge, which is inside
the 20 percent resolution rule.
"""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Histogram, disable_created_metrics, generate_latest

disable_created_metrics()

# Seconds. Neighbour ratio is 1.16, so (hi - lo) / lo = 0.16 <= 0.20.
BUCKETS = (
    0.03,
    0.0348,
    0.04037,
    0.04683,
    0.05432,
    0.06301,
    0.07309,
    0.08479,
    0.09835,
    0.1141,
    0.1323,
    0.1535,
    0.1781,
    0.2066,
    0.2396,
    0.278,
    0.3224,
    0.374,
    0.4339,
    0.5033,
    0.5838,
    0.6772,
    0.7856,
    0.9113,
    1.057,
    1.226,
    1.422,
    1.65,
    1.914,
    2.22,
)

REGISTRY = CollectorRegistry()

REQUEST_DURATION = Histogram(
    "http_server_request_duration_seconds",
    "Duration of HTTP server requests, in seconds.",
    labelnames=(
        "http_request_method",
        "http_route",
        "http_response_status_code",
    ),
    buckets=BUCKETS,
    registry=REGISTRY,
)

# Prometheus 3.15 refuses to scrape anything that is not text/plain.
METRICS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


def render_metrics() -> bytes:
    return generate_latest(REGISTRY)


def route_template(scope: dict) -> str:
    """Matched route template, or one constant for requests that miss every route."""
    route = scope.get("route")
    path = getattr(route, "path", None)
    if isinstance(path, str) and path:
        return path
    return "unmatched"
