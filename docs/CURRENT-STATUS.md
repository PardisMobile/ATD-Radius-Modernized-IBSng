# Current project status — ATD Radius / Modernized IBSng

Updated: 2026-10-10  
Repository: `PardisMobile/ATD-Radius-Modernized-IBSng`  
Branch: `main`  
Latest code/test commit: `ff29222f03cfacbe9dc7c8ecf143e81f327c7121` (source-backed VoIP caller-ID mutation; CI verified)

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
9. Full UI workflows — UI expansion remains frozen until core, RADIUS/RAS, billing, DB/API, migration and deployment stabilize.

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

Enabled `voip_preferred_language` through the existing generic user-attribute mutation endpoint after tracing `IBSng/core/user/plugins/voip_preferred_language.py`. It uses native `user_attrs` storage, generic user-attribute permission/owner scope, and native user audit; no dedicated VoIP table or endpoint is required. Added regression coverage. This is one additional source-backed plugin, not complete VoIP attribute parity. See `docs/A1.24-ATTRIBUTE-BEHAVIOR-AUDIT.md`.
