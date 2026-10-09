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

## Permanent Freeze Rule — DO NOT TOUCH VERIFIED WORK

**This is a permanent project rule.** Any subsystem, feature, behavior, attribute flow, protocol path, provider behavior, persistence contract, or other implementation that has already been **directly compared against the canonical IBSng A1.24 source, tested, and confirmed correct** is considered **FROZEN**.

- Do **not** modify, refactor, rewrite, simplify, rename, reorganize, or otherwise touch a verified/frozen area merely because a new chat starts or because a different implementation seems cleaner.
- Do **not** re-open a completed source-parity investigation just to re-check it. Reuse the established verified result as a dependency.
- A frozen area may be changed **only** when new, direct evidence from the canonical A1.24 Source of Truth proves that the current implementation is incorrect or incomplete.
- When such contradictory source evidence exists, record the evidence and scope the change strictly to what the source requires; do not use architectural preference or assumptions as justification.
- This rule applies across **all future ChatGPT conversations** and must be preserved in every handoff/checkpoint.
- In particular, **MultiLogin and any other previously source-verified behavior must not be altered without new canonical-source evidence**.

The working principle is: **VERIFY ONCE → TEST → FREEZE → BUILD AROUND IT.**

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

### Source-verification update — 2026-10-07
- Canonical A1.24 `InternetChargeRule.start/end` is now directly verified from the extracted archive. `start()` calls the base rule start, captures `getTypeObj().getInOutBytes(instance)` into `rule_start_inout[instance-1]`, then applies bandwidth limits; `end()` calls the base end and removes bandwidth limits. `calcRuleInOutUsage()` subtracts that exact per-instance baseline and `calcRuleTransferUsage()` sums the deltas.
- The source trace came from successful temporary GitHub Actions extraction; the temporary workflow was removed afterward. This is source evidence, not a parity-doc inference.
- ATD's per-session charge state explicitly models the same baseline concept with input/output counters.
- Transaction ownership is now understood: `infrastructure.db.connection()` wraps `psycopg.connect(...)` in a context manager, so normal exit commits and an escaping exception rolls the transaction back. `build_native_radius_runtime()` deliberately accepts a caller-owned connection so accounting persistence, credit settlement and repository reads share that transaction. `RadiusUDPServer` does not own a DB connection; production wiring must therefore preserve this single-connection/context boundary.

### Current ATD billing/accounting implementation
- src/atd_radius/domain/accounting_charge.py contains the settlement state machine.
- SessionState stores charge ID, effective rule ID, rule start time, per-rule input/output baselines, and accumulated charge.
- Native runtime composes InternetChargeSettlement with PostgresInternetChargeRuleRepository, UserRepository.policy_attributes, and UserCreditRepository.
- used_credit is passed to native connection-log close and no_commit produces zero settlement.
- Source-derived tests exist for charge calculation and accounting-charge settlement.

### Remaining charge validation
1. Validate an integration-level failure path proving that an exception after credit/log mutation escapes to the caller and causes the shared psycopg transaction to roll back.
2. Continue source-derived billing edge cases only where new canonical-source evidence requires them.
3. Keep the shared-connection requirement explicit in deployment/runtime wiring.
4. Update accounting parity docs only with evidence-backed status.

### Charge implementation checkpoint — 2026-10-07 follow-up
- Runtime charge settlement is now covered by source-derived tests for rule-start time/IN-OUT baselines, rule transition accumulation, independent per-session/multi-instance baselines, and A1.24 no_commit behavior.
- Accounting parity documentation now records runtime Charge integration as implemented rather than pending.
- The implementation keeps the A1.24 per-instance state model explicit instead of treating raw accounting deltas as the billing model.
- Remaining validation is deliberately limited to exact source confirmation of InternetChargeRule.start/end, the authoritative getTypeObj().getInOutBytes(instance) data path, and transaction/rollback atomicity.
- Temporary source-trace workflow created during this follow-up was removed; no temporary workflow is intentionally left in main.

- Follow-up tests now also cover counter reset (no negative transfer charge) and zero-credit settlement (A1.24-style zero-value credit commit remains observable).
- Source verification via temporary GitHub Action is now available from historical successful runs: the canonical archive trace directly verified `InternetChargeRule.start/end` and the `getTypeObj().getInOutBytes(instance)` baseline path. The temporary workflow was removed; no temporary workflow remains in `main`.


## Live RADIUS runtime wiring checkpoint — 2026-10-07

### Implemented
- Added `NativeRadiusRuntimeState` as the long-lived in-process state boundary for SessionRegistry, RAS runtime state and IP-pool runtime state.
- Added `NativeRadiusPacketHandler`: each UDP packet opens a fresh PostgreSQL connection/transaction through the existing `infrastructure.db.connection()` context, while the session/RAS/IP-pool state remains shared across packets.
- Added `PostgresRadiusSecretResolver`: active RAS/NAS secrets are resolved from PostgreSQL per incoming source IP instead of freezing secrets in process state.
- `main.py` can now start both authentication (1812) and accounting (1813) UDP listeners alongside FastAPI when `ATD_RADIUS_ENABLED=true`.
- The default remains disabled so existing API-only deployments are not unexpectedly changed.
- Existing `build_native_radius_runtime()` remains available for tests and explicit one-transaction composition; production UDP wiring uses the packet-scoped transaction handler.
- Added a runtime-state boundary test scaffold and CI coverage through the normal push workflows.

### Transaction/state invariant
The production RADIUS path must not keep one PostgreSQL transaction open for the lifetime of the UDP listener. Each packet gets its own DB context/commit/rollback boundary, while in-memory session and IP-pool state persists for the process lifetime. This is now the explicit runtime architecture.

### Current status
- Live UDP application wiring: implemented.
- Per-packet DB transaction boundary: implemented.
- Shared runtime session/IP-pool/RAS state: implemented.
- Authentication + Accounting + Disconnect/CoA all enter through the same UDP transport boundary.
- End-to-end production verification against a running PostgreSQL/RAS instance is still a deployment/integration test, not claimed as complete by unit CI alone.

### Next unresolved priorities
1. Finish source-derived RAS provider behavior parity and verify each provider against canonical A1.24 source.
2. Complete RADIUS dictionary/attribute coverage from canonical A1.24 source.
3. Continue source-derived RADIUS dictionary coverage and begin the credit-ledger/billing persistence layer.
4. Continue billing/credit ledger, API/RBAC/audit, UI workflows, migration and deployment work.


# MASTER PROJECT STATUS — 2026-10-07

This section is the authoritative handoff/status index for the current ATD project state. It is a status ledger, not a behavioral source. For behavior, the canonical IBSng A1.24 archive remains authoritative.

## A. DONE / IMPLEMENTED

### Reference & architecture
- [x] Canonical A1.24 archive retained and SHA recorded.
- [x] Source-only authority rule documented.
- [x] A1.24 source tree and major core/RAS architecture inspected.
- [x] ATD Python 3 foundation established.
- [x] PostgreSQL initial A1.24-shaped schema/migration foundation established.
- [x] Architecture/context/handoff documentation established.

### Core data & policy foundation
- [x] Users/groups/services/RAS/IP pools/session domain foundations.
- [x] User/group attribute inheritance and precedence boundary.
- [x] PostgreSQL user repository.
- [x] Group/service persistence repositories.
- [x] Native A1.24 IP-pool membership/runtime allocation model.
- [x] RAS-bound IP allocation and release lifecycle primitives.
- [x] Argon2 credential boundary.
- [x] Initial and searchable/paginated Users REST endpoints.
- [x] User detail workspace API boundary.

### RADIUS / AAA
- [x] RADIUS packet codec and core packet families.
- [x] PAP.
- [x] CHAP authentication boundary.
- [x] MS-CHAPv1 authentication boundary.
- [x] MS-CHAPv2 authentication boundary.
- [x] A1.24-aligned MS-CHAPv2 field consumption.
- [x] RFC 2759 AuthenticatorResponse / MS-CHAP2-Success.
- [x] RFC 3079 MPPE key derivation.
- [x] RFC 2548-style MPPE encryption with per-key salts.
- [x] Request-Authenticator context preserved for MPPE.
- [x] Message-Authenticator verification for current UDP Access path.
- [x] Duplicate-request identity/replay primitive.
- [x] Disconnect/CoA runtime boundary and RFC 5176 selector handling.
- [x] Source-compatible RAS runtime registry/loader.
- [x] MultiLogin semantics source-traced, including default=1, explicit zero, user-over-group precedence and RAS capability.
- [x] Session runtime registry.
- [x] Accounting Start/Stop/Alive plus Interim compatibility.
- [x] Native connection-log persistence boundary.
- [x] no_connection_log and no_commit semantics.
- [x] Internet charge-rule state machine and credit settlement runtime.
- [x] Source verification of A1.24 InternetChargeRule.start/end and IN/OUT baseline path.
- [x] Per-packet PostgreSQL transaction boundary for production UDP runtime.
- [x] Persistent in-process Session/RAS/IP-pool state across packets.
- [x] Auth listener wiring (1812) and Accounting listener wiring (1813), opt-in through ATD_RADIUS_ENABLED.
- [x] RAS secret lookup from PostgreSQL per incoming source IP.

### UI / product foundation
- [x] Modern ATD design shell.
- [x] Persian/English and RTL/LTR foundation.
- [x] Light/dark theme foundation.
- [x] HOME shell.
- [x] USER shell/table/search/status/pagination.
- [x] Read-only User Information surface.

## B. SOURCE-VERIFIED / FIXED — DO NOT RE-INVESTIGATE

