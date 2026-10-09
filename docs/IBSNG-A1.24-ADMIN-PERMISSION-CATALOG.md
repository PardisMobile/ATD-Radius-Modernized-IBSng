# IBSng A1.24 Administrator Permission Inventory

**Authority:** the canonical archive at `Source of Truth/IBSng-A1.24.tar.bz2` (SHA-256 `c7117a6a2fd252aa9b8149a1ee6606f9320888da347ee4f839614bb9349d18a8`).

This is a source-derived structural inventory of all 51 modules under `IBSng/core/admin/perms/`. The source-audit workflow extracts each module's registered permission name, value-type base, declared dependencies and whether it overrides `check()`. Structural inventory is not a substitute for tracing each permission's consumers or claiming complete RBAC parity.

Value types:
- **No value:** presence-only permission; dependencies are still enforced by source application logic.
- **All/Restricted:** a single value restricted to exactly `All` or `Restricted`; the target resource owner/context still matters.
- **Multi-value:** comma-separated text values parsed into a list.
- **Implemented subset:** permission is currently registered in the ATD API evaluator for the resource/report slice noted below. It does not mean all IBSng workflows using that permission are implemented.

| Native A1.24 permission | Value type | Source-declared dependencies | ATD status |
|---|---|---|---|
| ACCESS ALL CHARGES | No value | — | Not implemented |
| ACCESS ALL GROUPS | No value | — | Implemented for group visibility |
| ADD NEW ADMIN | No value | — | Not implemented |
| ADD NEW GROUP | No value | — | Implemented for group API |
| ADD NEW USER | No value | — | Implemented for user creation |
| CHANGE ADMIN DEPOSIT | No value | CHANGE ADMIN INFO | Implemented for deposit adjustment API; broader admin workflows remain open |
| CHANGE ADMIN INFO | No value | SEE ADMIN INFO | Implemented for native name/comment update and as dependency for deposit adjustment; other admin mutations remain open |
| CHANGE ADMIN PASSWORD | No value | SEE ADMIN INFO | Not implemented |
| CHANGE ADMIN PERMISSIONS | No value | SEE ADMIN INFO; SEE ADMIN PERMISSIONS | Not implemented |
| CHANGE BANDWIDTH MANAGER | No value | CHANGE CHARGE | Not implemented |
| CHANGE CHARGE | No value | ACCESS ALL CHARGES | Not implemented |
| CHANGE GROUP | All/Restricted | ADD NEW GROUP | Implemented for group API; All also checks group access |
| CHANGE IBS DEFINITIONS | No value | — | Not implemented |
| CHANGE IPPOOL | No value | LIST IPPOOL | Not implemented |
| CHANGE MAILBOX | No value | CHANGE NORMAL USER ATTRIBUTES | Not implemented |
| CHANGE NORMAL USER ATTRIBUTES | All/Restricted | CHANGE USER ATTRIBUTES | Not implemented |
| CHANGE RAS | No value | LIST RAS; GET RAS INFORMATION | Implemented for RAS API |
| CHANGE USER ATTRIBUTES | All/Restricted | GET USER INFORMATION | Registered; mutation API not implemented |
| CHANGE USER CREDIT | All/Restricted | GET USER INFORMATION | Implemented for single-user credit-change API with native deposit checks and logs |
| CHANGE USERS OWNER | No value | — | Not implemented |
| CHANGE VOIP TARIFF | No value | CHANGE CHARGE | Not implemented |
| CHANGE VOIP USER ATTRIBUTES | All/Restricted | CHANGE USER ATTRIBUTES | Not implemented |
| CHARGE ACCESS | Multi-value | — | Not implemented |
| CLEAR USER | All/Restricted | SEE ONLINE USERS | Not implemented |
| DELETE ADMIN | No value | SEE ADMIN INFO | Not implemented |
| DELETE REPORTS | No value | — | Not implemented |
| DELETE USER | All/Restricted | GET USER INFORMATION | Registered; delete API not implemented |
| GET RAS INFORMATION | No value | LIST RAS | Implemented for RAS API |
| GET USER INFORMATION | All/Restricted | — | Implemented for user list/detail owner scope |
| GOD | No value | — | Implemented as source-style bypass within registered evaluators |
| GROUP ACCESS | Multi-value | — | Implemented for group visibility |
| KILL USER | All/Restricted | SEE ONLINE USERS | Not implemented; disconnect remains unmounted |
| LIMIT LOGIN ADDR | Multi-value | — | Implemented in native admin authentication |
| LIMIT MAIL DOMAIN | Multi-value | CHANGE MAILBOX | Not implemented |
| LIST IPPOOL | No value | — | Not implemented |
| LIST RAS | No value | — | Implemented for RAS API |
| NO DEPOSIT LIMIT | No value | — | Implemented for administrator credit-change deposit enforcement |
| POST MESSAGES | No value | — | Not implemented |
| SEE ADMIN INFO | No value | — | Implemented for sorted admin username list and persisted admin detail; volatile activity fields omitted |
| SEE ADMIN PERMISSIONS | No value | SEE ADMIN INFO | Not implemented |
| SEE BW SNAPSHOTS | All/Restricted | — | Not implemented |
| SEE CONNECTION LOGS | All/Restricted | — | Implemented for user-detail connection-history field |
| SEE CREDIT CHANGES | All/Restricted | — | Implemented for user-detail credit-history field |
| SEE ONLINE SNAPSHOTS | No value | — | Not implemented |
| SEE ONLINE USERS | All/Restricted | — | Not implemented |
| SEE REALTIME SNAPSHOTS | No value | — | Not implemented |
| SEE SAVED USERNAME PASSWORDS | All/Restricted | GET USER INFORMATION | Not implemented |
| SEE USER AUDIT LOGS | All/Restricted | — | Not implemented |
| SEE VOIP TARIFF | No value | CHANGE CHARGE | Not implemented |
| SEE WEB ANALYZER LOGS | All/Restricted | — | Not implemented |
| VIEW MESSAGES | No value | — | Not implemented |

