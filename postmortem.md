---
lab4_postmortem:
  ticket: "50ceffde-fa49-40b3-b4ca-957734d74bf7"
  detecting_alert: ShopCheckoutErrors
  onset: 2026-10-12T06:36:23Z
  detection: 2026-10-12T06:39:19Z
  acknowledgement: 2026-10-12T06:40:09Z
  recovery: 2026-10-12T06:44:19Z
  mttd_seconds: 176
  mtta_seconds: 50
  mttr_seconds: 476
  identified_flags: [paymentFailure, loadGeneratorFloodHomepage]
---
<!-- ai-generated: 35% - an assistant helped organise the timeline and the PromQL; the verdicts and the flag calls are from the snapshot -->

# Postmortem: checkout failed charges, and the homepage was flooded

## Date

The incident is the recorded shop run of 12 October 2026. This postmortem was written on 25 October 2026 from that Prometheus snapshot and the P1 ticket, after the clocks were read off the snapshot.

## Authors

The on-call for the shop wrote this after the page. The role during the incident was on-call: open the P1, acknowledge it, and find which feature flags had started failing. No other person had a decision to make while the page was open.

## Status

Complete, action items in progress. Checkout was serving again when the detecting alert resolved; the problem record stays open until those flags cannot be turned on by the injector.

## Summary

For about eight minutes, starting at 06:36:23Z, a quarter of payment charges failed and the homepage was requested about fifteen times more often than on the quiet shop. Checkout's PlaceOrder failed with those charges. The page was ShopCheckoutErrors. Service was back at 06:44:19Z, when that alert's first firing run ended.

## Impact

Shoppers who reached payment during the fault lost about one order in four. From 06:36:30Z to 06:43:00Z the `charge` counter rose from 81 to 116 (35 new charges) and the error counter rose from absent to 8, so 8 of 35 charges failed, 23%. The same eight failures are the checkout server span `oteldemo.CheckoutService/PlaceOrder`. The five-minute rate at 06:42:00Z was 0.032 failed charges per second, against no error series at 06:31:23Z.

Query for the ratio inside the fault:

`sum(rate(traces_span_metrics_calls_total{service_name="payment",span_name="charge",status_code="STATUS_CODE_ERROR"}[5m])) / sum(rate(traces_span_metrics_calls_total{service_name="payment",span_name="charge"}[5m]))`

evaluated at 2026-10-12T06:42:00Z, result 0.29 over that five-minute window (the window is all inside the fault; the 23% figure is the whole fault, including the first minute before errors accumulated).

The homepage, not checkout, took the load. `GET /` on frontend went from 118 at 06:36:00Z to 18592 at 06:43:30Z. Server request rate for frontend went from 4.0/s at 06:31:00Z to 60.6/s at 06:41:30Z, a factor of 15. Checkout latency did not move: server p99 stayed near 50 ms, so the user-visible failure was errors, not slowness. No other service recorded a server error in that window.

## Root Causes

Two flags from the injector's pool match the measurements. A third class was drawn and is not named here, because neither candidate showed its symptom.

