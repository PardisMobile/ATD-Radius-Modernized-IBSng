# VERIFIED/FROZEN REGISTER LOCATION CORRECTED — 2026-10-29

The existing `docs/A1.24-USER-PLUGIN-INVENTORY.md` is the canonical plugin-by-plugin inventory and freeze record. `docs/COMPATIBILITY-MATRIX.md` remains the cross-cutting parity matrix and supplementary evidence; it does not replace the plugin inventory. The mistakenly created parallel file `docs/A1.24-VERIFIED-FROZEN.md` has been deleted. No separate freeze register should be created.

The final comment-only reset correction checkpoint `32d46f52620269f367edf2150683feb5851da709` has both full CI and Python workflows successful (runs `40800850638` and `40800850548`).

---

# SOURCE AUDIT CORRECTION — DAILY PERIODIC RESET CATCH-UP — 2026-10-29

The prior 2026-10-29 statement that daily reset advancement must always leave the next boundary strictly in the future was too broad and did not exactly reproduce canonical A1.24. In `IBSng/core/user/plugins/periodic_accounting.py::BasePeriodicAccounting._calcNextReset`, daily reset calculates `saved_next_reset + interval` first, then advances only while `candidate < time.time()`. If a delayed hook lands exactly on a missed interval boundary, the calculated reset may equal `now`; a subsequent due hook advances from that saved boundary again. The modernized implementation now preserves this source behavior, and a regression test covers both calls. This is a targeted correction, not evidence of complete plugin parity. CI for the corrective commits is running.

---

# VERIFIED A1.24 EXPIRY + PERIODIC RESET PARITY BATCH — 2026-10-29

Checkpoint `300a3799589b51f7b8918fed7537a8a063aba887` passed full CI on Python 3.11 and 3.12: **1,170 passed, 1 skipped, 2 warnings per version** (CI run [40798723019](https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/40798723019)). Python-only passed **1,128 passed, 43 skipped, 2 warnings** (run [40798723305](https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/40798723305)). Ruff, compilation and PHP syntax checks passed.

This batch source-traced three lifecycle boundaries against canonical A1.24:
- Periodic accounting: reset is due at `next_reset <= now`; daily anchored reset advances until the next event is strictly future, including when a callback arrives exactly on the boundary. Tests cover daily/monthly × time/traffic, consecutive exact-boundary events, and just-before-boundary no-op behavior.
- Absolute vs relative expiry: absolute expiration uses strict `deadline < now`, while relative expiry uses inclusive `deadline <= now`. The active-session scheduler now rechecks at the exact absolute boundary after its minimum interval rather than silently ending scheduling; exact relative expiry still terminates.
- First login: an A1.24 `first_login` candidate is committed only after successful Access-Accept and is not renewed on subsequent logins. Integrated dispatcher regression coverage verifies reject/accept and response attribute privacy.

This verifies these source-derived boundary slices, not complete user-plugin parity or live NAS behavior. The broader core plugin/runtime, provider interoperability and production adoption gates remain open.

---

# PERIODIC RESET BOUNDARY PARITY FIX — 2026-10-29

Canonical source `IBSng/core/user/plugins/periodic_accounting.py` confirms reset is due when `next_reset <= time.time()`. The modernized domain engine's due check now matches that inclusive condition, and its daily anchored schedule advances with `while next_reset <= now` so the next scheduled boundary is strictly future—even when the current instant equals the old boundary. Parametrized regression coverage exercises all four daily/monthly time/traffic quota types, exact-boundary repeated resets, and the no-op just before the next boundary. An earlier test expectation was corrected to match the anchored source schedule; the verified combined checkpoint above now passes both workflows.

---

# SEQUENCE HIGH-WATER SAFETY — 2026-10-29

The A1.24 row importer now preserves the next-value state of both source and target sequences, even when a sequence is ahead of the maximum currently stored row ID (for example, after deletes or manual allocation). Owned-column extrema are also considered and the selected restart value is checked against sequence bounds. During apply, destination sequences are locked in deterministic order before reading/restarting them to prevent concurrent target-side nextval() races. PostgreSQL acceptance regressions cover source/target sequence-state precedence and an uncalled target sequence. CI is pending for this increment; full legacy restore/cutover parity remains unverified.

# VERIFIED AUTHENTICATION INTEGRATION BATCH — 2026-10-26

Code checkpoint `20e9f8cbe8d59b54bec9d337e071d9cd59d486d1` passed full CI on Python 3.11 and 3.12: **1,140 passed per version, 2 warnings**. Python-only workflow also passed.

The native Access-Request path now has integrated regression coverage for CHAP using the packet authenticator, MS-CHAPv1 MPPE output, MS-CHAPv2 success and Send/Recv key derivation, malformed/wrong-response rejection without key leakage, and a full request → native dispatcher → response codec round-trip with encrypted MPPE keys. MS-CHAPv2 response normalization now explicitly supports bytes, bytearray and hexadecimal text adapters without an early-return path that could skip RAS enrichment.

This verifies the local native RADIUS pipeline and codec, **not** live NAS/supplicant interoperability. That remains an explicit release blocker, together with the remaining A1.24 plugin/runtime parity work. UI and installer remain deferred.

---

# PERIODIC ACCOUNTING CORE ENFORCEMENT BATCH — 2026-10-26

Latest implementation checkpoint: `b69bd90c0007f2819b224bd878b4f899bfecb4fe`. The four A1.24 periodic quotas are wired into Access admission and Accounting lifecycle; quota resets and source-shaped `_reload` behavior are implemented; usage/reset attributes use the native user-attribute repository; and per-session baselines are stored with durable RADIUS session snapshots and reconciled across workers. Recurring checks request provider-aware RAS termination when quotas expire. Traffic-quota deadlines now use the effective Internet charge rule's `assumed_kps`, and traffic periodic accounting is excluded for non-normal/VoIP users per source behavior.

Full CI and Python-only workflows passed for this checkpoint on Python 3.11 and 3.12. Remaining work in this area is concurrency/stress validation and final source-parity audit. Other A1.24 core plugin lifecycle and provider interoperability work remains; UI and installer are still intentionally deferred.

---

# PERIODIC ACCOUNTING CORE ENFORCEMENT BATCH — 2026-10-26

Latest implementation checkpoint: `6b29f32bc4587219e3f8d5e1fb9774e54f583e53`. Added native per-user quota persistence; Access-Request rejection on exhausted quotas; Accounting-Start baselines; recurring quota/reset checks with deferred RAS termination; source-shaped `_reload` behavior; and per-session baseline persistence/recovery in the durable RADIUS session snapshots. Before admission and accounting, active baselines are reconciled from shared PostgreSQL session state to cover sessions created by other workers. Regression coverage includes quota admission, changed period values, restart recovery, and composite session IDs.

Python-only CI passed for this checkpoint; full CI is still running. Remaining periodic-accounting gaps: exact charging-rule assumed-KPS calculation for traffic quota timing, and broader stress tests for cross-worker concurrent baseline updates. Other A1.24 core plugin parity remains in progress. UI and installer remain intentionally deferred.

---

# PERIODIC ACCOUNTING CORE ENFORCEMENT BATCH — 2026-10-26

Latest code checkpoint: `f007f24d2fd78fd0dcfc67696ecfccdbae9ff066`. The four A1.24 periodic quota types now have a native user-attribute adapter, Access-Request admission rejection, Accounting-Start baselines, recurring quota/reset checks, deferred RAS termination requests, and source-shaped attribute `_reload` behavior. Added policy, reload, and runtime admission regression tests.

CI for this newest checkpoint is running; do not treat it as green until both Python versions finish. Still open: restoring per-instance quota baselines after process restart / across workers, exact charging-rule assumed-KPS integration for traffic quotas, and full parity for other A1.24 plugin hooks. UI and installer remain deferred.

---

# LATEST PERIODIC ACCOUNTING RUNTIME INTEGRATION — 2026-10-26

Latest implementation commits: `e5d0563969d2ce0206226d2429fa975c2124af88` (runtime composite-session regression test). This batch adds a native PostgreSQL attribute adapter for the four A1.24 periodic quotas, binds effective group/user configuration while persisting per-user usage/reset attributes only, connects login/update/logout accounting hooks to the native RADIUS handler, preserves the coordinator across packet-scoped database transactions, and supports composite RAS/session identities in quota baselines.

CI for the newest commits is queued/running; this batch is **not yet verified green**. Remaining blockers include real termination/Disconnect integration when quota is exhausted, exact A1.24 `_reload` and attribute-update semantics, charging-rule assumed-KPS parity, durable/cross-worker baseline behavior, and broader plugin lifecycle parity. UI and installer remain deferred.

---

# LATEST IMPORT SAFETY GATE — 2026-10-25

Code checkpoint `57448c86f9353e0d8d537c5f82457fd99747ee4c` passed full CI on Python 3.11 and 3.12: **1,084 passed per version, 2 warnings**. Python-only: **1,050 passed, 34 skipped, 2 warnings**. Runs: [full CI](https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/40147630723), [Python-only](https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/40147630717).

The A1.24 row importer now also refuses source/target constraint-definition drift and verifies matching rule definitions, trigger definitions/trigger-function bodies, and source function/procedure definitions before any target writes. New PostgreSQL regressions cover function-body and rule drift. The import remains a row merge only: it does not import legacy DDL or database objects, and target-only rows are preserved. Full adoption is still not proven until a representative restored A1.24 database passes row/plugin parity and a rehearsed restore/rollback drill.

---

# LATEST MAIN INCREMENT — A1.24 DATA IMPORT FOUNDATION — 2026-10-25

Code checkpoint `6d537a0092423d7b51eb34f9efe82e84432f65f1` passed full CI on Python 3.11 and 3.12: **1,081 passed per version, 2 warnings**. Python-only: **1,050 passed, 31 skipped, 2 warnings**. Runs: [full CI](https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/40147404080), [Python-only](https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/40147404101).

Added the first operator-controlled A1.24 row importer, `atd-radius-a124-import`. It is dry-run by default, requires the canonical source archive checksum, validates canonical core table/column inventory and exact source/target column shape, includes matching plugin tables rather than silently skipping them, requires a stable unique key for each table, orders foreign-key dependencies, merges source rows by key, verifies each imported row against staging values, and reconciles sequences without lowering target high-water marks. It refuses unmapped source tables, schema/key drift, unsafe self-referencing cycles, and sequence-definition/ownership drift. PostgreSQL integration tests cover dry-run non-mutation, merge/upsert, foreign-key ordering, row verification, sequence high-water, unmapped/keyless tables, source-type drift, and cycle refusal.

This is an important foundation, **not yet a claim of complete lossless adoption**. It imports rows only from a live PostgreSQL source; it does not import DDL, functions, rules, triggers, roles or other unmapped objects, and it does not delete target-only rows. The operator must stop writes and back up both databases. A representative production-like migration/restore drill and plugin-object parity are still release gates.

---

# LATEST VERIFIED SCHEMA-AUDIT INCREMENT — 2026-10-25

Code checkpoint `bdfc5cc397cb2a058db59551d1bd410db04e6283` passed full CI on Python 3.11 and 3.12: **1,075 passed per version, 2 warnings**; Python-only: **1,050 passed, 25 skipped, 2 warnings**. CI: [full](https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/40146922761), [Python-only](https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/40146922755).

The read-only A1.24 schema audit now inventories normalized primary-key, foreign-key, unique, check and exclusion constraint definitions in addition to table/column names, column type/nullability/defaults, explicit index names and sequence names. Constraint definitions are compared only for same-named tables present in both inventories; missing/extra tables are already reported separately, and mapped tables with different names still require explicit mapping. Added regressions cover inline and table-level constraints and shared-table drift. This remains schema assessment only, not an importer or full plugin/data parity proof.

The next major release gate remains the lossless data adoption/import workflow, including row-level parity and verified restore. Live NAS/provider interoperability, safe reservation reconciliation, billing/plugin side effects and remaining UI/report/deployment work are still open.

---

# LATEST MAIN VERIFICATION — 2026-10-25

Main head: `7484ea5b0a23f32d4de05cc794ff12d1dc76f5c1`.
Full CI passed on Python 3.11 and 3.12: **1,073 passed per version, 2 warnings**, including Ruff, Python compilation, PHP syntax, and PostgreSQL-backed tests. Run: [40144748357](https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/40144748357).
Python-only: **1,048 passed, 25 skipped, 2 warnings**. Run: [40144748355](https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/40144748355).

Seven previously open PRs were reviewed and their unique changes ported directly to main without creating new PRs: EAP request integrity, MPPE VSA decoding/response integrity, MS-CHAPv2 regression coverage, static schema audit, PostgreSQL deletion safety, local A1.24 CLEAR USER, and migration-ledger gap protection.

Verified source counts: archive SHA-256 `c7117a6a2fd252aa9b8149a1ee6606f9320888da347ee4f839614bb9349d18a8`; 2,295 regular source files (2,477 archive members); `tables.sql` has 51 tables, 224 columns, 19 explicit indexes, 24 explicit sequences and 3 serial declarations.
Current repo: 376 tracked files, 279 Python files, 73 Markdown files, 10 SQL files, 148 test files, 3 PHP files and 10 UI files.

These are verified compatibility slices, not full IBSng parity. Lossless A1.24 import/adoption, complete row/plugin-object parity, live NAS/provider interoperability, stale reservation reconciliation, billing/expiry/bandwidth side effects, remaining XML-RPC/UI workflows, installer/upgrade/rollback/licensing remain release blockers.

---

# LATEST MAIN RECONCILIATION — 2026-10-25

