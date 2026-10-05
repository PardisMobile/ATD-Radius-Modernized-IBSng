# Architecture Decisions

## ADR-001 — Modernize IBSng, do not continue the Go implementation

The target is a modern IBSng-compatible AAA platform. Go is not the project core. Python 3 is selected because the behavioral reference is a Python-based AAA system and because the project must preserve its domain semantics while removing Python 2-era constraints.

## ADR-002 — Separate domain from protocol and presentation

RADIUS, REST, XML-RPC and the web UI are adapters. They must call application services rather than implement business rules.

## ADR-003 — EAP is first-class

EAP state and packet handling live in the protocol/authentication layers. Supported methods must be backed by parity tests.

## ADR-004 — Public repository stays clean

No production data, credentials, IBSng archive, generated binaries or copied legacy repository are committed.

## ADR-005 — UI is a full modernization

The old PHP/Smarty UI is a behavioral reference. The implementation uses a reusable ATD design system with RTL/LTR and Light/Dark/System modes.
