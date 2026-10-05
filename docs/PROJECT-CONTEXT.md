# Project Context — Carry-Forward Memory

## Identity

ATD Radius Modernized IBSng is a clean-room modernization project whose behavioral reference is IBSng A1.24. The old Go-based ATD repository is not part of this repository and must not be copied here.

## Fixed architecture

- Python 3.12+ core
- PostgreSQL
- RADIUS authentication/accounting
- EAP as a first-class capability
- REST API
- XML-RPC compatibility adapter
- PHP 8+ modern web UI
- ATD design system, RTL/LTR, Persian/English, Light/Dark/System
- migration tooling from existing IBSng installations

## Product intent

The user wants the proven IBSng product model modernized, not a greenfield AAA product with unrelated abstractions. Preserve useful operational semantics; replace obsolete runtime and presentation technology.

## UI intent

The UI must modernize IBSng workflows rather than discard them. Users, groups, services, RAS/NAS, IP pools, sessions, accounting, credit, reports and permissions must remain discoverable and operationally efficient.

## EAP

EAP is not an optional future plugin. The protocol/state-machine layer must be designed so supported EAP methods can be added without changing the domain or persistence layers.

## Repository rule

Never import code, documentation, generated files, secrets or production data from the previous ATD Radius repository. Do not commit the IBSng archive to this public repository.

## Working rule for future chats

Read this file, `ROADMAP.md`, `ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/phase-0-inventory.md`, and `ui/UI-SPEC.md` before making architectural changes. Then inspect the latest commits before editing code.