Repository: `PardisMobile/ATD-Radius-Modernized-IBSng`; integration target: `main`.
Canonical archive: `Source of Truth/IBSng-A1.24.tar.bz2`; verified SHA-256 `c7117a6a2fd252aa9b8149a1ee6606f9320888da347ee4f839614bb9349d18a8`.

## Verified inventory
- Canonical archive contains **2,295 files** (the tar stream has additional directory entries): 453 Python source files, 530 PHP files, 284 Smarty templates, and 20 SQL files; it also includes legacy compiled Python artifacts and static assets.
- Canonical `IBSng/db/tables.sql`: **51 tables, 224 columns, 19 explicit indexes, 24 explicit sequences, and 3 serial declarations**. Sequence names are compared as a deduplicated inventory; this DDL-only count is not full DB/plugin/data parity.
- Current `main` repository inventory before this reconciliation: **373 tracked files**, including 276 Python files, 73 Markdown files, 10 SQL migrations, 146 test files, 63 files under `docs/`, and 10 under `ui/`.
- The repository had **7 open PRs** based on an older main checkpoint. Their branches report merge conflicts; their changes must be reconciled against current files, not merged blindly.

## Direct-to-main integration batch
Integrated onto `main` without creating PRs: read-only static schema audit; damaged migration-ledger fail-closed checks; PostgreSQL user-deletion safety tests (fixture adapted for the current mailbox-cleanup outbox); local A1.24 `CLEAR USER` with no credit deduction or RAS kill; EAP Access-Request Message-Authenticator enforcement; encrypted MS-MPPE VSA decode and response-signature fix; and expanded non-ASCII MS-CHAPv2/MPPE regression coverage. The MS-CHAPv2 AuthenticatorResponse implementation itself was already present on main; its end-to-end regression was added.
- Source review correction: native A1.24 `CLEAR USER` is owner-scoped and explicitly depends on `SEE ONLINE USERS`; the implementation retains that source-defined dependency.
- These are focused compatibility slices, not completion of IBSng parity. Full CI passed on the reconciled head; live interoperability and the release blockers below remain open.

## Still release-blocking
Lossless A1.24 data importer/adoption; representative restore and row/plugin parity; full constraints/functions/plugin-created object parity; live NAS/provider interoperability and remote disappearance proof; stale accepted-login reservation recovery; billing/expiry/bandwidth and remaining plugin side effects; XML-RPC/report/UI completeness; and install/upgrade/rollback/licensing.

---

# LATEST HANDOFF — 2026-10-25

Repository: `PardisMobile/ATD-Radius-Modernized-IBSng`. Active integration branch and `main` are synchronized at `1b9d2aabac13a346447cff29c857d3807ff4888b`. The previously reported feature checkpoint `e73b146bfc4434a58d2f257a81b1879b4f9c89fe` was 40 commits behind main; the feature ref was fast-forwarded to main without rewriting history. No PR was created for this synchronization. The merge checkpoint includes reviewed A1.24 semantic-object inventory, safe migration-runner, read-only adoption preflight, and backup/restore acceptance work. CI runs are confirmed green on the prior feature checkpoint; a fresh CI result for the synchronized merge HEAD has not yet been verified.

Canonical source SHA-256: `c7117a6a2fd252aa9b8149a1ee6606f9320888da347ee4f839614bb9349d18a8`.

Do not claim overall completion based on CI. Major unfinished deliverables remain: a lossless A1.24 database importer/adoption and rollback workflow; representative real backup restore and full data parity; live NAS/provider RADIUS/MPPE and disconnect verification; stale accepted-login reservation recovery; remaining billing/bandwidth/plugin/XML-RPC/report/UI workflows; and supported install/upgrade/licensing. Continue implementation on `main` in substantial tested batches; avoid redoing completed/frozen slices. The semantic preflight is assessment-only and must not be represented as an importer.

---

# Current project status — ATD Radius / Modernized IBSng

Updated: 2026-10-22  
Repository: `PardisMobile/ATD-Radius-Modernized-IBSng`  
Branch: `main`  
Latest merged code checkpoint: `3430e1d6f585f630898a18f6649f81c2022770df` — cross-worker RAS termination claim coordination. The new change and its regression tests passed both Python 3.11 and 3.12 full CI jobs, including Ruff, Python compilation, PHP syntax checks, and PostgreSQL-backed integration.

## Latest release checkpoint — 2026-10-22

The charge-limit enforcement path now acquires the durable session advisory lock, reloads authoritative session state, and persists a termination claim before the external RAS provider call. A second worker waits on the same session lock and then observes the durable claim, suppressing duplicate termination commands. Missing/stopped durable sessions are removed from stale local state. Tests cover durable claim persistence and duplicate-claim suppression.

This improves cross-worker idempotency but does **not** prove the NAS/VoIP provider has removed the session. Provider interoperability, reconciliation after a provider timeout/ambiguous result, and full end-to-end A1.24 parity remain release gates.

## Mailbox cleanup outbox — 2026-10-24

User deletion now inserts post-commit mailbox cleanup jobs into the durable outbox in the same transaction as deleting users. The atd-radius-mailbox-cleanup worker processes bounded batches using a configured absolute executable path, argument-vector invocation (no shell), conservative username validation, timeout, attempt/error state and retries for failed/stale-running jobs. Migration 009_mailbox_cleanup_outbox.sql must be applied before deployment. The command is unset by default; external deletion is not claimed complete until an operator configures and runs the worker. See docs/MAILBOX-CLEANUP-OUTBOX.md.

## Reservation lifecycle note — 2026-10-23

A rejected Access-Request now deletes only its exact packet-derived login reservation. Regression coverage checks the repository delete key and the runtime rejection path. This does not solve accepted reservations that never receive Accounting-Start/Interim/Stop; those still require a safe reconciliation strategy that cannot mistakenly evict a genuinely online user.

## Remaining release blockers

1. Complete the source-to-implementation-to-test compatibility matrix across all A1.24 subsystems; do not infer parity from API/model presence.
2. Lossless A1.24 database import/restore and a representative backup parity report.
3. Close remaining authentication/accounting edge cases with end-to-end live UDP/PostgreSQL fixtures, including CHAP/MS-CHAPv2/MPPE interoperability and provider-specific accounting.
4. Complete billing and expiry parity, including bandwidth shaping, source plugin side effects and time-driven rule transitions.
5. Finish remaining admin/user workflows and modern responsive UI, then validate install/upgrade/rollback on supported deployment targets.
6. Live RAS interoperability and authoritative post-disconnect verification across supported provider types.

## Authority and validation

- Administrator permission editing and native administrator deletion are implemented. Administrator deletion code/test commit `3177193269ce94b36ae29e336b0f790820d6af17` passed full CI on Python 3.11 and 3.12: **636 passed, 2 warnings** per matrix job; compile, Ruff, PHP syntax and PostgreSQL integration all passed. Python-only workflow passed **634 passed, 2 skipped, 2 warnings**; its two skips are UDP/PostgreSQL integration tests not configured in that workflow. Full CI: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38062380412 ; Python-only: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38062380419.

- Canonical behavior source: `Source of Truth/IBSng-A1.24.tar.bz2`
- SHA-256: `c7117a6a2fd252aa9b8149a1ee6606f9320888da347ee4f839614bb9349d18a8`
- Main CI passed on Python 3.11 and 3.12: **607 passed, 2 warnings** per matrix job. This includes compile, Ruff, PHP syntax and PostgreSQL-backed integration tests.
- Main CI run: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38003678498
- Lightweight Python run: **605 passed, 2 skipped, 2 warnings**. Its two skips are live UDP/PostgreSQL integration tests because `ATD_TEST_DATABASE_URL` is not configured in that workflow. https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38003678515

## Implemented and tested slices

- Native admin login/session/logout; opaque session token digest storage, expiry/revocation and lock recheck.
- Native admin list/detail with source visibility rules, name/comment update, password change, deposit adjustment and lock/unlock.
- Native administrator permission viewing: `GET /api/v1/admins/{username}/permissions`, gated by `SEE ADMIN PERMISSIONS` and its `SEE ADMIN INFO` dependency; values are returned in stable order without exposing password material.
- Native administrator permission editing: `PUT /api/v1/admins/{username}/permissions/{permission_name}` adds a permission or changes a source-supported value; `DELETE /api/v1/admins/{username}/permissions/{permission_name}` removes a permission only when no assigned permission depends on it; `DELETE /api/v1/admins/{username}/permissions/{permission_name}/values?value=...` removes one value from a multi-value permission. All are gated by `CHANGE ADMIN PERMISSIONS` → `SEE ADMIN INFO` + `SEE ADMIN PERMISSIONS`, use a row lock and same-transaction operational audit. The source-derived catalog covers all 51 A1.24 permissions, including All/Restricted validation and GROUP ACCESS / CHARGE ACCESS / LIMIT LOGIN ADDR value validation.
- Native administrator deletion: `DELETE /api/v1/admins/{username}`, gated by `DELETE ADMIN` → `SEE ADMIN INFO`. It protects the native system account and applies the full A1.24 cleanup/reassignment sequence, emits IAS `DELETE_ADMIN` type 6 only when enabled, revokes sessions through FK cascade, and records ATD operational audit in the same transaction.
- Native administrator creation: `POST /api/v1/admins`, gated by `ADD NEW ADMIN`; validates A1.24 username/password character rules, uses `admins_id_seq`, stores a native MD5-crypt hash, trims name/comment, sets `creator_id` to the authenticated administrator, initializes deposit/due to zero, writes native IAS `ADD_ADMIN` (type 5) only when the native `IAS_ENABLED` flag is enabled (default off), and commits it plus operational audit in the same transaction.
- Password change preserves A1.24 behavior: self-change exemption; other-admin change requires `CHANGE ADMIN PASSWORD` → `SEE ADMIN INFO`; trim and ASCII letters/digits/underscore/hyphen validation; native MD5-crypt output with random 8-character salt. The password/hash is never written to operational audit.
- Lock/unlock preserves A1.24 `admin_locks` semantics. Multiple lock rows can exist; removing one lock does not unlock the admin if another row remains.
- RAS CRUD slice with native session and `LIST RAS` / `GET RAS INFORMATION` / `CHANGE RAS` checks; secret omitted from list response.
- Group CRUD slice with source-derived visibility and permission checks.
- User list/detail/create; native initial credit on creation; single/bulk user-credit changes with deposit rules, native ledger/IAS records and operational audit.
- User attribute mutation for `name`, `comment`, `phone`, `lock`, `multi_login`, `session_timeout`, and `idle_timeout`, with source-specific validation, native user audit and operational audit. `PUT /api/v1/users/{username}/owner` implements A1.24 `owner_name` semantics and requires `CHANGE USERS OWNER` when assigning a user to someone other than the acting admin. `PUT /api/v1/users/{username}/group` implements A1.24's specialized `group_name` updater by changing `users.group_id` (not `user_attrs`), checks target group access, and writes native user audit plus operational audit transactionally.
- User detail connection history and credit history are independently gated by `SEE CONNECTION LOGS` and `SEE CREDIT CHANGES`, including their own owner scope.
- Admin/user/group/RAS mutations covered here write operational audit in the same DB transaction where documented.
- Source-audit tooling catalogs 51 A1.24 admin permission modules. This is a structural inventory, not complete RBAC parity.

## Still open — do not mark complete

1. Administrator volatile activity fields (`last_request_ip`, `last_activity`, `online_status`) remain open; administrator permission editing and deletion are implemented and tested.
2. Extend the user-attribute mutation slice to remaining specialized plugin families; user deletion remains open (source audit recorded in `docs/A1.24-USER-DELETION-AUDIT.md`). Owner transfer and group reassignment have separate implemented routes.
3. Admin-facing online-user listing/permissions and administrative disconnect remain blocked on source-compatible admin identity/permission/audit wiring and supported single-process runtime topology. Inbound RFC 5176 Disconnect-Request and CoA-Request are already handled by the authenticated RADIUS control path; successful Disconnect settles and closes the native connection log and releases the IP-pool lease, while CoA updates only the currently supported authorization attributes. The admin HTTP disconnect endpoint remains intentionally unmounted.
4. Full billing persistence, charging/usage integration, expiry/subscription and report parity.
5. Complete RAS provider runtime/transport interoperability and RADIUS dictionary coverage.
6. XML-RPC compatibility.
7. Database importer, parity validation and rollback.
8. Installer, systemd, TLS, backup/upgrade, supported OS and licensing/edition enforcement.
9. Full UI workflows remain an active parallel workstream; continue UI inventory/specification and non-destructive implementation alongside core, RADIUS/RAS, billing, DB/API, migration and deployment work. Do not silently freeze or drop a workstream; sequence dependent production mutations behind their source-safety gates.

## User deletion source audit — 2026-10-10

The canonical A1.24 paths `core/user/user_handler.py::delUser` and `core/user/user_actions.py::delUser/__delUserQuery/__postDelUser` were traced and recorded in `docs/A1.24-USER-DELETION-AUDIT.md`. Native deletion requires an offline-user guard, blacklist coordination, refund of non-negative user credit to admin deposit, DEL_USER credit history, optional connection/audit-log deletion, IAS DELETE_USER, cleanup of subtype/messages/web-analyzer/bandwidth tables, user-pool change broadcasts, and post-commit mailbox deletion. ATD user deletion remains intentionally unimplemented until authoritative online-session resolution, table/FK parity, transactional refund/IAS/audit behavior, and post-commit side-effect handling are in place. A bare SQL delete is not acceptable.

## Non-negotiable implementation rules

