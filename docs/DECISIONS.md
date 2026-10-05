# Architecture Decisions

## ADR-001 — Modernize IBSng, do not continue the Go implementation

The target is a modern IBSng-compatible AAA platform. Go is not the project core. Python 3 is selected because the behavioral reference is a Python-based AAA system and because the project must preserve its domain semantics while removing Python 2-era constraints.

## ADR-002 — Separate domain from protocol and presentation

RADIUS, REST, XML-RPC and the web UI are adapters. They must call application services rather than implement business rules.

## ADR-003 — IBSng A1.24 terminology and schema are immutable compatibility targets

ATD must use the exact IBSng A1.24 terminology, entity names, table names, column names, menu names, field names and workflow concepts wherever the corresponding IBSng concept exists.

Modernization may change implementation technology, layout, responsiveness, component structure and visual presentation. It must not introduce a different name for an existing IBSng concept.

If existing ATD code uses a different name, that is parity debt to be corrected; it is not a reason to create additional terminology.

The PostgreSQL schema is likewise an exact compatibility target. Do not invent replacement tables/models for existing A1.24 concepts.

## ADR-004 — EAP is a protocol-boundary extension

A1.24 source inspection found no named EAP implementation. Before implementing EAP, ATD must first trace the existing IBSng protocol implementations end-to-end: packet entry, dispatch, authentication, attributes, RAS/session behavior and accounting. EAP may then be added only at the correct protocol/authentication boundary and must not rename or alter existing IBSng domain concepts.

## ADR-005 — Public repository stays clean

No production data, credentials, IBSng archive, generated binaries or copied legacy repository are committed.

## ADR-006 — UI modernization preserves IBSng terminology and information architecture

The modern UI may modernize layout, responsiveness, accessibility and interaction mechanics, but must retain the exact IBSng A1.24 operator terminology. It must not replace HOME/USER/GROUP/REPORT/GRAPH/ADMIN/SETTING or IBSng page names with ATD-specific taxonomy.

The old PHP/Smarty UI is a behavioral reference. The implementation uses a reusable ATD design system with RTL/LTR and Light/Dark/System modes.
