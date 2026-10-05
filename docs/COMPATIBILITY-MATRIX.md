# IBSng A1.24 → ATD Compatibility Matrix

This is the master parity ledger. A feature is not considered migrated merely because a similarly named model or endpoint exists. The implementation must preserve behavior, data, permissions and operator workflow.

## Rules

- Every IBSng capability gets a stable ATD capability ID.
- Source location is recorded before conversion.
- Core behavior, persistence, protocol behavior and UI workflow are tracked separately.
- A capability reaches **Complete** only when implementation and tests demonstrate parity.
- Additive ATD features (currently EAP and modern UX) are marked as `ATD-only` rather than pretending they came from IBSng.

## Current high-level ledger

| Capability | IBSng A1.24 reference | ATD target | Status |
|---|---|---|---|
| User identity | `core/user/*` | `domain.User` + user repositories/services | In progress |
| User attributes | user/plugin attribute system | Typed Attribute Policy Engine | In progress |
| Group policy | `core/group/*` and group plugins | Group policy + resolver | In progress |
| Service policy | service/plugin behavior | Service policy + resolver | In progress |
| RAS/NAS | `core/ras/*`, `radius_server/*` | RAS registry/adapters | Foundation |
| IP pools | `core/ippool/*` | Transaction-safe allocator | Foundation |
| Sessions | session/accounting plugins | Session domain + accounting store | Foundation |
| RADIUS authentication | `radius_server/*` | Python RADIUS server | Not started |
| PAP | IBSng RADIUS auth | RADIUS auth pipeline | Not started |
| CHAP | IBSng RADIUS auth | RADIUS auth pipeline | Not started |
| MS-CHAP | IBSng RADIUS auth/plugin behavior | RADIUS auth pipeline | Not started |
| Accounting | `radius_server/*` + accounting plugins | Accounting engine | Not started |
| Duplicate requests | IBSng RADIUS request handling | Request deduplication/idempotency | Not started |
| Disconnect | RADIUS/RAS behavior | RADIUS CoA/Disconnect adapter | Not started |
| Charging | charge plugins/core | Billing/charge engine | Foundation |
| Credit | credit plugins/core | Credit ledger/policy | Foundation |
| Reports | `interface/admin/report/*` | Report subsystem | Not started |
| Graphs | `interface/admin/graph/*` | Metrics/graphs | Not started |
| Admin permissions | admin/user management | RBAC/permission service | Foundation |
| XML-RPC/IAS | IBSng XML-RPC interfaces | Compatibility adapter | Not started |
| Admin UI | `interface/admin/*` + Smarty | Modern PHP 8 ATD UI | In progress |
| User UI | `interface/user/*` + Smarty | Modern user workspace | In progress |
| EAP | Not present in A1.24 | EAP subsystem | ATD-only / foundation |

## Attribute policy milestone

The attribute system is a first-class compatibility surface. The modern engine keeps:

- scope/provenance (system, RAS, service, group, user)
- deterministic precedence
- typed values
- multi-valued attributes
- explicit set/add/remove/replace operations
- explainability for the UI and audit tooling

The current implementation is deliberately additive and does not remove the older simple resolver API until all callers are migrated.

## Database compatibility

The final migration target is lossless restoration of an IBSng backup into ATD semantics. Schema normalization may differ where required by the modern architecture, but migration must preserve records and behavior. A future parity validator will compare users, groups, services, attributes, RAS, IP pools, sessions, accounting, billing, administrators and permissions before/after migration.

## Completion gate

No subsystem is marked complete until its source inventory, ATD implementation, database mapping, permissions, UI workflow and automated/integration tests are linked from this document or its subsystem ledger.