- A1.24 source archive wins over notes, tests, or assumptions.
- Review exact source path/callers/consumers before source-sensitive edits; do not claim all 2,295 files have been exhaustively reviewed.
- Tests prove the tested slice, not complete IBSng parity.
- Do not expose disconnect until native session target resolution, permission dependencies and correct side-effect/audit order are implemented.
- Do not replace the attribute plugin system with arbitrary direct writes to `user_attrs` or related tables.
- Shared API Bearer token is a perimeter gate, never an admin identity.
- Each coherent change requires regression tests, CI and updates to this status ledger/context/roadmap.

## Latest attribute mutation increment — 2026-10-10

Direct source trace: `core/user/user_handler.py::updateUserAttrs`, `core/user/user_actions.py::updateUserAttrsQuery`, `core/user/attribute_manager.py::getAttrUpdaters`, `core/user/attr_updater.py` generic query/audit behavior, and `core/user/plugins/comment.py`.

Added `PUT /api/v1/users/{username}/attributes` for `name`, `comment`, `phone`, `lock`, `multi_login`, `session_timeout`, and `idle_timeout`, plus `PUT /api/v1/users/{username}/owner` for source-backed owner transfer. It requires `CHANGE USER ATTRIBUTES` with the native `GET USER INFORMATION` dependency and owner scope; locks the user row; upserts/deletes native `user_attrs`; preserves `USER_AUDIT_LOG`, `_NOVALUE_`, and `insert_user_audit_log` behavior; and writes operational audit in the same transaction. Unknown attributes and specialized handlers not yet implemented are rejected. The source-traced `lock` updater preserves lock-by-presence semantics; `multi_login` is validated to 0–255; session/idle timeouts are normalized to integer strings. Added repository and API regression tests. Code/test checkpoint `60237946c885c8f541480f9b2428f253950f7772` passed full CI on Python 3.11 and 3.12: **649 passed, 2 warnings** per matrix job, including compile, Ruff, PHP syntax and PostgreSQL integration. Python-only workflow passed **647 passed, 2 skipped, 2 warnings**; its two skips are the live UDP/PostgreSQL integration tests not configured in that workflow. Full CI: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38063523662 ; Python-only: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38063523665.

Next: extend only to specialized attribute families after their source validators, query builders, broadcast and `postUpdate` effects are implemented. User deletion, group reassignment, and online-session safety remain open. Native admin deletion is complete; do not redo that slice without contradictory source evidence.


## Administrator creation IAS parity — 2026-10-10

Source audit against the checksum-verified A1.24 archive confirms `IBSng/core/admin/admin_actions.py` composes the native admin insert and `ias_main.getActionsManager().logEvent("ADD_ADMIN", creator_username, 0, username)` in one database transaction. `IBSng/core/ias/ias_actions.py` maps `ADD_ADMIN` to IAS event type **5**. `IASActions.logEvent` writes no event when `defs.IAS_ENABLED` is false; A1.24's default is `0` in `core/defs_lib/defs_defaults.py`. ATD now checks the native serialized integer flag and, only when enabled, writes the corresponding `ias_event` row (actor = creator username, amount = 0, destination = created username, empty comment) in the same caller-owned transaction as the `admins` insert and operational audit. Missing flag means disabled; malformed serialized values fail closed. ATD's native admin creation repository now writes the corresponding `ias_event` row (actor = creator username, amount = 0, destination = created username, empty comment) in the same caller-owned transaction as the `admins` insert and operational audit. Focused repository/API tests assert the event fields and creator identity. CI verification for code/test commit `aefba4b1079b7ddb7940461e59e572bebd21b834` passed: full CI on Python 3.11 and 3.12, **613 passed, 2 warnings** per matrix job, including compile, Ruff, PHP syntax and PostgreSQL integration; Python-only workflow passed **611 passed, 2 skipped, 2 warnings** (the two live UDP/PostgreSQL tests are skipped in that workflow). Full CI: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38059979595 ; Python workflow: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38059979654.


## Session concurrency increment — 2026-10-10

Added a re-entrant synchronization boundary for the in-process duplicate-request cache and live session registry. `AccountingSessionService.apply` now holds the registry lock across its compound Start/Interim/Stop decisions and related persistence/charging side effects. Added a parallel duplicate-Start regression test (24 concurrent calls, one session and one connection-log insert). Code/test commit: `25b7b9b0f96bf81c68708990bab5f68e13ddbbda`. Full CI passed on Python 3.11 and 3.12: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38070540152 ; Python-only: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38070540153.

Important limitation: this serializes the Accounting-Request resolution→apply path and publishes the same runtime state to API app.state when started through `atd_radius.main`. It is still process-local: external ASGI startup, multi-worker/multi-process active-session truth, restart recovery, and durable authoritative session state remain unresolved. RAS Disconnect and user deletion are still intentionally not exposed. See `docs/A1.24-SESSION-CONCURRENCY-AUDIT.md`.


## User group reassignment increment — 2026-10-10

Source-traced `IBSng/core/user/plugins/group.py::GroupNameAttrUpdater`: group assignment is a special updater that writes `users.group_id`, not a `user_attrs` row, and records user audit attribute `group`. Added `PUT /api/v1/users/{username}/group` with user-owner permission checks, target-group access checks and a `FOR SHARE` lock on the target group. Native user audit and ATD operational audit are written in the same transaction. Repository/API tests cover persistence and denied target-group access. Code/test commit `72896b1fffde57656bea37631f1ab6f8a5f5f3ff`; full CI passed Python 3.11 and 3.12: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38070959390 ; Python-only workflow passed: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38070959368. Detailed audit: `docs/A1.24-USER-GROUP-REASSIGNMENT-AUDIT.md`.


## Accounting request synchronization and runtime ownership — 2026-10-10

The native Accounting-Request path now holds `SessionRegistry.synchronized()` from accounting dispatch through username→user ID and peer IP→RAS ID resolution, session/provider resolution, `AccountingSessionService.apply`, and IP-pool session side effects. This closes the previously identified gap where accounting could resolve a user before a future admin operation acquired the registry lock but apply the session after that operation. `main._start_radius_servers` publishes that same `NativeRadiusRuntimeState` on `app.state.radius_runtime_state` before starting UDP servers, allowing same-process API code to use the exact registry rather than constructing a separate one.

Regression test asserts dispatch, identity lookups and apply all run inside the same registry lock. Code/test commits: `4cc070f0b8960a0ab8e43df2e1adc69c0c53ae5c`, `28d0989c6f43c3fcc8be18b54e5f2caa40dc68f7`. Full CI passed on Python 3.11 and 3.12: **654 passed, 2 warnings** per matrix job (compile, Ruff, PHP syntax and PostgreSQL integration included): https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38074052515. Python-only workflow: **652 passed, 2 skipped, 2 warnings**; skips are the live UDP/PostgreSQL integration tests not configured in that workflow: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38074052624.

This is a runtime-safety foundation, not full session parity. The runtime owner is shared only when the app is launched through `atd_radius.main` with RADIUS enabled; external ASGI launchers/multiple workers do not share process memory. Do not implement user deletion or RAS Disconnect until deployment topology and authoritative online-session/restart behavior are resolved.


## Deletion safety source recheck — 2026-10-10

A further exact trace of A1.24 `core/user/user_pool.py`, `core/user/loaded_user.py` and `core/user/online.py` found a key blocker beyond Accounting-Request synchronization: A1.24 sets `LoadedUser.online_flag` during login preparation and checks a deletion blacklist while holding its user-pool loading lock. It registers a user and individual RAS instances only after native login succeeds; the online flag is cleared only after the final instance logs out. ATD's RADIUS Accounting-Start registry does not represent this login-in-progress state, and Access-Accept may occur before Accounting-Start. Therefore it must not yet be treated as an A1.24-equivalent deletion guard. User deletion and online-user listing remain open until this lifecycle boundary is implemented and tested. See `docs/A1.24-USER-DELETION-AUDIT.md` and `docs/A1.24-SESSION-CONCURRENCY-AUDIT.md`.

## A1.24 VoIP caller-ID updater — verified 2026-10-10

Added dedicated PUT /api/v1/users/{username}/caller-ids and DELETE /api/v1/users/{username}/caller-ids. This follows IBSng/core/user/plugins/caller_id.py: persistence uses native caller_id_users, never user_attrs; authorization uses CHANGE VOIP USER ATTRIBUTES with the source dependency on CHANGE USER ATTRIBUTES and the user's owner scope; caller ID lists support A1.24 MultiStr comma-separated expressions and numeric ranges; existing global caller-ID assignments are rejected; native USER_AUDIT_LOG and ATD operational audit are written transactionally. To address the source's explicit “not thread safe” uniqueness warning, writes serialize with a PostgreSQL SHARE ROW EXCLUSIVE table lock.

Code/test commits: 947ab88df0503ce09ab344f5f4c772420c262672, 52c49e780f4938ba321cf49e49ddaf0e76a5cad7, add93ecfc8766114579489589b6130d52ea6ac2e, 6d21ed779acba45e773f6a2888efcb6263764cf1, ff29222f03cfacbe9dc7c8ecf143e81f327c7121. Full CI passed on Python 3.11 and 3.12: **662 passed, 2 warnings** per matrix job, including compile, Ruff, PHP syntax and PostgreSQL integration: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38081828572. Python-only workflow: **660 passed, 2 skipped, 2 warnings**; the two skipped tests need live UDP/PostgreSQL configuration: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38081828570.

Detailed source audit: docs/A1.24-CALLER-ID-AUDIT.md. The implemented endpoints operate on one named user at a time; A1.24's multi-user caller-ID updater allocation semantics are not exposed as a bulk API. Range expansion is capped at one million expanded values as a resource-safety guard.


## Latest user-attribute increment — 2026-10-10

Enabled `voip_preferred_language` through the existing generic user-attribute mutation endpoint after tracing `IBSng/core/user/plugins/voip_preferred_language.py`. It uses native `user_attrs` storage, generic user-attribute permission/owner scope, and native user audit; no dedicated VoIP table or endpoint is required. Added regression coverage. This is one additional source-backed plugin, not complete VoIP attribute parity. Full CI on Python 3.11 and 3.12 passed: **663 passed, 2 warnings** per matrix job (compile, Ruff, PHP syntax and PostgreSQL integration included). Run: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38082360746. Commit: `581fd60d87f2e15f6f4dd81cf50e0cbbb3772ed6`. See `docs/A1.24-ATTRIBUTE-BEHAVIOR-AUDIT.md`.


## Current work in progress — save_bw_usage marker

Added `save_bw_usage` to the generic attribute mutation slice from `IBSng/core/user/plugins/save_bw_usage.py`. Only the native empty-string marker is accepted; the existing delete path removes it and native audit behavior is retained. Full CI passed on the tested feature commit on Python 3.11 and 3.12: 664 passed, 2 warnings per matrix job (compile, Ruff, PHP syntax and PostgreSQL integration included). Run: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38082764002. The actual bandwidth-usage consumer remains pending.


## Source-backed attribute increment — fast_dial (2026-10-11)

Enabled `fast_dial` in the generic user-attribute mutation API after tracing `IBSng/core/user/plugins/fast_dial.py`. The string representation must contain exactly ten comma-separated entries; each entry is empty or digits only, matching the source's ten-item validation. The source explicitly disables native user audit for both change and delete, so ATD preserves that exception rather than applying the generic audit behavior. Three regression tests cover valid persistence/audit suppression, invalid input rejection before writes, and delete/audit suppression. This is mutation/storage support only; fast-dial runtime redirection and VoIP actions remain open. Full CI passed on Python 3.11 and 3.12: 667 tests passed in each matrix job, 2 warnings per job. CI: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38126347300 ; Python-only: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38126347240.


## Latest verified main state — 2026-10-11

- Current main HEAD at review start: `b1b1b698c0c349e6053fe340accf08d91bb699da` (documentation-only fast_dial CI record).
- Fast-dial code/test checkpoint: `2daa63380a2e9109cb950a057e0e1261bf38dc69`; full CI passed on Python 3.11 and 3.12 with **667 passed, 2 warnings** per matrix job (compile, Ruff, PHP syntax and PostgreSQL integration): https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38126347300. Python-only workflow also succeeded: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38126347240. Latest HEAD's Python workflow succeeded: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38126437021.
- The uploaded A1.24 archive was checksum-verified in this work session against the required SHA-256: `c7117a6a2fd252aa9b8149a1ee6606f9320888da347ee4f839614bb9349d18a8`.
- Source audit `docs/A1.24-FAST-DIAL-RUNTIME-AUDIT.md` traces the A1.24 fast-dial plugin and Asterisk/XML-RPC action flow. It confirms the plugin rewrites `called_number`, calls the RAS redirect-reply method, records `fast_dial_index` in instance metadata, and exposes add/get destination actions. ATD still implements mutation/storage only; runtime redirection, instance metadata lifecycle and actions-manager compatibility remain open. Do not mark fast_dial runtime complete.


## Fast-dial runtime foundation — 2026-10-11

- Added `src/atd_radius/domain/fast_dial.py` and `tests/domain/test_fast_dial.py` as a source-shaped runtime primitive: prefix gating, integer suffix parsing, called-number destination selection, per-instance `fast_dial_index`, redirect callback, and the native actions-manager's separate ten-slot destination validation. Tests explicitly preserve A1.24's Python negative-index behavior rather than imposing a modernized 0..9 restriction on the runtime plugin.
- This is a tested foundation, **not yet wired into a production VoIP/RAS login/update message path**. Runtime adapter integration and XML-RPC/action-manager endpoints remain open.
- Hash check correction: the hash string previously supplied in project instructions has 61 hex characters and is not a valid SHA-256. The uploaded archive's actual SHA-256 is `c7117a6a2fd252aa9b8149a1ee6606f9320888da347ee4f839614bb9349d18a8` (64 hex characters). Do not record these as matching; reconcile the intended reference hash before relying on it as a pin.
- Commits: `318b9b0f` (runtime helper), `8b70ba9b` (tests), `383472b2` (fixture correction). CI for these commits is pending until GitHub Actions completes.


