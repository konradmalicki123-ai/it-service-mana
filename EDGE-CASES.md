---
lab2_edge_cases:
  E1: {rule: R-08, count: 3}
  E2: {rule: R-06, count: 2}
  E3: {rule: R-09, count: 4}
  E4: {rule: R-10, count: 4}
  E5: {rule: R-12, count: 1}
  E6: {rule: R-13, count: 11}
---
<!-- ai-generated: 80% - assistant wrote the six sections from METRIC-SPEC.md and from the counts the service returns for the practice fixture -->

# Edge cases in the practice event log

## E1 - clock skew produces a negative lead time

- What the log contains: Three commits are timestamped after the successful production deployment that shipped them, so a raw subtraction of the two instants is negative.
- What a default definition would have done: Drop those pairs, or leave a negative duration in the median. The person reading the dashboard would either lose three real deliveries or see a lead time that cannot be explained to a manager.
- Why the rule is defensible: The deployment did happen and the change did ride on it. Clamping the pair to zero keeps it in the median and in the count of pairs, and `anomalies.negative_lead_time_pairs` says the clocks disagreed. Hiding the pair would make delivery look smaller than it was.

## E2 - a revert of a revert

- What the log contains: Two commits have a non-null `reverts`. One of them reverts a commit that is itself a revert, so the chain walks back to the original change.
- What a default definition would have done: Treat every commit, including each revert, as a new change. The dashboard would show three changes where the team did one piece of work and then undid and redid it.
- Why the rule is defensible: A revert is not a new unit of work. R-06 gives it the change_id of the commit it reverts, transitively, so a revert of a revert is the original change again. `revert_chains_collapsed` counts the commits that brought no change of their own. The reader sees one change, not the mechanics of the rollback.

## E3 - a hotfix that never touched main

- What the log contains: Four commits that reached a production deployment in the window have a branch other than `main`. They are hotfixes that never landed on the trunk.
- What a default definition would have done: Count only commits whose branch is `main`. Those four production changes would vanish from lead time, and the dashboard would say the hotfix never reached users.
- Why the rule is defensible: What reached the user is the production deployment, not the name of the branch. R-09 ignores `branch` for the pair and only records the off-trunk shas as `commits_never_on_main`. A reader who filtered on `main` would under-count a Friday hotfix.

## E4 - a deployment with zero linked commits

- What the log contains: Four production deployments in the window have an empty `commits` array. They are real deployment events with nothing attached.
- What a default definition would have done: Skip any deployment that has no commits, because there is nothing to subtract for lead time. Frequency, the fail rate and the rework rate would all lose those four events.
- Why the rule is defensible: Lead time needs a commit, so an empty deployment contributes no pair. It still happened, so R-10 keeps it in the deployment counts and in both rate denominators. Dropping it would let a team hide a failed or unplanned deploy by shipping it with an empty commit list.

## E5 - a deployment that failed and never recovered

- What the log contains: One failed production deployment in the window has no recovery instant. No covering incident resolves it.
- What a default definition would have done: Invent a recovery at the end of the window, or drop the failure from the fail rate as well as from the median. The dashboard would show a closed incident that is still open, or it would hide the failure.
- Why the rule is defensible: R-12 refuses to invent a duration. The open failure stays out of the recovery median and is counted in `open_failures`, and R-14 still counts it in the change fail rate. The reader sees an outage that has not ended, which is the fact they need.

## E6 - overlapping incidents

- What the log contains: Eleven unordered pairs of incidents have intervals that intersect. An open incident runs to the end of the window. One incident can name more than one failed deployment.
- What a default definition would have done: Merge the overlapping intervals, or add their durations together, and report one recovery for the pile. Two failures covered by one incident would be counted once, or the same hour would be added twice.
- Why the rule is defensible: Recovery belongs to the failed deployment, not to a merged blob of incidents. Both deployments take the same resolved instant from the one covering incident, and the overlap is reported rather than summed. The reader can see that two incidents were in flight together without the median being doubled.

## Gaming demonstration

The metric I improved is `deployment_frequency_per_day`, and the rule I used is R-11. Frequency is a count of production deployments in the window divided by the length of the window. It does not ask whether a deployment carried a change. I added twelve successful production deployments inside the window, each with an empty commit list, which R-10 says still counts. Frequency moves from 2.0 to about 2.57 per day, which is more than the 25 percent margin. The same extra deployments also dilute the change fail rate and the rework rate, because the denominator grows and the numerator does not. That is the same trick, not a second one.

The harm is on the work that was already in the log. R-19 lets me change the `commits` of a deployment and forbids deleting the deployment or flipping its outcome. I cleared `commits` on every successful production deployment that sat inside the window. Those deployments are still in the frequency count, but the changes they used to carry no longer reach production on a successful deployment, so `ground_truth.changes_delivered` for the original shas falls from 65 to 0. The checker's R-21 filter, which throws away any sha I might have added, still sees that drop. Lead time for the original work is no longer even defined, because nothing of it is delivered.

A team whose target is deployment frequency will split one release into several, or record a deploy that shipped no change, because each extra row is a better week. The person rewarded is whoever is scored on that frequency: the team lead, or the engineer whose board shows deploys per day. The person who loses is the one reading the dashboard as if it were delivered change, and the customer still waiting on the changes that the record no longer attaches to a successful deploy.