- [x] MultiLogin default/explicit-zero/user-vs-group semantics.
- [x] User-over-group attribute precedence.
- [x] A1.24 attribute table ownership model.
- [x] RAS-specific MultiLogin capability for inspected providers.
- [x] Duplicate identity tuple.
- [x] IP-pool membership versus runtime free/used state.
- [x] Native connection_log logical structure.
- [x] CHAP/MS-CHAPv1/v2 credential field consumption.
- [x] A1.24 MS-CHAP2-Success / MPPE response path.
- [x] InternetChargeRule.start/end and getTypeObj().getInOutBytes(instance) baseline path.
- [x] A1.24 accounting Start/Stop/Alive source path and no_connection_log/no_commit behavior.

## C. IN PROGRESS / PARTIAL

- [~] User identity: core repository exists, full application CRUD/services and all source behavior are not complete.
- [~] User/group/service policy parity.
- [~] RAS mutation/reload and complete provider behavior parity.
- [~] RADIUS authentication: runtime boundary exists, full source-derived end-to-end parity suite remains.
- [~] CHAP/MS-CHAPv1/v2: core cryptographic/field behavior implemented; complete end-to-end provider/dictionary/reply parity remains.
- [x] Accounting: live UDP -> PostgreSQL integration path and rollback/failure-path verification are implemented and CI-verified; provider-specific parity remains partial.
- [~] IP pools: allocator/session lifecycle exists; exhaustive source/provider integration parity remains.
- [~] Attribute system: modern policy engine and core wire dictionary are implemented; SIP/SER context-aware and USR vendor dictionary coverage remain.
- [~] Charging: Internet runtime integrated; broader A1.24 billing/credit/VoIP persistence parity remains.
- [~] Admin UI and user portal.
- [~] REST API surface.

## D. TODO / NOT STARTED OR NOT COMPLETE

### Phase 0
- [ ] Complete DB relationship parity map.
- [ ] Complete reuse/port/rewrite/drop matrix.

### Phase 1
- [ ] Full Users/Groups/Services CRUD application services.
- [ ] Complete RAS provider registry/mutation workflow.
- [ ] Permissions and audit enforcement.

### Phase 2
- [ ] Complete RAS provider behavior parity for every relevant A1.24 provider.
- [~] Complete source-derived RADIUS dictionary/attribute coverage; core/MS/provider-critical wire catalog is expanded, while SIP/SER context-aware and USR vendor coverage remain.
- [ ] End-to-end CHAP/MS-CHAPv1/v2 Access-Accept/Reject/provider tests.
- [x] Strong live UDP/PostgreSQL integration tests.
- [x] Transaction rollback integration test.
- [ ] EAP state machine/methods only if desired as ATD extension; it is NOT an A1.24 parity requirement.

### Phase 3
- [ ] Full credit ledger/business rules.
- [ ] PostgreSQL billing persistence parity.
- [ ] Plans/usage integration.
- [ ] Expiry/subscription state.
- [ ] Full VoIP charging/accounting parity.

### Phase 4
- [ ] Complete REST resources.
- [ ] XML-RPC compatibility adapter.
- [ ] API authentication/RBAC/audit.

### Phase 5
- [ ] User Information editing/high-frequency actions.
- [ ] GROUP and IBSng user/group policy workflows.
- [ ] RAS/IPPool/Online Users/Connection Logs/Connection Usages/Charge/Report workflows.
- [ ] Admin workflows.
- [ ] User portal workflows.

### Phase 6
- [ ] IBSng database importer.
- [ ] Migration validation/parity suite.
- [ ] Rollback-safe migration process.

### Phase 7
- [ ] Modern installer.
- [ ] systemd services.
- [ ] Supported Ubuntu/Debian deployment matrix.
- [ ] TLS/backup/upgrade procedures.
- [ ] Free/Pro licensing enforcement.

## E. IMPORTANT STATUS INTERPRETATION

The project is **not complete as a full IBSng replacement**. The core RADIUS/AAA/accounting/charging engine is substantially implemented, but full provider parity, complete dictionary/attribute coverage, billing/credit business layer, API/RBAC, UI workflows, migration and deployment remain.

Do not mark a subsystem Complete merely because its classes exist. Completion requires implementation + persistence mapping + source-derived behavior + tests/integration evidence appropriate to that subsystem.

## F. IMMEDIATE NEXT BATCH

1. Verify/complete all A1.24 RAS provider behavior from the canonical source.
2. Implement the context-aware SIP/SER dictionary/codec path, then add only provider-consumed USR vendor attributes.
3. Build stronger live UDP -> PostgreSQL integration tests, including rollback atomicity.
4. Reconcile all parity docs against this status and remove stale claims.
5. Continue into credit ledger/billing persistence and full CRUD/API/RBAC work.




## RADIUS dictionary context checkpoint — 2026-10-07
- Canonical source extraction directly verified SIP/SER dictionary types for attributes 101-119, 206-213 and 225, plus the internal 1063-1072 digest attributes.
- The source also confirms a real numeric collision between SIP 101-119 and core dictionary meanings such as Error-Cause 101. ATD therefore must not globally overwrite the core mapping; the remaining implementation is a context-aware SIP/SER dictionary and codec path with provider-aware tests.
- Canonical USR dictionary vendor id 429 was re-inspected. It is large and mixed-type; no guessed global USR mapping was added. Provider-consumed USR attributes remain a source-driven follow-up.
- The temporary source extraction workflow was removed immediately after the inspection; no temporary workflow remains intentionally in main.

## Live UDP/PostgreSQL + transaction atomicity checkpoint — 2026-10-07
- Fixed numeric RADIUS enum decoding for Acct-Status-Type and NAS-Port-Type, including MikroTik Ethernet/Virtual/Wireless assignment behavior on decoded wire values.
- Fixed the RAS SQL repository boundary so parameterized select_ras, select_ras_ports and select_ras_ippools queries bind their parameters through psycopg instead of being executed as raw %s SQL.
- Added real live UDP -> PostgreSQL integration coverage using a PostgreSQL 16 CI service, actual UDP sockets, canonical RADIUS Accounting-Request authenticators, native RAS/user records, connection-log persistence and Stop lifecycle.
- Added a real failure-path test with a PostgreSQL trigger that forces credit settlement to fail; the test proves the shared packet transaction rolls back the accounting mutation and credit change atomically.
- CI now provisions PostgreSQL for the integration suite. Final green commit: 6028f21d6f6ca4f2e7abdd1be31da9e6d000bcc2; Python and CI workflows both succeeded, with 225 tests passing in the CI test matrix.
- This checkpoint upgrades live UDP/PostgreSQL integration and rollback atomicity from TODO to implemented + integration-verified. It does not claim full RAS provider parity or complete billing/credit ledger parity.

## RAS provider source-audit checkpoint — 2026-10-07
- Direct canonical-source extraction completed for the concrete A1.24 RAS implementations under `core/ras/rases/`.
- Provider inventory and major provider-specific distinctions are recorded in `docs/A1.24-RAS-PROVIDER-AUDIT.md`.
- Source confirms that full parity cannot be represented by only a generic RAS boolean/profile: providers have distinct identity keys, attribute extraction, accounting lifecycle, byte/rate handling, IP-assignment behavior and disconnect/kill integrations; VoIP providers additionally have H323/SIP/Asterisk-specific behavior.
- The existing generic ATD RAS registry and common RADIUS/accounting lifecycle remain valid as the common layer.
- The next implementation target is a provider-adapter contract plus source-derived provider profiles/fixtures, starting with representative internet providers (MikroTik, BSAE, ChilliSpot, Cisco) before expanding to Cisco VPDN, PortMaster, PortSlave, Total Control and VoIP providers.
- Temporary source-inspection workflows used for this checkpoint were removed; none is intentionally left in `main`.


### RAS provider profile implementation checkpoint — 2026-10-07
- Added `domain/ras_provider.py` with source-derived provider identity/capability profiles and aliases.
- Added source-derived tests covering provider unique-id keys, explicit multi-login/IP-assignment capabilities, aliases and Start/Stop/Alive status support.
- `ras_allows_multi_login()` now consumes the provider profile for explicit source-defined restrictions while preserving Asterisk/GnuGk attribute overrides and the A1.24 default behavior for providers without an explicit restriction.
- This is the common provider-profile layer only; provider-specific packet normalization, accounting, disconnect/kill and VoIP integrations remain open.


### RAS provider identity checkpoint — 2026-10-07
- Added source-derived provider session identity resolution for providers whose A1.24 implementation keys online state by provider-specific identity rather than a generic session identifier.
- Implemented source-derived identity mappings for port, Acct-Session-Id, H323 conference id, Persistent-LAN mac/ip identity, Total Control interface index and SIP Call-ID, with standard Acct-Session-Id fallback.
- Wired the identity adapter into the live Accounting UDP path before SessionRegistry/charge/connection-log processing.
- Added unit coverage for representative provider identities.
- CI is green on commit `7aabfe7917d6399129052a57ff9de330c18a9e66`.
- Current test count: 214 passing in the Python workflow.


### RADIUS dictionary source-audit checkpoint — 2026-10-07
- Direct canonical-source extraction completed for `radius_server/dictionary`, `dictionary.ser`, `dictionary.sip` and `dictionary.usr`.
- Source confirms the ATD codec currently covers only a subset of the A1.24 wire dictionary.
- The missing coverage includes standard accounting/IPv6/EAP/ARAP attributes, SIP/Digest attributes and a large USR vendor dictionary.
- Added `docs/A1.24-RADIUS-DICTIONARY-AUDIT.md` with the source-derived inventory and implementation sequence.
- Temporary dictionary inspection workflows were removed.
- Next implementation step is the source-derived wire dictionary catalog/codec expansion, prioritizing attributes actually consumed by current RAS adapters and Accounting/AAA paths rather than blindly importing every legacy attribute.


