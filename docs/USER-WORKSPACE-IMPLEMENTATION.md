# User Workspace Implementation

This document records the first real user-centric workspace built from the IBSng A1.24 workflow inventory.

## Read-only surface delivered

The user detail API and PHP workspace expose the high-value information an operator needs without reproducing IBSng's legacy page chain:

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

1. Add explicit effective-policy resolution.
2. Add edit operations for status and credentials through application services.
3. Add group/service assignment and removal.
4. Add attribute editing with validation and audit records.
5. Add session actions such as disconnect/kill with permission checks.
6. Add credit actions through the billing ledger rather than direct balance mutation.
7. Add audit timeline to the workspace.

The UI must continue to use contextual tabs/drawers rather than recreate IBSng's old multi-page form chain.
