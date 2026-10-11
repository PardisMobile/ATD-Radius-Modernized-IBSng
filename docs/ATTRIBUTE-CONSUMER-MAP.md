# IBSng Attribute Consumer Map

This document is the working bridge between the A1.24 attribute catalog and the modern ATD policy engine.

## Rule

An attribute is **not migrated** merely because its name exists in the catalog. It becomes migrated only when its producer, consumer, persistence, enforcement path, and compatibility test are mapped.

| IBSng attribute | ATD boundary | Consumer / enforcement target | Status |
|---|---|---|---|
| `ippool` | Policy | IP allocation service | implemented; integration pending |
| `assign_ip` | Policy | IP allocation service | implemented; integration pending |
| `multi_login` | Policy | Session admission / concurrency guard | implemented; source-semantic acceptance tests added |
| `session_timeout` | RADIUS policy | `Session-Timeout` + session enforcement | catalogued; mapping pending |
| `idle_timeout` | RADIUS policy | `Idle-Timeout` + session enforcement | catalogued; mapping pending |
| `save_bw_usage` | Snapshot/accounting policy | periodic per-instance bandwidth sampler and `internet_bw_snapshot` consumer | RADIUS accounting delta integration implemented; source-equivalent periodic sampling and missed-update parity pending |
| `fast_dial` | VoIP call routing | called-number rewrite / redirect-number reply | mutation/storage and admin action API implemented; production VoIP runtime redirection pending |
| `normal_charge` | Billing policy | charge resolver | catalogued; implementation pending |
| `voip_charge` | Billing policy | charge resolver | catalogued; implementation pending |
| `radius_attrs` | Protocol policy | RADIUS attribute mapper | catalogued; implementation pending |
| `caller_id` | Authentication policy | caller-ID admission check | catalogued; implementation pending |
| `limit_caller_id` | Authentication policy | caller-ID admission check | catalogued; implementation pending |
| `limit_mac` | Authentication policy | station/MAC admission check | catalogued; implementation pending |
| `limit_station_ip` | Authentication policy | station-IP admission check | catalogued; implementation pending |
| `rel_exp` | Account lifecycle | expiry calculator | catalogued; implementation pending |
| `abs_exp` | Account lifecycle | expiry calculator | catalogued; implementation pending |
| `lock` | Authentication policy | account admission guard | catalogued; implementation pending |

### RAS-side MultiLogin

`RAS_DOESNT_ALLOW_MULTILOGIN` is an IBSng login error produced after the per-user `multi_login` limit is evaluated. The RAS capability comes from the RAS implementation's `RasMsg["multi_login"]` flag; where that flag is absent, IBSng treats the RAS as allowing multi-login. ATD resolves verified RAS attributes/types into the same effective decision before the RADIUS acceptance boundary.

## Migration states

- `catalogued`: name/type/scope information is known.
- `mapped`: producer and consumer are identified.
- `implemented`: ATD behavior exists.
- `verified`: compatibility fixture demonstrates equivalent behavior.
- `migrated`: all required stages are complete.

The project must not mark an attribute `migrated` based only on schema presence.


### Fast-dial runtime foundation — 2026-10-11

The new `domain/fast_dial.py` helper covers source-shaped prefix/index selection, instance index mutation and a redirect callback, with separate native actions-manager slot validation. It is not yet invoked by the production VoIP/RAS message lifecycle. Keep the consumer state as **runtime integration pending**, not implemented/verified. See `docs/A1.24-FAST-DIAL-RUNTIME-AUDIT.md`.


### Fast-dial action API — 2026-10-12

A1.24-compatible admin API GET/PUT operations now read or update one fast-dial slot by VoIP username. The write path validates digits-only destinations and indexes 0–9, locks the user row against concurrent slot writes, preserves native user-audit suppression, and writes operational audit. The production RAS `s_login`/`s_update` redirect side effect and per-instance metadata lifecycle are still pending; this attribute is not yet fully migrated.


### Bandwidth snapshot consumer — 2026-10-12

The RADIUS accounting runtime now writes counter deltas into the native `internet_bw_snapshot` table only for normal users whose effective attributes include `save_bw_usage`; group defaults are inherited and user attributes override group values. The write path aggregates deltas into one-minute buckets. This is a first production consumer integration, but its event-driven sampling differs from A1.24's periodic per-instance online loop. Keep full parity pending until missed Interim-Updates and provider counter behavior are validated.


Verification update — 2026-10-12: the implementation/test commit `f97af48b94204ac2e7d6065d522c29d2583dc76e` passed full CI on Python 3.11 and 3.12 (694 passed, 2 warnings per matrix job). The docs-only checkpoint `f87a63cf46c6b271d6efdcc2a7d80af2d649c760` also passed both full and Python-only CI: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38180343444 and https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38180343421. State remains partial because the source uses periodic per-instance polling while ATD currently uses RADIUS counter deltas.


### Source-content review correction — 2026-10-12

Direct review of `IBSng/core/user/plugins/save_bw_usage.py`, `IBSng/core/snapshot/bw_snapshot.py`, `IBSng/core/snapshot/snapshot_main.py`, `IBSng/core/snapshot/onlines_loop.py`, and `IBSng/core/snapshot/snapshot_searcher.py` confirms the marker is consumed by a periodic online-instance loop, not by the plugin itself. The consumer samples `getInOutBytes(instance)`, aggregates positive rates by user for that loop, and inserts timestamped rows into `internet_bw_snapshot`; the report sums `in_rate` and `out_rate` grouped by `snp_date`. ATD's accounting-delta consumer is therefore a different sampling model and cannot be labeled full parity. Preserve this explicit limitation until periodic sampling or a source-tested equivalent is implemented.
