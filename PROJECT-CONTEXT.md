# PROJECT CONTEXT — ATD Radius / Modernized IBSng

## Purpose
This file is the durable handoff for continuing the project across ChatGPT conversations. Read this before making architectural or parity changes.

## Source-of-truth rule — NON-NEGOTIABLE
**The actual IBSng A1.24 source archive is the sole behavioral authority for this project.**

Canonical archive:
`Source of Truth/IBSng-A1.24.tar.bz2`

SHA-256:
`c7117a6a2fd252aa9b8149a1ee6606f9320888da347ee4f839614bb9349d18a8`

Parity docs, inventories, matrices, notes, tests, and current ATD code are guides/records/validation artifacts only. They must never override or substitute for the actual IBSng source when the source is available. If any parity document conflicts with the source archive, **the source archive wins**.

For every source-sensitive change:
1. Inspect the actual A1.24 source implementation and its call path/consumers.
2. Record the source-derived behavior.
3. Implement the modern ATD equivalent without unnecessarily cloning legacy architecture.
4. Add/adjust tests.
5. Only call behavior "Verified" when source/integration evidence supports it.

See `docs/SOURCE-AUTHORITY.md` for the durable rule and current source-derived findings.

Do not replace or reconstruct the canonical archive. Do not use external IBSng mirrors as authoritative.

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
Latest source-driven checkpoint includes:
- direct A1.24 source extraction/inspection infrastructure removed after use
- durable source-only authority rule in `docs/SOURCE-AUTHORITY.md`
- MS-CHAPv1 authentication + A1.24 MPPE response path
- MS-CHAPv2 behavior aligned to A1.24 field consumption
- A1.24-style random MPPE salts
- duplicate identity aligned to `(source_ip, source_port, packet_id, packet_code)`

The current branch contains later source-authority, MultiLogin, attribute-inheritance and documentation checkpoint commits. Always inspect the actual current main HEAD before the next code change.

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
The canonical binary archive has been extracted and directly inspected through temporary GitHub Actions runner jobs. The extracted tree contains 2,295 files. Temporary inspection hooks are removed after use.

Important: this does **not** make parity docs authoritative. The source archive remains the sole behavioral authority. Current ATD tests are validation only.

The latest code changes around MS-CHAPv2/MPPE, Message-Authenticator, duplicate detection, and multi-login must be judged against the newly inspected source findings before being called source-parity Verified.

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
1. Continue systematic direct source inspection across the A1.24 RAS/user/session/accounting paths; source, not parity docs, determines behavior.
2. Finish source-derived MS-CHAPv1/v2 failure/error semantics and end-to-end Access-Accept/Reject behavior.
3. Verify the full Microsoft VSA dictionary/response surface against A1.24 source usage.
4. Complete RAS provider parity and multi-login source-derived behavior, including service-specific RAS flags.
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

### Newly fixed source-traced authentication checkpoint — 2026-10-06
- Canonical A1.24 source directly traced through `core/user/plugins/password.py`, `core/user/plugins/mschap_end.py`, and `radius_server/pyrad/packet.py`.
- CHAP uses CHAP-Identifier + password + CHAP-Challenge, falling back to the packet authenticator when CHAP-Challenge is absent.
- MS-CHAPv1 compares only the 24-byte NT-Response field at response offset 26 and does not require extra response-field validation beyond the source path.
- MS-CHAPv2 compares the 24-byte NT-Response at offset 26 using the supplied username and MS-CHAP-Challenge; successful authentication then emits the A1.24 MS-CHAP2-Success and MPPE material through the final plugin.
- Authentication failure in the A1.24 password plugin is a `WRONG_PASSWORD` GeneralException; ATD's authentication boundary maps invalid credentials to `Access-Reject` / `INVALID_CREDENTIALS`.
- This checkpoint confirms the credential verification and reply-material semantics already implemented in ATD. End-to-end RAS/provider coverage and complete attribute/dictionary coverage remain separate unresolved work.
- Do not re-investigate these exact CHAP/MS-CHAP verification semantics in later chats unless new canonical-source evidence contradicts them.

## Fixed source-traced checkpoints — do not restart

