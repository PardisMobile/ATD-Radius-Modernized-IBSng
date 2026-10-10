# Current project status — ATD Radius / Modernized IBSng

Updated: 2026-10-10  
Repository: `PardisMobile/ATD-Radius-Modernized-IBSng`  
Branch: `main`  
Latest code/test commit: `25b7b9b0f96bf81c68708990bab5f68e13ddbbda` (session concurrency locking; CI verified)

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
- User attribute mutation for `name`, `comment`, `phone`, `lock`, `multi_login`, `session_timeout`, and `idle_timeout`, with source-specific validation, native user audit and operational audit. `PUT /api/v1/users/{username}/owner` implements A1.24 `owner_name` semantics and requires `CHANGE USERS OWNER` when assigning a user to someone other than the acting admin.
- User detail connection history and credit history are independently gated by `SEE CONNECTION LOGS` and `SEE CREDIT CHANGES`, including their own owner scope.
- Admin/user/group/RAS mutations covered here write operational audit in the same DB transaction where documented.
- Source-audit tooling catalogs 51 A1.24 admin permission modules. This is a structural inventory, not complete RBAC parity.

## Still open — do not mark complete

1. Administrator volatile activity fields (`last_request_ip`, `last_activity`, `online_status`) remain open; administrator permission editing and deletion are implemented and tested.
2. Extend the user-attribute mutation slice to remaining specialized plugin families; user deletion remains open (source audit recorded in `docs/A1.24-USER-DELETION-AUDIT.md`). Owner transfer has a separate implemented route.
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

Important limitation: this only serializes operations within one process. The API and UDP runtime still do not share an authoritative runtime owner, and multi-process active-session truth/restart recovery remain unresolved. Therefore RAS Disconnect and user deletion are still intentionally not exposed. See `docs/A1.24-SESSION-CONCURRENCY-AUDIT.md`.
