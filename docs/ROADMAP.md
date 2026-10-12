# ATD Radius Modernized IBSng — Roadmap

## Verified checkpoint — 2026-10-10
The native Accounting-Request path now serializes identity resolution through persistence/session side effects, and the normal `atd_radius.main` launcher shares one in-process runtime owner between UDP and the API app. Full CI passed on Python 3.11/3.12 (654 passed each). This is not complete A1.24 session parity: cross-process/restart session truth, safe Disconnect, user deletion and remaining accounting/billing behavior are still open. See `docs/A1.24-SESSION-CONCURRENCY-AUDIT.md` and `docs/CURRENT-STATUS.md`.

## Verified feature increment — 2026-10-10
A1.24's special VoIP caller_id updater is now implemented for one user at a time, with native caller_id_users persistence, CHANGE VOIP USER ATTRIBUTES owner-scoped permission, MultiStr range expansion, serialized global uniqueness check and native/operational audit. Full CI: 662 passed on Python 3.11 and 3.12. See docs/A1.24-CALLER-ID-AUDIT.md. Bulk caller-ID assignment and the other incomplete A1.24 subsystems remain open.

## Phase 1 — Behavioral foundation
- [x] Typed attribute engine
- [x] Attribute precedence and provenance
- [x] IPv4 IP-pool allocation primitives
- [x] Accounting usage primitives
- [x] Charge/billing primitives
- [ ] Complete A1.24 consumer mapping

## Phase 2 — Database compatibility
- [ ] Inventory every A1.24 table, column, index and constraint
- [ ] Inventory official A1.24 backup/restore behavior
- [ ] Define native/mapped/transformed schema strategy
- [ ] Build lossless importer
- [ ] Build parity report
- [ ] Restore representative real-world IBSng backups

## Phase 3 — RADIUS / AAA
- [ ] PAP/CHAP and existing authentication semantics
- [ ] Access-Accept/Reject policy generation
- [ ] Accounting Start/Interim/Stop
- [ ] RAS lifecycle
- [ ] IP pool assignment integration
- [ ] Session enforcement

## Phase 4 — Billing and policy
- [ ] Normal/VoIP charging parity
- [ ] Credit and expiry semantics
- [ ] Bandwidth accounting
- [ ] Attribute/plugin parity

## Phase 5 — EAP
- [ ] EAP architecture
- [ ] EAP method support selected from requirements
- [ ] RADIUS/EAP integration tests

## Phase 6 — Modern UI
- [ ] Admin parity inventory
- [ ] User portal parity inventory
- [ ] Modern responsive theme
- [ ] Preserve IBSng workflow efficiency
- [ ] Attribute editor
- [ ] Session/accounting/billing views

## Phase 7 — Compatibility release
- [ ] Full A1.24 → ATD compatibility matrix
- [ ] Automated migration/parity suite
- [ ] CI green on supported Python versions
- [ ] Install/upgrade/rollback validation
- [ ] Production deployment documentation

**Definition of done:** ATD is not considered an IBSng modernization until the compatibility matrix and lossless database migration path demonstrate that required A1.24 behavior and data are preserved.


## Verified attribute increment — 2026-10-10

Enabled A1.24 `voip_preferred_language` in the generic user attribute API after source tracing its updater. It persists in `user_attrs` and uses the generic attribute authorization/audit path. Regression test added. Full CI passed on Python 3.11 and 3.12: 663 passed, 2 warnings per matrix job, run https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38082360746. Code/test commit: `581fd60d87f2e15f6f4dd81cf50e0cbbb3772ed6`. This does not imply parity for VoIP credentials, tariffs, preferred-language consumers or other VoIP plugins.


## Source-backed attribute increment — save_bw_usage

`save_bw_usage` marker mutation matches A1.24's empty-string persistence and generic delete path. Regression coverage is included. Full CI passed on the tested feature commit on Python 3.11 and 3.12: 664 passed, 2 warnings per matrix job (https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38082764002). Bandwidth accounting consumer integration remains pending.


## Source-backed attribute increment — fast_dial

Added mutation/storage support for A1.24 `fast_dial` from `IBSng/core/user/plugins/fast_dial.py`: exactly ten comma-separated entries, each empty or digit-only. The source explicitly passes `False` to `useGenerateQuery` for both update and delete, so native user-audit writes are suppressed for this attribute. Three regression tests added. Runtime called-number redirection, FASTDIAL_PREFIX processing and the source actions-manager API remain incomplete. Full CI passed on Python 3.11 and 3.12: 667 tests passed per matrix job, 2 warnings per job (https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38126347300). Python-only workflow passed (https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38126347240).


