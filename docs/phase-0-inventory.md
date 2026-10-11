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

## Remaining semantic-review targets

The structural inventories for SQL/schema, RADIUS dictionaries, the 51 admin permission modules and UI page files already exist. Do not repeat them as filename-only tasks. The remaining work is content/call-path review:

1. Finish column-by-column schema migration mapping and the import/parity report framework.
2. Trace each RADIUS attribute and authentication method through packet parsing, plugin consumers, response construction and accounting/session effects.
3. Trace each permission from its definition to all handlers and page visibility; distinguish registered permission evaluation from a completed workflow.
4. Inventory and trace every XML-RPC handler/signature and its callers.
5. Map every legacy admin/user page to implemented UI/API routes, including missing workflows.
6. Build source-vs-ATD fixtures for each verified behavior and label untested areas as partial.