### RADIUS codec dictionary expansion checkpoint — 2026-10-07
- Expanded the wire codec with canonical A1.24 core attributes: Framed-Compression, Login-* family, Framed-Route/IPX, Termination-Action, Proxy-State, LAT/AppleTalk, Acct-Link/Gigawords, ARAP/Prompt/Connect/EAP, Acct-Interim-Interval, Framed-Pool and IPv6 attributes, plus Digest-Response/Digest-Attributes.
- Expanded the Microsoft VSA catalog with source-defined MS-CHAP error, ARAP, accounting/EAP and DNS/NBNS attributes.
- Microsoft IPv4 VSAs are encoded as binary IPv4 values per the canonical dictionary type.
- Added wire round-trip tests for the new core and Microsoft attributes.
- CI is green on commit `b8649746bbb4dbac0956a20f16cb6c9eb74edd62`; Python workflow reports 217 passing tests.
- Temporary source-inspection workflow was removed.


### Provider VSA checkpoint — 2026-10-07
- Added source-derived provider-critical VSA wire support for Cisco, Quintum and MikroTik.
- Covered Cisco H323 conference identity/disconnect fields, Quintum H323 conference identity/disconnect fields, and MikroTik limits/rate/group/host fields.
- Extended provider session identity lookup to accept canonical Quintum H323 conference identity.
- Added wire round-trip coverage for provider VSAs.
- CI is green on commit `ae22c00098d9ca6c77c524f2907643fe85aed497`; Python workflow passes 218 tests.
- Temporary provider dictionary workflow was removed.


### Provider VSA checkpoint — 2026-10-07
- Added source-derived provider-critical VSA wire support for Cisco, Quintum and MikroTik.
- Covered Cisco H323 conference identity/disconnect fields, Quintum H323 conference identity/disconnect fields, and MikroTik limits/rate/group/host fields.
- Extended provider session identity lookup to accept canonical Quintum H323 conference identity.
- Added wire round-trip coverage for provider VSAs.
- CI is green on commit `ae22c00098d9ca6c77c524f2907643fe85aed497`; Python workflow passes 218 tests.
- Temporary provider dictionary workflow was removed.


### Accounting + provider normalization checkpoint — 2026-10-07
- Canonical A1.24 provider inspection confirmed Accounting Alive uses 32-bit octets plus Gigawords counters; ATD now composes `Acct-Input/Output-Octets` with corresponding Gigawords into full counters before session/charge processing.
- Added source-derived provider normalization metadata for ChilliSpot, Cisco, Cisco VPDN, MikroTik, PortMaster, PortSlave, Quintum Tenor and Total Control.
- ChilliSpot now has explicit source-derived Start/Stop-only status support in the provider profile.
- MikroTik IP-assignment behavior is now resolved from canonical `NAS-Port-Type`: Wireless-802.11 disables assignment; Ethernet/Virtual allow assignment.
- The Access context passes this provider decision into the IP-pool policy so provider-disabled assignment does not consume a native pool address.
- CI and Python workflows are green on commit `b5afca85474a`.
- A provider-specific Access-context test fixture was not added because the tool rejected that fixture operation; no test coverage is being claimed for that exact fixture yet.


### Chat handoff verification — 2026-10-07
- Verified against current `main` HEAD `e7e64321abe3e3e40a2d693f1e896a3877da4882` that the two previously announced dictionary/provider tasks were **partial, not complete**.
- Completed: canonical A1.24 core/SIP/SER/USR dictionary source audit; core standard + Microsoft + Cisco/Quintum/MikroTik provider-critical wire catalog expansion; numeric enum decoding; provider profile/identity/normalization layers; wire round-trip tests for implemented attributes; CI green.
- Still open: a context-aware SIP/SER dictionary+codec boundary because SIP 101-119 collide with core meanings; provider-consumed SIP/SER attribute integration/tests; source-driven selection of required USR vendor-429 attributes and their VSA codec; provider-specific wire-level tests for those paths.
- Therefore the earlier phrase “dictionary واقعی + providerهای واقعاً مصرف‌کننده attributeها + source/wire-level validation” must be treated as **not fully delivered**. Only the audited/implemented subset is verified.
- Current codec still has one global core mapping for each standard attribute and generic `Attr-N` fallback; this is intentionally unchanged until the context-aware SIP/SER boundary is implemented.
- Current RAS provider layer is also a common source-derived profile/normalization layer, not full provider-adapter parity. Provider-specific accounting/disconnect/VoIP behavior remains open.
- Current project estimate: the core RADIUS/AAA/accounting/charging engine is roughly **75-80% of the technical core**, while the full IBSng replacement/product is roughly **55-60% complete**. Remaining work is concentrated in provider parity, remaining dictionary/context codec work, billing/credit business layer, CRUD/API/RBAC, UI workflows, migration and deployment/licensing.
- Immediate next batch: (1) trace concrete provider consumers in canonical A1.24, (2) implement context-aware SIP/SER codec/catalog, (3) implement only consumed USR-429 VSAs, (4) add provider-specific wire/integration tests, (5) reconcile parity ledger and run CI before moving to the next subsystem.
- Do not restart the completed dictionary audit, MS-CHAPv1/v2 core semantics, accounting rollback integration, or provider profile foundation unless new source evidence contradicts them.


### SIP/SER context-aware codec checkpoint — 2026-10-07
- Canonical A1.24 SIP/SER dictionary names/types were source-traced and the numeric collision with core attributes was preserved rather than overwritten.
- Added a dedicated SIP/SER codec context in `radius_codec.py`: `encode_sip()` / `decode_sip()`.
- Implemented source-derived SIP wire catalog for 101-119, 206-208, 210-213 and 225; internal Digest attributes 1063+ remain intentionally non-wire and are not encoded as ordinary one-octet RADIUS attributes.
- Core `encode()/decode()` mapping remains unchanged; core 101 is still `Error-Cause`.
- Added round-trip/collision tests in `tests/test_radius_sip_codec.py`.
- Commit: `401a16221b4f1ddfabce5a95e3f6e4003e853c25`.
- CI status was not yet reported by GitHub at checkpoint time; do not call this checkpoint CI-green until a completed run is observed.
- Remaining immediately after this checkpoint: source-trace actual SER/MVTS consumer call paths and implement only the provider-consumed SIP attributes/semantics; then source-trace Total Control's `USR-Interface-Index` wire format and add only the required USR-429 VSA support.


### Provider consumer batch checkpoint — 2026-10-07
- Source-audited SER behavior is now represented in ATD provider normalization: SIP called-number derivation from `Sip-Req-URI` / translated URI and a source-scoped Digest/SIP attribute extraction set.
- Added provider-level tests for SER called-number derivation and Digest attribute consumption.
- SIP codec context and SER normalization are now separate from the core RADIUS dictionary, preserving A1.24's numeric collision boundary.
- Total Control remains intentionally incomplete at the wire-dictionary layer: canonical source says it consumes `USR-Interface-Index` (vendor 429), but the exact vendor sub-attribute number/type has not been re-established in the current tool-visible source extraction. No guessed VSA number was added.
- Next batch must re-establish the exact canonical `dictionary.usr` tuple for `USR-Interface-Index`, then implement vendor-aware USR decoding/encoding and Total Control packet normalization + wire tests in one pass.
- Commits in this batch: `e9ff3348cdbcbf9404054a11ec1ebac5a5c0f627` (SIP codec), `401a16221b4f1ddfabce5a95e3f6e4003e853c25` (SIP tests), `1e34ba01f3450a9c19fff25076c0af5723689e9c` (SER normalization), `ab8dbde8ccf2a1571f64a3247fce428e22205d5d` (SER tests).


### RAS provider registry facade checkpoint — 2026-10-07
- Added RASProviderRegistry plus the shared PROVIDER_REGISTRY instance over behavior already source-traced in docs/A1.24-RAS-PROVIDER-AUDIT.md.
- The facade exposes profile lookup, provider session identity, IP-assignment decision, supported accounting status, disconnect strategy, and SER SIP helpers without inventing new provider behavior.
- Added registry-level tests covering representative internet, ChilliSpot, Cisco, Total Control and SER behavior.
- This checkpoint does **not** claim concrete SNMP/RSH/launcher/H323/Asterisk provider adapters; those remain source-driven implementation work.
- Commits: 0bdfc601d2a971badb54d50da220500922761fb4 (registry), a9f9bb2b3bbc212a5d8502953957700f18aaff8b (tests), bb5971d4c415241e5866513bdb83ad19c3f37844 (audit doc).

### Permanent source-of-truth / continuation rule — 2026-10-07
- **ONLY the original IBSng A1.24 source code in `Source of Truth/IBSng-A1.24.tar.bz2` is the behavioral Source of Truth.**
- All repository Markdown files (root docs, `docs/**`, UI/project notes, matrices, audits, roadmaps, decisions and inventories) are mandatory project-context/record artifacts. They explain scope, decisions, status and completed verification, but **never override the canonical IBSng source**.
- For every source-sensitive implementation: inspect the canonical source call path/consumer, implement only source-supported behavior, add tests, and record the verified result and commit here/appropriate parity ledger so future chats do not redo the work.
- A behavior is marked **Verified** only when implementation/test evidence is traceable to the A1.24 source (and integration evidence where required).
- If any Markdown document conflicts with A1.24 source, the source wins and the documentation must be corrected.
- Current repository HEAD before this checkpoint: `806ae8f112691807f597fb3475fb25615c616b0e`.
- The canonical archive is present in the repository at `Source of Truth/IBSng-A1.24.tar.bz2`; its recorded SHA-256 is `c7117a6a2fd252aa9b8149a1ee6606f9320888da347ee4f839614bb9349d18a8`.
- Repository documentation inventory has been re-checked at this checkpoint; future work must read the relevant Markdown records before changing an already-audited subsystem.


