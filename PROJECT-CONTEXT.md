# PROJECT CONTEXT — ATD Radius / Modernized IBSng

## Purpose
This file is the durable handoff for continuing the project across ChatGPT conversations. Read this before making architectural or parity changes.

## Canonical hierarchy
1. `Source of Truth/IBSng-A1.24.tar.bz2` — canonical IBSng A1.24 behavior/source.
2. `docs/` parity/reference documents — source-derived project contracts.
3. Current ATD implementation.
4. Automated parity tests.
5. "Verified" only when reproducible source-derived or integration evidence exists.

Canonical archive SHA-256:
`c7117a6a2fd252aa9b8149a1ee6606f9320888da347ee4f839614bb9349d18a8`

Do not replace or reconstruct the archive. Do not use external IBSng mirrors as authoritative when the archive/docs answer the question.

## Architecture direction
ATD is a modern AAA/RADIUS/ISP-management platform with IBSng A1.24 behavioral compatibility. Compatibility is not architectural cloning: preserve A1.24 behavior, terminology, schema semantics and workflows where required, but keep the implementation modular and extensible.

Core direction:
- Users, Groups, Attributes, AAA/policies
- RAS/NAS, IP pools, sessions, accounting
- Billing/credit/charging
- RADIUS, REST, XML-RPC compatibility, modern PHP UI
- Future extension points: EAP, LDAP/SQL auth, OAuth/OIDC, MFA, observability/exporters, webhooks, HA/multi-tenancy and product integrations.

## Mandatory project rules
- Never claim full parity/Verified merely because similarly named code exists.
- Keep CHAP and MS-CHAPv2 first-class authentication paths.
- Keep MPPE semantics tied to the original Access-Request Request-Authenticator.
- Preserve A1.24 PostgreSQL concepts and native table semantics; do not flatten away unknown/custom attributes.
- Keep source-derived decisions in docs and tests so future chats can continue without re-discovery.
- User expects autonomous multi-step continuation; do related work in batches and commit coherent increments.
- If CI is running, do not call it green until the relevant latest run has completed successfully.

## Current checkpoint
Branch: `main`
HEAD: `2a98959328e810ebec5e0eaac494a8f1e4ddeae9`
Latest commit: `Lock duplicate identity to A1.24 source tuple`

Recent MS-CHAPv2/MPPE work:
- RFC-compatible CHAP/MS-CHAPv2 wire attribute handling.
- Canonical 50-byte MS-CHAP2-Response shape validation.
- RFC 2759 AuthenticatorResponse / MS-CHAP2-Success generation.
- RFC 3079 Send/Recv MPPE key derivation.
- RFC 2548-style MS-MPPE key encryption with per-key salts.
- MPPE encryption uses the Access-Request Request-Authenticator context during Access-Accept construction.
- Access-Request Message-Authenticator verification was added for the UDP path.
- Access responses now emit Message-Authenticator when the request contains one.
- AAA attribute typing was widened to permit wire-native values.
- RADIUS duplicate identity was aligned to the A1.24 source-derived tuple: source IP + source port + packet identifier + packet code.

## Current verification state
Latest commits have triggered GitHub Python/CI workflows. At handoff time they are not yet confirmed green. Earlier MS-CHAPv2 checkpoint run failed, so do not mark MS-CHAPv2/MPPE Verified yet.

The canonical binary archive is present in GitHub but the available GitHub text API cannot directly extract its binary contents. Source-derived project docs remain the working authority until the archive can be programmatically inspected.

## Key current files
- `src/atd_radius/domain/radius_auth.py`
- `src/atd_radius/domain/radius_codec.py`
- `src/atd_radius/domain/radius.py`
- `src/atd_radius/domain/radius_dispatch.py`
- `src/atd_radius/infrastructure/access_context.py`
- `src/atd_radius/infrastructure/radius_udp.py`
- `src/atd_radius/infrastructure/ras.py`
- `src/atd_radius/domain/ras.py`
- `src/atd_radius/domain/user_policies.py`
- `src/atd_radius/domain/accounting_session.py`
- `src/atd_radius/infrastructure/accounting_persistence.py`
- `src/atd_radius/infrastructure/connection_log_repository.py`

## Next technical priorities
1. Inspect the newest CI failure/result and fix any regression before adding more behavior.
2. Finish source-derived MS-CHAPv2 failure/error semantics and end-to-end Access-Accept/Reject behavior.
3. Verify MPPE VSA semantics and salts against the canonical A1.24 source/RFC behavior.
4. Complete RAS provider parity and multi-login source-derived behavior.
5. Complete PostgreSQL connection-log/accounting persistence and live UDP integration.
6. Expand source-derived RADIUS attribute dictionary/behavior coverage.
7. Continue session/IP-pool lifecycle parity.
8. Update parity ledger/docs only with evidence-backed status.
9. Continue toward billing, APIs, UI and migration without replacing the A1.24 schema contract.

## Important source-derived docs
- `ROADMAP.md`
- `ARCHITECTURE.md`
- `PROJECT-SCOPE.md`
- `docs/A1.24-AAA-RADIUS-PARITY.md`
- `docs/A1.24-RADIUS-DISPATCH-PARITY.md`
- `docs/A1.24-ACCOUNTING-SESSION-PARITY.md`
- `docs/A1.24-ATTRIBUTE-BEHAVIOR-AUDIT.md`
- `docs/A1.24-PROTOCOL-ARCHITECTURE-AUDIT.md`
- `docs/A1.24-RUNTIME-BATCH-AUDIT.md`
- `docs/COMPATIBILITY-MATRIX.md`
- `Source of Truth/README.md`

## Conversation handoff
When a new ChatGPT conversation starts, do not ask the user to restate the project. Read this file plus the canonical docs and inspect current `main` before continuing.
