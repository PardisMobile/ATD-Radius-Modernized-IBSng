# Current project status — ATD Radius / Modernized IBSng

Updated: 2026-10-10  
Repository: `PardisMobile/ATD-Radius-Modernized-IBSng`  
Branch: `main`  
Latest code/test commit: `3b6196b9a38e983e2bce335df2d12e15c4dee08f`

## Authority and validation

- Administrator permission viewing, native admin creation, and IAS `ADD_ADMIN` parity are committed through `aefba4b1079b7ddb7940461e59e572bebd21b834`. CI verification for code/test commit `aefba4b1079b7ddb7940461e59e572bebd21b834` passed: full CI on Python 3.11 and 3.12, **613 passed, 2 warnings** per matrix job, including compile, Ruff, PHP syntax and PostgreSQL integration; Python-only workflow passed **611 passed, 2 skipped, 2 warnings** (the two live UDP/PostgreSQL tests are skipped in that workflow). Full CI: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38059979595 ; Python workflow: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38059979654.

- Canonical behavior source: `Source of Truth/IBSng-A1.24.tar.bz2`
- SHA-256: `c7117a6a2fd252aa9b8149a1ee6606f9320888da347ee4f839614bb9349d18a8`
- Main CI passed on Python 3.11 and 3.12: **607 passed, 2 warnings** per matrix job. This includes compile, Ruff, PHP syntax and PostgreSQL-backed integration tests.
- Main CI run: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38003678498
- Lightweight Python run: **605 passed, 2 skipped, 2 warnings**. Its two skips are live UDP/PostgreSQL integration tests because `ATD_TEST_DATABASE_URL` is not configured in that workflow. https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38003678515

## Implemented and tested slices

- Native admin login/session/logout; opaque session token digest storage, expiry/revocation and lock recheck.
- Native admin list/detail with source visibility rules, name/comment update, password change, deposit adjustment and lock/unlock.
- Native administrator permission viewing: `GET /api/v1/admins/{username}/permissions`, gated by `SEE ADMIN PERMISSIONS` and its `SEE ADMIN INFO` dependency; values are returned in stable order without exposing password material.
- Native administrator creation: `POST /api/v1/admins`, gated by `ADD NEW ADMIN`; validates A1.24 username/password character rules, uses `admins_id_seq`, stores a native MD5-crypt hash, trims name/comment, sets `creator_id` to the authenticated administrator, initializes deposit/due to zero, writes native IAS `ADD_ADMIN` (type 5) only when the native `IAS_ENABLED` flag is enabled (default off), and commits it plus operational audit in the same transaction.
- Password change preserves A1.24 behavior: self-change exemption; other-admin change requires `CHANGE ADMIN PASSWORD` → `SEE ADMIN INFO`; trim and ASCII letters/digits/underscore/hyphen validation; native MD5-crypt output with random 8-character salt. The password/hash is never written to operational audit.
- Lock/unlock preserves A1.24 `admin_locks` semantics. Multiple lock rows can exist; removing one lock does not unlock the admin if another row remains.
- RAS CRUD slice with native session and `LIST RAS` / `GET RAS INFORMATION` / `CHANGE RAS` checks; secret omitted from list response.
- Group CRUD slice with source-derived visibility and permission checks.
- User list/detail/create; native initial credit on creation; single/bulk user-credit changes with deposit rules, native ledger/IAS records and operational audit.
- User detail connection history and credit history are independently gated by `SEE CONNECTION LOGS` and `SEE CREDIT CHANGES`, including their own owner scope.
- Admin/user/group/RAS mutations covered here write operational audit in the same DB transaction where documented.
- Source-audit tooling catalogs 51 A1.24 admin permission modules. This is a structural inventory, not complete RBAC parity.

## Still open — do not mark complete

1. Admin permission editing, admin deletion, and volatile activity fields. Admin creation writes native IAS `ADD_ADMIN` event type 5 only when `IAS_ENABLED` is on (native default is off). Admin creation, admin-deposit adjustments, user initial credit, and single/bulk user-credit events now all honor the flag; IAS enable/disable parity validated on code/test commit `3b6196b9a38e983e2bce335df2d12e15c4dee08f`: full CI passed on Python 3.11 and 3.12 with **616 passed, 2 warnings** per matrix job; Python-only workflow passed **614 passed, 2 skipped, 2 warnings**. The two skips are live UDP/PostgreSQL integration tests not configured in the lightweight workflow. Full CI: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38060443028 ; Python workflow: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38060443040. Permission editing remains blocked until full source permission value validation/dependency behavior is registered.
2. User attribute mutation/deletion/owner transfer through source-equivalent A1.24 action/plugin paths.
3. Online-user listing/permissions and safe disconnect/CoA session resolution, permission, side-effect and audit sequencing. **RAS disconnect remains unmounted.**
4. Full billing persistence, charging/usage integration, expiry/subscription and report parity.
5. Complete RAS provider runtime/transport interoperability and RADIUS dictionary coverage.
6. XML-RPC compatibility.
7. Database importer, parity validation and rollback.
8. Installer, systemd, TLS, backup/upgrade, supported OS and licensing/edition enforcement.
9. Full UI workflows — UI expansion remains frozen until core, RADIUS/RAS, billing, DB/API, migration and deployment stabilize.

## Non-negotiable implementation rules

- A1.24 source archive wins over notes, tests, or assumptions.
- Review exact source path/callers/consumers before source-sensitive edits; do not claim all 2,295 files have been exhaustively reviewed.
- Tests prove the tested slice, not complete IBSng parity.
- Do not expose disconnect until native session target resolution, permission dependencies and correct side-effect/audit order are implemented.
- Do not replace the attribute plugin system with arbitrary direct writes to `user_attrs` or related tables.
- Shared API Bearer token is a perimeter gate, never an admin identity.
- Each coherent change requires regression tests, CI and updates to this status ledger/context/roadmap.

## Next work

Continue with **admin permission editing and deletion**, after tracing A1.24 permission value validators/dependencies and delete cascades. Then proceed to user attribute lifecycle through source plugins. Do not redo already-tested slices above without contradictory direct source evidence.


## Administrator creation IAS parity — 2026-10-10

Source audit against the checksum-verified A1.24 archive confirms `IBSng/core/admin/admin_actions.py` composes the native admin insert and `ias_main.getActionsManager().logEvent("ADD_ADMIN", creator_username, 0, username)` in one database transaction. `IBSng/core/ias/ias_actions.py` maps `ADD_ADMIN` to IAS event type **5**. `IASActions.logEvent` writes no event when `defs.IAS_ENABLED` is false; A1.24's default is `0` in `core/defs_lib/defs_defaults.py`. ATD now checks the native serialized integer flag and, only when enabled, writes the corresponding `ias_event` row (actor = creator username, amount = 0, destination = created username, empty comment) in the same caller-owned transaction as the `admins` insert and operational audit. Missing flag means disabled; malformed serialized values fail closed. ATD's native admin creation repository now writes the corresponding `ias_event` row (actor = creator username, amount = 0, destination = created username, empty comment) in the same caller-owned transaction as the `admins` insert and operational audit. Focused repository/API tests assert the event fields and creator identity. CI verification for code/test commit `aefba4b1079b7ddb7940461e59e572bebd21b834` passed: full CI on Python 3.11 and 3.12, **613 passed, 2 warnings** per matrix job, including compile, Ruff, PHP syntax and PostgreSQL integration; Python-only workflow passed **611 passed, 2 skipped, 2 warnings** (the two live UDP/PostgreSQL tests are skipped in that workflow). Full CI: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38059979595 ; Python workflow: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38059979654.