### Direct A1.24 source verification checkpoint — BSAE — 2026-10-07
- Re-verified BSAE directly from the canonical Source of Truth/IBSng-A1.24.tar.bz2.
- Canonical file inspected: IBSng/core/ras/rases/bsae.py.
- Exact source behavior: __addUniqueIDToRasMsg() sets unique_id to port and derives port from getRequestPacket()["User-Name"][0].
- This confirms the ATD BSAE identity exception (User-Name instead of NAS-Port) against the actual A1.24 source.
- Direct source also confirms BSAE auth packet handling consumes User-Password, CHAP-Password, MS-CHAP-Response, and MS-CHAP2-Response.
- A temporary isolated audit branch/workflow was used only to extract the canonical archive in GitHub Actions and inspect the source; the temporary workflow was deleted afterward and was never merged to main.
- Source-sensitive rule remains absolute: Markdown audits are records only; canonical A1.24 source overrides them.


### Direct A1.24 source verification checkpoint — Total Control / USR VSA — 2026-10-07
- This batch was verified against the canonical archive itself, not against Markdown audits.
- Canonical files inspected: IBSng/core/ras/rases/total_control.py, IBSng/radius_server/dictionary.usr, IBSng/radius_server/pyrad/dictionary.py, and IBSng/radius_server/pyrad/packet.py.
- Source facts:
  - Total Control sets unique_id="interface_index".
  - interface_index comes from USR-Interface-Index.
  - dictionary.usr: VENDOR USR 429; USR-Interface-Index 0x9843 integer.
  - Canonical pyrad represents vendor attributes as (vendor_id, attribute_code) tuples.
  - Canonical packet encoding prepends the vendor ID as 32-bit; for USR vendor 429, the sub-attribute code is also encoded as 32-bit, followed directly by the value. Normal vendors use the standard one-byte type/length form.
  - Canonical decoding has the matching USR-specific 32-bit path.
- ATD implementation:
  - added USR-Interface-Index as (429, 0x9843, integer);
  - added USR-specific 32-bit VSA encode/decode handling;
  - added exact wire-level regression coverage.
- Commits:
  - e08aa4473b0d6b7363e8b77a8800a9265b093056 — source-derived USR 429 VSA codec
  - 4d28ff5b78ae186ab975f36513a1f570c683b659 — register USR interface VSA
  - 9d2d9dfe0068221aab2e68165b92d2930f867f55 — wire-level regression test
  - c326bd00a58339e199e3e0fb84d7381f855eb455 — source verification audit checkpoint
- Important: this does not mark the entire RADIUS dictionary complete. It closes only the directly verified USR-Interface-Index gap needed by Total Control.
- Temporary source-audit workflows were isolated on audit branches and are not present on main.


### Direct A1.24 source correction checkpoint — ChilliSpot — 2026-10-07
- Canonical source file inspected directly: IBSng/core/ras/rases/chilli_spot.py.
- Source proves ChilliSpot uses unique_id=port, derives port from NAS-Port, sets ip_assignment=False, consumes PAP/CHAP/MS-CHAP/MS-CHAP2, handles Start/Stop/Alive, and can re-online on Alive when configured. Disconnect uses a RADIUS Disconnect-Request to the configured disconnect IP/port with User-Name.
- A prior ATD profile statement that ChilliSpot did not support Alive was incorrect and has now been corrected. This was a real source-vs-audit discrepancy; source wins.
- Implementation commit: the ChilliSpot profile now exposes accounting statuses Start/Stop/Alive.
- Regression test added for provider_supports_status("ChilliSpot", "Alive").
- Audit correction commit: 2d59f39abf2a328a4fbbbad88c75073288e64a34.
- This checkpoint is explicitly marked source-verified so a future chat must not restore the old Alive=false assumption from an outdated document.

- Follow-up test correction commit: 0b5cf8758c3a1ca614f9477591a147dfa67914f9 — updated two legacy ChilliSpot assertions from Alive=false to Alive=true after the direct A1.24 source verification. Python workflow 745 completed successfully; latest CI workflow 680 is still in progress and must not yet be called green.


### Direct A1.24 source verification checkpoint — Cisco / Cisco VPDN — 2026-10-08
- Canonical source files directly inspected: `IBSng/core/ras/rases/cisco.py` and `IBSng/core/ras/rases/cisco_vpdn.py` from `Source of Truth/IBSng-A1.24.tar.bz2`.
- Cisco Internet identity is `port`; source derives it from Cisco-NAS-Port when present, otherwise NAS-Port-Type + NAS-Port, including Async normalization.
- Cisco VoIP identity is `h323_conf_id`; source explicitly sets VoIP multi-login false and single-session-H323 true.
- Cisco auth consumes User-Name, PAP, CHAP, MS-CHAP, MS-CHAP2 and Calling-Station-Id; Internet accounting handles Start/Stop/Alive and VoIP has its own Start/Stop/Alive path.
- Cisco kill/disconnect behavior is SNMP-or-RSH. Cisco VPDN uses Acct-Session-Id, handles Start/Stop/Alive, and uses RSH interface discovery/kill.
- ATD implementation commit: `e50d29758f4f6bc2d21a4f9f9b4f47f16ea03dd4` — added service-aware provider session identity so Cisco VoIP uses H323 conference ID while Internet remains port-based.
- Regression commit: `b13a2b0ba6fa47a6b96a251cb481f6fe981fb545` — added Cisco Internet/VoIP identity tests.
- Documentation commit: `126012b47d3d49851ff839eae2bc8e653771bda5` — recorded the direct Cisco/Cisco VPDN source facts in the provider audit.
- Temporary Cisco source-audit workflow remains isolated to `audit/a124-cisco-source`; it was not merged to `main`.
- Source-of-truth rule remains absolute: canonical A1.24 source overrides Markdown audits.


### CI verification checkpoint — Cisco parity batch — 2026-10-08
- HEAD: `a95a9c934b4ccbac924d55ccf042888009931f63`.
- Python workflow #757: **SUCCESS**.
- CI workflow #685: **SUCCESS**; both Python 3.11 and 3.12 test jobs passed, including Ruff, PHP syntax and the full test step.
- Therefore the Cisco service-aware identity change and its regression tests are CI-verified on main.
- PortMaster/PortSlave source audit has been started on isolated branch `audit/a124-portmaster-portslave-source`; no provider implementation has been changed from assumptions before direct source extraction.


### Direct A1.24 source verification checkpoint — PortMaster / PortSlave — 2026-10-08
- Canonical source files inspected: `IBSng/core/ras/rases/portmaster.py`, `IBSng/core/ras/rases/portslave.py`.
- Both use `unique_id=port` and derive port from NAS-Port.
- Both consume PAP/CHAP/MS-CHAP/MS-CHAP2 authentication inputs.
- Both handle Start, Stop and the non-Start/non-Stop accounting path as INTERNET_UPDATE; therefore A1.24 Alive is supported even though the source does not name a separate Alive branch.
- PortMaster kill/disconnect is SNMP port-based; PortSlave kill/disconnect uses its external launcher command with RAS IP.
- ATD implementation: `d2fae102448a1d9812c3a142f1accfeb67917f41` adds Start/Stop/Alive to both provider profiles.
- Regression tests: `236071cfbe5238bb8ba0d8885f3aa3393752142e`.
- Audit record: `c0f23b98cb207432241d3de7a0ccda7b06527598`.
- Source-audit branch `audit/a124-portmaster-portslave-source` was used only for extraction; no audit workflow was merged to main.


### Batch checkpoint — RAS packet-context boundary — 2026-10-08
- UI remains **FROZEN** by the established project decision. No new UI implementation is part of the active core batches; final UI work starts only after the core, persistence, APIs, migration and deployment are stable and the real IBSng A1.24 UI has been fully reviewed.
- Added `RASPacketContext` / `provider_packet_context()` as a side-effect-free boundary between generic RADIUS dispatch and future concrete A1.24 provider adapters.
- The context exposes only behavior already source-traced: provider profile, service, provider session identity, multi-login capability, IP-assignment behavior, accounting-status support and disconnect strategy.
- Deliberately **not** implemented here: SNMP/RSH/launcher/Asterisk/H323/SIP side effects. Those require concrete adapter implementations backed by canonical A1.24 source evidence and integration fixtures.
- Regression coverage added for Cisco VoIP context, BSAE User-Name identity and accounting-status gating.
- Commits:
  - `879fac8c0f671d23989071ba55c8a9448481873e` — provider packet-context boundary
  - `c2db9089e40d5eaa6f63cf7e2e2879a3aa62aa6b` — regression coverage
- This batch does not reopen or redo the already source-verified BSAE, Total Control/USR, ChilliSpot, Cisco/Cisco VPDN, or PortMaster/PortSlave audits.


## Source-driven DB/User persistence checkpoint — 2026-10-08

Canonical A1.24 source was consulted directly for this batch (not parity MDs): extracted source evidence covers core/user/user_loader.py, core/user/user_actions.py, core/user/plugins/normal_user.py, the GroupLoader path, and the native PostgreSQL tables/functions. The source confirms that subscriber state is split across users, normal_users, voip_users, user_attrs, caller_id_users, and persistent_lan_users; generic/group attributes are separate attribute stores, and normal-user credential operations use the native normal_users table/function boundary.

