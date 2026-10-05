# Project Context

This file is the portable memory of the project. Read it before making architectural changes.

## Identity
ATD Radius Modernized IBSng is a modernization of IBSng A1.24, not a greenfield Go AAA project.

## Reference
IBSng A1.24 is the behavioral reference. The complete archive is kept outside this public repository and must not be copied here.

## Technology decisions
- Python 3 for core/domain/AAA.
- PostgreSQL for persistence.
- PHP 8+ for the initial web UI.
- RADIUS is core.
- EAP is a core requirement.
- REST is the modern API.
- XML-RPC is a compatibility adapter.
- Modern systemd/Linux deployment replaces the old CentOS 7 assumptions.

## UI contract
The UI must preserve useful IBSng workflows while replacing its legacy visual system. It must support Persian/English, RTL/LTR, light/dark/system themes, responsive layouts, reusable components, accessible forms/tables, and a distinctive ATD identity. Do not build a generic dashboard template.

## Engineering rule
Behavior is migrated deliberately. Legacy implementation is not copied merely for familiarity. Every compatibility decision should be documented.

## Continuity rule
Update this file, ROADMAP.md, ARCHITECTURE.md and docs/DECISIONS.md when a major project decision changes. A future chat should be able to reconstruct the project direction from these files.