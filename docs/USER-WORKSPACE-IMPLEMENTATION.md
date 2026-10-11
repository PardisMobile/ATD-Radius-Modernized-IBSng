# User Information Implementation

This document records the first real User Information surface built from the IBSng A1.24 workflow inventory.

## Read-only surface delivered

The User Information API and PHP surface expose the high-value information an operator needs without reproducing IBSng's legacy page chain:

- identity and account status
- credential readiness
- group assignments
- service assignments and assignment windows
- inherited/user/service attribute bindings
- active sessions with RAS and framed IP
- recent credit ledger entries

API endpoint:

`GET /api/v1/users/{username}/detail`

UI entry point:

`ui/public/user.php?username=<username>`

## Compatibility rule

The first implementation is intentionally read-only. It does not invent edit semantics until the corresponding IBSng write workflows are mapped into application services. This avoids a UI that appears to support an operation while the core cannot enforce it safely.

## Attribute ordering

The API returns applicable user/group/service bindings ordered by precedence. This is a visibility surface, not yet the final RADIUS attribute resolver. The resolver remains a separate core concern and must define conflict, operator, and RAS precedence before authentication relies on it.

## Next user-workspace steps

The backend/API now supports selected source-backed edits (generic attributes, owner/group assignment, caller IDs, VoIP preferred language, fast-dial slot management and credit changes). These are not yet equivalent to a complete operator UI workflow. Continue the UI and service integration in parallel:

1. Wire the workspace to explicit effective-policy resolution and explain group/user precedence.
2. Add UI flows for implemented status/attribute/owner/group/credit APIs without duplicating business rules in PHP.
3. Add remaining credential and specialized attribute workflows only after their source validators and persistence side effects exist.
4. Add session listing only when the online-state model is authoritative; keep destructive disconnect/kill hidden until its permission, provider operation and audit sequence are safe.
5. Add the audit timeline with source-specific visibility checks.
6. Complete group/service assignment visibility and removal flows while preserving native permission and owner scope.

The UI must continue to use contextual tabs/drawers only as presentation mechanics; operator-facing names and workflows remain those of IBSng A1.24.