ATD change committed in b47719ff2ef4ae7256f6ad4cdc078200e7ef72b4: UserRepository now exposes native A1.24 subscriber components without flattening them into one synthetic table: normal credentials, VoIP credentials, caller IDs, and persistent-LAN records. This is persistence/read-boundary work only; no unverified attribute names or behavioral side effects were invented.

Regression coverage committed in fe3dd1d97d9e8494745e4b24b022f075addbff21: repository tests verify all four native component reads and their PostgreSQL column/table contracts.

CI status for this checkpoint must be checked against the new commit before claiming green. No CI result is claimed here yet.


## Large User/DB/API parity batch — 2026-10-08

Extended the source-driven user persistence work through the API boundary. A1.24 native subscriber components remain separated across normal_users, voip_users, caller_id_users and persistent_lan_users; ATD now exposes those components in the user detail contract while keeping passwords out of the API. The API reports username plus has_password for normal/VoIP credentials, caller IDs, and persistent-LAN bindings (MAC/IP/RAS).

Implementation commits: b47719ff2ef4ae7256f6ad4cdc078200e7ef72b4, 27a6363c77cb04cb2eb75e75cde174db1766c843, ae3c63e4baa0ef40c7c8f5ed784f1c02fa76c25.

Regression commits: fe3dd1d97d9e8494745e4b24b022f075addbff21 and ee4b9c5147d7f0feb07d12f6a82249f59e71d9b0. The latter explicitly prevents a password field from entering the public user component API contract.

Source-first note: no new Service/Plan behavior was invented in this batch. The existing RouteBox service catalog is a separate application/product layer and is not being conflated with IBSng A1.24 core Service semantics until the canonical service source is mapped directly.

CI status: must be evaluated on the final checkpoint commit before declaring green.


## 2026-10-08 source-parity continuation checkpoint

- Verified the native schema inventory contains no generic “services” or “plans” tables. Therefore the RouteBox service catalog must NOT be treated as IBSng A1.24 Service/Plan parity. No guessed Service/Plan persistence was added.
- Re-reviewed native subscriber persistence: users, normal_users, voip_users, user_attrs, caller_id_users, persistent_lan_users and group_attrs remain separate native boundaries.
- Found and corrected a regression in the new user-detail API where the VoIP credential path still exposed the raw password. It now exposes only username + has_password, matching the normal credential contract.
- Added an explicit VoIP API privacy regression test.
- Superseded by the durable source-traced finding in docs/SOURCE-AUTHORITY.md: A1.24 UserLoader/UserAttributes inheritance is already directly traced. User attributes override group attributes; when absent at user scope, the group value is effective. NativeAccessContext may therefore consume the existing policy_attributes boundary; no re-investigation is required unless contradictory canonical evidence appears.

Latest implementation checkpoint before this continuation: d95c2d8eb33d711a5b79c3910dcb2e349fd53a92.
CI had not reported a workflow run for that checkpoint; this remains historical status only.


## MASTER FREEZE / OPEN-WORK LEDGER — 2026-10-08

**This is the handoff contract for every future ChatGPT conversation. Read this section before touching code.**

### 🔒 FROZEN — source-verified + implemented + tested

The following areas are CLOSED. Do not modify, refactor, simplify, rename, reinterpret, or re-investigate them merely because work continues in a new chat. Treat them as trusted dependencies.

#### Authentication / RADIUS core
- [x] PAP authentication boundary.
- [x] CHAP source semantics: CHAP-Identifier + password + CHAP-Challenge, with packet-authenticator fallback when challenge is absent.
- [x] MS-CHAPv1 source field consumption and NT-Response semantics.
- [x] MS-CHAPv2 source field consumption: Peer-Challenge `[2:18]`, NT-Response `[26:]`.
- [x] MS-CHAPv2 username/challenge-hash semantics, including no domain-prefix stripping.
- [x] MS-CHAPv2 Flags/Reserved handling as source-traced.
- [x] MS-CHAP2-Success / AuthenticatorResponse generation.
- [x] MS-CHAP/MPPE response-material generation path.
- [x] MPPE Send/Recv key derivation.
- [x] MPPE encryption context using the original Access-Request Request-Authenticator.
- [x] A1.24-style random high-bit MPPE salts and distinct Send/Receive salts.
- [x] RADIUS duplicate identity: `(source_ip, source_port, packet_id, packet_code)`.

#### Attributes / user loading / MultiLogin
- [x] `multi_login` is an attribute, not a users-table column.
- [x] Absent `multi_login` => default limit 1.
- [x] Explicit `multi_login=0` => real zero limit; first login is rejected.
- [x] User attribute overrides group attribute.
- [x] Group attribute is effective when no user override exists.
- [x] UserLoader/UserAttributes aggregation boundary.
- [x] Native attribute table structure: `user_attrs`, `group_attrs`, `ras_attrs`.
- [x] User instance increment occurs before USER_LOGIN hooks.
- [x] RAS MultiLogin capability is provider-specific and separate from user `multi_login`.
- [x] Existing ATD MultiLogin implementation and its source-derived tests are frozen. **Do not touch MultiLogin without new contradictory A1.24 source evidence.**

#### Database / persistence
- [x] Native subscriber split: `users`, `normal_users`, `voip_users`, `user_attrs`, `caller_id_users`, `persistent_lan_users`.
- [x] Native user/group/RAS attribute persistence contract.
- [x] IP-pool membership in PostgreSQL versus runtime free/used state.
- [x] Native `connection_log` / `connection_log_details` structure.

#### Accounting / charging
- [x] A1.24 provider accounting lifecycle concept: Start/Stop/Alive.
- [x] Native connection-log persistence boundary.
- [x] `no_connection_log` behavior.
- [x] `no_commit` zero-settlement behavior.
- [x] Internet charge-rule source state model: effective rule, rule-start time, per-instance IN/OUT baseline, transition accumulation, final settlement.
- [x] Direct source verification of `InternetChargeRule.start/end` and `getTypeObj().getInOutBytes(instance)` baseline path.
- [x] Shared DB transaction ownership model for runtime composition.

#### Directly verified RAS providers
- [x] BSAE: unique identity = User-Name-derived port; PAP/CHAP/MS-CHAP/MS-CHAP2 inputs.
- [x] Total Control / USR: interface-index identity and exact USR vendor-429 `0x9843` 32-bit wire encoding/decoding.
- [x] ChilliSpot: port identity, IP assignment false, PAP/CHAP/MS-CHAP/MS-CHAP2, Start/Stop/Alive.
- [x] Cisco / Cisco VPDN: source-derived identities, service-specific Cisco VoIP identity, Start/Stop/Alive, source-derived disconnect strategy.
- [x] PortMaster / PortSlave: port identity, PAP/CHAP/MS-CHAP/MS-CHAP2, Start/Stop/Alive behavior and source-derived disconnect strategy.

#### RAS architecture already source-derived
- [x] RAS provider profile/registry foundation.
- [x] RASPacketContext / provider_packet_context boundary and its tested source-derived fields.
- [x] UI sequencing decision: UI remains frozen while core/source-parity work is active.

**Freeze rule:** changing any item above requires direct canonical A1.24 evidence showing the current behavior is wrong/incomplete. Architectural preference, cleanup, refactoring, or a new-chat re-check is NOT sufficient.

### 🟡 OPEN — do NOT treat as complete

These are the active work areas. Implement them in batches, using the canonical A1.24 source first, without reopening the frozen ledger.

#### RADIUS / provider parity
- [ ] Remaining A1.24 RAS providers and their concrete runtime adapters.
- [ ] Concrete SNMP/RSH/launcher/H323/Asterisk/SIP provider side effects where required by source.
- [ ] Full provider-specific wire/integration fixtures.
- [ ] Complete RADIUS dictionary coverage and context-aware provider attribute handling.
- [ ] Remaining SIP/SER provider-consumed attribute semantics/integration.
- [ ] EAP and other unimplemented authentication families.

#### Accounting / billing
- [ ] PostgreSQL credit-ledger persistence.
- [ ] Full billing/credit business layer and expiry/subscription state.
- [ ] VoIP tariff/prefix runtime parity where still unimplemented.
- [ ] Bandwidth-limit side effects and remaining charge-rule edge cases where source requires them.
- [ ] Integration-level transaction rollback proof against a live PostgreSQL runtime.

#### API / product
- [ ] Full CRUD for remaining native A1.24 resources.
- [ ] Permissions/RBAC/audit.
- [ ] XML-RPC compatibility.
- [ ] Remaining REST resource workflows and mutation coverage.
- [ ] Group workflows, RAS/IP-pool/online/logs/usage/charge/report workflows.
- [ ] ADMIN and user-portal workflows.

#### Migration / deployment / licensing
- [ ] A1.24 migration/import tooling.
- [ ] Validation/parity migration tests and rollback-safe migration.
- [ ] Installer/systemd/Ubuntu-Debian deployment.
- [ ] TLS/backup/upgrade workflows.
- [ ] Licensing / product edition limits.

#### Service / Plan semantics
- [ ] Do not invent generic Service/Plan persistence. Current schema inventory has no generic `services` or `plans` tables.
- [ ] If Service/Plan parity is required, trace the exact canonical A1.24 source first; RouteBox service catalog is not automatically IBSng Service/Plan parity.

