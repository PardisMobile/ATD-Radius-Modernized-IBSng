# Project Context — Carry-Forward Memory

## Identity

ATD Radius Modernized IBSng is a clean-room modernization project whose behavioral reference is the uploaded IBSng A1.24 source archive. The old Go-based ATD repository is not part of this repository and must not be copied here.

## Reference archive facts

The inspected A1.24 archive contains 2,477 members and 2,295 regular files: 1,028 under `core/`, 1,049 under `interface/`, 131 under `addons/`, 41 under `radius_server/`, 22 under `docs/`, and 19 under `db/`. It contains 453 Python sources, 530 PHP files and 284 Smarty templates plus legacy bytecode/assets.

## Fixed architecture

- Python 3.12+ core
- PostgreSQL
- RADIUS authentication/accounting
- EAP as a first-class ATD extension
- REST API
- XML-RPC compatibility adapter
- PHP 8+ modern web UI
- ATD design system, RTL/LTR, Persian/English, Light/Dark/System
- migration tooling from existing IBSng installations

## Product intent

The user wants the proven IBSng product model modernized, not a greenfield AAA product with unrelated abstractions. Preserve useful operational semantics; replace obsolete runtime and presentation technology.

## IBSng behavior that must remain visible in the design

- plugin-driven user attributes
- user/group/service policy composition
- RAS provider model
- IP pool allocation
- duplicate RADIUS request handling
- authentication and accounting separation
- online/session state
- credit and charge rules
- admin permissions and audit history
- XML-RPC service behavior
- admin and user workflows

## EAP finding

A source-wide text search of the uploaded A1.24 archive found no EAP implementation. Therefore EAP is an ATD modernization extension, not an IBSng feature claim. It must live at the protocol/authentication boundary and never leak into the domain model.

## UI intent

The UI must modernize IBSng workflows rather than discard them. Users, groups, services, RAS/NAS, IP pools, sessions, accounting, credit, reports and permissions must remain discoverable and operationally efficient. The UI is a dedicated ATD operations console, not a generic SaaS dashboard.

## Repository rule

Never import code, documentation, generated files, secrets or production data from the previous ATD Radius repository. Do not commit the IBSng archive to this public repository.

## Working rule for future chats

Read this file, `ROADMAP.md`, `ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/phase-0-inventory.md`, `docs/ibsng-a124-full-inventory.md`, and `ui/UI-SPEC.md` before making architectural changes. Then inspect the latest commits before editing code.
