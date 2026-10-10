# Roadmap

## Phase 0 — Reference and specification
- [x] Inventory IBSng A1.24 source tree
- [x] Inspect all 22 IBSng reference documents
- [x] Map major core subsystems and RAS providers
- [x] Confirm Python 2 / PHP + Smarty legacy runtime boundaries
- [x] Confirm XML-RPC and RADIUS architecture
- [x] Confirm EAP is an ATD extension, not an A1.24 feature
- [x] Define ATD UI principles and carry-forward project context
- [ ] Finish database table/relationship parity map
- [x] Finish first-pass admin/user page workflow map
- [ ] Finish reuse/port/rewrite/drop matrix

## Phase 1 — Core foundation
- [x] Python 3 project foundation
- [x] PostgreSQL initial migrations
- [x] Typed users, groups, services, RAS, IP pools and sessions
- [x] Attribute inheritance foundation
- [x] IP allocation service contract
- [x] PostgreSQL user repository and native A1.24 IP pool membership/runtime allocation
- [x] Native RAS-bound IP pool allocation and session lease lifecycle
- [x] Initial users REST resource
- [x] Searchable/paginated users REST resource
- [x] Argon2 credential boundary
- [x] Group/service persistence repositories
- [ ] Users/groups/services full CRUD application services
- [x] RAS provider registry
- [ ] permissions and audit enforcement

## Phase 2 — AAA
- [x] RADIUS wire codec and core packet families
- [x] PAP User-Password RFC algorithm
- [x] Native Access-Request authentication boundary
- [x] Accounting Start/Interim/Stop runtime lifecycle
- [x] RAS-bound IP allocation on Access-Accept and lease release on Accounting-Stop/Disconnect
- [x] Duplicate request identity/replay boundary and expiry primitive
- [x] Disconnect/CoA runtime boundary and RFC 5176 selectors
- [x] RFC 5176 Message-Authenticator boundary for current control path
- [x] CHAP/MS-CHAPv1/v2 core field semantics, AuthenticatorResponse and MPPE response path are source-traced and tested
- [ ] End-to-end Access-Accept/Reject parity across all relevant provider and dictionary contexts
- [x] Source-compatible RAS runtime registry/loader
- [ ] Full RAS provider behavior parity (source audit complete; provider adapters/fixtures remain)
- [x] Native psycopg SQL placeholder contracts for user/group/attribute persistence
- [x] PostgreSQL connection-log persistence on the live Accounting-Request path
- [ ] Complete source-derived RADIUS attribute/dictionary coverage
- [ ] EAP state machine and supported methods (optional ATD extension; not an A1.24 parity gate)

## Phase 3 — Billing
- [ ] credit ledger (single/bulk credit-change APIs, user-create initial credit, and native admin-deposit adjustment implemented; full billing ledger remains open)
- [x] charge-rule selection and Internet billing primitives
- [x] VoIP tariff/charge-rule primitives
- [ ] PostgreSQL billing persistence and A1.24 parity
- [ ] plans and usage integration
- [ ] expiry and subscription state

## Phase 4 — APIs
- [x] Initial REST resource boundary
- [x] Users list/search/filter API
- [x] User detail workspace API
- [ ] REST API resources
- [ ] XML-RPC compatibility adapter
- [ ] API authentication, RBAC and audit (user/RAS/group slices plus admin-deposit adjustment implemented; full admin RBAC remains open)

## Phase 5 — UI
- [x] ATD design-system shell
- [x] Persian/English and RTL/LTR foundation
- [x] Light/dark theme foundation
- [x] HOME shell
- [x] USER shell and data table
- [x] Search User, status filters and pagination
- [x] User Information read-only surface
- [ ] User Information edit actions and high-frequency IBSng actions
- [ ] GROUP and IBSng user/group policy workflows
- [ ] RAS, IPPool, Online Users, Connection Logs, Connection Usages, Charge and REPORT workflows
- [ ] ADMIN workflows (deposit adjustment, source-scoped persisted info list/detail, name/comment update, and lock/unlock implemented; remaining admin CRUD and volatile activity parity open)
- [ ] IBSng user portal workflows

