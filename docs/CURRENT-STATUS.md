# Current project status — ATD Radius / Modernized IBSng

Updated: 2026-10-12  
Repository: `PardisMobile/ATD-Radius-Modernized-IBSng`  
Branch: `main`  
Latest verified code/test commit: `5429fde6d17249568277c143c21e98732f1a427e` (bandwidth interface/tree/node read API; full CI run `38285636476`: Python 3.11 and 3.12 each 804 passed, 2 warnings; Ruff, compilation, PHP syntax and PostgreSQL integration passed). Python-only run `38285636565`: 796 passed, 8 skipped, 2 warnings. Check Actions separately for the latest documentation-only HEAD.

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
3. Online-user listing/permissions and safe disconnect/CoA session resolution, permission, side-effect and audit sequencing. **RAS disconnect remains unmounted.**
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
- The uploaded A1.24 archive was checksum-verified in this work session against the required SHA-256: `c7117a6a2fd252aa9b8149a1ee6606f9320888da347ee4f839bb9349d18a8`.
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