`paymentFailure` fails a fixed fraction of charges (the pool's variants are 10%, 25% and 50%). Eight failures in 35 charges is 23%, which is the 25% variant with a short sample, not 10% and not 50%. Checkout's only error span is the client call `oteldemo.PaymentService/Charge`, at the same rate as `charge`. Product-catalog and ad recorded no server errors, so `productCatalogFailure` and `adFailure` are not this draw.

`loadGeneratorFloodHomepage` multiplies frontend traffic by about 15 and adds the load-generator span `user_flood_home`. Frontend server rate rose by 15.1 times, `GET /` carried almost all of the new traffic, and `user_flood_home` climbed from 0 to 92 between 06:37:30Z and 06:42:30Z. Ad p99 stayed under 6 ms, shipping average stayed near 1 ms, and product-catalog average stayed near 2 ms, so `adManualGc`, `intlShippingSlowdown` and `productCatalogLockContention` are not this draw.

The resource class did not show. Email container memory stayed at 58 MiB across the fault and the container did not restart, so `emailMemoryLeak` did not reach an out-of-memory kill. Recommendation server average latency fell from 3.6 ms to 2.1 ms and its RSS did not climb with the fault, so `recommendationCacheFailure` is not supported either. Naming either of them would be a guess. The identified set is the two flags the counters support.

## Trigger

The injector had been armed at 06:32:03Z, after a baseline that began at 06:22:03Z. At 06:36:23Z `seeded_fault_active` became 1. That sample is the onset. Nothing in the shop's deploy changed; the flags switched together, which is what the injector does at the onset.

## Resolution

The fault series returned to 0 at 06:43:18Z, which is when the failing flags were switched off. The workaround is the injector, not the demo's flag file: `POST /flags/paymentFailure/off` and `POST /flags/loadGeneratorFloodHomepage/off`. Payment was first because that is what shoppers felt as failed orders; the flood was second because it was load, not a failed charge. The detecting alert's five-minute window still contained the errors after the flags were off, so ShopCheckoutErrors kept firing through its last sample at 06:44:19Z. That second is the recovery `incident 4` prints, and MTTR counted from the onset is 476 seconds.

## Detection

ShopCheckoutErrors, severity P1, service checkout, started firing at 06:39:19Z. That is the earliest firing run at or after the onset, so it is the detecting alert. MTTD is 176 seconds. A P2, ShopServiceErrors, started a minute later on checkout and on payment; it did not beat the P1. No P1 sample exists in the ten minutes before the onset. The pager counter `itsm_pager_notifications_total{receiver="pager",status="firing"}` stepped to 1 at 06:39:45Z. Without the page, the next person to notice would have been whoever next placed an order, or whoever looked at the checkout dashboard. The flood alone would not have paged this rule, because checkout's error ratio, not frontend traffic, is what crossed the threshold.

## Action Items

| Action Item | Type | Owner | Bug |
|---|---|---|---|
| Keep a P1 on checkout server error ratio and a P1 on checkout server p99 in the same rule group, so a latency-only draw still pages and the two start together | prevent | checkout on-call | ITSM-41 |
| Add a P2 on frontend server rate above 5 times its 30-minute baseline, and on `user_flood_home`, so a homepage flood is visible before it only shows up as checkout noise | mitigate | shop platform | ITSM-42 |
| In the on-call card, the first two queries after a checkout page are payment `charge` error ratio and frontend `GET /` rate, each compared with five minutes before the onset | process | on-call | ITSM-43 |

## Lessons Learned

### What went well

The page named a checkout symptom, and the ticket was acknowledged 50 seconds later. The baseline held: no P1 fired in the ten minutes before the onset. Payment's error ratio and the frontend rate each separated the fault from the quiet shop on the first comparison, so the two flags did not have to be read from a flag document.

### What went wrong

Detection waited on a five-minute error rate, so MTTD was 176 seconds on a fault that was already failing charges. The resource-class flag left no counter we could defend, which means a future draw of the same class can ride along unseen if email does not restart and recommendation does not slow down. The investigator looked only at error counters and concluded the cause was payment, and missed the flood entirely.

### Where we got lucky

The error variant was partial. Three quarters of charges still succeeded, so the shop did not go fully dark, and the eight failures were enough to tell 25% from 10% and from 50%. The flood hit `GET /` and not PlaceOrder, so it did not hide the payment errors inside a latency spike. Checkout p99 never left 50 ms.

## Timeline

All times are UTC on 12 October 2026.

- 06:35:23, the last quiet minute before the onset. `max_over_time` of a firing P1 over the preceding ten minutes is empty. Frontend server rate is about 4/s and payment `charge` has no error series.
- 2026-10-12T06:36:23Z, onset. First sample of `seeded_fault_active` is 1. The run id is c1daa7d0f4acf990. The on-call does not know this instant yet; the injector does not announce it.
- 06:37:30, `user_flood_home` is still 0. By 06:38:30 it is 27 and climbing. Homepage `GET /` is where the extra traffic goes.
- 2026-10-12T06:39:19Z, detection. ShopCheckoutErrors (P1, service checkout) records its first firing sample. MTTD 176 seconds.
- 06:39:45, the pager hook has taken one firing notification.
- 2026-10-12T06:40:09Z, acknowledgement. Ticket 50ceffde-fa49-40b3-b4ca-957734d74bf7, priority P1, title "Shop checkout failing, paged by ShopCheckoutErrors", is acknowledged. It was opened at 06:39:44Z. MTTA 50 seconds.
- 06:40:19, ShopServiceErrors (P2) starts on checkout and on payment. The chat hook does not take a firing notification until 06:44:45Z, the same sample as the pager's resolved notification, which is an inhibition holding the P2 while the P1 is firing.
- 06:42:00, the payment hypothesis is tested. Ledger H1, query `sum(rate(traces_span_metrics_calls_total{service_name="payment",span_name="charge",status_code="STATUS_CODE_ERROR"}[5m])) > 0.01`, returns 0.032/s. The same query at 06:31:23Z returns nothing. Ledger H3, query `sum(rate(traces_span_metrics_calls_total{service_name="checkout",span_kind="SPAN_KIND_CLIENT",span_name="oteldemo.PaymentService/Charge",status_code="STATUS_CODE_ERROR"}[5m])) > 0.01`, returns the same 0.032/s. That is the checkout failure the page reported, and it is the payment call.
- 06:42:00, the flood is measured separately. The investigator never stated it. `sum(rate(traces_span_metrics_calls_total{service_name="frontend",span_kind="SPAN_KIND_SERVER"}[5m]))` is 60.6/s against 4.0/s at 06:31:00Z.
- 06:43:18, `seeded_fault_active` returns to 0. The failing flags are off. Email memory is still 58 MiB and recommendation latency has not grown, so no resource flag is switched on the basis of a guess.
- 2026-10-12T06:44:19Z, recovery. This is the last firing sample of ShopCheckoutErrors, which is the recovery `incident 4` prints. MTTR 476 seconds, counted from the onset, not from the acknowledgement. The pager's resolved notification follows at 06:44:45Z.

## Supporting information

The snapshot is `incident/tsdb-snapshot.tar.gz` and the ticket is `incident/ticket.json`, recording lab4-rec-4, run `c1daa7d0f4acf990`. The four instants are what `itsmlab incident 4` prints from this snapshot and this ticket: the first `seeded_fault_active` sample, the first firing sample of ShopCheckoutErrors, the ticket's `acknowledged_at`, and the recovery of that firing run, each as a UTC second. Durations are the differences of those printed instants.

Impact queries, both instant queries: the charge ratio above, and `sum by (service_name) (rate(traces_span_metrics_calls_total{span_kind="SPAN_KIND_SERVER"}[5m]))` at 06:31:00Z and at 06:41:30Z. Latency was `histogram_quantile(0.99, sum by (service_name, le) (rate(traces_span_metrics_duration_milliseconds_bucket{span_kind="SPAN_KIND_SERVER"}[5m])))`. Email memory was `container_memory_usage_total_bytes{container_name="email"}`, flat at 58 MiB. The ledger is `ai-rca-eval.json`. The transcript is the recorded investigator, model qwen3:4b-instruct. The pager series is `itsm_pager_notifications_total`.

## Problem record

- Incident record: ticket 50ceffde-fa49-40b3-b4ca-957734d74bf7, closed as an incident when ShopCheckoutErrors resolved at 2026-10-12T06:44:19Z
- Root cause: paymentFailure was failing about a quarter of charges, and loadGeneratorFloodHomepage had multiplied frontend traffic by about fifteen; the resource-class flag in this draw was not identified
- Known error: PlaceOrder fails when the payment charge span is set to fail a fraction of calls, and a homepage flood from the load generator does not by itself fail checkout
- Workaround: switch paymentFailure and loadGeneratorFloodHomepage off through the injector and keep them off; do not edit the demo flag file, which the injector overrides