## Fast-dial runtime foundation CI result — 2026-10-11

Current main HEAD: `2dd944de4f8df82792f23912f301d6725263d9ff`. Full CI succeeded on Python 3.11 and 3.12, including compile, Ruff, PHP syntax and test steps: **672 passed, 2 warnings** on Python 3.11 (the Python 3.12 job also passed). CI: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38159213377 ; Python workflow: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38159213530. An earlier intermediate test commit failed because its fixture accidentally used index 72; this was corrected in `383472b2`, and the final HEAD is green. Runtime helper remains unintegrated into the production VoIP/RAS lifecycle.


## Fast-dial action-manager API — 2026-10-12

Implemented `src/atd_radius/infrastructure/fast_dial_actions.py` plus owner-scoped GET/PUT routes under `/api/v1/users/voip/{voip_username}/fast-dial/{index}`. GET returns the stored destination or an empty string for missing/out-of-range slots; PUT validates a digits-only destination and index 0–9, takes a row lock before changing one of ten slots, suppresses native user audit exactly as A1.24 does, and records ATD operational audit. Tests cover storage semantics, negative-index read compatibility, invalid writes, row locking, API permission checks and audit.

**Boundary:** admin action API/storage is implemented; the production VoIP/RAS `s_login`/`s_update` runtime path still does not call the redirect helper. Called-number rewrite, redirect reply and per-instance `fast_dial_index` lifecycle remain open. Do not report full fast-dial parity yet.

Code/test commits: `94485ec9`, `781d8f78`, `b1eec8e8`, `291aec12`, `04d0f713`, `0807517e`. Full CI passed on commit `44c46a5aadee4ed5087f5789694b03a570b6e2b4` on Python 3.11 and 3.12; compile, Ruff, PHP syntax and tests all succeeded. Full CI: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38179760306. Python-only workflow passed for code/test commit `0807517e0cadfe271dc3a776d41c2c20949a595b`: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38179731575. The subsequent `920bf47d` commit only clarified the runtime-cache boundary in a docstring; its CI is still running.


## Bandwidth snapshot accounting increment — 2026-10-12

Traced A1.24 `core/snapshot/bw_snapshot.py`, `core/snapshot/plugins/internet_bw.py`, `core/snapshot/snapshot_main.py`, and `db/tables.sql`. Added `PostgresBandwidthSnapshotRepository` for the native `internet_bw_snapshot(snp_date,user_id,in_rate,out_rate)` table, with non-negative counter checks, timezone normalization, one-minute bucket aggregation, and conflict accumulation. Wired the RADIUS accounting runtime to record positive input/output counter deltas only when the resolved account is a normal user and its **effective** attributes (group defaults then user overrides) contain `save_bw_usage`. Added tests for aggregation, SQL key semantics, retry-safe collector behavior, marker gating and non-normal-user exclusion.

**Compatibility boundary:** A1.24 samples each active instance on its periodic online loop (default `SNAPSHOT_BW_INTERVAL=60`) and sums rates per user. ATD currently derives deltas from Accounting-Request counter changes and buckets those deltas into one-minute rows; this is a useful live integration but is not yet identical to sampling all active instances. Missed Interim-Updates and provider counter behavior need acceptance validation before marking full bandwidth-snapshot parity. Full CI passed on code/test HEAD `f97af48b94204ac2e7d6065d522c29d2583dc76e` (694 passed, 2 warnings on Python 3.11 and 3.12); the subsequent docs-only checkpoint `f87a63cf46c6b271d6efdcc2a7d80af2d649c760` passed both full and Python-only CI. Newer documentation-only commits are tracked separately and must pass CI before they are called green.


## Latest bandwidth snapshot verification — 2026-10-12

Implementation commits include `fbbee3e9` (runtime wiring), `38d68bb7` (record method), `bcb942ad` (A1.24 local-time conversion), `4fc25c53` (batch timestamp normalization), and the follow-up regression commits through `f97af48b`. Python-only CI passed on latest code/test HEAD `f97af48b94204ac2e7d6065d522c29d2583dc76e`: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38180272821. Full CI passed on implementation commit `bcb942adf311b3369dbe1a9d1da486bc1b633433`: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38180263093. The full CI run for the newest test-only adjustment is still in progress; do not claim that exact HEAD's full matrix is green until it completes.


## Current main verification and full Markdown review — 2026-10-12

- Current main HEAD: `f87a63cf46c6b271d6efdcc2a7d80af2d649c760`.
- Full CI on this exact HEAD passed: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38180343444
- Python-only CI on this exact HEAD passed: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38180343421
- The full suite on the preceding implementation/test HEAD `f97af48b94204ac2e7d6065d522c29d2583dc76e` passed on Python 3.11 and 3.12: 694 passed, 2 warnings per matrix job.
- A repository-tree pass found 65 Markdown files. All 65 files were fetched from current `main` and inventoried by headings, status markers, dates, and latest recorded checkpoints. This is the start of a content-consistency audit, not a claim that every historical assertion in every document has already been source-verified.
- The first inconsistency found is stale historical verification language: some older documents still describe later CI runs as pending or describe implementation wiring as pending. Historical checkpoints must remain historically accurate; current status should point to the latest verified HEAD and clearly distinguish full feature parity from tested partial slices.
- The uploaded archive was independently re-hashed: `c7117a6a2fd252aa9b8149a1ee6606f9320888da347ee4f839614bb9349d18a8`. It contains 2,477 archive members and 2,295 regular source files; file inventory includes 453 Python sources, 530 PHP files, 284 Smarty templates, and 20 SQL files.
- Full source review remains an active requirement. Inventory counts are not evidence that every file has been semantically reviewed. Source passes must trace each file's callers, consumers, database effects, runtime hooks, and corresponding ATD implementation/tests, while preserving frozen verified behavior.

### Active continuation order

1. Complete a semantic consistency pass across all 65 Markdown files and correct only demonstrable stale/conflicting current-state statements.
2. Continue full A1.24 source-to-ATD parity passes by subsystem, recording exact source paths and consumers in the parity ledger.
3. Prioritize production integration gaps already source-traced: Fast Dial's authoritative VoIP/RAS login/update lifecycle, bandwidth snapshot sampling semantics, accounting/charging persistence, session/login-in-progress truth, provider interoperability, XML-RPC, schema migration/import, installer/upgrade/rollback.
4. For each coherent implementation batch: source evidence first, focused regression tests, full CI on the resulting HEAD, and status/context/roadmap update. Do not mark a feature complete based on inventory or unit tests alone.


## Content review — specific corrections made 2026-10-12

This review is reading document content against source paths and current code, not counting filenames. Corrections made so far: `save_bw_usage` is now described as a partial accounting-delta consumer rather than unimplemented; native connection-log persistence is recorded as runtime-wired while full source parity remains open; the RADIUS Disconnect/CoA packet boundary is distinguished from an authenticated/provider-integrated kill workflow; current admin creation/deletion/password/permission capabilities are reconciled with older checkpoint text; and UI work is recorded as a continuing parallel workstream rather than frozen. Direct source tracing also confirmed that A1.24 Fast Dial is a VoIP/RAS message hook on both login and update, mutates called_number, stores fast_dial_index per instance, and invokes setRedirectNumber on the reply packet—none of which is provided by ATD's RADIUS-only production runtime today.

The full semantic review of every Markdown document and every source file is not yet complete. Files are marked reviewed only after their claims, dependencies, call sites, persistence effects, implementation and test evidence have been checked; structural inventory alone does not count.


## VoIP tariff persistence increment — 2026-10-12

Added `PostgresVoipTariffRepository` for source-defined `voip_charge_rule_tariff` and `tariff_prefix_list`. The mapping deliberately preserves the native SQL spelling `min_chargable_duration` while exposing the domain field `min_chargeable_duration`; it uses parameterized lookup, supports a missing tariff, and loads prefixes into the existing longest-prefix domain selector. Regression tests cover native column mapping, longest-prefix selection, missing tariff behavior and listing.

This closes the **read-only tariff persistence adapter slice only**. It does not wire VoIP tariff selection into the live RAS/VoIP call lifecycle, implement tariff mutation/permission/audit actions, or prove VoIP charge settlement parity. Those remain backend work; UI and installer remain later-stage workstreams.

Current main at the start of this increment was `aed0b3f112fc7aafd1176b2bd658f5c4ad1f88b3`; full Python workflow run `38183660075` completed successfully. CI for this new increment must be checked on the resulting commit before calling it verified.


## Native VoIP tariff read API — 2026-10-12

Added source-backed `SEE VOIP TARIFF` authorization and read-only API routes for tariff listing and tariff detail by native tariff name. The list omits prefixes as A1.24 `listTariffs` does; detail can include prefixes and applies the native prefix-name regular-expression filter. API output preserves the source spelling `min_chargable_duration`. Regression tests cover permission denial, listing order, optional prefix filtering, unknown tariffs and invalid regex input.

This is the read-only API slice only. `CHANGE VOIP TARIFF` mutation workflows, native validation and transaction semantics, cache reload behavior, and live VoIP charging remain unfinished. UI/installer are still reserved for the final stage.


## VoIP tariff mutation API increment — 2026-10-12

Extended the native tariff adapter beyond reads: create/update/delete tariff, add/update/delete prefix operations now target the A1.24 `voip_charge_rule_tariff` and `tariff_prefix_list` tables. Source-backed checks include the native tariff-name character rule, digit-only prefix codes, non-negative rate/duration values, duplicate tariff/prefix prevention, and blocking tariff deletion while a native `voip_charge_rules` row references it. Mutations use row/table locking and parameterized SQL, then write operational audit in the same transaction.

This does not complete VoIP charging parity. Source-driven tariff mutation APIs are present, but source-compatible cache/live-call lifecycle effects, exact end-to-end charging, billing settlement and full PostgreSQL integration coverage still need verification. CI for this increment is required before treating it as verified.


## A1.24 charge-rule port semantics correction — 2026-10-12

Direct source trace of `IBSng/core/charge/charge_rule.py::anytimeAppliable` found a domain mismatch: A1.24 requires exact port membership or explicit `_ALL_`; an empty port list is not wildcard. Corrected `ChargeRule.applies_to` and changed test fixtures to use explicit `_ALL_` for intended wildcard rules. Added regression coverage for the empty-port case. This affects source-compatible billing rule selection and must remain distinct from the frozen PAP/CHAP/MS-CHAP/MPPE and accounting persistence contracts. Full CI on the resulting commit must pass before this correction is verified.


## Native VoIP charge-rule persistence — 2026-10-12

Added a read-only `PostgresVoipChargeRuleRepository` mapping the native inherited `voip_charge_rules` table and its days/ports child tables. The domain record now preserves `charge_id`, `tariff_id` and `time_limit`, with regression tests for native mapping and charge filtering. This is not yet connected to a production VoIP call lifecycle or credit settlement. The separate source-backed empty-port semantics correction is included in the same source-to-ATD parity track.


CI fixture correction — 2026-10-12: the source-backed empty-port change exposed an integration fixture that inserted an internet charge rule without any `charge_rule_ports` rows. A1.24 does not treat that as a wildcard, so the fixture now inserts the explicit `_ALL_` marker for the intended all-port rule. This keeps the live UDP/PostgreSQL test representative of the native source rather than reverting the compatibility fix.


Source correction — prefix ordering: A1.24 `Tariff.__getPrefixesInfo` applies the optional name regex and then sorts prefix records by `prefix_name` ascending. The API now follows that order. Prefix mutation responses select by `prefix_id` rather than relying on repository row order.


## Verified backend increment — 2026-10-12 (current checkpoint)

Current code HEAD before this status-only commit: `057b69789e9c353a8531d927129e09fafaf3105d`.

Verified on that exact HEAD:
- Full CI: Python 3.11 **720 passed, 2 warnings**; Python 3.12 **720 passed, 2 warnings**. Compile, Ruff, PHP syntax and PostgreSQL integration all passed: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38184422207
- Python-only: **718 passed, 2 skipped, 2 warnings**; the skips are PostgreSQL/UDP integration tests excluded from that workflow: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38184422151

Source-backed work in this increment:
- Added native PostgreSQL VoIP tariff/prefix read and mutation support against `voip_charge_rule_tariff` and `tariff_prefix_list`, including parameterized writes, duplicate prevention, locking, and deletion refusal when a tariff is referenced by `voip_charge_rules`.
- Added `GET/POST/PUT/DELETE /api/v1/voip-tariffs` workflows and prefix add/update/delete endpoints; reads use `SEE VOIP TARIFF`, mutations use `CHANGE VOIP TARIFF`.
- Corrected the native permission chain: `CHANGE CHARGE` depends on `ACCESS ALL CHARGES`; `SEE VOIP TARIFF` and `CHANGE VOIP TARIFF` depend on `CHANGE CHARGE`.
- Added a native `voip_charge_rules` reader preserving `charge_id`, `tariff_id`, `time_limit`, days and ports.
- Corrected A1.24 port semantics: only explicit `_ALL_` is wildcard; an empty port set matches no port. The live PostgreSQL fixture now inserts `_ALL_` where intended.
- Corrected VoIP prefix API ordering to match A1.24's `prefix_name` ascending order.

