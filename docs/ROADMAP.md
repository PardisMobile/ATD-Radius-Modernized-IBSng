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