## Fast-dial runtime audit — 2026-10-11

Source trace and explicit implementation gates are recorded in `docs/A1.24-FAST-DIAL-RUNTIME-AUDIT.md`. Mutation/storage is verified by the existing full CI checkpoint (667 passed on Python 3.11 and 3.12, 2 warnings each); this is not runtime parity. Remaining work: VoIP/RAS called-number rewrite and redirect reply, per-instance index metadata, and source-compatible add/get actions-manager endpoints/adapter. Add source-derived regression tests for prefix handling, malformed/out-of-range indices, empty destinations, login/update lifecycle, redirect side effects and concurrent updates before changing the compatibility status. Do not expose user deletion or RAS Disconnect as part of this increment.


## Fast-dial runtime foundation — 2026-10-11

Implemented and regression-tested a source-shaped domain primitive in `domain/fast_dial.py` for prefix handling, destination indexing, redirect callback and per-instance index tracking. Separate action-manager destination validation is also represented. Next gate: wire this into an authoritative VoIP/RAS login/update lifecycle and source-compatible actions-manager/API adapter; do not expose it as a generic RADIUS response attribute. CI status must be checked on the current branch before treating this increment as verified. See `docs/A1.24-FAST-DIAL-RUNTIME-AUDIT.md`.

Source archive integrity discrepancy: the previously specified hash is 61 hex characters (not a valid SHA-256); the uploaded archive hashes to `c7117a6a2fd252aa9b8149a1ee6606f9320888da347ee4f839614bb9349d18a8`. Resolve the intended canonical hash before describing it as pinned/verified.


## Fast-dial foundation verification — 2026-10-11

Latest main HEAD `2dd944de4f8df82792f23912f301d6725263d9ff` passed full CI on Python 3.11 and 3.12; Python 3.11 reported 672 passed, 2 warnings. This verifies the new helper and regressions, not production runtime parity. Next implementation step is the authoritative VoIP/RAS login/update adapter and source-compatible actions-manager API, with explicit redirect and instance-state integration tests. Archive hash pin remains unresolved because the supplied literal is not valid SHA-256.


## Fast-dial action-manager API increment — 2026-10-12

Added the native-style fast-dial slot repository and admin GET/PUT API keyed by VoIP username. Writes validate destination/index as A1.24 does, lock the owning user row to avoid lost updates, preserve native USER_AUDIT_LOG suppression, and emit transactional operational audit. Regression coverage includes slot semantics and API permission checks. This closes the API/action-manager persistence slice only. The production VoIP `s_login`/`s_update` message rewrite, redirect-reply integration, and per-instance index lifecycle remain open. Do not mark fast_dial runtime parity complete before those are wired and verified.


## Bandwidth snapshot runtime increment — 2026-10-12

Implemented native-table persistence for `internet_bw_snapshot` and wired RADIUS Accounting-Request input/output deltas into it when the resolved user is normal and the effective A1.24 `save_bw_usage` marker exists. User and group attribute precedence is resolved through the existing repository. Rows aggregate by the source default one-minute interval bucket and repeated writes accumulate at `(user_id, snp_date)`. Tests cover runtime eligibility and SQL behavior. This is **partial consumer integration**, not complete A1.24 parity: the original samples every online instance periodically; ATD currently depends on Accounting-Request deltas. Validate gaps, counter resets, and provider Interim-Update intervals before marking the feature verified.


Verification update — 2026-10-12: Python-only CI passed on latest test HEAD `f97af48b94204ac2e7d6065d522c29d2583dc76e` (https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38180272821). Full CI passed on the implementation commit `bcb942adf311b3369dbe1a9d1da486bc1b633433` (https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38180263093); full CI for the latest test-only adjustment remains pending. Do not mark full bandwidth snapshot parity complete until periodic per-instance sampling is matched or the documented event-driven transformation is explicitly accepted by compatibility tests.


## Full source + Markdown audit checkpoint — 2026-10-12

Current verified implementation baseline before documentation-only audit updates: `f87a63cf46c6b271d6efdcc2a7d80af2d649c760`; full CI and Python-only CI both passed on that exact HEAD (runs 38180343444 and 38180343421). The status/context audit notes were then updated in documentation-only commits; CI must be checked on the newest main HEAD before claiming the documentation commits are green.

