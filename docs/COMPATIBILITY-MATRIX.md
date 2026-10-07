# IBSng A1.24 → ATD Compatibility Matrix

This is the master parity ledger. A feature is not considered migrated merely because a similarly named model or endpoint exists. The implementation must preserve behavior, data, permissions and operator workflow.

## Rules
- Every IBSng capability gets a stable ATD capability ID.
- Source location is recorded before conversion.
- Core behavior, persistence, protocol behavior and UI workflow are tracked separately.
- A capability reaches Complete only when implementation and tests demonstrate parity.
- Additive ATD features (currently EAP and modern UX) are marked as ATD-only.

## Current high-level ledger

| Capability | IBSng A1.24 reference | ATD target | Status |
|---|---|---|---|
| User identity | core/user/* | domain.User + user repositories/services | In progress |
| User attributes | user/plugin attribute system | Typed Attribute Policy Engine | Implemented boundary / parity fixtures pending |
| Group policy | core/group/* and group plugins | Group policy + resolver | In progress |
| Service policy | service/plugin behavior | Service policy + resolver | In progress |
| RAS/NAS | core/ras/*, radius_server/* | RAS registry/adapters | Runtime registry + live packet lookup + source-derived provider profiles implemented / provider-specific behavior parity pending |
| IP pools | core/ippool/* | Transaction-safe allocator | Native membership repository + A1.24-compatible runtime allocation / claim / release; Access/session lifecycle integration pending |
| Sessions | session/accounting plugins | Session domain + accounting store | Runtime implemented / persistence and source parity pending |
| RADIUS authentication | radius_server/* | Python RADIUS server | Runtime + live UDP wiring implemented / end-to-end parity pending |
| PAP | IBSng RADIUS auth | RADIUS auth pipeline | Implemented / end-to-end parity pending |
| CHAP | IBSng RADIUS auth | RADIUS auth pipeline | Implemented / end-to-end parity pending |
| MS-CHAP | IBSng RADIUS auth/plugin behavior | RADIUS auth pipeline | MS-CHAPv1/v2 + MPPE implemented / end-to-end parity pending |
| Accounting | radius_server/* + accounting plugins | Accounting engine | Start/Stop/Alive + native connection-log + no_connection_log + Charge/Credit runtime + live UDP wiring implemented / live integration parity pending |
| Duplicate requests | IBSng RADIUS request handling | Request deduplication/idempotency | Implemented boundary / full parity pending |
| Disconnect | RADIUS/RAS behavior | RADIUS CoA/Disconnect adapter | Runtime implemented / full parity pending |
| Charging | charge plugins/core | Billing/charge engine | Internet charge runtime implemented / broader billing persistence parity pending |
| Credit | credit plugins/core | Credit ledger/policy | Foundation |
| Reports | interface/admin/report/* | Report subsystem | Not started |
| Graphs | interface/admin/graph/* | Metrics/graphs | Not started |
| Admin permissions | admin/user management | RBAC/permission service | Foundation |
| XML-RPC/IAS | IBSng XML-RPC interfaces | Compatibility adapter | Not started |
| Admin UI | interface/admin/* + Smarty | Modern PHP 8 ATD UI | In progress |
| User UI | interface/user/* + Smarty | Modern user workspace | In progress |
| EAP | Not present in A1.24 | EAP subsystem | ATD-only / foundation |

## Attribute policy milestone
The attribute system is a first-class compatibility surface. The modern engine keeps scope/provenance, deterministic precedence, typed values, multi-valued attributes, explicit set/add/remove/replace operations and explainability. The compatibility gate remains source-derived fixtures for user/group/RAS load and mutation behavior.

## Database compatibility
The final migration target is lossless restoration of an IBSng backup into ATD semantics. No subsystem is complete until schema mapping, persistence, behavior and migration evidence agree.

## Completion gate
No subsystem is marked complete until its source inventory, ATD implementation, database mapping, permissions, UI workflow and automated/integration tests are linked from this document or its subsystem ledger.


### 2026-10-07 Dictionary parity update
- Core wire attribute catalog expanded from the earlier subset to the source-defined A1.24 standard attributes used by AAA/Accounting, including EAP-Message, Acct-Interim-Interval, Gigawords, IPv6 and Digest attributes.
- Microsoft RFC 2548 VSA catalog expanded for MS-CHAP error/ARAP/accounting/EAP and DNS/NBNS attributes.
- Full legacy/vendor dictionary parity remains open; Cisco, Quintum, MikroTik and USR vendor catalogs still require adapter-specific wire fixtures before being marked complete.