Still open before UI/installer: VoIP call/RAS lifecycle and charge settlement parity; Fast Dial runtime wiring; periodic bandwidth snapshot parity; authoritative login-in-progress/session state and safe destructive operations; remaining billing administration and rule mutation; XML-RPC/IAS; full database restore/import parity; provider-backed Disconnect/CoA; remaining reports and user/admin workflows. Do not claim backend complete yet. UI and installer remain final-stage workstreams after these backend gates are addressed.


## Native VoIP charge-rule management API — 2026-10-12

Added source-backed endpoints for listing, creating, updating and deleting VoIP charge rules. Persistence uses the A1.24 inherited `voip_charge_rules` table plus `charge_rule_day_of_weeks` and `charge_rule_ports`, the native `charge_rules_id_seq`, and tariff/charge name lookup. Mutations are transaction-scoped and operationally audited. Validation covers source day names, time windows, VoIP charge type, tariff existence, RAS-specific port requirements and overlap checks. The overlap implementation intentionally preserves the legacy A1.24 behavior of comparing equal RAS IDs and literal port intersections rather than silently broadening wildcard conflict semantics.

This is management/persistence parity only. The source's `charge_main.getLoader().loadCharge()` runtime reload behavior and live VoIP call charging, prefix changes during a call, free seconds, missed-call handling, rounding and credit settlement are still not implemented end-to-end. UI and installer remain final-stage work.


## Source-backed VoIP prefix applicability — 2026-10-12

Implemented `select_effective_voip_rule` matching `VoipChargeRule.anytimeAppliable`: for a non-empty called number, a candidate rule is applicable only if its tariff has a matching prefix; an empty called number is allowed before the RAS supplies it. Effective selection retains A1.24's strict-greater-priority replacement behavior. Regression tests cover a non-matching higher candidate, no matching tariff prefix, and the not-yet-acquired called number case. This is a domain primitive; production call lifecycle wiring remains open.


## VoIP charge-rule CRUD regression coverage — 2026-10-12

Added repository tests for updating a rule while replacing its day/port child rows, deleting child rows before the inherited VoIP rule row, and refusing to mutate a rule belonging to a different charge. RAS-specific rules now validate that the RAS exists and that every named port is configured on that RAS; `_ALL_` remains an explicit marker.


## VoIP charge-rule backend increment — 2026-10-12

Code checkpoint before this documentation update: `2d645d7a08e599e53006d38c4d868987caed0aa8`.

New source-backed work in this increment:
- Added VoIP charge-rule list/create/update/delete API workflows using `CHANGE CHARGE` and `ACCESS ALL CHARGES` permission checks, with transactional operational audit.
- Added native PostgreSQL persistence against inherited `voip_charge_rules`, `charge_rule_day_of_weeks`, and `charge_rule_ports`, using `charge_rules_id_seq`.
- Added validation for native charge type, tariff existence, time/day fields, source-style overlap behavior, RAS existence, and named ports configured for the selected RAS.
- Added `select_effective_voip_rule` to match A1.24 `VoipChargeRule.anytimeAppliable`: a non-empty called number must match a prefix in the candidate tariff; an empty called number remains eligible while the RAS has not supplied it.
- Added mocked CRUD regressions and a real PostgreSQL create/update/delete round-trip test using the CI schema.

CI: the preceding code checkpoint `452b9b67cc060136778f8edeb2b5e7ba0c9813c1` passed full CI with **737 passed, 2 warnings** on both Python 3.11 and 3.12. Python-only for the code checkpoint containing the PostgreSQL round-trip test reported **735 passed, 3 skipped, 2 warnings**; PostgreSQL integration is excluded from that workflow. Full CI for `2d645d7` was still running when this note was written, so do not mark that exact checkpoint verified until its CI finishes.

Still open before UI/installer: the native charge loader/cache reload side effect, production VoIP/RAS call lifecycle, call-time rule transitions, free-second tracking, missed-call behavior, rounding across rule transitions, credit settlement, and broader remaining backend parity. Do not enable destructive user/RAS operations until authoritative session/login-in-progress state and provider-backed termination are safe.


## Source-accurate empty-port persistence — 2026-10-12

A deeper trace of `ChargeActions.__addChargeRulePortsQuery` found that an empty submitted port list is stored as one `charge_rule_ports.ras_port = NULL` row, not as zero child rows. The loader returns that SQL NULL unchanged, and `ChargeRule.anytimeAppliable` still does not treat it as a wildcard; only a literal port match or `_ALL_` applies. The VoIP adapter now preserves this exact storage/mapping behavior and overlap checks distinguish SQL NULL from the string `"None"`.


## Verified billing administration checkpoint — 2026-10-12

Code checkpoint `1e66ad4e9f0b418f46da2568915879ceb8ea292f` passed full CI:
- Python 3.11: **749 passed, 2 warnings**
- Python 3.12: **749 passed, 2 warnings**
- Full CI includes Ruff, Python compilation, PHP syntax checks, and PostgreSQL-backed integration tests: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38189213820
- Python-only workflow: **745 passed, 4 skipped, 2 warnings** (PostgreSQL/UDP integration tests are excluded): https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38189213782

Backend work now includes native VoIP tariff/prefix CRUD, VoIP charge-rule CRUD, Internet charge-rule CRUD, transactional operational audit, RAS/port validation, and real PostgreSQL create/update/delete round trips. Internet rule persistence includes native bandwidth leaf IDs and validates paired leaf names, CPM/CPK, positive assumed KPS, and non-negative bandwidth limit. VoIP rule selection now checks called-number prefixes as A1.24 does. Empty submitted port lists persist the native SQL NULL row and are not treated as wildcard; only literal port match or `_ALL_` applies.

Remaining before UI/installer: runtime reload of charge definitions, Internet bandwidth shaping side effects, production VoIP call lifecycle and credit settlement, VoIP rule transitions/free seconds/missed calls/rounding, periodic bandwidth snapshot parity, authoritative login-in-progress/session state, safe provider-backed Disconnect/CoA, XML-RPC/IAS, and full restore/import/report/workspace parity. Do not unfreeze validated PAP/CHAP/MS-CHAP/MPPE/MultiLogin/accounting persistence behavior without direct source evidence.


## Verified charge administration + bandwidth leaf catalog — 2026-10-12

Code checkpoint `32422e4922a8895e72edcddd4b8b9f85005fe3b9` passed full CI:
- Python 3.11: **752 passed, 2 warnings**
- Python 3.12: **752 passed, 2 warnings**
- Ruff, Python compilation, PHP syntax and PostgreSQL integration all passed: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38189408404
- Python-only: **748 passed, 4 skipped, 2 warnings**: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38189408419

Additional backend work: read-only `GET /api/v1/bandwidth-manager/leaves` and leaf-by-name API now map the native `bw_leaf` fields needed by Internet charge rules. Access uses the A1.24 `CHANGE BANDWIDTH MANAGER → CHANGE CHARGE → ACCESS ALL CHARGES` permission chain. The API is intentionally read-only until bandwidth hierarchy mutations can include native validation and safe loader/tree reload side effects.

Still unfinished before UI/installer: write-side bandwidth manager (interfaces/nodes/leaves/services and loader effects), applying/removing Internet bandwidth limits through real RAS/provider operations, charge loader reload after rule mutations, full VoIP call lifecycle/settlement, periodic bandwidth snapshot parity, authoritative login-in-progress/session state, provider-backed Disconnect/CoA, XML-RPC/IAS and complete import/report/workspace parity.


## Verified charge catalog + user charge assignment — 2026-10-12

Code checkpoint `09044676484684c9400025abe3b7364ed924f33e` passed full CI:
- Python 3.11: **771 passed, 2 warnings**
- Python 3.12: **771 passed, 2 warnings**
- Ruff, Python compilation, PHP syntax and PostgreSQL integration passed: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38189815507
- Python-only: **765 passed, 6 skipped, 2 warnings**: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38189815435

New source-backed functionality:
- Charge catalog list/get/create/update/delete with native `charges_id_seq`, `Internet`/`VoIP` type checks, name validation, audit, and delete guards for user/group assignments; deletion removes associated native rule child rows.
- User `normal_charge` and `voip_charge` assignment/get/delete endpoints store native charge IDs in `user_attrs`, validate the corresponding component and charge type, enforce user-change permissions and A1.24 `canUseCharge` rules (visible-to-all, GOD, ACCESS ALL CHARGES, or CHARGE ACCESS), and preserve native user audit names.
- Integration tests cover real PostgreSQL charge catalog mutation/deletion guard and normal/VoIP user charge assignment round trips.

Still open before UI/installer: bandwidth hierarchy writes and runtime shaping, charge loader/RAS reload effects, complete VoIP call lifecycle/settlement, periodic bandwidth snapshot parity, authoritative login-in-progress/session state, provider-backed Disconnect/CoA, XML-RPC/IAS, and complete import/report/workspace parity. This checkpoint does not certify all backend parity.


## Verified IAS event API increment — 2026-10-12

Code checkpoint `35f23bea970f519f3779a7a5afd548951c94a18f` passed full CI:
- Python 3.11: **778 passed, 2 warnings**
- Python 3.12: **778 passed, 2 warnings**
- Ruff, compilation, PHP syntax and PostgreSQL integration passed: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38190051467
- Python-only workflow passed: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38190051470

Added native IAS event list/delete API with GOD-only authorization, using A1.24 event-type IDs, `event_id > from_event_id`, ordered pagination, and parameterized deletes. The API caps pagination at 3000 rows and rejects the legacy `from == to` edge because A1.24's DB helper accidentally omits LIMIT in that case. PostgreSQL integration verifies IAS event read/delete. IAS event list/delete and user-info REST endpoints are implemented with GOD-only authorization. Source audit found no registered `HANDLE IAS EVENTS` permission class; the native IAS handler methods `lockUser` and `lockAdmin` are defined but not registered, so they are not exposed source methods and should not be treated as missing parity. Native XML-RPC transport/auth compatibility remains open.


## IAS permission source correction — 2026-10-12

Direct inspection of the complete A1.24 `core/admin/perms/` directory found no `HANDLE_IAS_EVENTS.py` permission class. Although `IASHandler` calls `canDo("HANDLE IAS EVENTS")`, the permission loader rejects unregistered permission names; `Admin.canDo` bypasses permission checks only for GOD. Therefore the registered native IAS methods are effectively GOD-only in A1.24. The REST IAS event/user-info routes now enforce GOD rather than inventing a grantable `HANDLE IAS EVENTS` permission. The old permission-catalog entry is corrected accordingly.


## XML-RPC request-boundary hardening — 2026-10-12

The /xmlrpc IAS compatibility endpoint now reads request bodies incrementally and enforces the 1 MiB limit during streaming, with an early Content-Length rejection when declared. This avoids buffering arbitrarily large request bodies before applying the existing transport limit. Regression tests cover streamed oversize bodies and declared oversize bodies. Code/test commit: 2b6849b10613ba24354c3296b9c6ed5f17b012f6. Full CI passed on code/test commit 2b6849b10613ba24354c3296b9c6ed5f17b012f6: Python 3.11 and 3.12 each reported 791 passed, 2 warnings; Ruff, compilation, PHP syntax, and PostgreSQL integration all passed (CI run 38228913843). Python-only CI also passed (run 38228913960). This is transport hardening only; full XML-RPC/IAS semantic parity remains open.


## Charge visibility parity correction — 2026-10-12

Direct A1.24 source review confirmed that `ChargeHandler.listCharges` filters by `Admin.canUseCharge(charge_name)` and `getChargeInfo`/`listChargeRules` apply the same per-charge gate. This is not equivalent to requiring `ACCESS ALL CHARGES` for every read: charges marked `visible_to_all` and charges explicitly granted through `CHARGE ACCESS` are usable by the corresponding admin. The charge catalog GET/list/detail and Internet/VoIP charge-rule list endpoints now apply this source-compatible visibility filter; explicitly requested inaccessible charge IDs return 403 and unknown IDs return 404. Mutations remain behind the source `CHANGE CHARGE` dependency chain. Regression coverage includes public, granted, denied, and all-charge access. Code/test commit `7a2d5d15d55b1a74409933851f6eb0c90185b4c3` passed full CI: Python 3.11 and 3.12 each **795 passed, 2 warnings**; Ruff, compilation, PHP syntax and PostgreSQL integration passed (CI run `38229910982`); Python-only workflow passed **787 passed, 8 skipped, 2 warnings** (run `38229910991`). This closes only the read-visibility slice, not complete billing/runtime parity.


### Charge visibility route-level regression tests — 2026-10-12

Added direct route-level tests for charge catalog list/detail and Internet/VoIP rule listing. The tests verify public and explicitly granted charge visibility, filtering of ungranted hidden charges, and 403 on a direct hidden-charge detail request. These strengthen the existing `canUseCharge` unit coverage without broadening the parity claim.


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


## VoIP timer-engine foundation — 2026-10-15

New code slice: `src/atd_radius/application/voip_limit_scheduler.py` adds a thread-safe single-worker timer engine with key-scoped replacement/cancellation, bounded delays and explicit callback error handling; `tests/application/test_voip_limit_scheduler.py` covers its lifecycle races. This is not yet production-integrated. `VoipCharge.checkLimits` scheduling, live provider termination, and restart-safe billing/session recovery remain incomplete. CI for the new slice must be checked before recording it as verified.


## VoIP limit-check orchestration — 2026-10-15

Added `VoipLimitCheckLoop` on top of the one-shot scheduler. It invokes a supplied per-user limit planner, forwards each session's exact kill reason to a supplied termination adapter, reschedules at the next planned boundary, and retries transient planning/provider failures. Regression tests are present. This remains an injectable orchestration layer, not yet wired into `NativeRadiusPacketHandler`; no production provider termination or restart-safe timer recovery is claimed. CI status must be read from the workflow runs for the resulting commits.


