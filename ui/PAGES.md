# ATD UI Page Map

This document maps the modern implementation directly to the IBSng A1.24 UI. It must not introduce a second operator-facing naming system.

## Implemented

### HOME
- `ui/public/index.php`
- Global navigation
- RTL/LTR switch
- Light/dark theme
- Compact operational summary
- Entry points using IBSng USER terminology

### USER
- `ui/public/users.php`
- Search by username
- Status filter
- Paginated table
- Active/disabled/expired/locked status presentation
- Responsive layout
- Persian/English labels
- Theme persistence
- Backed by `GET /api/v1/users`

## User Information

User Information will consolidate the legacy IBSng user workflows into one modern responsive surface while preserving their behavior:

1. Overview
2. Identity
3. Authentication / credentials
4. Groups and services
5. Effective attributes / policy
6. Credit and limits
7. Active sessions and kill action
8. Accounting
9. Audit history
10. User-specific reports

Secondary actions should use drawers, dialogs or inline actions where that improves flow; destructive operations must remain explicit and auditable.

## Remaining IBSng A1.24 areas

- GROUP
- RAS
- IPPool
- Bandwidth Management
- Charge
- VoIP Tariff
- REPORT
- GRAPH
- ADMIN
- SETTING

The legacy IBSng source and page inventory remain the compatibility reference. Technical source filenames may differ, but operator-facing names must remain the A1.24 names.
