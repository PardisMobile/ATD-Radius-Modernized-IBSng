# IBSng Attribute Consumer Map

This document is the working bridge between the A1.24 attribute catalog and the modern ATD policy engine.

## Rule

An attribute is **not migrated** merely because its name exists in the catalog. It becomes migrated only when its producer, consumer, persistence, enforcement path, and compatibility test are mapped.

| IBSng attribute | ATD boundary | Consumer / enforcement target | Status |
|---|---|---|---|
| `ippool` | Policy | IP allocation service | catalogued; implementation pending |
| `assign_ip` | Policy | IP allocation service | catalogued; implementation pending |
| `multi_login` | Policy | Session admission / concurrency guard | catalogued; implementation pending |
| `session_timeout` | RADIUS policy | `Session-Timeout` + session enforcement | catalogued; mapping pending |
| `idle_timeout` | RADIUS policy | `Idle-Timeout` + session enforcement | catalogued; mapping pending |
| `save_bw_usage` | Accounting policy | usage recorder | catalogued; implementation pending |
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

## Migration states

- `catalogued`: name/type/scope information is known.
- `mapped`: producer and consumer are identified.
- `implemented`: ATD behavior exists.
- `verified`: compatibility fixture demonstrates equivalent behavior.
- `migrated`: all required stages are complete.

The project must not mark an attribute `migrated` based only on schema presence.
