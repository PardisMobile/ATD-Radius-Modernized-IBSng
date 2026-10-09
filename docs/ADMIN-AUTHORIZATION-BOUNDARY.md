# Administrator authorization boundary

## Source-derived constraints

The canonical IBSng A1.24 source archive is the behavioral authority. Directly inspected source paths are recorded in docs/A1.24-ADMIN-PERMISSION-AUDIT.md.

- hasPerm(name) checks permission presence only.
- checkPerm(name, ...) evaluates the registered permission and denies unknown permissions or missing required arguments.
- canDo uses checkPerm, except for the source-defined GOD administrator bypass.
- Permission values are stored in admin_perms as text. Multi-values are comma-separated; an empty multi-value becomes an empty list.
- Permission dependencies are enforced by application code. The source-defined KILL USER permission depends on SEE ONLINE USERS.
- Native admin locks are loaded separately from permission values.

## ATD implementation boundary

src/atd_radius/domain/admin_permissions.py provides a testable evaluator for explicitly registered permission specifications. It distinguishes presence from authorization, supports no-value/single-value/multi-value/contextual permission types, dependency checks, cycle denial, and the source-defined GOD bypass in can_do.

The current implementation now includes `application/admin_authentication.py`. It reads the native admin record, verifies A1.24-compatible legacy password values via `domain/ibsng_password.py`, enforces `LIMIT LOGIN ADDR` as a comma-separated allowlist of IPv4/IPv6 addresses or address/netmask entries, then rejects any admin with one or more native lock rows. This order follows the source login path: password check, address restriction, lock check. Tests cover a canonical MD5-crypt vector, plaintext compatibility, address allow/deny, and lock denial.

This is not yet complete A1.24 RBAC parity. Only register permission definitions and value rules after tracing their actual A1.24 source. Unknown permissions fail closed. The native admin login/session slice is implemented in the API, but the permission registry remains intentionally incomplete. The API shared bearer token must never be treated as an administrator identity.

Do not expose RAS disconnect or other privileged endpoints until the application resolves a trusted native administrator identity, loads permissions and locks from PostgreSQL, resolves the target session from trusted runtime state, enforces the exact permission and dependencies, and records an audit outcome in the correct transaction/side-effect order.


## Native admin session transport — 2026-10-10

- `POST /api/v1/admin/login` authenticates a native admin and issues an opaque random session token. The existing shared API Bearer token remains a separate perimeter gate for this route.
- `migrations/006_admin_sessions.sql` stores only the SHA-256 token digest, expiry, revocation timestamp, admin foreign key, and login address. The raw token is returned only at login.
- `GET /api/v1/admin/session` accepts `X-Admin-Session`, validates that the session is not revoked/expired, and rechecks the native admin lock. `DELETE /api/v1/admin/session` revokes the session and writes a successful logout audit event.
- Successful login and logout audit records share the same DB transaction as session creation/revocation. Failed logins are not yet written to the current operational audit schema because it requires a valid non-null admin actor; do not fabricate one for unknown usernames.
- Session lifetime defaults to eight hours and is configurable with `ATD_ADMIN_SESSION_TTL_SECONDS`.

**Important:** This is a first native identity/session slice, not complete RBAC. The RAS CRUD routes now require `X-Admin-Session` and enforce the source-traced `LIST RAS`, `GET RAS INFORMATION`, and `CHANGE RAS` permissions (including dependencies and GOD behavior). RAS mutation audit events are inserted in the same transaction as each mutation. The RAS list response no longer returns `radius_secret`; that field is limited to the detail route. Groups now require a native admin session: list/detail enforce source-derived group visibility; create/delete require `ADD NEW GROUP`; update/attribute changes enforce `CHANGE GROUP`, its dependency, ownership/access scope, and GOD bypass. Group mutations are audited in the same transaction. User list/detail routes now require a native admin session and enforce `GET USER INFORMATION` with `All`/`Restricted` owner scope. User detail report fields are independently gated by the A1.24 `SEE CONNECTION LOGS` and `SEE CREDIT CHANGES` permissions, including each permission's own `All`/`Restricted` owner scope; unauthorized report data is returned as `null` and is not queried. User creation requires `ADD NEW USER`, an accessible group, assigns the authenticated admin as owner, and audits creation transactionally. The single-user credit endpoint (`POST /api/v1/users/{username}/credit`) independently enforces `CHANGE USER CREDIT` plus `GET USER INFORMATION` owner scope, locks the user and admin deposit rows, checks non-negative user credit and `NO DEPOSIT LIMIT`, and writes native credit/IAS logs plus operational audit in the same transaction. The create API requires `group_id` and supports source-derived initial credit/deposit/log handling. Single and bulk user-credit routes are implemented with source permissions and native ledger writes. Broader user mutation routes for attribute changes and deletion remain unexposed; disconnect remains unmounted. Future endpoints must enforce their individual source permissions and dependencies. RAS disconnect remains unmounted until the broader authorization, trusted target-session resolution, and side-effect sequencing are complete.


## Administrator lock lifecycle — 2026-10-10

Source paths directly inspected: `IBSng/core/admin/admin_handler.py:104-119`, `core/admin/admin_actions.py:313-349`, and `core/admin/admin_lock.py`. ATD routes are `POST /api/v1/admins/{username}/locks` and `DELETE /api/v1/admins/{username}/locks/{lock_id}`. Both require `CHANGE ADMIN INFO` with the native `SEE ADMIN INFO` dependency. Lock rows retain reason, locker admin ID and the native sequence; unlock is scoped to both target admin ID and lock ID. Multiple lock rows are allowed, and the native login/session boundary denies access while any lock remains. Mutations and operational audit share the transaction. Admin password changes, permission editing, create/delete and volatile activity parity are still open.


## Administrator password changes — 2026-10-10

Source paths: `IBSng/core/admin/admin_handler.py:47-52`, `core/admin/perms/CHANGE_ADMIN_PASSWORD.py`, `core/lib/password_lib.py`, and `core/admin/admin_actions.py:54-81`. ATD exposes `PUT /api/v1/admins/{username}/password`. Self-change is allowed without `CHANGE ADMIN PASSWORD`; changing another admin requires that permission and its `SEE ADMIN INFO` dependency. Submitted password is stripped and validated against A1.24's allowed character set; the native `admins.password` field is updated using compatible MD5-crypt. Audit does not include the password/hash and shares the update transaction. This hash format is used solely for native IBSng compatibility.
