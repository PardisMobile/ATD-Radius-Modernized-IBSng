# IBSng-to-ATD Migration Map

This document defines the first implementation boundary from the verified A1.24 source.

| IBSng area | ATD treatment | First milestone |
|---|---|---|
| User core/plugins | Rewrite domain + application services | User CRUD/auth policy |
| Groups | Rewrite with explicit inheritance | Group CRUD + effective policy |
| Services | Rewrite as reusable policy objects | Service assignment |
| Attributes | Preserve semantics, modernize storage/resolution | Effective attributes |
| RAS | Provider registry + typed adapters | Generic + MikroTik/Cisco targets |
| IPPool | Transaction-safe PostgreSQL allocator | allocate/release/exclude |
| Radius server | Rewrite protocol boundary | Access-Request/Accept/Reject |
| Request list | Rewrite as idempotency/duplicate cache | duplicate detection |
| Accounting | Rewrite as durable event/session ledger | Start/Interim/Stop |
| Charge | Rewrite behind billing application service | usage/credit ledger |
| Reports | Rewrite from normalized query models | first operational reports |
| XML-RPC | Compatibility adapter | selected legacy methods |
| PHP/Smarty UI | Do not port templates; preserve workflows | ATD admin shell + Users |
| Installer/init.d | Retire | systemd + supported Linux |
| Python 2 runtime | Retire | Python 3.12+ |
| EAP | New ATD capability | state machine + methods |

## Compatibility priority

1. User authentication and authorization behavior.
2. Group/service/attribute resolution.
3. RAS and IP allocation.
4. RADIUS accounting and session lifecycle.
5. Charging/credit.
6. Administrative workflows.
7. XML-RPC compatibility for integrations that need it.

## Non-goals

- Blind source conversion from Python 2 to Python 3.
- Reproducing Smarty templates.
- Preserving obsolete init scripts.
- Recreating every legacy UI page before the core behavior is tested.