## Source-specific RAS termination adapters — 2026-10-15

Added `SourceRASDisconnectClient` for the exact A1.24 ChilliSpot and MVTS RFC 5176 paths. ChilliSpot uses its configured disconnect IP/port and User-Name; MVTS uses the RAS IP/authentication port with User-Name and H323-conf-id. Responses are checked for expected endpoint, identifier and code; MVTS preserves A1.24's explicit exception for zero-filled response authenticators, while ChilliSpot retains RFC response-authenticator verification. Unsupported providers fail closed. Unit tests cover ACK/NAK, endpoint spoofing, source attributes and the MVTS exception.

The client is **not yet wired** into `VoipLimitCheckLoop` or `NativeRadiusPacketHandler`; all other A1.24 provider-specific SNMP/RSH/launcher/telephony actions remain unimplemented. Production timer integration and restart-safe state are still open.


VoIP planner safety follow-up: `VoipLimitPlan.kill_reasons` now carries the full `SessionKey(user_id, ras_id, unique_id)`, not just a provider session string, preventing ambiguous cross-RAS termination when IDs collide. `VoipLimitCheckLoop` forwards that full key. Unsupported provider adapters are treated as a capability gap rather than retried every second. Latest CI for the current commit is pending; do not call this slice green until the actual workflow result is successful.


## Production VoIP limit-loop wiring — 2026-10-15 (CI pending)

`NativeRadiusPacketHandler` now starts and owns `VoipLimitCheckLoop`, refreshes per-user schedules after Accounting packets, opens fresh database transactions for each check, reads native credit/rules/tariffs, and plans only sessions tagged `charge_kind="voip"` by the native user-type router. Per-session decisions use the full `SessionKey`; a successful termination request is marked in process to avoid duplicate requests until Accounting-Stop, and failed requests clear the marker for retry. The loop is closed during normal shutdown.

The actual VoIP runtime termination client currently supports MVTS; other VoIP providers fail closed because their A1.24 H.323/SIP/telephony or SNMP/RSH/launcher side effects are not yet implemented end-to-end. ChilliSpot's source-specific RFC 5176 adapter exists, but ChilliSpot is an Internet provider and is not treated as a VoIP session. In-memory session/timer state is still not restart-safe. Do not mark full `checkLimits` or RAS parity complete. CI for the latest commit must be verified before marking this increment green.

## MVTS source-identity correction — 2026-10-15

A source re-check of `IBSng/core/ras/rases/mvts.py::killUser` found that A1.24 builds Disconnect-Request `User-Name` from the user's `voip_username` attribute, not necessarily the inbound RADIUS `User-Name`/normal IBSng login. The production VoIP termination path now resolves `voip_users.voip_username` through the native user repository in the same fresh transaction and uses it for MVTS; a missing VoIP credential fails closed as a permanent configuration gap instead of sending a disconnect for the wrong identity. Regression coverage verifies the provider sees the source-required username. This is a targeted parity correction, not full provider or restart-recovery completion.

## Accounting identity namespace parity — 2026-10-17

The native accounting identity resolver now checks both A1.24 namespaces: `normal_users.normal_username` and `voip_users.voip_username`. This is separate from Access-Request authentication. Only a unique user ID is accepted; missing or cross-user ambiguous names fail closed so usage is not charged to an arbitrary account. Regression tests cover VoIP-only names, missing identities, collisions, and runtime delegation. CI for commit `8168619ba1334a8e4819977d1eae92abb7d18084` is running. Durable session/timer recovery and the remaining provider-specific termination paths remain incomplete.

## Accounting identity CI follow-up — 2026-10-17

The first CI run after the accounting namespace change caught one stale unit-test fixture: a generic Mock dynamically exposed `accounting_user_id`, so the resolver correctly selected it instead of the legacy fallback the test intended to exercise. The fixture now explicitly sets that optional method to None; production code was not weakened to accommodate the mock. Fix commit: `c2cbb216a22502c7d415552bc9b18db220dcd2ad`. The fix needs a fresh full CI run before this checkpoint can be marked green.

## VoIP limit-rule clock parity correction — 2026-10-17

Production VoIP limit planning now evaluates effective rules using the server's local timezone (datetime.now().astimezone()), matching A1.24's local time.time() / secondsFromMorning rule-window semantics. Passing an explicitly UTC timestamp could select a different day/time rule when the host timezone is not UTC, affecting the next limit deadline or causing an incorrect no-effective-rule termination. Regression test added at commit 0dabee3f0d925ed51620f3a981ddc98602c102e9; GitHub Actions Python workflow is queued at time of this note. This is a targeted timezone-parity correction, not completion of VoIP parity. Durable session/timer recovery and provider-specific termination paths remain open.

## Inbound Disconnect-Request settlement — 2026-10-17

The inbound RFC 5176 Disconnect-Request path now transitions matched sessions through the ordinary accounting lifecycle after the request is accepted: it settles any configured charge, closes the associated native connection_log record, records the last known counters, strips internal runtime-only attributes from persisted event details, and releases any claimed native IP-pool lease. Selection and transition are held under the session registry lock to avoid interleaving Accounting packets. Regression coverage was added in tests/application/test_radius_runtime.py. CI for the new commits is running; this change is not marked verified until the latest run finishes. This does not implement durable session recovery or expand the outbound VoIP provider termination adapters.



## Native RADIUS restart recovery — 2026-10-17

A cohesive recovery path now queries successful `connection_log` rows with no logout time and restores eligible sessions into the in-memory `SessionRegistry` on the first production packet-handler transaction. Recovery restores the native log ID, Acct-Session-Id, last persisted input/output counters, original login timestamp, current RAS MultiLogin capability, and any persisted framed-IP lease; it uses the existing A1.24 tables and adds no parallel session schema. The registry restore operation refuses to overwrite a session already present in memory, and recovery is one-shot per runtime state.

Important boundary: A1.24 `connection_log` does not persist the in-memory charge-rule transition accumulator. The implementation therefore reinitializes the current charge baseline at recovery time rather than fabricating historical accrued transitions. Usage during process downtime and exact historical billing across rule changes still require a durable, source-compatible accounting checkpoint design; restart recovery is a major resilience step, not a claim of full billing parity. Records missing user/RAS/session identity or referencing an unavailable RAS are logged and skipped. Regression coverage exercises query grouping, recovered session identity/counters/log linkage, IP lease reclaim, and one-shot recovery.

The preceding Disconnect-Request regression test had an assertion-type mismatch (the settlement service passes `Decimal` to the persistence contract); that test now asserts the numeric value instead of a string. CI must be checked against the newest commit before treating this batch as green.



## 2026-10-17 continuation: recovery identity and pending IP lease lifecycle

Restart recovery now uses `provider_session_id()` rather than assuming every provider's session key is `Acct-Session-Id`. A regression exposed a wire-name alias gap for `H323-conf-id`; the provider identity table now recognizes the canonical decoded attribute spelling, allowing MVTS call recovery to use the actual H.323 call ID.

Access-Accept IP allocations now carry a process-local pending reservation keyed by RAS and IP with the expected username. Matching Accounting-Start adopts the reservation; a later reject releases a pending allocation; and unadopted reservations are expired after five minutes as RADIUS traffic continues. The implementation uses the existing pool's free/used queue semantics and adds no schema/table. Tests cover pending adoption, expiry, username mismatch and production Access-Request context. This remains partial until live NAS integration, concurrency stress and crash behavior are tested.

Do not mark the current batch verified until the latest CI run finishes. Python-only runs in the preceding intermediate commits exposed fixture/expectation issues, which were corrected in subsequent commits; full CI also intermittently failed during GitHub Actions container initialization.


## Restart recovery — VoIP timer re-arming

On first recovery of native open `connection_log` rows, the runtime now collects users whose restored sessions resolve to an active VoIP charge and re-arms the process-local limit scheduler for those users. This closes the gap where recovered calls could remain open without any timer-driven limit check until another Accounting packet arrived. Regression coverage verifies the recovery result for an MVTS call using its source-defined H323-conf-id. This does not make the timer/session state durable: it rebuilds timers from native open rows at startup, and historical charge-transition accumulators still cannot be reconstructed from the A1.24 schema.


## Native connection_log service classification — 2026-10-17

The Accounting runtime now carries the source-derived service family from the resolved RAS into the persistence event. Native `connection_log.service` is written as 1 for Internet and 2 for VoIP instead of hard-coding Internet for every Accounting-Start. Regression coverage checks both the runtime MVTS service classification and the persisted VoIP service ID. This fixes service classification only; it does not close the remaining restart-safe charge accumulator or full provider accounting parity gaps.


## Service-aware provider session identity — 2026-10-17

Live Accounting now passes the resolved RAS service family into `provider_session_id()`, matching the restart-recovery path. This matters for provider profiles whose online identity differs by service: Cisco Internet uses its port identity, while Cisco VoIP uses the H.323 call ID when present. A runtime regression test verifies that a Cisco VoIP Accounting-Start is keyed by `H323-Conf-ID` rather than incorrectly falling back to `NAS-Port` or `Acct-Session-Id`. This is an identity-resolution fix only; it does not claim full Cisco RAS interoperability.


## Cisco dual-service Accounting dispatch — 2026-10-17

A direct trace of `IBSng/core/ras/rases/cisco.py::__isInternetPacket` and `handleRadAcctPacket` showed Cisco is a dual-service RAS: A1.24 selects Internet only when `Framed-Protocol == PPP`; otherwise the packet enters the VoIP branch, where H.323 call-type/origin checks apply. Added a dedicated accounting service resolver for Cisco and used it before resolving provider session identity. Regression coverage checks both PPP/Internet and H.323/VoIP classification, including the VoIP call-ID key. This is the source-defined packet dispatch boundary, not complete Cisco accounting/termination parity.


Restart recovery now applies the same Cisco Accounting packet discriminator as the live path when selecting the provider session key. A recovered Cisco VoIP connection log containing both H.323 call ID and NAS-Port is restored under the H.323 call identity, avoiding a mismatch between live and post-restart session keys.


## Accounting packet scalar normalization — 2026-10-17

The Accounting event parser now normalizes scalar attributes whether the decoder supplies a direct value or an A1.24-style one-element attribute list. This prevents values such as `['PPP']`, `['NAS-Port']`, or `['H323-Conf-ID']` from leaking into service selection, session identity and persisted native details. Regression coverage exercises status, username, session ID, framed IP, service discriminator, NAS port and counters in list-shaped decoder input. Multi-valued vendor-attribute semantics and complete decoder parity remain separate work.


## Cisco VoIP call-leg gating — 2026-10-17

Added source-derived action gating for Cisco VoIP Accounting: Start/Stop require the VoIP/originate call leg; VoIP Alive no longer triggers normal charge/session lifecycle. The legacy `Telephony/answer` Stop path remains fail-closed until the pre-auth H.323 ID list is implemented. This narrows incorrect charge mutations but is not complete Cisco RAS parity.


## Cisco wire-value and Internet port identity parity — 2026-10-17

The provider identity resolver now decodes Cisco-style H.323 name=value values before using conference IDs and call-leg fields. Cisco Internet session identity now prefers Cisco-NAS-Port and falls back to the source-defined NAS-Port-Type + NAS-Port combination, rather than incorrectly preferring bare NAS-Port. Focused regression tests cover Async-port extraction, concatenated port identity and H.323 wire-form values.


## Cisco VoIP accounting username resolution — 2026-10-17

The Accounting runtime now resolves Cisco RAS and service context before user identity lookup. For Cisco VoIP Start/Stop legs accepted by the source call-leg guard, it splits the concatenated User-Name using cisco_voip_username_length (default 8) before resolving the native VoIP user. This fixes the namespace mismatch where A1.24's Cisco packet contains username+password but native voip_users are keyed by voip_username. Internet and other RAS paths remain unchanged.


## Cisco pre-authorization state parity — 2026-10-17

The runtime now tracks successful Cisco VoIP authorization conference IDs in process-local state. This enables the source-specific Telephony/answer Stop branch only for previously authorized calls, and a normal VoIP/originate Start consumes the corresponding ID. This closes the previous fail-closed gap without broadening acceptance to arbitrary answer-leg packets.


## Cisco Alive handling parity — 2026-10-17

Cisco Internet and VoIP Alive packets no longer enter the normal AccountingSessionService lifecycle. They update only the provider's process-local online tracker according to the source's username/port or H.323 call-leg checks. Start/Stop remain on the charge/session path where A1.24 dispatches user actions.


## Cisco missing-identity safety — 2026-10-19

Cisco session identity now fails closed when its source-defined key is absent: VoIP requires H.323 conference ID; Internet requires Cisco-NAS-Port or NAS-Port-Type + NAS-Port. Generic Acct-Session-Id is no longer used as an accidental fallback for Cisco. Regression coverage protects both service branches.


Cisco restart recovery now has an integration regression asserting that a VoIP row with Acct-Session-Id and NAS-Port but no H.323 conference ID is skipped rather than restored under a false identity.


Follow-up regression confirmed that the generic H.323 alias list also included Acct-Session-Id for other providers. Cisco now uses a dedicated alias subset so an Accounting session ID cannot masquerade as a Cisco H.323 conference ID.


## Verified checkpoint — 2026-10-19

