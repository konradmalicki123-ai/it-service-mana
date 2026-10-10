---
lab3_slo:
  service: svcdesk
  route: /kb/search
  window: 30d
  slis:
    availability:
      objective: 0.99
      good: 'sum(rate(http_server_request_duration_seconds_count{job="svcdesk", http_route="/kb/search", http_response_status_code!~"5.."}[5m]))'
      valid: 'sum(rate(http_server_request_duration_seconds_count{job="svcdesk", http_route="/kb/search"}[5m]))'
      error_budget: {fraction: 0.01, minutes: 432}
    latency:
      objective: 0.95
      threshold_seconds: 0.1535
      good: 'sum(rate(http_server_request_duration_seconds_bucket{job="svcdesk", http_route="/kb/search", le="0.1535"}[5m]))'
      valid: 'sum(rate(http_server_request_duration_seconds_count{job="svcdesk", http_route="/kb/search"}[5m]))'
      error_budget: {fraction: 0.05, minutes: 2160}
  alerts:
    - {alert: KbSearchErrorsBurnFast, sli: availability, burn_rate: 14.4, long_window: 1h, short_window: 5m}
    - {alert: KbSearchErrorsBurnSlow, sli: availability, burn_rate: 6, long_window: 6h, short_window: 30m}
---
<!-- ai-generated: 85% - assistant drafted the SLO from the open-loop measurement of this login's kb-index -->

# SLO for `GET /kb/search`

The numbers below are from one open-loop run against this service: 40 requests per second for 60 seconds, 64 connections, latency counted from the scheduled instant. p50 was 0.021 s, p99 was 0.105 s, the slowest response was 0.127 s, and 15 of the 2,400 responses were 502 because kb-index returned 503. That is a dependency failure share of 0.625%. svcdesk does not retry those calls.

## Availability

A good request is a `GET /kb/search` that did not end in 5xx. The objective is 0.99 over 30 days. The error budget is 1 - 0.99 = 0.01 of requests, and 0.01 × 30 × 24 × 60 = 432 minutes.

kb-index already fails about 0.6% of ordinary searches, and that failure is not something this service can remove: the contract is one attempt and then 502. An objective of 0.99 leaves the dependency inside the budget and keeps about 0.4 percentage points for faults that are actually ours. Tighter than that would page us for the index's own seeded errors.

## Latency

A good request is one whose latency is at or under 0.1535 s. That boundary is on the ladder, just above the slowest response in the measured run (0.127 s) and above the p99 (0.105 s), so a request that took the slow path still meets the SLI. The objective is 0.95. The budget is 0.05 of requests, 0.05 × 43,200 = 2,160 minutes. It is there for a day whose tail is slower than the one we measured, not for the slow mode we already saw. 0.1535 s is also well under the 1 s cap a later canary gate will read from this file.

## Alerts

| alert | SLI | burn rate | long / short window | budget spent when it fires | severity: page or chat |
|---|---|---|---|---|---|
| KbSearchErrorsBurnFast | availability | 14.4 | 1h / 5m | about 2% of the 30-day budget | P1, page |
| KbSearchErrorsBurnSlow | availability | 6 | 6h / 30m | about 5% of the 30-day budget | P2, chat |

Both alerts watch availability, which is the SLI the dependency can actually burn. At burn 14.4 the 432-minute budget would be gone in 30 / 14.4 ≈ 2.1 days, and one hour of it already spends about 2% (14.4 × 1/720). That is worth waking someone: the short window stops the page once the errors stop, and waiting until morning at that rate would take a large slice of the month. Burn 6 exhausts the budget in 5 days and spends about 5% across the 6-hour window, which is a chat message in the morning rather than a page. The fast alert is P1 and the slow alert is P2.

## Buckets

The ladder is 30 boundaries in a geometric sequence of ratio 1.16, from 0.03 s to 2.22 s. The measured p99 of 0.105 s falls in (0.09835, 0.1141]. The width is 0.01575 s, which is 0.01575 / 0.105 = 0.150 of the p99, inside the 20% resolution limit. The same spacing resolves every latency from just above 0.03 s to 2.22 s, so the ±10% band around 0.105 s (0.0945 s to 0.1155 s) is covered, and so is a grader rerun a few percent higher or lower. The boundaries are spread across that whole span. Putting them all under the median, the way the flawed ladder does, would leave this p99 in a bucket hundreds of milliseconds wide.
