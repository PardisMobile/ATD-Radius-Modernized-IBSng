# Roadmap

## Phase 0 — Reference and specification
- Inventory IBSng A1.24 source tree
- Map domain objects and database behavior
- Map RADIUS/EAP behavior
- Map permissions and accounting
- Map UI workflows
- Record reuse/port/rewrite/drop decisions

## Phase 1 — Core foundation
- Python 3 project
- PostgreSQL migrations
- Users, groups, services, attributes
- RAS/NAS and IP pools
- permissions and audit

## Phase 2 — AAA
- RADIUS server
- PAP/CHAP/MS-CHAPv2
- accounting start/interim/stop
- sessions and disconnect
- EAP framework and supported methods

## Phase 3 — Billing
- credit ledger
- charge rules
- plans and usage
- expiry and subscription state

## Phase 4 — APIs
- REST API
- XML-RPC compatibility
- authentication, RBAC and audit

## Phase 5 — UI
- ATD design system
- admin panel
- user portal
- RAS, IP pool, sessions, accounting, billing and reports

## Phase 6 — Migration
- IBSng importer
- validation and parity tests
- rollback-safe migration process

## Phase 7 — Deployment
- modern installer
- systemd services
- supported Ubuntu/Debian releases
- TLS, backup and upgrade procedures
- licensing and Free/Pro enforcement

Every phase requires automated tests and documentation updates before it is considered complete.