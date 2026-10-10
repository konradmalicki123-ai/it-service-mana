---
lab3_first_draft:
  source: ai
  tool: "Cursor Grok 4.7, 10 October 2026"
  ladder: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
  verdict: refuted
  evidence: {p99_seconds: 0.105, bucket: [0.1, 0.25], relative_width: 1.429}
lab3_flawed_ladder:
  verdict: refuted
  evidence: {p99_seconds: 0.105, bucket: [0.04, 0.5], relative_width: 4.381}
---
<!-- ai-generated: 80% - the prompt and the answer are the assistant's first draft; the verdicts use the measured p99 -->

# The assistant's first draft, and two verdicts

The p99 below is from `load`'s published shape run locally against this login's kb-index, through svcdesk: after a warm-up, 40 requests per second for 60 seconds over 64 connections, each latency taken from the instant the request was scheduled. The p99 was 0.105 s.

## Prompt

Design histogram bucket boundaries, in seconds, for a Prometheus histogram named http_server_request_duration_seconds on GET /kb/search of a Python service that uses prometheus_client. Also give one Prometheus alerting rule for error responses on that route. The dependency usually answers in a few tens of milliseconds and sometimes fails. If you are not sure of the distribution, use the client library's default buckets.

## Answer

Use the prometheus_client default buckets. They are the usual choice when the latency distribution is not known yet, and they cover a range from 5 ms to 10 s:

0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10

For the alert, page when the 5xx share of GET /kb/search over the last five minutes exceeds 14.4 times the error budget of a 0.99 availability objective:

```
groups:
  - name: kb-search
    rules:
      - alert: KbSearchErrorsHigh
        expr: |
          sum(rate(http_server_request_duration_seconds_count{http_route="/kb/search", http_response_status_code=~"5.."}[5m]))
          /
          sum(rate(http_server_request_duration_seconds_count{http_route="/kb/search"}[5m]))
          > (14.4 * (1 - 0.99))
        for: 5m
        labels:
          severity: P1
          service: svcdesk
```

That is a single five-minute window. It will go quiet within a few minutes after the errors stop.

## Verdict on the draft ladder

The measured p99 is 0.105 s. On the default ladder the bucket that contains it is (0.1, 0.25]: 0.1 is the largest boundary below 0.105, and 0.25 is the smallest boundary at or above it. The width is 0.25 - 0.1 = 0.15 s. The relative width is 0.15 / 0.105 = 1.429, so the bucket is 143% of the p99. The resolution rule allows at most 0.20 × 0.105 = 0.021 s. 0.15 is about seven times that. A quantile read back from this histogram can fall anywhere from 0.1 s to 0.25 s, a span wider than the p99 itself, which is why the draft does not resolve the measurement. Verdict: refuted.

## The draft alert rule

The draft rule compares a single five-minute error ratio with 14.4 × (1 - 0.99) and pages at P1. The constant and the route filter are the part worth keeping, and KbSearchErrorsBurnFast still uses that same 14.4 burn on availability. The single window is not what shipped. After the errors stop, a five-minute ratio falls quickly, but a long window alone would stay above the threshold for about half its length, so the shipped rules require the short window and the long window together. A second rule, KbSearchErrorsBurnSlow, watches the same SLI at burn 6 over 6h and 30m and is P2 rather than a page. The draft had no slow burn and no second window.

## Verdict on the instructor's flawed ladder

The flawed boundaries are 0.001, 0.0025, 0.005, 0.0075, 0.01, 0.0125, 0.015, 0.0175, 0.02, 0.025, 0.03, 0.04, 0.5, 2.5. The same p99, 0.105 s, falls in (0.04, 0.5]. The width is 0.5 - 0.04 = 0.46 s, and 0.46 / 0.105 = 4.381. Fourteen boundaries are spent at or below 0.04 s, which is under the median of this profile (the measured p50 was 0.021 s), and the next boundary is 0.5 s. The p99 sits in that gap. 0.46 is far above 0.20 × 0.105 = 0.021, so the ladder does not resolve it. Verdict: refuted.