The user explicitly requires continuing all workstreams without pausing, reviewing the complete IBSng A1.24 source archive semantically (not just inventorying files), and reviewing every project Markdown file. First pass fetched and inventoried all 65 repository Markdown files. Next: resolve cross-document stale/current-state statements while preserving historically accurate checkpoint notes, then continue source-to-ATD semantic review by subsystem.

The archive has 2,477 members and 2,295 regular source files (453 Python, 530 PHP, 284 Smarty templates, 20 SQL files). Inventory counts are not source-review completion. For each source pass, track source file and callers, behavior, DB side effects, runtime hooks, ATD implementation/tests, compatibility gaps, and evidence. Never claim full parity from unit tests alone.

Do not stop or silently drop UI, migration, RADIUS/RAS, billing, EAP, XML-RPC, API, source audit, or deployment work. Prioritize cohesive implementation batches across the remaining gaps and keep frozen source-verified protocol/authentication/MultiLogin/persistence behavior unchanged unless exact A1.24 evidence requires correction.


## Content-level audit corrections and parallel workstreams — 2026-10-12

A direct content review has begun across the source and subsystem Markdown files; this is not merely a filename inventory. Confirmed corrections have been made to the current status, compatibility/migration ledgers, bandwidth attribute consumer map, Fast Dial runtime audit, connection-log/persistence audit, RADIUS dispatch parity, runtime batch audit and session-state audit. Those edits distinguish historical checkpoints from current implementation status and explicitly record the evidence/source call chains.

No project workstream is to be silently stopped. UI inventory/specification and safe non-destructive UI implementation continue in parallel with RADIUS/RAS, billing, EAP, API/RBAC, XML-RPC, database import/parity, source review and deployment work. Operations that can corrupt user/accounting state or terminate a live session remain gated until their A1.24 lifecycle and safety requirements are implemented; this is a safety dependency, not abandonment of that workstream.

Latest known code/test CI baseline remains `f97af48b94204ac2e7d6065d522c29d2583dc76e` (full matrix passed, 694 passed and 2 warnings on Python 3.11 and 3.12). Docs-only commit `f87a63cf46c6b271d6efdcc2a7d80af2d649c760` also passed both workflows. The current documentation review has generated newer commits; their CI status must be checked on the exact current HEAD before they are called green.


## VoIP tariff persistence adapter — 2026-10-12

Added a read-only PostgreSQL adapter against the exact A1.24 tariff tables `voip_charge_rule_tariff` and `tariff_prefix_list`. Source-specific `min_chargable_duration` spelling is retained at the SQL boundary. Tests cover mapping, unknown IDs and longest-prefix lookup. This is a persistence foundation, not complete VoIP billing parity: runtime RAS call lifecycle, charge-rule selection/transition, credit settlement, mutation authorization/audit and integration tests remain open. Keep this backend work ahead of the final UI/installer stage.


## Native VoIP tariff read API — 2026-10-12

The read-only tariff API is now wired with source-backed `SEE VOIP TARIFF` permission. It exposes native tariff list/detail and optional prefix-name regex filtering. The native PostgreSQL loader and API tests are present. Remaining backend parity includes `CHANGE VOIP TARIFF` operations, A1.24 validation and mutation/reload semantics, and connection to the live VoIP/RAS charging lifecycle. Do not mark VoIP tariff/charging complete from read API coverage.


## VoIP tariff management API — 2026-10-12

Added source-backed tariff and prefix CRUD endpoints under `/api/v1/voip-tariffs`, guarded by `CHANGE VOIP TARIFF`; reads remain guarded by `SEE VOIP TARIFF`. The adapter uses native tariff/prefix tables, preserves `min_chargable_duration`, validates names/codes/rates/durations, rejects duplicate names/codes, and blocks deleting a tariff referenced by `voip_charge_rules`. Remaining: verify native sequence names on restored A1.24 databases, test mutations against PostgreSQL, and wire tariff/rule evaluation into the real VoIP/RAS call lifecycle. Do not count this as VoIP charge runtime parity.


## A1.24 charge-rule port semantics correction — 2026-10-12

Fixed the source-backed wildcard rule: only the explicit `_ALL_` port marker represents all ports; an empty configured port set matches no port, exactly as `ChargeRule.anytimeAppliable` specifies. Added regression coverage and corrected fixtures that previously relied on the ATD mismatch. Re-run full CI before marking this behavior verified.


## Native VoIP charge-rule loader — 2026-10-12