## Phase 6 — Migration
- [ ] IBSng database importer
- [ ] data validation and parity tests
- [ ] rollback-safe migration process

## Phase 7 — Deployment
- [ ] modern installer
- [ ] systemd services
- [ ] supported Ubuntu/Debian releases
- [ ] TLS, backup and upgrade procedures
- [ ] licensing and Free/Pro enforcement

Every phase requires automated tests and documentation updates before it is considered complete.


## UI sequencing rule — established project decision
UI implementation is frozen while core parity work is active. Existing shell/foundation work is retained, but no further UI workflow expansion is to be treated as active roadmap progress. Final UI implementation begins only after Core/RADIUS/RAS/Billing/DB/API/Migration/Deployment are stabilized and the real IBSng A1.24 UI has been fully reviewed and mapped to the finished core.

## Current delivery estimate — 2026-10-09

These are scope estimates, not CI metrics or a guarantee of a specific finish date.

- **Technical core:** approximately 75–80% complete based on the current project status ledger.
- **Full modern IBSng replacement:** approximately 55–60% complete; roughly 40–45% of the total product scope remains.
- **Focused engineering estimate to full planned scope:** about 6–10 working weeks, assuming steady implementation and review. This includes the remaining provider/dictionary work, billing persistence, API/RBAC/XML-RPC, migration/deployment/licensing, deferred full UI workflows and final integration hardening.

### Remaining delivery blocks

1. **RAS and protocol parity — 1–2 weeks:** finish source-derived provider request/adapters, context-aware dictionary gaps and provider-specific integration fixtures. Real SNMP/RSH/launcher interoperability still depends on access to representative devices.
2. **Billing and persistence — 1–2 weeks:** credit-ledger/business rules, PostgreSQL billing persistence, expiry/subscription state and remaining VoIP tariff behavior.
3. **API and security — 1–2 weeks:** native-resource CRUD completion, authentication, permissions/RBAC, audit and XML-RPC compatibility.
4. **Migration and operations — 1–2 weeks:** importer, parity validation, rollback-safe migration, installer/systemd, TLS, backup/upgrade and edition enforcement.
5. **Final UI and release validation — 1–2 weeks:** begin the remaining IBSng workflows only after core and persistence contracts stabilize, then complete end-to-end release checks.

Some blocks can overlap, so these ranges should not be mechanically summed into a promised date. The estimate excludes delays caused by unavailable production RAS hardware or external deployment credentials.


## RAS external-operation progress — 2026-10-09

Source-backed request construction now includes ChilliSpot authenticated RADIUS Disconnect, PortMaster SNMP, Total Control SNMP, PortSlave/PPPD launcher envelopes, and Cisco VPDN/MikroTik RSH request builders. Cisco VPDN also has a source-pattern parser and optional remote-IP interface disambiguation. These increments are **partial adapter coverage**, not full RAS parity: transport execution/orchestration, live-device validation, remaining provider-specific accounting/counter semantics, and source-derived dictionary coverage remain open. Cisco generic SNMP-or-RSH remains unresolved rather than guessing the source branch.

The canonical archive checksum recorded in the handoff was corrected after re-hashing the checked-in archive on a runner. Correct SHA-256: `c7117a6a2fd252aa9b8149a1ee6606f9320888da347ee4f839614bb9349d18a8`. Archive contents were not modified.

Cisco's conditional disconnect strategy is now covered at the request-construction level: source-derived IF-MIB description mapping + Cisco SNMP SET (default) and the configured RSH Async/Serial branches. This does not close the RAS parity milestone; mapping refresh/transport execution, live-device validation, and the remaining provider/accounting/dictionary work remain outstanding.


## RADIUS codec compatibility increment — 2026-10-09 (source-corrected)

The initial type claim for Framed-IPX-Network was wrong and has been corrected against the actual A1.24 dictionary/parser: Framed-IPX-Network is `ipaddr`; Login-LAT-Port is `integer`. Integer encoding uses the source's unsigned network-order 32-bit format. Enum mappings now include direct-source labels for Framed-Routing, Acct-Authentic, Acct-Status-Type (including the duplicate-value reverse-map behavior), and NAS-Port-Type. Cisco's configurable SNMP version and the source launcher timeout default were also preserved. This batch improves fidelity but does not close the overall dictionary/SIP/USR or RAS parity milestones.