### ⚠️ STATUS DISCIPLINE
- "Source-traced" means canonical source was inspected.
- "Tested" means ATD regression/unit/integration coverage exists.
- "CI-green" means a completed CI run passed; never infer it from local tests.
- "Frozen" in this ledger means source-traced + implemented + tested and must not be touched without contradictory source evidence.
- Historical commits/checkpoints remain records; current `main` code is the only implementation state.
- If a future chat is uncertain whether something is frozen, **do not change it**; inspect this ledger and the canonical source first.


## Provider action-layer checkpoint — 2026-10-08

- Added provider_accounting_action() and the corresponding RASProviderRegistry.accounting_action() facade.
- This layer maps only accounting branches already directly traced in the A1.24 provider source/audit:
  - Internet Start -> INTERNET_UPDATE
  - Internet Alive -> INTERNET_UPDATE
  - Internet Stop -> INTERNET_STOP
  - Persistent LAN Start/Stop -> the source-native persistent-LAN actions.
- The mapping is deliberately side-effect free. It does not implement or infer SNMP, RSH, launcher, Asterisk, H323 or SIP network operations.
- VoIP accounting is intentionally not mapped here where the exact source action sequencing has not yet been re-established; tests explicitly prevent accidental guessed behavior.
- Added regression coverage in tests/test_ras_provider_actions.py for representative internet providers, Persistent LAN, unsupported status/provider handling, and the deliberate VoIP non-guessing boundary.
- Implementation commit: 7fd00008105e52ab867a1f7d16476084f8f4b76d.
- Test commit: 7ebf26b29979e88aa85e51b570cf54f788c384d3.
- CI status for these new commits has not been independently confirmed yet; do not call this batch CI-green.

### Accounting status correction

The earlier OPEN ledger line saying live PostgreSQL transaction rollback proof is still pending is stale relative to the verified checkpoint at commit 6028f21d6f6ca4f2e7abdd1be31da9e6d000bcc2, which included a real PostgreSQL trigger failure-path test and passed 225 tests in the CI matrix. The open item is therefore removed from the active TODO list; future work should focus on provider-specific accounting parity rather than redoing the already-verified rollback test.


## Provider action-layer hardening — 2026-10-08

- Corrected the provider accounting action layer so only the eight Internet providers whose Internet accounting branches were directly traced in A1.24 can produce Internet session actions: MikroTik, BSAE, ChilliSpot, Cisco, Cisco VPDN, PortMaster, PortSlave and Total Control.
- VoIP-oriented profiles (Asterisk, GnuGk, MVTS, SER, Quintum Tenor) no longer inherit Internet Start/Stop actions merely because their profile metadata contains generic accounting statuses.
- Added regression coverage for this boundary.
- Implementation: 21c95b0badd5014c1ddbc37ee8814020bcc93e6a.
- Regression: 4e681ecae529c91ea04b10a40d32b4745dc88c06.
- CI for this new hardening commit has not been independently confirmed yet.


## RAS adapter checkpoint — 2026-10-08

### MikroTik
- The canonical A1.24 provider audit already contains direct source-derived MikroTik behavior: Internet identity is `port` from NAS-Port; NAS-Port-Type Ethernet/Virtual enables IP assignment while Wireless-802.11 disables it; Internet accounting handles Start, Stop and Alive, with Start/Alive entering the provider's update path and Stop finalizing octets.
- ATD now exposes these already-traced facts through the side-effect-free `MikroTikPacketAdapter` in `src/atd_radius/domain/ras_provider_adapters.py`.
- The adapter delegates to the existing source-derived registry functions and performs no SNMP/RSH or other external side effects.
- Regression tests cover NAS-Port identity, numeric Wireless NAS-Port-Type normalization, and Start/Alive/Stop action mapping.
- No frozen authentication, MultiLogin, attribute, persistence, or generic RAS behavior was modified.
- PPPD and Persistent LAN concrete adapters remain intentionally open until their exact canonical call paths/side effects are directly traced; no behavior is guessed from provider names or profile metadata.
- CI status for this checkpoint is not claimed until the push-triggered workflow is independently observed as successful.


## Large RAS adapter batch checkpoint — 2026-10-08

### Persistent LAN
- The source audit records PersistentLanRas as a distinct lifecycle: internal `mac_ip` identity, `persistent_lan=True`, accounting start, IP assignment disabled, and its own online/waiting lifecycle.
- ATD now exposes the source-traced normalization through `PersistentLanPacketAdapter`.
- Start maps to `PERSISTENT_LAN_AUTHENTICATE`; Stop maps to `PERSISTENT_LAN_STOP`; Alive is intentionally not guessed for this provider.

### SER
- The source audit records SER identity as `call_id`, Start on SIP INVITE/call-id creation, Stop on call-id removal, Digest input extraction, and called-number derivation from the SIP URI.
- ATD now exposes these pure normalization/action facts through `SERPacketAdapter`.
- No external SIP daemon side effect is implemented by this adapter.

### Asterisk / GnuGk / MVTS / Quintum Tenor
- Asterisk and GnuGk now have source-derived capability adapters for their RAS attributes `asterisk_multi_login` and `gnugk_multiple_login`; absent/zero means disabled and nonzero enables the provider capability.
- MVTS exposes its source-defined H323 conference identity.
- Quintum Tenor exposes its source-defined H323 conference identity, `multi_login=False`, and `single_session_h323=True`.
- Provider-specific Asterisk Manager, H323, remaining-time and external telephony side effects are intentionally not implemented without a concrete source-traced operation boundary.

### PPPD
- No direct canonical PPPD call-path evidence is currently present in the durable source findings. The profile says only `unique_id=port`; that is insufficient to safely invent authentication/accounting/kill behavior.
- PPPD therefore remains open rather than being filled from analogy with PortMaster/PortSlave.

### Safety boundary
- These adapters are pure normalization/capability boundaries. They do not perform SNMP, RSH, launcher, Asterisk Manager, H323, SIP or other external side effects.
- Frozen authentication, MultiLogin core semantics, attribute inheritance, persistence contracts, IP-pool runtime state and generic RAS registry behavior were not reopened or modified.
- CI is not claimed green for this batch; the available workflow lookup does not expose a completed push run.

### Continuation checkpoint — 2026-10-09

- Added build_chillispot_disconnect_request() in src/atd_radius/domain/ras_external.py.
- The builder is limited to source-traced facts: configured disconnect IP/port and subscriber User-Name; it validates endpoint port bounds and emits a transport-neutral RADIUS-disconnect request.
- Added regression coverage for the exact request envelope and invalid inputs in tests/test_ras_external.py.
- This does not yet implement RADIUS Disconnect-Request wire encoding or real network I/O; those remain open.
- Frozen authentication, MultiLogin, MPPE, persistence and existing provider identity/accounting contracts were not changed.
- CI must be checked on the new HEAD before describing this increment as passing.

- Follow-up increment on 2026-10-09: added a separate encode_control_request() codec path for outbound RFC 5176 Disconnect/CoA requests, including request-authenticator generation and Message-Authenticator recomputation when present. Added round-trip/verifier regression tests. This does not alter the frozen inbound control path; provider-specific network dispatch remains open.
- Further ChilliSpot increment: encode_chillispot_disconnect_datagram() now builds an authenticated Disconnect-Request datagram using the configured endpoint and source-audited User-Name selector. Regression coverage verifies packet code, identifier, destination, decoded attributes, and request authenticator. It deliberately does not open a socket; dispatch/retry/ACK handling remains open.

- 2026-10-09 follow-up: added verification for outbound Disconnect/CoA responses (including Message-Authenticator when applicable) and a UDP client with endpoint matching, timeout/retry bounds, and authenticated ACK/NAK handling. Fake-socket tests avoid live network effects. ChilliSpot packet creation is limited to the source-audited User-Name selector; real RAS integration remains open.

- 2026-10-09: wired ChilliSpot's source-derived User-Name Disconnect-Request packet to the authenticated UDP control client via ChilliSpotDisconnectClient. The adapter returns validated ACK/NAK responses and is covered by fake-socket tests. Live-RAS integration remains open.

- 2026-10-09: expanded shared control-transport regression coverage for CoA ACK/NAK, Disconnect NAK, spoofed-peer rejection, retry-after-timeout, and timeout/retry bounds. This is protocol transport hardening; provider-specific source fields remain separately scoped.


## RADIUS control destination validation batch — 2026-10-09

- Hardened `RadiusControlUDPClient`: the AF_INET client now accepts literal IPv4 destinations only, normalizes the address before sending and peer comparison, and rejects invalid/boolean/out-of-range ports before socket creation.
- Timeout must be finite and positive; retry count must be a positive integer. This explicitly rejects NaN, infinities, booleans and fractional/string retry values rather than relying on downstream socket/loop errors.
- ChilliSpot's source-derived disconnect request builder validates and canonicalizes the configured IPv4 address. The provider contract remains IPv4/UDP and uses only the source-audited User-Name selector.
- Added regression tests for invalid destination classes, timeout/retry edge cases, and the ChilliSpot builder's IPv4 boundary.
- No frozen authentication, CHAP/MS-CHAPv2, MPPE, MultiLogin, attribute inheritance, persistence, or accounting-core behavior was changed.
- The batch's CI is pending until the final HEAD's workflow runs complete; do not mark it green before verifying the runs.


## IPv4 control-transport batch — CI confirmation — 2026-10-09

