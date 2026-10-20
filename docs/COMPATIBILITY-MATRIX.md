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


## Verified VoIP prefix metadata checkpoint — 2026-10-12

Code/test commit `865932176d49e231e59a4b53594d3d990cee4724` passed full CI run `38286353453`: Python 3.11 and 3.12 each **806 passed, 2 warnings**, including Ruff, compilation, PHP syntax and PostgreSQL integration. Python-only CI run `38286353345` passed: **798 passed, 8 skipped, 2 warnings**.

On first matching VoIP prefix, settlement now persists native `min_duration` and `prefix_name` into session attributes, as A1.24's VoIP charge-rule start path does. If Called-Station-Id arrives after Accounting-Start, free seconds are reduced by elapsed time from the original session start instead of restarting the free allowance. Two regression tests cover initial metadata and delayed called-number acquisition.

This does not complete VoIP call-time sourcing, missed-call treatment, scheduled rule/credit boundaries, RAS effects or restart-safe billing state.


## Verified VoIP missed-call threshold — 2026-10-12

Source trace: `IBSng/core/user/voip_user.py::logout` sets usage to zero and the kill reason to `Missed Call` when `disconnect_time - connect_time < instance_info["min_duration"]`. This threshold is distinct from `min_chargable_duration` and `round_to`, which are billing-rounding controls.

Code/test commit `9b0fafcfc818fd855fd706c88ecedd3c867daa4b` passed full CI run `38287188581`: Python 3.11 and 3.12 each **808 passed, 2 warnings**; Ruff, compilation, PHP syntax and PostgreSQL integration passed. Python-only run `38287188578` passed **800 passed, 8 skipped, 2 warnings**.

ATD VoIP settlement now applies the first matching prefix's native `min_duration` during final settlement, charges zero for a call shorter than that threshold, and marks the in-memory session as a missed call. Regression tests cover below-threshold and exact-threshold durations. The normal zero-credit settlement call is preserved, matching the source's `used_credit = 0` path when a successful authenticated call is committed.

Scope remains deliberately limited: this check currently uses the Accounting lifecycle's observed start/end times (and original session start when called-number metadata arrives late). Exact RAS-provided `connect_time`/`disconnect_time` parsing, provider-specific kill-reason propagation, timer-driven `checkLimits` events, restart-safe session state, and end-to-end RAS validation remain open. Do not mark VoIP parity complete; UI and installer remain deferred.


## Verified RAS call-time support for missed-call threshold — 2026-10-12

Source trace: `IBSng/core/ras/voip_ras.py::setH323TimeInAttrs` converts H.323 connect/disconnect times to epoch values; provider implementations map these to `connect_time` and `disconnect_time`. `IBSng/core/user/voip_user.py::logout` compares those values against the prefix `min_duration`.

Code/test commit `37c6d26ae3e964687962ce91ce443e394c1a70a9` passed full CI run `38287573708`: Python 3.11 and 3.12 each **809 passed, 2 warnings**, with Ruff, compilation, PHP syntax and PostgreSQL integration passing. Python-only run `38287573799` passed **801 passed, 8 skipped, 2 warnings**.

When RAS epoch timestamps are available, the VoIP settlement now prefers them for call-start free-second initialization and for deciding whether a call is shorter than `min_duration`; malformed/missing values fall back safely to the observed accounting timestamps. A regression test verifies that an observed 30-second accounting interval is still treated as a missed call when authoritative RAS connect/disconnect times indicate a 7-second call.

Boundary: this increment does **not** yet recompute all billing from RAS call times across historical rule transitions or implement the native asynchronous `checkLimits` scheduler/provider kill path. Those require a restart-safe call event model and provider-backed lifecycle tests. VoIP billing parity remains incomplete; UI and installer remain deferred.


## Verified non-lazy VoIP settlement from RAS call times — 2026-10-12

Direct source trace against the canonical A1.24 archive: `IBSng/core/charge/voip_charge.py::calcInstanceCreditUsageFromStart` recalculates a non-lazy call from RAS connect time, starts billing after the first prefix's free seconds, walks the effective rule intervals, sums each interval's prefix CPM, and applies final-prefix minimum-chargeable-duration/rounding to the whole call. `IBSng/core/user/voip_user.py::logout` supplies RAS connect/disconnect timestamps before committing usage.

