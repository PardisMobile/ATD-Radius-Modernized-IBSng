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


## VoIP timer-engine checkpoint — 2026-10-15

Added tested scheduler and limit-loop application primitives. The scheduler supports per-key cancellation/replacement, bounded delays, callback error reporting, next-boundary rescheduling, and retry after provider action failures. This is a foundation only: the production RADIUS runtime is not yet wired to a transaction-scoped limit planner or source-specific RAS kill adapters, and restart recovery remains open. Do not mark the VoIP phase complete.


## VoIP limit enforcement and RAS actions — 2026-10-15

The scheduler and per-user orchestration now exist, and source-traced Disconnect-Request adapters cover ChilliSpot and MVTS with provider-specific response validation. This remains a partial foundation. The production runtime must still supply transaction-scoped planning and wire these adapters into lifecycle events. Implement remaining source-defined SNMP/RSH/launcher/telephony actions and durable session/timer recovery before claiming `VoipCharge.checkLimits` parity.


Safety increment — full session identity: VoIP kill decisions and the orchestration callback now carry `SessionKey` (user ID, RAS ID, provider ID), avoiding ambiguous matches across RASes. Unsupported termination strategies are reported as a capability gap instead of being hot-retried. Production runtime wiring and restart recovery are still required.


## Production VoIP limit-loop wiring — 2026-10-15

The production packet handler now owns the recurring scheduler and triggers rechecks after Accounting updates, using fresh database transactions and native credit/tariff/rule repositories. Session charging kind comes from the native user subtype, not a guessed RAS label. MVTS has a source-specific outbound Disconnect-Request path; the other VoIP providers' concrete kill effects, durable session/timer recovery and end-to-end provider parity remain required before phase completion. CI is pending.

## MVTS source-identity correction — 2026-10-15

A source re-check of `IBSng/core/ras/rases/mvts.py::killUser` found that A1.24 builds Disconnect-Request `User-Name` from the user's `voip_username` attribute, not necessarily the inbound RADIUS `User-Name`/normal IBSng login. The production VoIP termination path now resolves `voip_users.voip_username` through the native user repository in the same fresh transaction and uses it for MVTS; a missing VoIP credential fails closed as a permanent configuration gap instead of sending a disconnect for the wrong identity. Regression coverage verifies the provider sees the source-required username. This is a targeted parity correction, not full provider or restart-recovery completion.

## Accounting identity namespace parity — 2026-10-17

The native accounting identity resolver now checks both A1.24 namespaces: `normal_users.normal_username` and `voip_users.voip_username`. This is separate from Access-Request authentication. Only a unique user ID is accepted; missing or cross-user ambiguous names fail closed so usage is not charged to an arbitrary account. Regression tests cover VoIP-only names, missing identities, collisions, and runtime delegation. CI for commit `8168619ba1334a8e4819977d1eae92abb7d18084` is running. Durable session/timer recovery and the remaining provider-specific termination paths remain incomplete.


## Cisco Accounting service/identity parity checkpoint — 2026-10-17

Added a source audit at `docs/A1.24-CISCO-ACCOUNTING-AUDIT.md` tracing `CiscoRas.__isInternetPacket`, the Internet port identity, VoIP H.323 identity and source-specific Start/Stop/Alive branches. ATD now has service-aware Cisco routing and matching identity during live accounting and recovery, plus scalar normalization for list-shaped decoded values. This is **not full Cisco RAS parity**: call-type/origin gating, the pre-auth H.323 list and Cisco VoIP Alive side-effect semantics remain open. The integrated dispatcher regression is pending CI.


## Cisco Accounting source-gated increment — 2026-10-17

The live Accounting path and restart recovery now share Cisco's A1.24 service discriminator and H.323 call identity. Cisco VoIP Start/Stop are gated on `H323-call-type == VoIP` and `H323-call-origin == originate`; VoIP Alive is not routed through charge/session settlement. The `Telephony/answer` Stop branch remains unsupported until the pre-auth H.323 ID list is modeled. Scalar list-shaped Accounting attributes are normalized before provider selection and persistence.

Validation for code checkpoint `23858795ed6f70a19bb2bfc66c790c7d66e81b92`: Python-only CI passed **863 passed, 8 skipped, 2 warnings** (run [38982271980](https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38982271980)). Full CI run [38982272049](https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38982272049) had Python 3.11 fail during container initialization; Python 3.12 was still running at this checkpoint. This is not marked full-CI verified until the remaining matrix result is known. Cisco device interoperability and the explicit pre-auth H.323 state remain open.


## Cisco Telephony/answer Accounting-Stop branch

