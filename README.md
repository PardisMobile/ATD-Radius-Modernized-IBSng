# ATD Radius — Modernized IBSng

ATD Radius is a clean modernization of IBSng A1.24. The goal is simple: keep the proven IBSng AAA/domain behavior that operators rely on while replacing its obsolete Python 2, PHP/Smarty and CentOS 7-era deployment stack.

## Target stack

- Python 3.12+ core
- PostgreSQL
- RADIUS authentication and accounting
- EAP as a later protocol-boundary extension after source-first analysis of existing IBSng protocols
- REST API
- XML-RPC compatibility adapter
- PHP 8+ web panel
- ATD design system with Persian/English, RTL/LTR and Light/Dark/System modes
- Migration tooling for existing IBSng installations

## Important project rule

ATD uses the exact IBSng A1.24 terminology and PostgreSQL schema for existing IBSng concepts. UI modernization must not rename menus, fields, entities or workflows. New protocol extensions such as EAP require source-first analysis of the existing IBSng protocol mechanism before implementation.

This is a clean repository. Nothing from the previous Go-based `ATD-Radius` repository is imported here. The IBSng archive, production databases, credentials and generated legacy binaries are not committed to this public repository.

## Current status

The project foundation is now live:

- Python package and test configuration
- Native IBSng A1.24 PostgreSQL schema migration sequence (`tables.sql → functions.sql → initial.sql → defs.sql`)
- user/group/service/RAS/IP-pool/session domain primitives
- layered attribute policy primitive
- RADIUS packet transport foundation
- EAP packet foundation
- FastAPI health/meta API
- first modern IBSng-compatible web shell
- design-system and UI specification
- IBSng reference inventory
- CI test workflow

This is **not yet production-ready AAA**. Authentication, accounting state machines, charging, permissions, XML-RPC parity and migration are implemented incrementally and must be parity-tested before release.

## Documentation that carries project memory

Start every new development session by reading:

1. `docs/PROJECT-CONTEXT.md`
2. `ROADMAP.md`
3. `ARCHITECTURE.md`
4. `docs/DECISIONS.md`
5. `docs/phase-0-inventory.md`
6. `ui/UI-SPEC.md`
7. `ui/DESIGN-SYSTEM.md`

These files are the durable project context so a future chat does not need to reconstruct the architecture from conversation history.

## License

The final license and attribution strategy will be documented before redistributing any derivative IBSng implementation. The repository must remain compliant with the applicable IBSng A1.24 license terms.