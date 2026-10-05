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
- [x] PostgreSQL user repository and transaction-safe IP allocation
- [x] Initial users REST resource
- [x] Searchable/paginated users REST resource
- [x] Argon2 credential boundary
- [x] Group/service persistence repositories
- [ ] Users/groups/services full CRUD application services
- [ ] RAS provider registry
- [ ] permissions and audit enforcement

## Phase 2 — AAA
- [ ] RADIUS server parity
- [ ] PAP/CHAP/MS-CHAPv2
- [ ] accounting start/interim/stop
- [ ] duplicate request cache
- [ ] sessions and disconnect
- [x] EAP packet primitives
- [ ] EAP state machine and supported methods

## Phase 3 — Billing
- [ ] credit ledger
- [ ] charge rules
- [ ] plans and usage
- [ ] expiry and subscription state

## Phase 4 — APIs
- [x] Initial REST resource boundary
- [x] Users list/search/filter API
- [x] User detail workspace API
- [ ] REST API resources
- [ ] XML-RPC compatibility adapter
- [ ] API authentication, RBAC and audit

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
- [ ] ADMIN workflows
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
