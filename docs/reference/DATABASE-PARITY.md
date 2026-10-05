# Database Parity Model — First Pass

ATD uses a normalized PostgreSQL model. The legacy database remains an import source, not the long-term schema.

## Identity and policy

- `users`: stable identity and lifecycle state.
- `user_credentials`: authentication material and credential metadata.
- `groups`: subscriber/policy groups.
- `services`: reusable service definitions.
- `user_groups`: user-to-group membership.
- `user_services`: explicit service assignment.
- `attributes`: typed policy attributes.
- `attribute_bindings`: scope + precedence for RAS/group/service/user attributes.

## Network

- `ras`: NAS/RAS identity, type, address and shared-secret reference.
- `ip_pools`: named IPv4 allocation networks.
- `ip_pool_addresses`: explicit allocation state and reservation metadata.
- `ip_allocations`: auditable lease history.

## AAA/session

- `sessions`: authentication/session lifecycle.
- `accounting_events`: immutable Start/Interim/Stop events.
- `radius_request_cache`: duplicate request/idempotency state.
- `disconnect_requests`: controlled session termination requests.

## Billing

- `plans`: reusable service/billing plans.
- `charges`: charge definitions.
- `credit_ledger`: append-only financial/usage ledger.
- `subscriptions`: service-plan lifecycle and expiry.

## Administration

- `admins`: operator identities.
- `permissions`: explicit capabilities.
- `admin_permissions`: RBAC assignment.
- `audit_log`: security-sensitive administrative actions.

## Invariants

1. Usernames are unique within the configured identity namespace.
2. IP allocation is serialized transactionally; two concurrent requests cannot receive the same address.
3. Accounting events are idempotent by NAS/session/event identity.
4. Credit changes are ledger entries; balance is derived or transactionally maintained from the ledger.
5. Effective attributes are resolved deterministically by documented precedence.
6. Secrets are never stored in source control or returned by ordinary API responses.
