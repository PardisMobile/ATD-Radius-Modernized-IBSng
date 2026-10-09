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

This is not yet complete A1.24 RBAC parity. Only register permission definitions and value rules after tracing their actual A1.24 source. Unknown permissions fail closed. Authentication, login/session bootstrap, password verification, admin-lock enforcement, and permission loading from PostgreSQL are not implemented by this module. The API shared bearer token must never be treated as an administrator identity.

Do not expose RAS disconnect or other privileged endpoints until the application resolves a trusted native administrator identity, loads permissions and locks from PostgreSQL, resolves the target session from trusted runtime state, enforces the exact permission and dependencies, and records an audit outcome in the correct transaction/side-effect order.