The Cisco VoIP pre-auth H.323 ID list from A1.24 is now modeled as process-local runtime state: successful Authorization records the ID, VoIP/originate Start consumes it, and Telephony/answer Stop requires membership. It intentionally resets on process restart to match the source's in-memory list. Python and full CI validation for this increment must be checked before marking complete.


Cisco Accounting Alive packets are now provider-tracker-only, not normal charge/session updates. The runtime keeps Cisco port/H.323 online metadata in memory, with username checks for Internet tracker updates and valid VoIP/originate gating. Validate with the current Python and full CI workflows before considering this checkpoint verified.


Cisco source-identity recovery coverage now asserts that missing H.323 conference IDs do not fall back to Acct-Session-Id or NAS-Port. This protects against recovering a Cisco VoIP connection under an identity that the source RAS would not use.


## Verified Cisco identity checkpoint — 2026-10-19

Full CI for commit 8a0e4ddd2aadfb42d66c0e4ee762b1c60cc9a85f passed on both Python versions (883 passed, 2 warnings per job). Strict provider identity is now checked by domain tests and a recovery integration regression. Next Cisco source-parity item is caller-ID / VOIP_AUTHORIZE behavior; do not treat it as implemented just because standard Cisco VoIP authentication and Accounting are covered.


## Production termination expansion — Cisco, PortMaster, Total Control

The production VoIP termination client now invokes source-audited external operation builders for Cisco (SNMP default, configured RSH alternative), PortMaster (ifIndex = NAS port + 2, IF-MIB admin-down), and Total Control (ordered interface down/up SETs). These are reachable from the existing limit-check loop rather than only isolated application use cases. Unsupported providers remain fail-closed. Validation is pending for the current commit.


## Next provider-enforcement increment — 2026-10-19

Added production VoIP termination wiring for the source-defined PortSlave and PPPD configured-launcher branches. This uses the existing shell-free bounded launcher transport, native command attribute names, exact `(RAS-IP, port)` argument order, and explicit successful-exit validation. Regression coverage includes both provider dispatches and failed launcher outcomes. Full CI is required before marking this slice verified; live provider interoperability and the remaining provider-specific kill mechanisms are still open.


## Provider disconnect result integrity — 2026-10-19

Added strict success-result validation across the currently wired Cisco, PortMaster, Total Control, PortSlave, and PPPD termination branches. Failure-shaped SNMP responses and launcher exits are surfaced instead of being reported as successful kills. New regression tests cover these negative paths. Continue with provider-side session verification/recovery only after this commit's Python and full CI evidence is reviewed.


## GnuGk status-port termination — source-traced, command-delivery only

Canonical source: `IBSng/core/ras/rases/gnugk.py::GnuGKRas.killUser`. A1.24 only opens the status-port connection when `gnugk_multiple_login` is enabled, defaults `gnugk_status_port` to 7000, waits for a semicolon prompt, sends `disconnectalias <voip_username>`, then sends `exit`. ATD now executes that exact sequence through a bounded TCP connection, requires the source-defined VoIP alias, rejects control characters, validates the port, and fails closed if the prompt is absent/oversized or the transport errors. Tests cover command order, custom port, gate-off behavior, missing identity, invalid port, command injection and prompt failure. A completed write is not proof that the remote call disappeared; independent session verification and live GnuGk interoperability remain open.


## GnuGk runtime identity integration

The production limit-enforcement callback now resolves the native `voip_username` from the user repository before calling the GnuGk adapter, rather than assuming the RADIUS/IBSng login is the Gatekeeper alias. MVTS retains its source-specific User-Name override. A runtime regression verifies the GnuGk session keeps the original inbound User-Name while passing the database-resolved alias separately as `voip_username`.


## Production termination expansion — MikroTik and Cisco VPDN

Canonical A1.24 source paths: `IBSng/core/ras/rases/mikrotik.py::killUser` and `IBSng/core/ras/rases/cisco_vpdn.py::killUser`. Both kill paths are connected to production VoIP-limit enforcement. MikroTik resolves the native normal username, requires the session IP and NAS-Port-Type, preserves the source split between Wireless-802.11 hotspot removal and PPP active-session removal, and uses configured SSH wrapper credentials through bounded RSH. Cisco VPDN resolves the normal username and source remote IP, performs `show caller user` interface discovery, selects the matching interface when an IP is available (source behavior: first match if absent), then runs `clear interface`. Both require explicit transport success and fail closed on missing identity/configuration. Regression tests cover provider dispatch and runtime identity resolution. Live NAS interoperability and independent proof of session disappearance remain unverified.


