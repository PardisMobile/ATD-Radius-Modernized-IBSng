# Markdown Content Audit — 2026-10-23

## Scope and method

Reviewed all 71 Markdown files in the repository tree on branch `feat/a124-semantic-object-inventory`, including the root project documents, both project-context/status/roadmap ledgers, source-trace audits, compatibility/migration documents, API/admin/security contracts, UI inventory/specifications, and reference inventories. This is a content-level review, not a claim that every source-code call path has been re-audited. The canonical IBSng archive remains the behavioral authority.

## Authority and frozen-work rules

- Canonical source: `Source of Truth/IBSng-A1.24.tar.bz2`.
- Correct SHA-256: `c7117a6a2fd252aa9b8149a1ee6606f9320888da347ee4f839bb9349d18a8`.
- Source-first workflow: inspect the actual source and consumers; implement; test; verify CI; update the relevant ledgers.
- Do not repeat completed/frozen source-verified work without contradictory evidence.
- A migration/preflight inventory is not a lossless importer or production cutover approval.
- Do not claim full A1.24 parity from API/model presence or green unit tests alone.
- Keep UI and installer/release polish behind the core behavior, persistence, parity and safety gates.

## Important content inconsistencies found

1. **Root `PROJECT-CONTEXT.md` has a stale 2026-10-14 “current” checkpoint.** It still describes user deletion and cross-worker login reservation as absent, although later status/roadmap entries record an implemented user-deletion API with a remaining mailbox side-effect gap and durable login-in-progress reservations. Its opening SHA-256 string is mistyped as `...f839614bb...`; use the canonical hash above.
2. **`docs/PROJECT-CONTEXT.md` opens with a 2026-10-14 checkpoint** and is behind the current code/doc work. Its dated sections are useful historical evidence, but not the latest handoff.
3. **`docs/CURRENT-STATUS.md` still opens with branch `main` and a 2026-10-22 head**, although this work is on `feat/a124-semantic-object-inventory`. Historical checkpoints remain useful, but the opening block must identify the current branch/head and separate code CI from later documentation-only CI.
4. **The root `ROADMAP.md` and `docs/ROADMAP.md` contain old unchecked phase lists and dated “pending/not implemented” notes alongside later implementation entries.** These must be interpreted chronologically; current verified status must come from the latest checkpoint, not an old paragraph.
5. **Some subsystem inventories are stale snapshots.** For example, `docs/IBSNG-A1.24-ADMIN-PERMISSION-CATALOG.md` contains an older status table marking DELETE USER / KILL USER and several permissions as not implemented, while later status documents describe newer slices. Do not treat old status tables as current without reconciliation.
6. **Compatibility and audit documents intentionally retain historical checkpoints.** Where a later dated section explicitly supersedes an earlier statement, the later evidence wins; source code/archive and current tests remain authoritative over either note.

## Current verified checkpoint

- Code head reviewed: `3cb3faac5cb07f771fc9e49a160971199ec0f245`.
- Python-only workflow passed.
- PostgreSQL-backed CI passed on Python 3.11 and 3.12; Ruff, Python compilation and PHP syntax checks passed.
- Changes covered source-compatible A1.24 MS-CHAPv2 AuthenticatorResponse conversion (including non-ASCII regression coverage) and MultiLogin precedence/RAS-capability semantics.
- Documentation follow-up commits were then added to `docs/CURRENT-STATUS.md`, `docs/ROADMAP.md`, and `docs/COMPATIBILITY-MATRIX.md`. Their fresh workflows must be checked independently before calling the documentation head green.

## Release blockers that remain

- Lossless A1.24 database import/adoption, complete data/plugin-object parity, manually managed/unowned sequence review, representative backup/restore drills and a reviewed ledger-baseline process.
- Live NAS interoperability for PAP/CHAP/MS-CHAPv1/v2, MPPE, accounting and provider-specific disconnect/CoA; proof of remote session disappearance.
- Reconciliation of durable accepted-login reservations when accounting lifecycle packets never arrive.
- Full billing/VoIP time-boundary and provider side-effect parity, bandwidth hierarchy writes and live traffic-control behavior.
- Remaining specialized attribute handlers, full administrator/user/group/report/portal UI workflows, remaining XML-RPC/plugin parity, and supported install/upgrade/rollback/licensing delivery.
- User deletion remains partial until the post-commit mailbox deletion side effect is implemented or explicitly supported; do not claim that side effect succeeded when no transport exists.
- `CLEAR USER` semantics and complete production UI/release validation remain open.

## Operating rule for future batches

Choose a cohesive multi-file behavior gap from the current ledgers. Reuse frozen/tested components; inspect canonical A1.24 source and all consumers; implement the behavior and persistence/side-effect boundaries; add focused and integration tests; run the full CI matrix; then update `docs/CURRENT-STATUS.md`, both roadmaps where applicable, `docs/COMPATIBILITY-MATRIX.md`, and the relevant subsystem audit. Record precise tested commit/run IDs and distinguish “implemented”, “tested”, “source-parity verified”, and “live interoperability verified”.
