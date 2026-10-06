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

- Main branch currently advances through native A1.24 schema migration and USER persistence/UI work.
- The native migration contains the A1.24 tables/sequences/indexes; parallel modern schema names such as `user_credentials`, `user_groups`, `user_services`, `credit_ledger`, `attribute_bindings`, `sessions`, `services` and `online_sessions` are forbidden.
- Latest confirmed main commit at this checkpoint: `5282cc3ac31c4929fa6f3eaaaf3b53b580cd5681`.
- CI status must be re-checked from GitHub after each batch; do not assume queued/in-progress runs passed.
- USER API/persistence is mapped to `users`, `normal_users`, `user_attrs` and related A1.24 tables. USER lock is presence of the `lock` attribute.
- GROUP work is implemented directly against `groups` and `group_attrs`, preserving A1.24 names and semantics.
- RAS work is now implemented directly against `ras`, `ras_ports`, `ras_attrs` and `ras_ippools`; `ras_ippools.serial` remains database-generated and is returned by insertion.
- RAS API now exposes RAS List, RAS Information, Add New RAS, Edit RAS Information and RAS Ports boundaries using native column names.
- A1.24 GROUP source behavior verified: group names accept only ASCII alphanumeric, underscore and hyphen; creation uses `groups_group_id_seq`; deletion is blocked when `users.group_id` references the group; group attributes are one value per `(group_id, attr_name)`.
- A1.24 GroupActions/GroupHandler source was inspected directly before implementing the GROUP repository/API.
- Remaining high-priority parity gaps include RAS lifecycle, full AAA/RADIUS UDP integration, accounting/session integration, permissions/audit, billing source verification, remaining UI areas, installer verification, and migration/import testing.
- Do not mark any subsystem Verified merely because an implementation exists; Verified requires source-derived behavior tests and/or database parity evidence.