Code/test commit `111f8adc590f755ae62f974a7b46c2fa288e38b7` passed full CI run `38289856978`: Python 3.11 and 3.12 each **810 passed, 2 warnings**, including Ruff, compilation, PHP syntax and PostgreSQL integration. Python-only run `38289856903` passed **802 passed, 8 skipped, 2 warnings**.

When both RAS timestamps and the called number are available, ATD now recalculates the entire call across effective rule interval ends rather than relying on Accounting packet timing; free seconds are applied once at call start. A regression test spans a 11:00 rule boundary and proves 10 seconds at CPM 60 plus 10 seconds at CPM 120 yields 30 credit units even when Accounting-Stop arrives later. RAS times are converted using the host's local timezone for rule/day selection, matching the legacy epoch/time-of-day model.

Remaining limits: this is source-shaped non-lazy settlement, not full VoIP parity. Exact handling of overlapping rule start boundaries, asynchronous `checkLimits` credit/free-seconds scheduling and RAS kill actions, restart-safe state, and provider-backed end-to-end call fixtures remain open. UI and installer remain deferred.


## Verified first-prefix metadata after late Accounting start — 2026-10-12

Follow-up regression coverage confirms that when Accounting-Start arrives after a tariff transition, the call's `min_duration` and `prefix_name` are taken from the effective prefix at the authoritative RAS connect time, not from the rule active when accounting began. This keeps the missed-call threshold consistent with the same first-prefix semantics used for the source's free-second allowance.

Code/test commit `a0e232b0ab664246f1576c4e9f6bf3c54e5a64c8` passed full CI run `38290092747`: Python 3.11 and 3.12 each **811 passed, 2 warnings**, including Ruff, compilation, PHP syntax and PostgreSQL integration. Python-only run `38290092706` passed **803 passed, 8 skipped, 2 warnings**. Full non-lazy RAS-time calculation checkpoint: `111f8adc590f755ae62f974a7b46c2fa288e38b7` (full CI run `38289856978`, 810 passed per Python version).


## Runtime composition parity — 2026-10-14

The one-transaction `build_native_radius_runtime()` helper now wires the same user-type-aware charging composition as production UDP packets: normal users use Internet charging and VoIP users use VoIP tariff/prefix settlement. Previously the helper passed `InternetChargeSettlement` directly, so VoIP Accounting behavior differed depending on which supported runtime composition was used. A regression test asserts both settlement implementations are composed and routed by `UserChargeSettlement`. This fixes composition consistency only; timer-driven VoIP `checkLimits`, RAS kill effects, and restart-safe state remain open.


## Verified VoIP connection-log timestamps — 2026-10-14

Verified code/test checkpoint `be3ba58e27eab49e92f1e47eef4b2f523c619588`: native accounting persistence maps valid RAS connect_time/disconnect_time epoch attributes to native connection-log login/logout timestamps, matching A1.24 VoipUser call-time behavior even when charging is not configured. Invalid/missing times preserve existing fallbacks. Full CI passed: Python 3.11 and 3.12 each **814 passed, 2 warnings**, including PostgreSQL integration, Ruff, compilation and PHP syntax (run [38473850387](https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38473850387)). Python-only CI passed **806 passed, 8 skipped, 2 warnings** (run [38473850375](https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38473850375)); skipped tests require live UDP/PostgreSQL integration not configured in that workflow. Timer-driven `checkLimits`, provider-specific RAS kill effects and restart-safe VoIP state remain open.


## Source-backed VoIP limit planner increment

Added a tested `next_limit_event_seconds` decision primitive for A1.24 `VoipCharge.checkLimits` boundaries (rule end, more-applicable rule, initial free seconds and credit exhaustion). Three regression tests were added. It does not claim timer lifecycle, multilogin aggregation or provider termination parity; those remain open.


## Multi-instance VoIP limit planning increment — 2026-10-14

