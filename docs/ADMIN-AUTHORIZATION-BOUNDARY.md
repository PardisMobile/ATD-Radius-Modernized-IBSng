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

**Important:** This is a first native identity/session slice, not complete RBAC. The RAS CRUD routes now require `X-Admin-Session` and enforce the source-traced `LIST RAS`, `GET RAS INFORMATION`, and `CHANGE RAS` permissions (including dependencies and GOD behavior). RAS mutation audit events are inserted in the same transaction as each mutation. The RAS list response no longer returns `radius_secret`; that field is limited to the detail route. Groups now require a native admin session: list/detail enforce source-derived group visibility; create/delete require `ADD NEW GROUP`; update/attribute changes enforce `CHANGE GROUP`, its dependency, ownership/access scope, and GOD bypass. Group mutations are audited in the same transaction. User list/detail routes now require a native admin session and enforce `GET USER INFORMATION` with `All`/`Restricted` owner scope. User detail report fields are independently gated by the A1.24 `SEE CONNECTION LOGS` and `SEE CREDIT CHANGES` permissions, including each permission's own `All`/`Restricted` owner scope; unauthorized report data is returned as `null` and is not queried. User creation requires `ADD NEW USER`, an accessible group, assigns the authenticated admin as owner, and audits creation transactionally. The create API now requires `group_id` to preserve the native owner/group model. Broader user mutation routes (attribute changes, credit, deletion, and disconnect) are not exposed by this API slice; any future endpoints must enforce their individual source permissions and dependencies. RAS disconnect remains unmounted until the broader authorization, trusted target-session resolution, and side-effect sequencing are complete.