## Internet session limit enforcement — source-shaped planning

Canonical source: `IBSng/core/charge/internet_charge.py::checkLimits` and `IBSng/core/charge/charge.py::_getNextMoreApplicableRuleForTime`. Normal-user sessions now share the existing per-user timer worker with VoIP sessions. The Internet planner handles exhausted credit, per-session missing effective rules, aggregate concurrent-instance time/assumed-transfer rates, current rule end boundaries, and the start of a more-applicable rule; effective-rule transitions use the same settlement state machine as Accounting. Runtime selects the Internet or VoIP planner according to the same `normal_users` classification used by `UserChargeSettlement`. This also makes the source-audited MikroTik and Cisco VPDN termination adapters reachable from the appropriate normal-user limit path. Provider live interoperability and post-command session disappearance remain unverified.


## Charge-limit scheduler scope correction — 2026-10-20

The existing per-user scheduler now includes active Internet charge sessions as well as VoIP sessions. Planner selection follows each active session's `charge_kind`, which was assigned by the A1.24-compatible `UserChargeSettlement` classification, and refuses mixed Internet/VoIP charge kinds for one user instead of silently selecting one planner. Regression coverage updates the previous Internet-only-not-scheduled expectation to the source-derived shared scheduling behavior.


## Asterisk Manager termination — source-traced

Canonical source: `IBSng/core/ras/rases/asterisk.py::AsteriskRas.killUser` and `IBSng/core/lib/asterisk/manager.py::AsteriskManager.run`. The production charge-limit path now honors `asterisk_use_manager`, parses the stored `channel||unique_id` identity and issues only the source-defined AMI Login followed by Hangup for the channel. The transport has bounded connection/read time, frame-size and frame-count limits, matching ActionID checks, explicit manager rejection handling, and header-control-character validation. It does not claim independent proof that the channel has disappeared. Live Asterisk Manager interoperability remains unverified.


## Runtime control and enforcement checkpoint — 2026-10-20

Latest code checkpoint: `101d8151a324a90801bf80dc122baf44b21c9d30`. Source-shaped Internet and VoIP limit planners share the recurring per-user enforcement loop; production termination is wired for audited providers with actual A1.24 kill behavior, including Asterisk AMI, GnuGk, MikroTik, Cisco VPDN and earlier SNMP/launcher/Disconnect-Request adapters. Incoming RFC 5176 Disconnect closes accounting through settlement/persistence and releases the IP lease; incoming CoA mutates only supported authorization attributes. Admin-facing online-session management remains gated on authoritative runtime/session ownership, permission dependencies and audit sequencing.

Validation: Python-only CI passed 912 tests with 8 skips on the latest code. Python 3.11 passed latest full CI; Python 3.12 failed before checkout during container initialization, so rerun before marking the matrix green. This is not a full compatibility release. Database importer/parity validator, cross-process session authority, full deletion/billing/plugin parity, remaining UI, and installer/upgrade/rollback work remain open.


## Authenticated RAS-scoped Disconnect/CoA — 2026-10-20

The inbound RFC 5176 control path now scopes both Disconnect and CoA target resolution to the RAS ID resolved from the authenticated peer IP. A username-only selector cannot affect a same-named session attached to another RAS. Unresolved peer-to-RAS identity returns NAK / Error-Cause 503 without mutation. Regression tests cover both control actions and the unresolved-peer boundary.

Validation: Python-only 916 passed, 8 skipped. The full PostgreSQL-backed Python 3.12 job ran 924 passed, 2 warnings, with Ruff, compilation and PHP syntax checks successful. Python 3.11's latest full-matrix attempt failed during container initialization before checkout/tests and remains to be rerun.


## Durable RADIUS session recovery — 2026-10-20

The new ATD extension table `atd_radius_live_sessions` snapshots runtime session and billing state in the same transaction as Accounting mutations, restores it before native open-log fallback, supports sessions intentionally omitted from `connection_log`, and preserves accrued rule state across restart. Legacy open native log rows are restored and upgraded into snapshots. A source `no_connection_log` Stop removes the prematurely created ATD history row to prevent false recovery.

Still open: multi-worker row/advisory lock coordination, lifecycle reconciliation for sessions that never send Stop, and full live provider verification. This batch is pending CI validation on its new HEAD.


## CI reliability follow-up — 2026-10-20

Python-only suite for the durable-session batch: 925 passed, 8 skipped. Full PostgreSQL CI failed before checkout because the public ECR Postgres image pull hit its data limit. The workflow now uses official Docker Hub `postgres:16-alpine`; rerun the matrix before declaring the durable-session batch fully verified.