## SNMP transport progress — 2026-10-09

A bounded standard-library SNMPv1/v2c SET transport now executes source-derived integer SET envelopes, validates authenticated-by-community response context and request matching, retries within explicit limits, and reports partial completion for ordered SET sequences. Unit tests use fake sockets only. Cisco ifDescr GETNEXT walk and the lookup → ifIndex resolution → Cisco SNMP SET orchestration are now implemented with fake-socket tests. Remaining before production completion: wire this service into the RAS runtime and configured-branch lifecycle, implement RSH/launcher transports, handle source-specific refresh lifecycle where required, and validate against representative devices.


## Launcher transport progress — 2026-10-09

A shell-free subprocess transport now handles only audited PPPD and PortSlave launcher envelopes, with absolute executable path checks, source argument ordering, timeout/error handling and bounded returned output. The test suite uses a mocked subprocess runner. This closes the launcher execution primitive, not its runtime integration; RSH execution, RAS runtime wiring and real-device validation remain open.

## Native user-credit workflow increment — 2026-10-10

A1.24 credit adjustment is now exposed at `POST /api/v1/users/{username}/credit` and `POST /api/v1/users/credit/bulk` for bounded multi-user changes. The operation enforces `CHANGE USER CREDIT` and `GET USER INFORMATION` All/Restricted owner scope; locks user and administrator deposit rows; prevents negative user credit; applies `NO DEPOSIT LIMIT`; updates `users.credit` and `admins.deposit`; inserts native `credit_change` / `credit_change_userid` and `ias_event` rows; and appends operational audit in the same transaction.

This advances a narrow user-credit API workflow, **not** the complete billing milestone. Still open: add-user initial credit/deposit parity, deposit administration workflows, credit-ledger/business rules, charging/usage integration, expiry/subscription behavior, and full billing/report parity. CI status must be checked on the latest commit before treating the increment as validated.



## Latest validation checkpoint — 2026-10-10

Latest code/test commit: `fc7fd61c354ec8d91201433348131d996f28a548` (administrator lock/unlock). Main CI run: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38003343081. Python 3.11 and 3.12 passed with **596 passed, 2 warnings** each; the lightweight Python workflow passed with **594 passed, 2 skipped, 2 warnings**. The two skips are the live UDP/PostgreSQL tests in the lightweight workflow only; main CI configures PostgreSQL and executes both.


## Latest validation checkpoint — 2026-10-10

Latest code/test commit: `1faae684bef7a342d3a2f56ca53f9ed7b1657bf6` (administrator password change plus lint cleanup). Main CI: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38003678498 — Python 3.11 and 3.12 each passed **607 tests, 2 warnings**, including PostgreSQL-backed integration tests. Lightweight Python workflow: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38003678515 — **605 passed, 2 skipped, 2 warnings**; only the two live UDP/PostgreSQL integration tests are skipped there because no test database URL is configured.


## Administrator creation IAS parity — 2026-10-10

Source audit against the checksum-verified A1.24 archive confirms `IBSng/core/admin/admin_actions.py` composes the native admin insert and `ias_main.getActionsManager().logEvent("ADD_ADMIN", creator_username, 0, username)` in one database transaction. `IBSng/core/ias/ias_actions.py` maps `ADD_ADMIN` to IAS event type **5**. ATD's native admin creation repository now writes the corresponding `ias_event` row (actor = creator username, amount = 0, destination = created username, empty comment) in the same caller-owned transaction as the `admins` insert and operational audit. Focused repository/API tests assert the event fields and creator identity. CI verification for code/test commit `aefba4b1079b7ddb7940461e59e572bebd21b834` passed: full CI on Python 3.11 and 3.12, **613 passed, 2 warnings** per matrix job, including compile, Ruff, PHP syntax and PostgreSQL integration; Python-only workflow passed **611 passed, 2 skipped, 2 warnings** (the two live UDP/PostgreSQL tests are skipped in that workflow). Full CI: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38059979595 ; Python workflow: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38059979654.