Added `next_limit_event_seconds_for_sessions`, which aggregates CPM across active calls before computing credit exhaustion, while preserving the earliest per-call rule/free-seconds boundary. A regression test covers two simultaneous CPM-60 calls against 10 units of credit. Production timer scheduling, per-instance kill reasons, RAS provider termination and restart recovery remain open.


The multi-instance limit-planning increment and future more-applicable-rule boundary test passed full CI run [38524146446](https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38524146446): Python 3.11 and 3.12 each **819 passed, 2 warnings**; Ruff, compilation, PHP syntax and PostgreSQL integration passed. Python-only run [38524145969](https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38524145969) passed **811 passed, 8 skipped, 2 warnings**.


## VoIP limit-plan decision increment — 2026-10-14

Added a per-session RAS/port context resolver for multi-call planning and `VoipLimitPlan` structured decisions for immediate credit-finished/no-effective-rule outcomes. Regression tests cover all charged calls when credit is exhausted and selective no-rule kill decisions. This is not provider execution or a production timer loop.


Latest VoIP limit-plan decision increment `43325d2c1cb71815c3bd85854e512c41eacdf3c0` passed full CI run [38524638385](https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38524638385): Python 3.11 and 3.12 each **821 passed, 2 warnings**; Ruff, compilation, PHP syntax and PostgreSQL integration passed. Python-only run [38524638404](https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38524638404) passed **813 passed, 8 skipped, 2 warnings**.


## VoIP time-driven enforcement status — 2026-10-15

The domain planner now has an application-level scheduler and per-user limit-loop orchestration primitive, with tests for timer lifecycle, next-boundary rechecks and per-session kill-reason forwarding. Status remains **partial** until the production RADIUS runtime supplies fresh-transaction planning, source-specific provider actions, durable/recoverable session state and end-to-end RAS parity tests. The existence of these primitives is not evidence that A1.24 `VoipCharge.checkLimits` is fully implemented.


## RAS termination implementation status — 2026-10-15

Source-specific ChilliSpot and MVTS Disconnect-Request adapters are implemented and unit-tested, including A1.24's MVTS zero-filled response-authenticator exception. The timer engine and limit-loop orchestration are present but not wired into production. All other provider termination mechanisms and restart-safe enforcement remain **partial/not implemented**; provider profile metadata alone does not count as termination parity.


VoIP kill decisions now preserve full `SessionKey` identity rather than only the provider's session string. This is required to distinguish sessions across users/RASes. Unsupported provider actions fail closed and do not enter an aggressive retry loop. Full runtime wiring and restart-safe enforcement remain partial.


## VoIP enforcement implementation status — 2026-10-15

The recurring loop is now wired to the native RADIUS Accounting runtime and recomputes limit plans in fresh DB transactions. Native user-type routing labels each session's charge kind; termination targets a full `SessionKey`. The real VoIP provider termination path currently covers MVTS only. Other VoIP provider kill actions, durable restart recovery and end-to-end RAS interoperability remain **partial/not implemented**. CI for the current integration is pending.

## MVTS source-identity correction — 2026-10-15

A source re-check of `IBSng/core/ras/rases/mvts.py::killUser` found that A1.24 builds Disconnect-Request `User-Name` from the user's `voip_username` attribute, not necessarily the inbound RADIUS `User-Name`/normal IBSng login. The production VoIP termination path now resolves `voip_users.voip_username` through the native user repository in the same fresh transaction and uses it for MVTS; a missing VoIP credential fails closed as a permanent configuration gap instead of sending a disconnect for the wrong identity. Regression coverage verifies the provider sees the source-required username. This is a targeted parity correction, not full provider or restart-recovery completion.



## Provider-specific active-session identity recovery — 2026-10-17

Restart recovery now resolves the session registry key through the same `provider_session_id()` function used by live Accounting, including the source-defined RAS identity (`NAS-Port`, `H323-conf-id`, `call_id`, and provider-specific variants) before the standard `Acct-Session-Id` fallback. This prevents recovered MikroTik/Cisco/VoIP sessions from being keyed under an Accounting identifier when A1.24 indexes the online instance by a different provider identity. Regression tests cover the provider-specific identity precedence for a port-based Internet RAS and an MVTS VoIP call. This advances restart recovery; durable charging accumulators and downtime accounting remain open.