- Final implementation/test HEAD before this context-only update: `e406c5ffabd23c6a0ee344e0dfcc118072448b4c`.
- Python workflow #845 (run `37857664848`): success.
- CI workflow #771 (run `37857664923`): success on both Python 3.11 and 3.12; compile, Ruff, PHP syntax and full test steps all passed.
- During the batch, an intermediate commit briefly failed test collection because the newly added parametrized tests lacked a module-level pytest import; this was fixed in `e406c5f`, and both workflows passed on that final implementation HEAD.
- Since this context file update itself triggers CI, the new HEAD must be checked again before claiming the repository's current HEAD is green.


## RADIUS control-request attribute-stream validation — 2026-10-09

- Fixed `verify_control_request()` to validate the complete attribute stream via the shared Message-Authenticator offset parser before accepting a request.
- This closes an early-exit gap: the previous verifier stopped scanning after the first Message-Authenticator and could overlook a duplicate authenticator or malformed trailing attribute.
- Added regression tests that create packets with valid request and Message-Authenticator signatures but deliberately duplicate the authenticator or append an invalid attribute. These test malformed structure specifically, not just a bad signature.
- No source-frozen authentication, CHAP/MS-CHAPv2, MPPE, MultiLogin, persistence, attribute inheritance, or accounting behavior was changed.
- Implementation/test commits: `603b905ac03f0c56e6043bf558188422c124bdbe`, `cbf8567980c79780976c0cf9257422c25c4f4c16`. CI for this batch is pending until the newest HEAD's workflows complete.


## RADIUS datagram framing hardening — 2026-10-09

- Accounting-Request, Disconnect/CoA request, and Disconnect/CoA response authenticators now reject a datagram when the RADIUS Length field differs from the received byte count. This prevents a valid prefix from being accepted while trailing bytes remain in the UDP datagram.
- Added tests for valid signed control request/response packets with a trailing byte and extended Accounting-Request length coverage.
- Corrected the duplicate Message-Authenticator test fixture to use a second structurally valid attribute, ensuring it exercises duplicate-attribute detection rather than accidentally testing malformed trailing bytes.
- This remains protocol-boundary validation; frozen A1.24 auth/session/accounting semantics and CHAP/MS-CHAPv2/MPPE behavior are unchanged.
- Implementation/test commits for this continuation: `130e6eb58b6c17aa8ef3ede09e6927e6dc7b3330`, `657228a49a1e41e0910ebb73f586fbd85264fbf3`, `3f4325fade1b10480c6cf92d3843e482c6ed720f`. CI remains pending until newest HEAD workflows finish.


## Immutable provider operation request boundary — 2026-10-09

- `ProviderOperationRequest` now snapshots incoming parameters and wraps them in a read-only mapping. Mutation of the caller's original dictionary no longer changes a queued request, and consumers cannot mutate the request's parameter mapping.
- Provider and action identifiers must be non-empty strings.
- Added tests for source-parameter snapshot isolation, read-only request parameters, and invalid empty identity fields.
- No external command/OID/launcher argument was invented, and no frozen A1.24 authentication, CHAP/MS-CHAPv2, MPPE, MultiLogin, persistence, or accounting behavior was changed.
- Code/test commits: `93bd725705b672392280ef1aecc409523278f60c`, `15cf3c218927a62e3ace70c96b96183b8d02d54f`. The newest HEAD must pass CI before this batch is marked green.


## Control-request parser hardening — 2026-10-09

- Updated `verify_control_request()` to scan the complete attribute stream using the shared Message-Authenticator parser. A malformed attribute after Message-Authenticator can no longer escape validation, and duplicate Message-Authenticator attributes are rejected.
- The verifier rejects datagrams whose actual byte length differs from the declared RADIUS packet length.
- Added negative regression cases for malformed trailing attributes, duplicate Message-Authenticator attributes, and extra bytes past the declared packet length. Corrected the duplicate-attribute fixture to contain an actual 16-byte attribute value.
- Existing Python and CI workflows were green on the prior implementation/documentation commits; the corrected test fixture has triggered a fresh CI run and is not yet marked green until that run completes.
- No frozen PAP/CHAP/MS-CHAPv2, MPPE, MultiLogin, attribute, persistence or accounting behavior was changed.


## RFC 5176 packet-boundary correction — 2026-10-09

- Corrected control request/response verifiers to follow RFC 5176 §2.3: declared packet length must be 20..4096 and must not exceed received datagram length.
- Bytes beyond the declared packet length are legal padding and ignored; datagrams shorter than declared length are rejected. This replaces an earlier strict-equality check that would have rejected valid padded packets.
- Added regression tests for padding, truncation and the 4096-byte maximum on both Disconnect/CoA requests and responses.
- Source: https://www.rfc-editor.org/rfc/rfc5176.html
- CI is being re-run on the latest test and documentation commits; no green status is claimed until both workflows complete.


## Provider envelope deep-freeze hardening — 2026-10-09

- ProviderOperationRequest now recursively snapshots/freezes nested mappings, lists, tuples and sets, closing the mutation gap left by a top-level MappingProxyType alone.
- ChilliSpot disconnect builder and packet builder reject non-string, empty and whitespace-only usernames with a clear ValueError instead of raising incidental AttributeError or accepting invalid input.
- Regression tests cover nested mutation isolation, nested read-only behavior, and invalid username types/values.
- The RFC 5176 packet-padding/maximum-length work and this envelope hardening are awaiting CI completion on the latest HEAD.


## Outbound control encoder bounds — 2026-10-09

- `encode_control_request()` now rejects identifiers that are not integer values in 0..255 (including bool) and encoded packets larger than 4096 bytes.
- Added regression tests for negative, oversized, boolean, fractional and string identifiers, plus oversized attribute payloads.
- These checks apply only to outbound Disconnect/CoA control requests; existing authentication and accounting paths were left untouched.
- Full CI is pending for the latest implementation/test/documentation commits; verify both workflows before calling the current HEAD green.


## RADIUS control hardening batch — verified implementation checkpoint — 2026-10-09

The implementation/test HEAD `8799d378dfbbf45ff7616e2e0c3c60cb35369cdc` passed:
- Python workflow #879 / run `37926033059`: success, 319 passed and 2 skipped.
- CI workflow #805 / run `37926033053`: success on Python 3.11 and 3.12, including compile, Ruff, PHP syntax and test steps.

Included in this batch:
- Full control-request attribute validation, rejecting malformed trailing attributes and duplicate Message-Authenticator attributes.
- RFC 5176 packet length handling: 20..4096-byte declared length, reject truncation, accept/ignore bytes beyond declared length as padding.
- Outbound control request encoder validates one-octet identifier values and rejects packets exceeding 4096 bytes.
- Provider operation requests recursively freeze nested mappings/lists/tuples/sets; ChilliSpot username inputs receive explicit type/value validation.
- Added regression tests for these boundaries.

Some intermediate CI runs failed while the tests were being introduced (missing pytest import, then assertion/fixture expectations); these were corrected. The implementation/test HEAD above is green. This context-only commit itself triggers fresh CI and must not be considered green until its own run completes.

No frozen A1.24 authentication, CHAP/MS-CHAPv2, MPPE, MultiLogin, attribute inheritance, persistence, or accounting-core behavior was changed.


## Provider operation envelope runtime validation — 2026-10-09

- Hardened ProviderOperationRequest.__post_init__: operation must be an ExternalOperation enum member, and parameters must implement Mapping before the immutable snapshot is built.
- Added regression tests rejecting arbitrary operation strings and non-mapping parameters, plus nested mutation isolation.
- Scope is restricted to the external-operation envelope. No frozen authentication, CHAP/MS-CHAPv2, MPPE, MultiLogin, attribute inheritance, persistence, accounting core, or provider-specific side-effect behavior was changed.
- Current main HEAD before this batch: 520fcb906b984f7a78a2700553711731a4406dc1. CI status for this new batch remains pending until fresh workflow results for the resulting HEAD are observed; the previous green checkpoint is 8799d378dfbbf45ff7616e2e0c3c60cb35369cdc, not this documentation/code update.


## RAS external operation boundary batch — 2026-10-09

- Generic disconnect request builders now reject non-Mapping parameter containers before conversion; malformed false-y inputs can no longer silently become empty parameter dictionaries. An explicit empty mapping remains valid.
- Added regression cases for invalid parameter containers in both generic and provider-specific builders.
- Expanded RAS adapter tests to enumerate every currently source-traced disconnect strategy and assert that providers without audited strategies do not gain guessed operations.
- The seven single-family strategies covered are ChilliSpot RADIUS Disconnect, Cisco VPDN RSH, MikroTik RSH, PortMaster SNMP, PortSlave launcher, Total Control SNMP and Quintum Tenor H323. Cisco SNMP-or-RSH remains deliberately unresolved at the generic adapter layer.
- No concrete SNMP OID, RSH command, launcher argument, Asterisk Manager command, H323 sequence or SIP side effect was invented. No frozen PAP/CHAP/MS-CHAPv2, MPPE, MultiLogin, attribute, persistence, or accounting-core behavior was changed.
- Implementation/test/docs commits for this batch: `694621fb7389781f523dabe8e00c556e3b90edda`, `2177c4a33329f66fd4dae3f4b929a567d620cf39`, `e20b1fe18fcf5518e0e74a432252837e9b841520`. CI is pending for the newest HEAD until its actual runs are observed.

## Concrete RAS SNMP request-construction checkpoint — 2026-10-09

