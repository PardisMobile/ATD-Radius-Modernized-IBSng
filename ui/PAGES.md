# ATD UI Page Map

This document is the implementation map for the modernized IBSng interface. It is intentionally organized by operator workspace rather than by the number of legacy PHP/Smarty files in IBSng A1.24.

## Implemented

### Dashboard
- `ui/public/index.php`
- Global navigation
- RTL/LTR switch
- Light/dark theme
- Compact operational summary
- Entry point to Users workspace

### Users
- `ui/public/users.php`
- Search by username
- Status filter
- Paginated table
- Active/disabled/expired/locked status presentation
- Responsive layout
- Persian/English labels
- Theme persistence
- Backed by `GET /api/v1/users`

## Planned User workspace

The User workspace will consolidate the legacy IBSng user workflows into one operator surface while preserving their behavior:

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

## Remaining workspaces

- Groups
- Services
- RAS / NAS
- IP Pools
- Sessions / online users
- Accounting
- Billing / charges / credit
- Reports
- Graphs / realtime operations
- Administration / permissions
- System settings

The legacy IBSng page inventory remains the compatibility reference; this page map is the modernization target.