## Access-Accept IP lease lifecycle — 2026-10-17

Native IP-pool allocation now marks addresses allocated by the production Access-Request policy as pending reservations tied to the source RAS identity and username. A matching Accounting-Start adopts the reservation into the live session; an explicit later policy rejection releases a still-pending allocation; and unadopted reservations expire after a bounded five-minute grace period. Expiration runs on incoming RADIUS traffic and before subsequent allocations, preventing abandoned Access-Accept allocations from consuming pool capacity indefinitely. Ownership mismatch does not silently transfer a pending address to another username. Regression tests cover adoption, expiry, release ordering, ownership mismatch and production context wiring. Full live-NAS interoperability and race behavior under high concurrency remain open.


## Native connection_log service classification — 2026-10-17

Accounting events now retain the resolved RAS service family through the application boundary, and `NativeAccountingPersistence` maps Internet to native service ID 1 and VoIP to native service ID 2. This corrects the prior behavior where every new native connection log was written with service=1. Tests cover MVTS runtime classification and VoIP persistence. Full live RAS/accounting parity remains open.


## Service-aware provider identity consistency — 2026-10-17

The live Accounting path now supplies the resolved service family to provider identity resolution, as restart recovery already does. This preserves Cisco's source-defined distinction between Internet port identity and VoIP H.323 call identity. A runtime regression test covers Cisco VoIP identity precedence. Provider transport and full Cisco RAS interoperability remain open.


## Cisco dual-service Accounting routing — 2026-10-17

Service selection for Cisco Accounting now follows the A1.24 packet discriminator (`Framed-Protocol == PPP` → Internet; otherwise VoIP branch) instead of incorrectly treating all Cisco packets as Internet because of the RAS type alone. The resolved service is then passed into provider identity selection, so Cisco VoIP uses the H.323 call identity. Tests cover the source discriminator and runtime session identity. Full Cisco accounting, call-type/origin filtering and RAS interoperability remain open.


Restart recovery uses the same service-aware provider identity resolver as live Accounting, including Cisco's source-defined H.323 identity for VoIP rows. Regression coverage verifies Cisco VoIP recovery when the record also contains a NAS-Port value.


## Accounting decoder-shape normalization — 2026-10-17

Accounting scalar extraction now accepts both scalar and list/tuple decoder representations and consistently consumes the first value, as source call sites do for single-value RADIUS fields. Tests cover identity, Cisco service selection fields, IP and octet counters. This is scalar-shape compatibility only; full multi-valued vendor attribute handling remains open.


Cisco VoIP accounting now applies source-derived call-type/origin guards for Start/Stop and suppresses VoIP Alive from the charge lifecycle. The special pre-authenticated Telephony/answer Stop path remains intentionally unsupported until its H.323 authorization-ID state is implemented.


Cisco identity handling follows the native A1.24 packet representation: Internet uses Cisco-NAS-Port or NAS-Port-Type plus NAS-Port; VoIP H.323 IDs and call-leg discriminators strip the legacy name=value prefix. This correction is scoped to identity/discriminator normalization and does not claim full Cisco RAS parity.


Cisco provider session identity is strict to A1.24 source keys. Internet requires Cisco-NAS-Port or the NAS-Port-Type + NAS-Port composition; VoIP requires H.323 conference ID. If those are absent, runtime identity resolution returns no session key instead of falling back to Acct-Session-Id or an unrelated port.


Cisco VoIP's strict identity extraction uses only Cisco-supported H.323 conference-ID aliases. The generic Acct-Session-Id fallback remains available to provider profiles whose A1.24 implementation defines it, but is excluded from Cisco's branch.


## Production VoIP termination adapters

Cisco's configured SNMP/RSH termination branch and PortMaster/Total Control SNMP disconnects are now wired to the production SourceRASDisconnectClient. This does not imply that all provider profiles have executable kill behavior: Asterisk/GnuGK/SER, Cisco VPDN, MikroTik, PortSlave/PPPD and other source-specific operations still require their own production wiring and integration evidence.


## VoIP enforcement — PortSlave and PPPD launcher paths (pending CI)

