# Project Context — Carry-Forward Memory

## Identity

ATD Radius Modernized IBSng is a clean-room modernization project whose behavioral reference is the uploaded IBSng A1.24 source archive. The old Go-based ATD repository is not part of this repository and must not be copied here.

## Reference archive facts

The inspected A1.24 archive contains 2,477 members and 2,295 regular files: 1,028 under `core/`, 1,049 under `interface/`, 131 under `addons/`, 41 under `radius_server/`, 22 under `docs/`, and 19 under `db/`. It contains 453 Python sources, 530 PHP files and 284 Smarty templates plus legacy bytecode/assets.

## Non-negotiable compatibility rule

ATD must not create a different name for an existing IBSng A1.24 concept. This applies to UI menus, pages, entities, fields, database tables/columns, attributes, configuration concepts, workflows and protocol/domain terminology.

Modernization is limited to implementation technology, responsive layout, accessibility, componentization, performance and visual presentation.

## Database rule

The A1.24 PostgreSQL schema is the database source of truth. Do not invent a replacement ATD schema for an existing IBSng table. Any schema change requires an explicit compatibility decision and must preserve import/restore compatibility.

## Fixed architecture

- Python 3.12+ core
- PostgreSQL
- RADIUS authentication/accounting
- EAP as a later protocol-boundary extension after source-first analysis of existing IBSng protocol implementations
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

## EAP rule

A source-wide text search of the uploaded A1.24 archive found no EAP implementation. Therefore EAP is an ATD modernization extension, not an IBSng feature claim. It must live at the protocol/authentication boundary and never leak into the domain model.

## UI intent

The UI must modernize IBSng A1.24 workflows rather than create a new operator taxonomy. The exact IBSng names and concepts remain visible in navigation, headings, fields and actions. Layout, responsiveness and interaction mechanics may be modernized.

## Repository rule

Never import code, documentation, generated files, secrets or production data from the previous ATD Radius repository. Do not commit the IBSng archive to this public repository.

## Working rule for future chats

Read this file, `ROADMAP.md`, `ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/phase-0-inventory.md`, `docs/ibsng-a124-full-inventory.md`, and `ui/UI-SPEC.md` before making architectural changes. Then inspect the latest commits before editing code.


## Current implementation checkpoint — 2026-10-06

- Main branch now includes a real RADIUS wire codec covering the core Access/Accounting packet codes and common A1.24 attributes.
- PAP User-Password encryption/decryption uses the RFC shared-secret algorithm and request authenticator.
- Response encoding now calculates the RADIUS response authenticator from the request authenticator and shared secret.
- A synchronous UDP transport boundary exists with NAS secret resolution by source IP; it is deliberately not claimed as production-ready until lifecycle, request verification, duplicate handling integration, and full dispatcher wiring are completed.
- Codec tests cover common attribute round-trips, PAP, malformed packets, and response authenticator calculation.
- Latest implementation checkpoint commit: `c5e9c9dfd8abf3c88614e958877fd7f6462a9205`.
- CI must be re-checked after this batch; the GitHub combined-status endpoint currently reports no status entries for the latest commit, so this batch is not being marked CI-verified.
- Remaining high-priority gaps are NAS/RAS secret lookup wiring, real dispatcher integration, Accounting request authenticator verification, duplicate request cache integration, Message-Authenticator/EAP boundary work, session/accounting persistence, permissions/audit, billing, remaining UI, installer verification, and migration/import testing.
- Do not mark any subsystem Verified merely because an implementation exists; Verified requires source-derived behavior tests and/or database parity evidence.