Added source-backed mapping of `voip_charge_rules` plus `charge_rule_day_of_weeks` and `charge_rule_ports`, preserving inherited `charge_id`, `time_limit`, RAS and tariff ID. This is the next persistence building block for VoIP charging; live RAS call timing, tariff-prefix transitions, free seconds, rounding, missed-call behavior and credit settlement remain unfinished.


CI fixture correction — 2026-10-12: the source-backed empty-port change exposed an integration fixture that inserted an internet charge rule without any `charge_rule_ports` rows. A1.24 does not treat that as a wildcard, so the fixture now inserts the explicit `_ALL_` marker for the intended all-port rule. This keeps the live UDP/PostgreSQL test representative of the native source rather than reverting the compatibility fix.


Source correction — prefix ordering: A1.24 `Tariff.__getPrefixesInfo` applies the optional name regex and then sorts prefix records by `prefix_name` ascending. The API now follows that order. Prefix mutation responses select by `prefix_id` rather than relying on repository row order.


## Latest verified checkpoint — 2026-10-12

Current code checkpoint `057b69789e9c353a8531d927129e09fafaf3105d` passed full CI on Python 3.11 and 3.12 (**720 passed, 2 warnings per matrix job**) and Python-only (**718 passed, 2 skipped, 2 warnings**). See the full run and Python-only run in `docs/CURRENT-STATUS.md`.

The native VoIP tariff/prefix management API and read-only VoIP charge-rule repository are implemented and tested. Source corrections from this pass: tariff permission dependencies follow A1.24; tariff prefixes are returned by name ascending; empty port lists are not wildcards (only `_ALL_` is). This does not finish billing: live VoIP/RAS call lifecycle and settlement, rule mutation/overlap checks, and active-session side effects remain backend work. Keep UI and installer at the end.


## Native VoIP charge-rule management API — 2026-10-12

Added source-backed endpoints for listing, creating, updating and deleting VoIP charge rules. Persistence uses the A1.24 inherited `voip_charge_rules` table plus `charge_rule_day_of_weeks` and `charge_rule_ports`, the native `charge_rules_id_seq`, and tariff/charge name lookup. Mutations are transaction-scoped and operationally audited. Validation covers source day names, time windows, VoIP charge type, tariff existence, RAS-specific port requirements and overlap checks. The overlap implementation intentionally preserves the legacy A1.24 behavior of comparing equal RAS IDs and literal port intersections rather than silently broadening wildcard conflict semantics.

This is management/persistence parity only. The source's `charge_main.getLoader().loadCharge()` runtime reload behavior and live VoIP call charging, prefix changes during a call, free seconds, missed-call handling, rounding and credit settlement are still not implemented end-to-end. UI and installer remain final-stage work.


## Source-backed VoIP prefix applicability — 2026-10-12

Implemented `select_effective_voip_rule` matching `VoipChargeRule.anytimeAppliable`: for a non-empty called number, a candidate rule is applicable only if its tariff has a matching prefix; an empty called number is allowed before the RAS supplies it. Effective selection retains A1.24's strict-greater-priority replacement behavior. Regression tests cover a non-matching higher candidate, no matching tariff prefix, and the not-yet-acquired called number case. This is a domain primitive; production call lifecycle wiring remains open.


## VoIP charge-rule CRUD regression coverage — 2026-10-12

Added repository tests for updating a rule while replacing its day/port child rows, deleting child rows before the inherited VoIP rule row, and refusing to mutate a rule belonging to a different charge. RAS-specific rules now validate that the RAS exists and that every named port is configured on that RAS; `_ALL_` remains an explicit marker.


## VoIP charge-rule CRUD and prefix applicability — 2026-10-12

The native VoIP charge-rule API now includes list/create/update/delete and RAS/port validation; tests include an actual PostgreSQL round trip. The domain selector also enforces called-number prefix matching as A1.24 does. See `docs/A1.24-BILLING-RULE-PARITY.md` for exact boundaries. The latest exact code checkpoint's full CI must pass before this increment is considered verified. Production call lifecycle and settlement remain unfinished; UI and installer stay last.


## Verified Internet + VoIP charge administration — 2026-10-12

The code checkpoint `1e66ad4e9f0b418f46da2568915879ceb8ea292f` passed full CI on Python 3.11 and 3.12 (**749 passed, 2 warnings each**), including PostgreSQL integration. Python-only reported 745 passed, 4 skipped. Added Internet charge-rule CRUD API and repository alongside VoIP tariff/prefix and VoIP charge-rule CRUD. Native bandwidth leaf IDs are preserved, paired leaf selection and source validation are enforced, and PostgreSQL integration tests cover create/update/delete. Production billing/runtime parity remains incomplete; keep UI and installer last.


