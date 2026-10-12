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
| Sessions | session/accounting plugins | Session domain + accounting store | Accounting-backed in-process runtime and connection-log persistence implemented / authoritative A1.24 online/login-in-progress state, restart recovery and full source parity pending |
| RADIUS authentication | radius_server/* | Python RADIUS server | Runtime + live UDP wiring implemented / end-to-end parity pending |
| PAP | IBSng RADIUS auth | RADIUS auth pipeline | Implemented / end-to-end parity pending |
| CHAP | IBSng RADIUS auth | RADIUS auth pipeline | Implemented / end-to-end parity pending |
| MS-CHAP | IBSng RADIUS auth/plugin behavior | RADIUS auth pipeline | MS-CHAPv1/v2 + MPPE implemented / end-to-end parity pending |
| Accounting | radius_server/* + accounting plugins | Accounting engine | Start/Stop/Alive + native connection-log + no_connection_log + Charge/Credit runtime + live UDP wiring implemented / live integration parity pending |
| Duplicate requests | IBSng RADIUS request handling | Request deduplication/idempotency | Implemented boundary / full parity pending |
| Disconnect | RADIUS/RAS behavior | RADIUS CoA/Disconnect adapter | RADIUS control packet boundary and session matching implemented; provider side effects and admin HTTP action remain gated/unmounted / full RAS interoperability pending |
| Charging | charge plugins/core | Billing/charge engine | Charge catalog/assignment and Internet/VoIP rule/tariff CRUD implemented; VoIP settlement is wired into accounting Start/Interim/Stop. Bandwidth interface/tree/node/leaf read APIs are implemented. Time-driven VoIP rule/credit events, RAS prefix/min-duration effects, missed-call parity, bandwidth hierarchy/service mutations, live tc shaping and full billing parity remain pending |
| Credit | credit plugins/core | Credit ledger/policy | Foundation |
| Reports | interface/admin/report/* | Report subsystem | Not started |
| Graphs | interface/admin/graph/* | Metrics/graphs | Not started |
| Admin permissions | admin/user management | RBAC/permission service | Source-backed evaluator plus selected admin/user/RAS/VoIP-tariff API workflows implemented; remaining feature workflows pending |
| XML-RPC/IAS | IBSng XML-RPC interfaces and IAS handler | IAS event REST adapter / XML-RPC compatibility adapter | Partial: /xmlrpc transport/auth for the three registered IAS methods and bounded request streaming implemented; full response/error and persistence semantics parity still pending. lockUser/lockAdmin are not registered source methods. |
| Admin UI | interface/admin/* + Smarty | Modern PHP 8 ATD UI | Deferred until backend parity; final stage |
| User UI | interface/user/* + Smarty | Modern user workspace | Deferred until backend parity; final stage |
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


- Provider-critical Cisco, Quintum and MikroTik VSAs: source-derived wire fixtures implemented; full vendor dictionary parity remains open.


## XML-RPC bounded transport verification — 2026-10-12

The request-body limit is now enforced incrementally and before streaming when Content-Length already exceeds 1 MiB. Code/test commit 2b6849b10613ba24354c3296b9c6ed5f17b012f6 passed full CI: 791 tests on Python 3.11 and 3.12, 2 warnings each, including PostgreSQL integration, Ruff, compilation and PHP syntax. Python-only CI passed as well. This verifies transport hardening, not complete XML-RPC/IAS semantic parity.


## Charge visibility parity correction — 2026-10-12

Charge catalog and Internet/VoIP rule-list reads now use A1.24 `Admin.canUseCharge` semantics rather than requiring `ACCESS ALL CHARGES` for every GET. Visible-to-all charges, GOD/ACCESS ALL CHARGES, and exact `CHARGE ACCESS` values are handled through the shared native policy helper. Inaccessible explicit IDs return 403; missing IDs return 404. Code/test commit `7a2d5d15d55b1a74409933851f6eb0c90185b4c3` passed full CI with 795 tests on each Python version, 2 warnings each, including PostgreSQL integration; Python-only CI passed with 787 passed and 8 skipped.


## Charge visibility regression verification — 2026-10-12

Route-level regression tests now exercise charge catalog list/detail and Internet/VoIP charge-rule lists with public, explicitly granted and restricted charges. Code/test commit `28c70624ee362305a313cb9d55518b03a3759389` passed full CI: Python 3.11 and 3.12 each **797 passed, 2 warnings**; Ruff, compilation, PHP syntax and PostgreSQL integration passed (CI run `38230282116`). Python-only workflow passed (run `38230282098`). The behavior remains a focused authorization-parity correction, not full charge/billing completion.


## Verified VoIP accounting settlement increment — 2026-10-12

Code/test checkpoint `98e43155ad63b211c4fd289d9d7a0fd999a40401` passed full CI on Python 3.11 and 3.12: **801 passed, 2 warnings per job**, including Ruff, Python compilation, PHP syntax and PostgreSQL integration (CI run `38284989251`). Python-only CI passed **793 passed, 8 skipped, 2 warnings** (run `38284989298`).

Added A1.24-shaped VoIP settlement to the live Accounting-Request lifecycle: user-type routing selects normal versus VoIP charging; VoIP rules are selected with called-number tariff-prefix applicability; free seconds are consumed from the initial prefix; rule changes accrue the outgoing tariff without rounding; final settlement applies the active prefix's minimum-chargeable-duration/round-to formula and updates user credit. Interim accounting attributes are merged so a called number acquired after Start becomes available to the charging selector.

This is a verified runtime settlement increment, **not complete VoIP billing parity**. Still open: time-driven rule-transition/credit-exhaustion scheduling, source-specific RAS kill and prefix/min-duration attributes, missed-call semantics, authoritative provider call start/end times, restart-safe call state, complete credit/audit transaction parity, and full end-to-end RAS tests. UI and installer remain last.


## Verified bandwidth-manager read API increment — 2026-10-12

Code/test checkpoint `5429fde6d17249568277c143c21e98732f1a427e` passed full CI on Python 3.11 and 3.12: **804 passed, 2 warnings per job**, including Ruff, compilation, PHP syntax and PostgreSQL integration (CI run `38285636476`). Python-only CI passed **796 passed, 8 skipped, 2 warnings** (run `38285636565`).

Added source-backed reads for the native bandwidth interface catalog, interface tree, node details and existing leaf catalog/detail. The tree reproduces A1.24's recursive node/leaf structure, uses native `bw_interface`, `bw_node`, and `bw_leaf` tables, preserves leaf names and hierarchy order, returns 404 for missing interfaces/nodes or interfaces without a root, and detects corrupted parent cycles instead of recursing indefinitely.

This is read-only groundwork for the deferred UI. Interface/node/leaf/service mutations, validation parity, live traffic-control (tc) effects and reload/rollback behavior remain pending; no bandwidth shaping is claimed complete.