Source-defined `Portslave` and `pppd` `killUser` operations are wired to the bounded configured-launcher transport using the native command attributes and `(RAS-IP, port)` argument order. A failed/non-confirmed launcher result is not treated as a successful disconnect. Unit regression coverage is added; live NAS/provider interoperability remains unverified.


## RAS termination response acceptance (pending current CI)

Cisco, PortMaster, Total Control, PortSlave, and PPPD termination paths now validate transport success explicitly. SNMP requires a non-empty all-success response sequence; launcher-backed paths require a successful exit; absent, empty, failed, and unrecognized results are rejected. This improves result integrity but does not yet prove that a remote session has disappeared after an accepted command.


## GnuGk status-port termination — source-traced, command-delivery only

Canonical source: `IBSng/core/ras/rases/gnugk.py::GnuGKRas.killUser`. A1.24 only opens the status-port connection when `gnugk_multiple_login` is enabled, defaults `gnugk_status_port` to 7000, waits for a semicolon prompt, sends `disconnectalias <voip_username>`, then sends `exit`. ATD now executes that exact sequence through a bounded TCP connection, requires the source-defined VoIP alias, rejects control characters, validates the port, and fails closed if the prompt is absent/oversized or the transport errors. Tests cover command order, custom port, gate-off behavior, missing identity, invalid port, command injection and prompt failure. A completed write is not proof that the remote call disappeared; independent session verification and live GnuGk interoperability remain open.


## GnuGk runtime identity integration

The production limit-enforcement callback now resolves the native `voip_username` from the user repository before calling the GnuGk adapter, rather than assuming the RADIUS/IBSng login is the Gatekeeper alias. MVTS retains its source-specific User-Name override. A runtime regression verifies the GnuGk session keeps the original inbound User-Name while passing the database-resolved alias separately as `voip_username`.


## Production termination expansion — MikroTik and Cisco VPDN

Canonical A1.24 source paths: `IBSng/core/ras/rases/mikrotik.py::killUser` and `IBSng/core/ras/rases/cisco_vpdn.py::killUser`. Both kill paths are connected to production VoIP-limit enforcement. MikroTik resolves the native normal username, requires the session IP and NAS-Port-Type, preserves the source split between Wireless-802.11 hotspot removal and PPP active-session removal, and uses configured SSH wrapper credentials through bounded RSH. Cisco VPDN resolves the normal username and source remote IP, performs `show caller user` interface discovery, selects the matching interface when an IP is available (source behavior: first match if absent), then runs `clear interface`. Both require explicit transport success and fail closed on missing identity/configuration. Regression tests cover provider dispatch and runtime identity resolution. Live NAS interoperability and independent proof of session disappearance remain unverified.


## Internet session limit enforcement — source-shaped planning

Canonical source: `IBSng/core/charge/internet_charge.py::checkLimits` and `IBSng/core/charge/charge.py::_getNextMoreApplicableRuleForTime`. Normal-user sessions now share the existing per-user timer worker with VoIP sessions. The Internet planner handles exhausted credit, per-session missing effective rules, aggregate concurrent-instance time/assumed-transfer rates, current rule end boundaries, and the start of a more-applicable rule; effective-rule transitions use the same settlement state machine as Accounting. Runtime selects the Internet or VoIP planner according to the same `normal_users` classification used by `UserChargeSettlement`. This also makes the source-audited MikroTik and Cisco VPDN termination adapters reachable from the appropriate normal-user limit path. Provider live interoperability and post-command session disappearance remain unverified.


## Asterisk Manager termination — source-traced

Canonical source: `IBSng/core/ras/rases/asterisk.py::AsteriskRas.killUser` and `IBSng/core/lib/asterisk/manager.py::AsteriskManager.run`. The production charge-limit path now honors `asterisk_use_manager`, parses the stored `channel||unique_id` identity and issues only the source-defined AMI Login followed by Hangup for the channel. The transport has bounded connection/read time, frame-size and frame-count limits, matching ActionID checks, explicit manager rejection handling, and header-control-character validation. It does not claim independent proof that the channel has disappeared. Live Asterisk Manager interoperability remains unverified.