## Verified bandwidth leaf catalog increment — 2026-10-12

Added read-only native bandwidth leaf listing and lookup by name, guarded by the source permission dependency chain `CHANGE BANDWIDTH MANAGER → CHANGE CHARGE → ACCESS ALL CHARGES`. The code checkpoint `32422e4922a8895e72edcddd4b8b9f85005fe3b9` passed full CI: 752 tests on both Python 3.11 and 3.12, including PostgreSQL integration. Keep write-side bandwidth hierarchy and provider side effects as backend work; UI and installer remain last.


## Verified charge assignment workflow — 2026-10-12

Added native charge catalog CRUD and user `normal_charge`/`voip_charge` assignment endpoints with A1.24 type checks, `canUseCharge` permission/visibility semantics, native audit, and PostgreSQL round-trip tests. Full CI for `09044676484684c9400025abe3b7364ed924f33e` passed **771 tests** on Python 3.11 and 3.12. Bandwidth hierarchy writes/shaping and production VoIP runtime/settlement remain backend tasks; UI and installer remain last.


## Verified IAS event management — 2026-10-12

Added REST endpoints for IAS event listing and deletion with GOD-only access, matching the source's unregistered `HANDLE IAS EVENTS` permission, with native event-type mapping, bounded pagination, operational audit on deletion, and PostgreSQL integration coverage. Full CI on `35f23bea970f519f3779a7a5afd548951c94a18f` passed 778 tests on Python 3.11 and 3.12. Remaining IAS/XML-RPC work is the native XML-RPC transport/auth compatibility layer. IAS user-info REST is implemented; `lockUser` and `lockAdmin` exist in source but are not registered by `IASHandler.__init__`, so they are not exposed A1.24 handler methods.


## IAS permission source correction — 2026-10-12

Direct inspection of the complete A1.24 `core/admin/perms/` directory found no `HANDLE_IAS_EVENTS.py` permission class. Although `IASHandler` calls `canDo("HANDLE IAS EVENTS")`, the permission loader rejects unregistered permission names; `Admin.canDo` bypasses permission checks only for GOD. Therefore the registered native IAS methods are effectively GOD-only in A1.24. The REST IAS event/user-info routes now enforce GOD rather than inventing a grantable `HANDLE IAS EVENTS` permission. The old permission-catalog entry is corrected accordingly.


## XML-RPC request-boundary hardening — 2026-10-12

The /xmlrpc IAS compatibility endpoint now reads request bodies incrementally and enforces the 1 MiB limit during streaming, with an early Content-Length rejection when declared. This avoids buffering arbitrarily large request bodies before applying the existing transport limit. Regression tests cover streamed oversize bodies and declared oversize bodies. Code/test commit: 2b6849b10613ba24354c3296b9c6ed5f17b012f6. Full CI passed on code/test commit 2b6849b10613ba24354c3296b9c6ed5f17b012f6: Python 3.11 and 3.12 each reported 791 passed, 2 warnings; Ruff, compilation, PHP syntax, and PostgreSQL integration all passed (CI run 38228913843). Python-only CI also passed (run 38228913960). This is transport hardening only; full XML-RPC/IAS semantic parity remains open.


## Charge visibility parity correction — 2026-10-12

Direct A1.24 source review confirmed that `ChargeHandler.listCharges` filters by `Admin.canUseCharge(charge_name)` and `getChargeInfo`/`listChargeRules` apply the same per-charge gate. This is not equivalent to requiring `ACCESS ALL CHARGES` for every read: charges marked `visible_to_all` and charges explicitly granted through `CHARGE ACCESS` are usable by the corresponding admin. The charge catalog GET/list/detail and Internet/VoIP charge-rule list endpoints now apply this source-compatible visibility filter; explicitly requested inaccessible charge IDs return 403 and unknown IDs return 404. Mutations remain behind the source `CHANGE CHARGE` dependency chain. Regression coverage includes public, granted, denied, and all-charge access. Code/test commit `7a2d5d15d55b1a74409933851f6eb0c90185b4c3` passed full CI: Python 3.11 and 3.12 each **795 passed, 2 warnings**; Ruff, compilation, PHP syntax and PostgreSQL integration passed (CI run `38229910982`); Python-only workflow passed **787 passed, 8 skipped, 2 warnings** (run `38229910991`). This closes only the read-visibility slice, not complete billing/runtime parity.


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