Before starting new work, read docs/SOURCE-AUTHORITY.md. The following areas have already been directly traced against A1.24 source and should be treated as established unless new source evidence contradicts them: MS-CHAPv1/v2 field semantics and MPPE response generation; MultiLogin default/explicit-zero semantics; user-over-group attribute precedence; A1.24 attribute table structure; user attribute aggregation; RAS-specific MultiLogin capability; duplicate request identity; IP-pool membership vs runtime free/used state; connection_log native structure.

Do not re-open these as fresh investigations merely because a new chat starts. Work only on the unresolved items listed in SOURCE-AUTHORITY.md and this file.

## Conversation handoff
When a new ChatGPT conversation starts, do not ask the user to restate the project. Read this file plus the canonical docs and inspect current `main` before continuing.

## Accounting / Charge source-traced checkpoint — 2026-10-07

### A1.24 accounting lifecycle
- Canonical RAS providers explicitly handle Start, Stop and Alive. A1.24 does not use RADIUS Interim-Update as the provider-side status in the inspected source; Alive is the source-native periodic update concept.
- core/user/connection_log.py calls the native insert_connection_log DB function.
- core/user/user.py suppresses native connection logging when no_connection_log is present.
- Normal-user logout computes used_credit through the active Charge object and passes that value into connection-log persistence.
- no_commit suppresses credit settlement in the source logout path.
- ATD accounting state now supports START/STOP/INTERIM/ALIVE, native connection-log persistence, no_connection_log and no_commit handling, observed event time, and charge settlement.

### A1.24 Internet Charge source findings
- core/charge/charge.py starts accounting with the effective rule, records the rule start time, and invokes the rule start hook.
- core/charge/user_charge.py maintains per-instance credit_prev_usage, effective_rules, rule_start and Internet-user rule_start_inout state.
- core/charge/internet_charge_rule.py calcRuleInOutUsage subtracts the per-instance rule-start IN/OUT baseline from current IN/OUT counters; transfer usage is the sum of those deltas.
- core/charge/internet_charge.py actively detects effective-rule changes, ends the old rule, starts the new rule, and replaces the effective rule for the instance.
- Logout preserves accumulated per-instance usage across rule transitions and then ends the effective rule.
- ATD InternetChargeSettlement now mirrors the source state machine conceptually: effective rule selection, per-rule time start, per-rule IN/OUT baseline, transition accumulation, final settlement, and credit decrement.
- This checkpoint is source-traced but not yet full parity Verified: the remaining validation target is the exact implementation of the A1.24 InternetChargeRule.start/end hooks and the source of getTypeObj().getInOutBytes(instance) compared with ATD accounting counters.

### Current ATD billing/accounting implementation
- src/atd_radius/domain/accounting_charge.py contains the settlement state machine.
- SessionState stores charge ID, effective rule ID, rule start time, per-rule input/output baselines, and accumulated charge.
- Native runtime composes InternetChargeSettlement with PostgresInternetChargeRuleRepository, UserRepository.policy_attributes, and UserCreditRepository.
- used_credit is passed to native connection-log close and no_commit produces zero settlement.
- Source-derived tests exist for charge calculation and accounting-charge settlement.

### Remaining charge validation
1. Directly trace InternetChargeRule.start/end from the canonical archive.
2. Directly trace getTypeObj().getInOutBytes(instance) and its accounting update path.
3. Add source-derived tests for rule transition, counter reset, multiple instances, zero-credit commit and atomic credit/log persistence.
4. Verify transaction/rollback boundaries so credit and connection-log settlement remain consistent on failure.
5. Update accounting parity docs only after these checks pass.

### Charge implementation checkpoint — 2026-10-07 follow-up
- Runtime charge settlement is now covered by source-derived tests for rule-start time/IN-OUT baselines, rule transition accumulation, independent per-session/multi-instance baselines, and A1.24 no_commit behavior.
- Accounting parity documentation now records runtime Charge integration as implemented rather than pending.
- The implementation keeps the A1.24 per-instance state model explicit instead of treating raw accounting deltas as the billing model.
- Remaining validation is deliberately limited to exact source confirmation of InternetChargeRule.start/end, the authoritative getTypeObj().getInOutBytes(instance) data path, and transaction/rollback atomicity.
- Temporary source-trace workflow created during this follow-up was removed; no temporary workflow is intentionally left in main.
