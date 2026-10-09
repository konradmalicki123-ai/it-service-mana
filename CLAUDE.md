# svcdesk agent notes

Work from REQUIREMENTS.md, API.md and METRIC-SPEC.md. Where an assistant's definition and METRIC-SPEC.md disagree, METRIC-SPEC.md wins.

The three conflict resolutions are already chosen and must not be flipped: C1 wallclock, C2 immutable, C3 vip. They are recorded in specs/spec.md and DECISIONS.md and the running service has to exhibit those same values.

Do not add a host-path bind mount. Do not install dependencies at container start. Do not put hostnames, usernames or doctor output in this repository.