Commit 8a0e4ddd2aadfb42d66c0e4ee762b1c60cc9a85f passed full CI on Python 3.11 and 3.12 (883 passed, 2 warnings each). Strict Cisco source identity is now enforced in live Accounting and restart recovery: no H.323 ID means no Cisco VoIP session identity; no source-defined port means no Cisco Internet identity. See the matching test run and CI links in PROJECT-CONTEXT.md. Cisco caller-ID authorization remains unimplemented and intentionally fails closed.


## Source-backed VoIP termination wiring — 2026-10-19

SourceRASDisconnectClient now delegates Cisco's configured SNMP/RSH kill branch to the existing audited application service and wires the existing PortMaster and Total Control SNMP request builders into the production termination entry point. Provider-specific defaults and source session keys are used; unsupported Cisco RSH port forms fail closed. This expands the automatic VoIP limit-enforcement path, not full provider termination parity. CI must be checked for the current commit.


## Production VoIP termination increment — 2026-10-19

PortSlave and PPPD are now connected to the automatic VoIP limit-enforcement termination path using their A1.24-configured `portslave_kill_port_command` / `pppd_kill_port_command` and exact `(RAS-IP, port)` argument order. Launcher success is accepted only when `succeeded is True`; failures are surfaced as permanent termination errors and are not recorded as successful kills. Regression tests cover both providers and failure results. This code increment requires full CI verification before being treated as verified. Remaining provider termination mechanisms and restart-safe enforcement remain open.


## External termination success semantics — 2026-10-19

A follow-up correctness increment closes a false-success gap in RAS termination. Provider calls no longer treat any non-`None` transport return as proof of success: launcher results must report `succeeded is True`; SNMP results must contain a non-empty sequence of zero-error responses; unknown/empty/error responses fail closed. Regression coverage includes Cisco RSH nonzero exit, Cisco and PortMaster SNMP agent errors, and an empty Total Control response sequence. Remote session disappearance is still not independently verified by a provider poll.


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


## Latest verified runtime batch — 2026-10-20

- Production charge-limit termination reaches source-audited Asterisk AMI, GnuGk, MikroTik, Cisco VPDN, Cisco SNMP/RSH, PortMaster, Total Control, PortSlave/PPPD, ChilliSpot and MVTS adapters where A1.24 defines a kill operation. SER remains unsupported because the canonical source's kill method is a no-op.
- The production limit planner covers normal Internet and VoIP sessions, aggregates per-user active-session charge rates and fails closed on ambiguous mixed charge classification.
- Inbound RFC 5176 Disconnect/CoA processing is part of RadiusRuntimeHandler; Disconnect uses the accounting settlement/persistence path and IP lease release, rather than only toggling an in-memory flag. Administrative online-user/disconnect API is still not exposed.
- Python-only tests: 912 passed, 8 skipped. Latest full CI Python 3.11 passed; Python 3.12 failed before checkout during container initialization and must be rerun. Full matrix verification is still pending.
- Main remaining production blockers: cross-process authoritative session coordination, A1.24 login-in-progress reservations, complete user deletion with refund/IAS/audit/side-effects, complete billing and bandwidth persistence parity, provider live interoperability, full schema/data migration parity, remaining attribute/plugin and XML-RPC parity, UI workflows, installer/upgrade/rollback, and release hardening. Frozen PAP/CHAP/MS-CHAPv2/MPPE and MultiLogin areas will not be reopened without a source-backed defect.


## Authenticated RAS control scope — 2026-10-20

Inbound Disconnect-Request and CoA-Request now constrain session selection to the native RAS resolved from the authenticated UDP peer IP. NAS-IP-Address/NAS-Identifier remain RAS-level identifiers within that scope rather than requiring them to appear in each session detail row. An unresolved RAS returns NAK with Error-Cause 503 and cannot mutate sessions. Tests cover Disconnect cross-RAS isolation, CoA cross-RAS isolation, and unresolved-peer fail-closed behavior.

Validation checkpoint: Python-only suite 916 passed / 8 skipped; full PostgreSQL-backed Python 3.12 suite 924 passed / 2 warnings, plus Ruff, Python compilation and PHP syntax. Python 3.11's latest attempt failed before checkout during container initialization; rerun it before calling the matrix green.


## Durable session-state batch — 2026-10-20

Added ATD-owned `atd_radius_live_sessions` snapshots in migration 007. Accounting transitions persist full active runtime state in the same caller-owned transaction; recovery prefers exact snapshots (including billing accumulators and sessions without connection_log history) and falls back to legacy open native connection_log rows only where no snapshot exists. Legacy recovered rows are upgraded to snapshots. A1.24 `no_connection_log` Stop now discards the early-opened log/details rather than leaving a stale open row.

This is restart recovery progress, not full multi-worker parity. Concurrent workers still need database-coordinated session ownership/mutation. Previous full CI on `9ede4ff39d81788913944385281d303e1554938c` passed 924 tests on PostgreSQL/Python 3.12 and 916 on Python-only; CI on this new session-snapshot batch must run before it is marked verified.


## CI environment correction — 2026-10-20

The session snapshot batch passes the Python-only workflow: 925 passed, 8 skipped, 2 warnings. The full PostgreSQL matrix did not reach checkout/tests on Python 3.11 because the runner's pull of `public.ecr.aws/docker/library/postgres:16` was rejected with `toomanyrequests: Data limit exceeded`; this is a registry/container initialization failure, not a test failure. The CI service image has been switched to the official Docker Hub `postgres:16-alpine` image to avoid the exhausted ECR image quota. Full CI must be rerun on this workflow change.


## Cross-worker Accounting serialization — 2026-10-20

Accounting session mutation now takes a transaction-scoped PostgreSQL advisory lock keyed by the full native session identity, refreshes the state from the durable table after locking, and then applies/persists the event. This closes the stale in-memory counter/charge-state race for Accounting packets arriving at different workers. Stopped tombstones remain for seven days to preserve cross-worker duplicate-Stop idempotency.

Latest completed full CI before this change: Python 3.11 and 3.12 both passed 933 tests, 2 warnings each; Ruff, compilation and PHP syntax passed. The latest Python-only run also passed 925 tests with 8 skips. The new advisory-lock batch is awaiting CI.


## Cross-worker Disconnect/CoA refresh — 2026-10-20

Inbound RFC 5176 control now reconciles the authenticated source RAS's session set against durable snapshots and acquires per-session transaction advisory locks before selecting targets. Sessions active on another worker are visible to control processing; local stale entries are replaced or removed from the authoritative durable result.

Latest full CI before this control-refresh batch: Python 3.11 and 3.12 each passed 935 tests, 2 warnings; Ruff, compilation and PHP syntax passed. Python-only suite passed 927 tests, 8 skipped. This control-refresh change is pending CI.


## Cross-worker login reservation batch — 2026-10-20

Added migration 008 and a PostgreSQL login-reservation repository traced to A1.24's `user_pool.getUserByID(..., online_flag=True)` / `LoadedUser.online_flag` lifecycle. Access-Request admission locks the user before MultiLogin evaluation, refreshes durable sessions, includes reservations accepted by other workers, and excludes only the exact request key for retransmission idempotency. Access-Accept creates a durable reservation; a newly created Accounting Start/Interim consumes one reservation under the same user-level lock. Duplicate Start does not consume another reservation.

Last completed full CI before this batch passed 936 tests on Python 3.11 and 3.12; Python-only suite passed 928 with 8 skips. The login-reservation batch is pending CI.


## Cross-worker enforcement and transactional user deletion — 2026-10-21

- Limit-triggered RAS termination now takes the durable per-session advisory lock and persists its pending marker before issuing the external provider operation. A second worker reloads the durable claim and suppresses a duplicate command. Regression tests cover claim persistence and duplicate suppression. Merged commit: `3430e1d6f585f630898a18f6649f81c2022770df`.
- Charge-limit planning refreshes the user's durable active session set under deterministic session locks before computing deadlines. It includes sessions created by other workers and removes stale local copies. Merged commit: `ed798990a8c755e64c38bd76d74f78d1393b1a33`.
- Source-backed user deletion is implemented on PR #3: owner-scoped `DELETE USER` permission, user-level login reservation lock, online/login-in-progress rejection, native credit refund/history, IAS event, dependent-table cleanup, optional connection/audit history deletion, and transactional operational audit.
- Latest full CI for the deletion implementation: Python 3.11 and 3.12 each passed **950 tests, 2 warnings**, including PostgreSQL integration, Ruff, Python compilation and PHP syntax (run [39598521257](https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/39598521257)). Python-only workflow passed **941 tests, 8 skipped, 2 warnings** (run [39598521382](https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/39598521382)).
- Remaining deletion release gap: no ATD mailbox transport is configured. The endpoint reports and audits `mailbox_cleanup_pending` usernames instead of claiming that the A1.24 post-commit mailbox deletion occurred. Live production backup/restore and concurrent-operation exercises are still needed.
- These increments do not mean the entire IBSng modernization is complete. Schema importer/parity, remaining A1.24 billing/plugin/XML-RPC behavior, full admin/user UI, and installer/upgrade/rollback remain release work.


## Admin online-session reporting and kill action — 2026-10-21

- Added source-backed `SEE ONLINE USERS` and `KILL USER` owner-scoped permissions.
- `GET /api/v1/online-sessions` now reports durable active session snapshots and Access-Accept login-in-progress reservations, without returning credential-bearing attributes.
- `POST /api/v1/online-sessions/disconnect` refreshes authoritative user sessions, verifies ownership and permission, invokes the existing A1.24 provider termination path, and records success/failure in operational audit. It explicitly reports that remote disappearance is not verified until Accounting-Stop.
- Fixed stale local termination markers: durable state is now authoritative, so a worker can retry after another worker clears a failed claim; failure cleanup no longer depends on object identity after refreshing the registry snapshot.
- Latest full CI: **954 passed, 2 warnings** on Python 3.11 and 3.12 (run [39600839533](https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/39600839533)). Python-only: **945 passed, 9 skipped, 2 warnings** (run [39600839199](https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/39600839199)).
- Remaining: live RAS interoperability and proof of remote session disappearance; CLEAR USER semantics remain unimplemented. Full UI, schema import/parity, remaining billing/plugins/XML-RPC, and install/upgrade/rollback are still release blockers.


## Explicit PostgreSQL migration runner — 2026-10-23

A clean-install migration CLI is now implemented on PR branch `feat/safe-migration-runner`:
- `atd-radius-migrate --check`, `--dry-run`, and explicit apply mode.
- Numbered migration validation, SHA-256 ledger, immutable applied-migration checksums, transaction-scoped advisory lock, and all-or-nothing application of pending migrations.
- Refuses an untracked database with existing public tables instead of accidentally applying the clean-install schema to an existing IBSng installation.
- Never runs automatically at service startup; documented in `docs/MIGRATION-RUNNER.md`.

This closes the missing operator-controlled migration-runner mechanism for clean installs, **not** the lossless A1.24 data importer/adoption workflow, backup/restore automation, or verified rollback. Tests cover ordering, checksums, idempotence, unsafe adoption refusal, and rollback after a failed migration. A real PostgreSQL acceptance test applies all eight migrations in an isolated database, verifies the ledger and idempotence, then confirms a deliberately failing ninth migration leaves no schema or ledger residue. Full CI passed on Python 3.11 and 3.12 with **962 passed, 2 warnings per version**; Python-only passed **952 passed, 9 skipped, 2 warnings**. Ruff, compilation, and PHP syntax checks passed. See PR #14.



## Read-only A1.24 adoption preflight — 2026-10-23

Added `atd-radius-a124-preflight` on PR branch `feat/a124-adoption-preflight`. It pins the canonical archive SHA-256 and emits JSON drift evidence for native tables/columns, explicit indexes, sequences, function names and argument signatures, the exact A1.24 `defs` baseline values, the system-admin/GOD seed, core IBS state markers, and the two native deletion-protection rules. It is strictly read-only and supports a nonzero exit with `--fail-on-drift`.

This is an adoption-readiness checkpoint, **not** a lossless importer and not permission to stamp migration versions. Column definition normalization is conservative and can flag equivalent expressions. The report explicitly disclaims constraint semantics, function bodies, plugin objects, all row data, sequence values, backup/restore fidelity, and runtime behavior. These remain release gates. Tests cover schema inventory parsing and both legacy escaped-quote styles in A1.24 `defs.sql`; Latest full PostgreSQL CI passed on Python 3.11 and 3.12 with **971 passed, 2 warnings per version** (run [39939097821](https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/39939097821)). Python-only CI passed **961 passed, 10 skipped, 2 warnings** (run [39939097671](https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/39939097671)). Ruff, compilation, PHP syntax, and PostgreSQL-backed integration checks passed.


## A1.24 semantic-object inventory expansion — 2026-10-23

The read-only adoption preflight now captures target-side PostgreSQL constraint definitions, non-internal trigger definitions, rewrite-rule definitions, and sequence configuration/current-value evidence in its JSON report. Added a PostgreSQL-backed acceptance test that creates an isolated schema with primary/unique/check/foreign-key constraints, functions, a trigger, and a standalone sequence, then verifies the inventory output. This is evidence collection only: semantic comparison with canonical source definitions, function-body parity, sequence ownership/data consistency, complete row-data parity, and backup/restore proof remain release gates. No target database is modified by the preflight command itself.


## A1.24 source-rule parity check — 2026-10-23

Extended the read-only preflight to parse the canonical initial.sql protection rules and compare both native deletion guards against target catalog evidence for presence, event type, target table, and normalized predicate. The check participates in passes_audited_checks, so missing or drifted guards fail --fail-on-drift. Unit coverage covers both A1.24 rule definitions and the parser's fail-closed behavior. This is a narrow semantic comparison, not full constraint/trigger/function parity or approval for adoption.