## Source-sensitive rules already confirmed

- A1.24 `hasPerm(name)` checks presence only; it is not an authorization decision. `checkPerm` evaluates the permission and `canDo` applies the source-defined GOD bypass.
- `CHANGE GROUP` with `All` requires group access; `Restricted` requires ownership.
- `GET USER INFORMATION`, `CHANGE USER ATTRIBUTES`, and `DELETE USER` use the All/Restricted owner scope; the latter two depend on GET USER INFORMATION.
- `CHANGE RAS` depends on both LIST RAS and GET RAS INFORMATION.
- `KILL USER` and `CLEAR USER` depend on SEE ONLINE USERS.
- `SEE CONNECTION LOGS` and `SEE CREDIT CHANGES` are independent All/Restricted permissions. The user-detail API now enforces each separately instead of treating GET USER INFORMATION as sufficient.
- `CHANGE USER CREDIT` is independently All/Restricted and depends on `GET USER INFORMATION`. Credit changes must debit/credit the administrator deposit, prevent user credit from going negative, and write native `credit_change`/`credit_change_userid` plus IAS event records. The implemented endpoint performs those writes in one transaction and also appends the ATD operational audit event. User creation now accepts an explicit non-negative initial credit, debits the creator's deposit, writes native credit action `ADD_USER` (1), and records the source event sequence `ADD_USER` (IAS type 3) then `CHANGE_CREDIT` (IAS type 1), all in the same transaction.
- `NO DEPOSIT LIMIT` permits the native administrator deposit to go below zero; it does not bypass the user-credit non-negative check. The API supports both single-user and bounded bulk credit changes; bulk operations lock users in stable ID order, check every user's scope/balance before writes, apply delta × count to administrator deposit, link one native credit-change record to every affected user, and write one IAS event. Initial credit/deposit/log parity on add-user is implemented for the current single-user API; full deposit administration and broader billing/quota semantics remain open.

## Audit limitations and next steps

This inventory does **not** claim that every permission's custom `check()` behavior, all source call sites, page visibility, mutation transactions, or related side effects have been fully reviewed. Continue by tracing each permission from its definition to handlers and data consumers, then implement only the workflows whose source contract and tests are complete. Do not expose online-user clearing/disconnect or other privileged actions based on this inventory alone.


## Administrator deposit adjustment — 2026-10-10

Source trace: `IBSng/core/admin/admin_handler.py:68-76` requires `CHANGE ADMIN DEPOSIT`; `core/admin/perms/CHANGE_ADMIN_DEPOSIT.py` depends on `CHANGE ADMIN INFO`, which depends on `SEE ADMIN INFO`. `core/admin/admin_actions.py:161-183` writes `admin_deposit_change`, increments the target admin's deposit by the signed delta, then records IAS event type 2 (`CHANGE_DEPOSIT`) with the actor username and target username. A1.24 does not impose a non-negative target-deposit rule for this operation.

ATD now exposes `POST /api/v1/admins/{username}/deposit` with the native dependency chain, row locking, signed deposit adjustment, native `admin_deposit_change` row, IAS type-2 event and operational audit in one transaction. This does not implement admin listing, details, info/password/lock changes, permission editing, or deletion.


### Administrator information read APIs — 2026-10-10

A1.24 `admin_handler.py` permits `getAdminInfo` for the current admin without `SEE ADMIN INFO`, but requires the permission for other admins. `getAllAdminUsernames` returns all sorted usernames when permission is present and only the current username otherwise. ATD now implements those visibility rules and returns the persisted identity, name/comment, deposit, creator and lock details. A1.24's in-memory `last_request_ip`, `last_activity`, and `online_status` fields are not fabricated; they remain unavailable in this persistence-backed API.


### Administrator name/comment update — 2026-10-10

Source trace: `core/admin/admin_handler.py:62-66` and `core/admin/admin_actions.py:111-123`. The update requires `CHANGE ADMIN INFO`, which depends on `SEE ADMIN INFO`; source changes only `admins.name` and `admins.comment` and reloads the in-memory admin object. ATD now row-locks the target, updates only those two native fields, and commits operational audit in the same transaction. Password changes, lock/unlock, permission editing, and admin deletion remain separate unimplemented workflows.
