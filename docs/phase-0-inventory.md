# Phase 0 Inventory

## Confirmed reference subsystems

- Python core server and XML-RPC dispatcher
- RADIUS transport/authentication/accounting
- PostgreSQL persistence
- PHP/Smarty admin and user interfaces
- User/group/attribute editing
- Online user and audit reporting
- RAS/NAS and IP-pool domain
- Addons using XML-RPC

## UI inventory anchors

The reference admin UI includes user search, add-user, user information, edit attributes, delete, kill, credit changes, online-user reports, audit reports, group list/info/add, and reporting generators. fileciteturn118file0L10-L42

## Migration classification

### Rewrite
- Python 2 runtime and compatibility shims
- PHP legacy front-end and Smarty templates
- installer/init scripts
- authentication/session plumbing

### Port with behavioral tests
- user/group/attribute domain behavior
- RAS/IP-pool behavior
- accounting/session behavior
- charge/credit rules
- permissions
- XML-RPC contract
- RADIUS packet handling

### Preserve as reference only
- obsolete filesystem assumptions
- old init.d packaging
- old PHP request conventions
- binary `.pyc/.pyo` artifacts

### Do not import
- production data
- secrets
- old repository code
- legacy generated artifacts

## Next inventory targets

1. Complete DB schema extraction and mapping.
2. Enumerate all RADIUS attributes and authentication methods.
3. Enumerate permission names and admin roles.
4. Enumerate all XML-RPC handlers and method signatures.
5. Map every admin/user page to an ATD route.
6. Build parity fixtures.