## A1.24 stored-function body parity — 2026-10-23

The preflight now decodes the quoted function bodies from the canonical A1.24 functions.sql, hashes each body, collects PostgreSQL prosrc hashes keyed by function name and identity argument types, and reports body drift for matching signatures. Body drift is included in passes_audited_checks and therefore fails --fail-on-drift. Parser tests cover doubled SQL quotes and malformed/missing bodies. This closes the function-body comparison gap for the source-defined native function set, but not plugin-specific functions, all data parity, sequence ownership/current-value consistency, or backup/restore validation.


## A1.24 sequence safety validation — 2026-10-23

The read-only preflight now compares source-defined serial ownership mappings with PostgreSQL ownership metadata and checks each target-owned sequence's current value against MAX(owning_column). A sequence that has not been advanced, or is behind explicitly inserted IDs, is reported as drift and blocks passes_audited_checks. Added PostgreSQL acceptance coverage that first verifies a generated identity value is consistent, then inserts an explicit high ID and verifies the mismatch is detected. Manually advanced or unowned sequences and full sequence/data migration semantics still require separate review.


## Complete initial IBS state seed parity — 2026-10-23

The preflight now parses every ibs_states seed from canonical A1.24 initial.sql (currently seven rows) and compares exact values in the target database. Missing or drifted seed values are included in the JSON report and fail --fail-on-drift. Unit tests cover the full seed set and duplicate-source-row rejection. This complements the existing exact defs baseline and admin/GOD guards; it is still not a full data importer or complete parity of all application/plugin rows.


## Exact initial administrator seed parity — 2026-10-23

The preflight now parses the complete positional system-admin seed row using the canonical source table column order and compares every field with the target. It also compares all fields of the explicit GOD permission seed row. Reports expose only drifted field names, not target values or password material. Unit tests cover numeric/string parsing and exact seed shape. This supplements the seven-state-value and defs checks; it does not validate all runtime data or plugin-owned rows.


## Relational constraint signature parity — 2026-10-23

Added source-derived PK, UNIQUE, FK, and CHECK constraint signatures from canonical A1.24 tables.sql and compares them with PostgreSQL catalog semantics, including ordered local/referenced columns and normalized check expressions. Missing or extra signatures now block passes_audited_checks. Unit tests cover inline and table-level constraints; PostgreSQL acceptance tests compare a representative schema against the catalog. Full index-definition and trigger-body parity remain open.


## Explicit index shape parity — 2026-10-23

The preflight now compares each explicit source index's table, uniqueness, access method, key count, expression-index presence, and partial-predicate presence against PostgreSQL catalog metadata. This detects shape drift even when index names match. Full expression and predicate text comparison remains open because PostgreSQL canonicalizes some A1.24 expressions differently from their source SQL; it must be normalized conservatively and tested against the canonical schema before being used as an adoption gate.


## Explicit index expression/predicate parity — 2026-10-23

Extended source and PostgreSQL catalog index inventories to compare normalized expression SQL and partial-predicate SQL in addition to index table, uniqueness, access method, key count, and expression/partial flags. Normalization covers the canonical A1.24 CAST-to-bigint expression and PostgreSQL's IN-list-to-ANY predicate display for user_attrs_abs_exp_date. Any expression/predicate drift now contributes to index_definition_drift and blocks passes_audited_checks. Parser tests cover both canonical and PostgreSQL-rendered forms. This is conservative normalization for the source's current index forms, not a general SQL equivalence engine.


## Preflight partial-schema robustness — 2026-10-23

PR #17 adds guards around all source-seed and marker probes (`defs`, `ibs_states`, system-admin row, GOD permission row, and seed markers). If a target table exists but lacks required columns, the preflight skips the unsafe query and reports the existing missing/drift evidence rather than crashing with a database undefined-column error. Regression tests cover incomplete seed schemas. CI result for this increment: pending at time of note; do not claim verified until both matrix workflows pass.


## Operator backup/restore batch — 2026-10-23

Added the explicit `atd-radius-backup` command: custom-format `pg_dump`, archive-list validation with `pg_restore --list`, SHA-256 sidecar manifest, overwrite protection, manifest-based verification, and restore guarded by an exact configured database-name confirmation. Added unit tests for checksum tampering, archive verification, overwrite refusal and restore confirmation; documented the destructive restore boundary in `docs/BACKUP-RESTORE.md`.

This is operator tooling, not proof of disaster-recovery readiness. Production readiness still requires isolated real-PostgreSQL restore drills, data/application acceptance checks, scheduled off-host retention and monitoring. CI for this batch is running; do not call it verified until both workflows pass.


## Backup safety and round-trip acceptance — 2026-10-23

Hardened the backup CLI by keeping database credentials in the child-process environment (not command-line arguments or the parent process environment), forwarding common libpq TLS/connection options, restricting manifest permissions, and expanding command-path regression tests. Added a real PostgreSQL acceptance test that creates isolated source/target databases, backs up a table with data, restores it into the target, and compares the restored rows. The acceptance test skips only when the PostgreSQL client utilities are absent; CI status for this latest batch is pending.


## A1.24 sequence semantic parity batch — 2026-10-23

The read-only adoption preflight now compares canonical sequence configuration (start/minimum/maximum/increment/cycle/cache) separately from ownership and high-water safety. Explicit A1.24 sequences and serial-generated integer sequences are modeled with their respective PostgreSQL defaults. Regression tests cover extracted defaults, multiple drift fields, missing target-state evidence, and unexpected native-table triggers. CI must be checked against the latest commit before describing this batch as verified; this remains an assessment tool, not an importer or production adoption approval.


## MS-CHAPv2 non-ASCII and MultiLogin regression batch — 2026-10-23

Verified on head `3cb3faac5cb07f771fc9e49a160971199ec0f245`: Python-only workflow passed, and the full PostgreSQL-backed CI matrix passed on Python 3.11 and 3.12. The MS-CHAPv2 AuthenticatorResponse now uses the same A1.24 byte-wise password conversion helper as NT-response verification and MPPE derivation; an explicit non-ASCII regression test covers that parity decision while the RFC ASCII vector remains covered. MultiLogin policy now enforces the configured instance limit before checking the incoming and existing RAS MultiLogin capabilities. False-like RAS values are normalized consistently and rejection reasons retain the established AAA/API mapping. Regression tests cover precedence, existing/incoming RAS restrictions, and the all-RAS-allow case.

This does not close live NAS interoperability or establish the source database/client charset for non-ASCII passwords. Durable accepted-login reservations can remain stale when Accounting never arrives and still require an operational reconciliation path. No claim of full A1.24 runtime parity is made.

## A1.24 import audit evidence — 2026-10-25

The row importer now emits persistent per-table audit evidence: source rows, target counts before/after, source rows verified, rows inserted/updated, and target-only rows preserved. Apply reports also record source and target sequence state and the selected restart/high-water value. The optional `--report-file` output is private (mode 0600), refuses overwrite, and is preflighted before database work. Unit tests cover report privacy and immutable output; PostgreSQL acceptance coverage checks row and sequence report fields.

Latest code checkpoint: `190b99259684fb917021f824490380ed25bba4f8`. Python-only CI passed for this checkpoint. PostgreSQL-backed CI on Python 3.11 and 3.12 is still running; do not mark the latest full matrix green until it completes. No representative restored A1.24 backup is available in this environment, so this is audit tooling progress—not real-world migration validation.

## Explicit login-reservation reconciliation — 2026-10-25

Added an admin-only, audited manual reconciliation endpoint for a single accepted login reservation. It uses the shared per-user advisory lock, checks the exact reservation, blocks removal when a durable active session or successful open connection log exists, requires `CLEAR USER` permission, an explicit offline confirmation, and a nonblank operator reason. There is no automatic TTL because age alone cannot prove that the NAS session is gone. Python-only and full PostgreSQL CI passed on the previous checkpoint `e5a680ddd2f5d8436c1f12da366dee33e94c53fe`; latest validation including whitespace-only reason rejection is running on `20dddd6666ba4d6ed9630347edb4c1a1a7b06cb4`. Manual provider verification remains required.

## Core-first AAA plugin batch — 2026-10-25

The live Access-Request pipeline now runs three source-backed login restrictions from native user attributes:
- `limit_caller_id`: regex search semantics, source-mapped Caller-ID fields for Cisco/GnuGk/MVTS/Tenor, and the explicit allow-missing flag.
- `limit_mac`: conditional check when the provider's source-defined handler supplies `mac`; mappings cover BSAE, ChilliSpot, and MikroTik Ethernet/Wireless.
- `limit_station_ip`: conditional check against individual IPs or IP/netmask ranges; mappings cover PPPD and MikroTik Virtual.

Added provider normalization, domain policy, access-context and actual dispatcher rejection tests. Full PostgreSQL-backed CI passed on code checkpoint `da36df946da9b0400afddd949cc501d29ee60f85` on both Python 3.11 and 3.12; Python-only CI also passed. Commits after that code checkpoint update documentation only, and fresh CI for the latest documentation head is still running. One earlier caller-ID test fixture initially failed because its regex was incorrectly anchored; the fixture was corrected and subsequent Python and full CI runs passed.

This is not completion of all IBSng core behavior. The user-specified sequence is now recorded as a strict gate: finish core parity first, then UI, then installer/upgrade/rollback, then end-to-end capability testing. No UI/installer work is being substituted for core parity.



## Core-first periodic-accounting foundation — 2026-10-26

Added a new domain engine and regression tests for A1.24 periodic-accounting arithmetic: time and traffic usage across active instances, persisted/committed usage, quota checks, per-instance start baselines (including the source's un-clamped traffic deltas), logout accumulation, daily reset scheduling, reset-time baseline rebasing, and estimated remaining time. Monthly reset calculation now ports A1.24's Gregorian/Jalali local-midnight month-boundary helpers; it does not substitute a guessed 30-day month.

This is a meaningful foundation, **not a completed plugin migration**: runtime hook integration, persistent attribute updates, _reload semantics, exact calendar helper wiring and end-to-end quota termination remain open. Full CI for the new commits is running; no result is claimed until GitHub Actions completes.


## Periodic-accounting lifecycle increment — 2026-10-26

Added an application coordinator for the four A1.24 daily/monthly time/traffic quota attributes. It exposes login, update (only rebases when `start_accounting` is explicitly set), logout usage commit, reset processing, quota decisions, remaining-time estimates, and termination callbacks. Added application-level tests for usage persistence and quota exhaustion. This coordinator is an adapter foundation and is not yet wired to the live RADIUS runtime/native attribute repository; parity is not complete until that wiring and multi-worker durability are proven.


The periodic-accounting lifecycle adapter was tightened against the original `periodic_accounting.py`: instance baselines are recorded only when the RAS message carries `start_accounting`; absent baselines contribute zero; update rebases only when that signal is explicit; tests cover both paths.


## Accounting-Stop periodic traffic settlement fix — 2026-10-26

Fixed a lifecycle ordering defect in the live runtime: Accounting-Stop updates and removes the active session before periodic quota logout was reading its traffic counter, so the callback could return zero and subtract the stored baseline from accumulated usage. The runtime now passes the final octet total from the stopped accounting state into the coordinator, which validates and commits that explicit counter. Added regression coverage for a session whose live counter has already disappeared. Full PostgreSQL-backed CI passed on Python 3.11 and 3.12: **1,142 passed, 2 warnings per version**; Ruff also passed. This validates the code path and regression suite, not live NAS interoperability.


## Periodic-accounting reset-boundary source correction — 2026-10-29

A source re-read of canonical `IBSng/core/user/plugins/periodic_accounting.py` found that A1.24 treats `next_reset == time.time()` as due: both `_checkResetTimer` and `s_canStayOnline` use an inclusive `<=` boundary. The modernized domain engine previously deferred the reset until time advanced beyond the exact epoch. Corrected the comparison and replaced the prior strict-boundary assertion with parametrized exact-boundary regressions for daily/monthly time and traffic quotas. This is a narrow source-parity correction; CI for this checkpoint must pass before it is considered validated.


## Importer locked schema revalidation — 2026-10-26

Apply mode now repeats the full source/target compatibility plan after target tables are locked and before staging or row writes. This detects target schema/object drift introduced after preflight and refreshes target row counts under the lock. The new PostgreSQL acceptance test injects a target-only index after the first plan and verifies that the second, locked check refuses the import without changing existing row data.

Validation for this checkpoint: pending its own Python-only and PostgreSQL-backed CI. The previous index-parity checkpoint b6d91555 passed both workflows; that result does not substitute for validation of this change.


## A1.24 importer column-semantics parity — 2026-10-26

Expanded column shape checks to include normalized default expressions and declared collations, alongside order/type/nullability/generated/identity metadata. Added PostgreSQL acceptance coverage for source/target default drift and no-write refusal. This is layered onto locked schema revalidation; validation remains pending until CI for the combined latest checkpoint finishes.


## Importer table-behavior and RLS parity — 2026-10-26

Added source/target checks for table kind/persistence, RLS flags, replica identity, partition-key definitions, and RLS policy definitions/role scopes/expressions. Added PostgreSQL integration coverage for policy drift and no-write refusal. Latest combined checkpoint is pending Python-only and PostgreSQL-backed CI; do not treat this batch as validated until both pass.


## Importer partition/storage semantics — 2026-10-26

Extended table behavior parity to compare partition bounds and parent topology plus table storage options, in addition to relation kind/persistence, RLS flags, replica identity and partition keys. This catches partition-layout/storage drift that column-only checks cannot detect. Validation of the combined importer batch is still pending the latest PostgreSQL-backed CI.