- Re-extracted the canonical Source of Truth archive in an isolated audit branch and verified SHA-256 c7117a6a2fd252aa9b8149a1ee6606f9320888da347ee4f839614bb9349d18a8 before inspecting source call paths.
- PortMaster killUser() is now represented by a concrete transport-neutral SNMP request builder: NAS-Port maps to ifIndex int(port) + 2; IF-MIB ifAdminStatus is set to integer 2; source defaults are SNMP v1, UDP/161, community public, timeout 10, retries 3.
- Total Control killUser() is now represented by a concrete transport-neutral SNMP request builder: the source-derived interface_index receives two ordered IF-MIB ifAdminStatus SETs, integer 2 then integer 1, using source defaults community public, timeout 10, retries 3, UDP/161, SNMP version 1.
- The request builders are wired through PortMaster and Total Control provider adapter objects and have tests for exact OIDs, offsets, operation ordering, defaults and invalid inputs.
- Implementation/test commits: eecc12dbccf38b0e695085364defd65aa1ec45ee, 473699bfcbc8ddcc7f3b57981ae62b8e193dd1b0, 6aa00418fa3fe99c814e8c6a020b076f29d5c62b, 919c0cffd66290e4f14d6d09f1b625e55c9f0d3e.
- Documentation commits: 665b1484a94e87b17a1977b21455d88c7b2aff30, 1117091a5292f83d210315fed5de901107b2746a.
- These builders create request envelopes only; no SNMP network I/O or live-device interoperability is claimed. Current main CI must be checked after the final context update before marking this batch green.
- The temporary source-inspection workflow was kept off main; it must be removed from the audit branch after source review is complete.

## Source-audit correction — PPPD and Quintum Tenor disconnect strategies — 2026-10-09

Direct canonical-source extraction (archive SHA-256 verified) found that the prior provider strategy inventory contained one omission and one false positive:

- PPPD in core/ras/rases/pppd.py overrides killUser() and calls the configured pppd_kill_port_command via the launcher with arguments [RAS-IP, port]. Its default command is IBS_ADDONS-relative pppd/kill. The provider profile now declares the launcher strategy and a source-derived immutable request builder preserves this argument order.
- Quintum Tenor in core/ras/rases/tenor.py does not override killUser(); it inherits the base Ras.killUser() no-op. Quintum-h323-disconnect-cause is accounting Stop metadata only, not an H323 kill operation. The incorrect h323-cause disconnect strategy and generic H323 mapping have been removed.

The earlier audit statements that PPPD lacked a kill path and Quintum Tenor had an H323 disconnect operation are superseded by this correction. The PPPD builder constructs an envelope only; it does not execute the launcher. Live external-operation integration remains open.

## Delivery estimate checkpoint — 2026-10-09

The current planning estimate is recorded in ROADMAP.md and is not a CI metric:
- Technical core: approximately 75–80%.
- Full modern IBSng replacement: approximately 55–60%, leaving about 40–45% of the planned product scope.
- Estimated focused engineering effort to full planned scope: roughly 6–10 working weeks, assuming steady implementation and review. This includes provider/dictionary parity, billing persistence, API/RBAC/XML-RPC, migration/deployment/licensing, final UI workflows and integration hardening.
- Real-device SNMP/RSH/launcher interoperability depends on access to representative RAS hardware and cannot be proven by unit CI alone.

The estimate must be revised as complete milestones land; do not promise a calendar finish date from this range alone. The user's instruction is to continue in cohesive autonomous batches without requiring repeated “continue” prompts.

## Canonical archive checksum correction and RSH provider batch — 2026-10-09

A fresh GitHub Actions runner independently calculated the SHA-256 of the checked-in canonical archive at `Source of Truth/IBSng-A1.24.tar.bz2`. The measured digest is:

`c7117a6a2fd252aa9b8149a1ee6606f9320888da347ee4f839614bb9349d18a8`

Earlier copies of this handoff contained a mistyped digest (`...839bb934...`). The checked-in archive was not modified; this corrects the recorded checksum to match the bytes currently in the repository. Future source audits must compare against the corrected digest.

Direct extraction after digest verification confirmed:
- Cisco VPDN RSH uses configured `cisco_rsh_command`, targets the RAS IP, has a default concurrency limit of 3, resolves the user's virtual interface via `show caller user <username>` (optionally matching remote IP), and disconnects via `clear interface <interface>`.
- MikroTik's configured `mikrotik_ssh_wrapper` receives the RAS IP plus the argument sequence `[mikrotik_ssh_username, mikrotik_ssh_password, command]`. For exact NAS-Port-Type `Wireless-802.11`, source runs the hotspot active removal command keyed by normalized username and client IP; all other types run the PPP active removal command.
- ATD now provides immutable, transport-neutral request builders and adapter wiring for both paths. Cisco VPDN has a `show caller user <username>` lookup request, a parser matching the source regex/username+optional-remote-IP selection behavior, and a separate `clear interface <resolved-interface>` request builder. Lookup → parse → disconnect is not yet orchestrated through a real RSH transport. MikroTik command interpolation is guarded by a conservative token allowlist because the source uses unquoted interpolation and RouterOS escaping semantics must not be guessed.
- These are request envelopes, not an execution layer. No RSH wrapper is run and no live router is contacted in unit tests.

The temporary source-inspection workflow was used only on `audit/a124-rsh-provider-20261009`; it must not be merged into main and should be removed from that audit branch after the source findings are recorded.

Cisco VPDN lookup/parser follow-up: the source-derived lookup request and pure output parser are now exposed on `CISCO_VPDN_EXTERNAL_ADAPTER`; tests cover first-match behavior, remote-IP disambiguation, no-match and unsafe inputs. This remains request construction and parsing only, not a live RSH client or end-to-end disconnect flow.

## Cisco source-configured disconnect branches — 2026-10-09

Direct inspection of the verified canonical archive established the previously unresolved Cisco branch details:
- `cisco_kill_use_snmp` defaults to enabled. The SNMP path uses IF-MIB ifDescr walk `.1.3.6.1.2.1.2.2.1.2` to map a port description to the final numeric ifIndex suffix, then SETs Cisco OID `.1.3.6.1.4.1.9.2.1.76.0` as ASN integer with the ifIndex value. Defaults: SNMP v2c, community public, timeout 10, retries 3, UDP/161.
- When the setting is disabled, source sends `clear line <suffix>` for ports matching `Async[0-9/]+`, and `clear interface <port>` for ports beginning `Serial`. Other ports have no RSH operation in the source branch.
- ATD now has a pure port-description-to-ifIndex resolver and configured SNMP/RSH request builders with validation and tests. Generic strategy metadata stays `snmp-or-rsh`; the caller must supply the actual source-derived config and SNMP index instead of silently selecting a branch.
- These are request builders/resolvers only; live SNMP/RSH execution and the five-hour mapping refresh lifecycle remain open. Frozen AAA/authentication/accounting semantics were not changed.

## Latest verified checkpoint — 2026-10-09

- Main HEAD before this handoff update: `5c4286d2b5df2cbf9d9a88b2bd0511815a0afa0a` (Cisco Async/Serial source-syntax validation fix).
- Python unit suite: **393 passed, 2 skipped, 2 existing deprecation warnings** on that commit.
- Full GitHub Actions CI: **success** for Python 3.11 and 3.12, including Python compile, Ruff, PHP syntax and tests: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/37936839064
- The previous temporary canonical-source inspection workflows have been removed from the audit branch after extraction. No audit workflow was added to `main`.
- The latest Cisco/PPPD/PortSlave/PortMaster/Total Control/MikroTik/Cisco VPDN request builders are construction-only. Do not represent them as real transport execution or device integration. Full RAS parity remains open.


## RADIUS codec wire-type correctness batch — 2026-10-09

Main now includes a correction to the core RADIUS dictionary codec:
- `Framed-IPX-Network` is encoded/decoded as uint32, not IPv4; it was erroneously in both type sets and the IPv4 branch took precedence.
- Added numeric types for `Framed-Routing`, `Acct-Authentic`, `Acct-Link-Count`, both accounting gigaword counters, `ARAP-Zone-Access` and `ARAP-Security`; removed `Login-LAT-Port` from the integer set so it follows its string dictionary type.
- Added strict uint32 bounds and rejects bool/float values and invalid values via `RadiusCodecError` rather than leaking struct errors or truncating floats.
- Added encoding of known enum labels for `Acct-Status-Type` and `NAS-Port-Type` into canonical integer wire values; unknown labels remain rejected. The separate SIP codec remains context-isolated.
- Tests cover wire numbers, four-byte payload lengths, max uint32, round-trip values, enum label encoding and invalid values. The previous codec-only CI run for the numeric type batch passed; the newer enum-label batch is being checked on both supported Python versions.

No PAP/CHAP/MS-CHAPv1/v2, MPPE, MultiLogin, persistence, or accounting state machine semantics were changed in this batch.


## Executable SNMP SET transport increment — 2026-10-09

A new infrastructure transport, `src/atd_radius/infrastructure/snmp_transport.py`, now executes the already source-derived integer SET envelopes for Cisco (SNMPv2c), PortMaster (SNMPv1) and Total Control (ordered SNMPv1 down/up). It implements BER encoding/response parsing with the Python standard library; validates target IPv4/UDP port, version, community, request ID, peer, response OID, error status and exception varbinds; uses bounded timeout/retry settings; and reports prior successful SETs when a later operation in a sequence fails. Tests inject a fake socket and cover version/endpoint selection, ordered multi-SET execution, retry, agent error/partial completion, community mismatch, and invalid requests before socket creation.

This is the first real transport implementation, but it is **not yet wired into the RAS runtime** and no live hardware was contacted. It supports SET only: Cisco ifDescr walk/port-map refresh, RSH and launcher execution remain unimplemented. Latest isolated pytest run passed **425 tests, 2 skipped, 2 warnings** on the test checkpoint; full Python 3.11/3.12 CI for the current commit was still running at the time of this note.
