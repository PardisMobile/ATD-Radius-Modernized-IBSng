# Project Context — Carry-Forward Memory

## Identity
ATD Radius Modernized IBSng is a clean-room modernization project whose behavioral reference is the uploaded IBSng A1.24 source archive. The old Go-based ATD repository is not part of this repository and must not be copied here.

## Reference archive facts
The inspected A1.24 archive contains 2,477 members and 2,295 regular files: 1,028 under core/, 1,049 under interface/, 131 under addons/, 41 under radius_server/, 22 under docs/, and 19 under db/. It contains 453 Python sources, 530 PHP files and 284 Smarty templates plus legacy bytecode/assets.

## Non-negotiable compatibility rule
ATD must not create a different name for an existing IBSng A1.24 concept. This applies to UI menus, pages, entities, fields, database tables/columns, attributes, configuration concepts, workflows and protocol/domain terminology.

Modernization is limited to implementation technology, responsive layout, accessibility, componentization, performance and visual presentation.

## Database rule
The A1.24 PostgreSQL schema is the database source of truth. Do not invent a replacement ATD schema for an existing IBSng table. Any schema change requires an explicit compatibility decision and must preserve import/restore compatibility.

## Fixed architecture
- Python 3.12+ core
- PostgreSQL
- RADIUS authentication/accounting
- EAP as an ATD protocol-boundary extension after source-first analysis
- REST API
- XML-RPC compatibility adapter
- PHP 8+ modern web UI
- ATD design system, RTL/LTR, Persian/English, Light/Dark/System
- migration tooling from existing IBSng installations

## Product intent
The user wants the proven IBSng product model modernized, not a greenfield AAA product with unrelated abstractions. Preserve useful operational semantics; replace obsolete runtime and presentation technology.

## IBSng behavior that must remain visible
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
A source-wide search of the A1.24 archive found no EAP implementation. EAP is therefore an ATD modernization extension, not an IBSng feature claim. It must live at the protocol/authentication boundary and never leak into the domain model.

## Repository rule
Never import code, documentation, generated files, secrets or production data from the previous ATD Radius repository. Do not commit the IBSng archive to this public repository.

## Working rule for future chats
Read this file, ROADMAP.md, ARCHITECTURE.md, docs/DECISIONS.md, docs/phase-0-inventory.md, docs/ibsng-a124-full-inventory.md, and ui/UI-SPEC.md before architectural changes. Then inspect the latest commits before editing code.

## Current implementation checkpoint — 2026-10-06 (RADIUS authentication + wire integration checkpoint)

### RADIUS wire/protocol boundary
- Real RADIUS wire codec covers Access, Accounting and RFC 5176 Disconnect/CoA packet families.
- PAP User-Password encryption/decryption uses the RFC shared-secret algorithm and request authenticator.
- Response authenticators are calculated from the request authenticator and shared secret.
- Accounting-Request authenticators can be verified.
- RFC 5176 Disconnect/CoA Request-Authenticators can be verified.
- Optional Message-Authenticator verification is implemented for Disconnect/CoA requests.
- Control responses emit Message-Authenticator when the request contained one.
- Dynamic authorization attributes needed by the current control path are registered in the codec.
- Focused codec and RFC 5176 tests exist.
- CHAP verification is implemented against the RFC 2865 response format.
- MS-CHAPv2 verification now implements the RFC 2759 challenge-hash, NT-password MD4 hash and DES-based NT-Response check, with a published RFC test vector and native Access-Request coverage.
- This is not yet a claim of full A1.24 RADIUS parity: full RAS coverage, complete attribute dictionary coverage, MS-CHAPv2 success/failure response parity, Message-Authenticator handling for Access-Request, source-derived authentication integration parity and end-to-end parity remain open.

### RADIUS runtime composition
- Native RadiusDispatcher handles Access-Request, Accounting-Request, Disconnect-Request and CoA-Request.
- RadiusRuntimeHandler composes the dispatcher with AccountingSessionService and native User/RAS identity resolution.
- Accounting requests resolve native user/RAS identities and apply the live AccountingSessionService when both identities are available.
- Runtime session control is backed by SessionRegistry and RFC 5176 selector semantics.
- Session selection supports the source-derived NAS/session identifiers currently implemented.
- Disconnect stops all matching active sessions.
- CoA applies the currently supported authorization changes: Filter-Id and NAS-Filter-Rule.
- RFC 5176 NAK error causes are represented for unsupported attributes, missing selectors and no matching sessions.
- UDP dynamic-authorization wire flow has focused integration coverage.
- Dispatcher construction can still be improved by explicit dependency injection instead of runtime mutation; this is technical cleanup, not a completion claim.

### Duplicate request handling
- Duplicate identity includes source IP, source port, RADIUS identifier/code and request authenticator.
- Duplicate cache has expiry/purge support.
- Current runtime has duplicate replay and stale-cache handling.
- Full production lifecycle policy and complete source-derived parity remain open.

### Authentication
- Native Access-Request context resolves users through the canonical A1.24 users / normal_users boundary and loads user attributes.
- Native normal_password comparison is used deliberately; Argon2 is not substituted for the A1.24 credential field.
- Unknown users, wrong credentials and locked users fail authentication before AAA policy acceptance.
- AAA result attributes are output-only; request credentials are not copied into Access-Accept/Reject attributes.
- Multi-login policy preserves A1.24 user-limit and RAS-level semantics, including legacy RAS multi-login compatibility.
- Session timeout / idle timeout policy boundaries are represented in the current AAA pipeline.

### Accounting/session lifecycle
- AccountingSessionService applies native Start / Interim-Update / Stop events to SessionRegistry.
- Start/interim bootstrap preserves initial input/output counters.
- Accounting deltas are calculated against the previous runtime snapshot.
- Stop marks the runtime session inactive.
- Accounting events preserve RADIUS attributes needed for later session selection.
- Native accounting persistence/repository adapters exist, including idempotent connection-log detail upserts.
- Native Accounting persistence is composed into the live RADIUS runtime and persists connection_log plus connection_log_details through the native schema.
- The live path still needs source-derived credit_used settlement, transaction/error semantics and end-to-end connection-history parity tests.
- A1.24 online state is primarily runtime state; internet_onlines_snapshot / voip_onlines_snapshot are the source-confirmed persistence surfaces.

### IP pools / RAS
- Native PostgreSQL `ippool` / `ippool_ips` repository mapping is implemented without inventing an allocation table.
- IP pool runtime preserves the A1.24 process-local free/used model, first-free allocation, explicit claim/release and reload behavior.
- Reload preserves active addresses that remain in the refreshed membership list and drops deleted members.
- `ras_ippools` remains the authoritative RAS-to-pool binding surface.
- Access-Request now allocates from the RAS-bound native pools in `ras_ippools` order and emits the A1.24-compatible `Framed-IP-Address` / `/32` netmask reply.
- Accounting-Start adopts the returned address into the process-local runtime after restart if necessary; Accounting-Stop and successful Disconnect release the runtime lease. CoA does not release it.
- RAS repository plus source-compatible runtime registry/loader is implemented; repository mutation hooks support targeted runtime reload.
- Native user/group/attribute SQL contracts were normalized to psycopg `%s` placeholders; no `$1...` placeholders remain in the infrastructure `*_sql.py` contracts.

### Billing
- Internet charge-rule selection implements source-derived priority: RAS-specific +2, port-specific +1.
- Equal-priority rules retain loader/input order, matching A1.24 replacement semantics.
- Internet charging primitives implement CPM and CPK formulas from the source audit.
- VoIP tariff primitives and charge-rule boundaries exist.
- Native PostgreSQL mapping for internet_charge_rules, charge_rule_day_of_weeks and charge_rule_ports is implemented.
- Native users.credit read/change persistence is implemented through the existing A1.24 change_user_credit() function.
- Effective-rule integration into active accounting, charge persistence/credit settlement, VoIP tariff/prefix runtime parity and end-to-end A1.24 billing parity remain open.

### UI/API
- Initial REST users resources, search/pagination and read-only user workspace exist.
- ATD UI shell, RTL/LTR and theme foundations exist.
- User Information edit actions, high-frequency IBSng workflows, GROUP/RAS/IPPool/REPORT/GRAPH/ADMIN workflows and full user portal parity remain open.

### Current repository head
- The main branch has progressed beyond the historical bd7e48582530e5b584e446b7cd5960425289ce7b checkpoint.
- Latest implementation work adds canonical RFC 2548 Microsoft RADIUS VSA handling for CHAP/MS-CHAPv2 wire attributes, canonical 50-byte MS-CHAP2-Response verification, and wire-level codec tests. The immediate commits are 08052a37, 7fbdd113, adf16472, ae271547, e867ce52, 4f87df0d, c9cdb075 and 795641c6.
- The historical bd7e485 checkpoint remains useful as the pre-wire-integration MS-CHAPv2 checkpoint; do not treat it as current HEAD.
- The code checkpoint immediately before this documentation update has green Python and CI workflow runs.
- Do not mark a subsystem Verified merely because an implementation exists. Verified requires source-derived behavior tests and/or database parity evidence.

## MS-CHAPv2 / MPPE continuation checkpoint — 2026-10-06

- HEAD has advanced through the MS-CHAPv2 wire integration and the subsequent MPPE work; the latest documentation commit is tracked separately from the implementation commits.
- MS-CHAPv2 now covers canonical RFC 2548 50-byte response validation, RFC 2759 NT-Response verification, AuthenticatorResponse generation and Access-Accept MS-CHAP2-Success construction.
- RFC 3079-style 128-bit MPPE Send/Recv key derivation is now implemented from the NT-Response/password material.
- RFC 2548 MS-MPPE-Send-Key and MS-MPPE-Recv-Key wire encryption is now implemented with unique per-packet salts and the corresponding Access-Request Request-Authenticator context.
- Focused tests cover the MPPE derivation and RFC 2548 encrypt/decrypt structure.
- This work is **not** marked Verified yet: the repository's GitHub workflow lookup reports no run for the latest commits, and direct extraction of the binary Source of Truth archive through the GitHub text API is unavailable. Source-first verification against the canonical archive remains an explicit gate.
- MS-CHAP2-Success currently preserves the RFC 2548 Ident byte plus the 42-octet success string.
- Access-Request Message-Authenticator and remaining source-derived MS-CHAP error/failure semantics remain open.

## Immediate continuation priorities
1. Complete mutation-triggered RAS reload integration with transaction-safe source-derived semantics.
2. Wire persistent connection history into the live Accounting-Request path and test idempotency/parity.
3. Strengthen live session admission/termination integration against A1.24 online/session behavior.
4. Complete source-derived RADIUS authentication attributes and remaining protocol coverage.
5. Complete billing/credit settlement, effective-rule integration and connection_log credit_used parity.
6. Continue UI/API parity without changing established IBSng terminology.
7. Complete migration/import, installer, permissions/audit and XML-RPC boundaries only from source-confirmed behavior.

All work above must be driven by repository documents and the A1.24 Source of Truth before implementation.


### Batch checkpoint — API mutation contract hardening — 2026-10-08
- Existing User/Group/RAS CRUD APIs were reviewed before modification; no duplicate CRUD layer was created.
- Fixed Group attribute mutation so `PATCH /groups/{group_id}/attributes/{attr_name}` consumes the declared body model `GroupAttributePayload` instead of an undeclared query parameter.
- Fixed RAS port mutation so the persisted port identity comes from the validated `RASPortPayload.port_name` rather than silently ignoring the body identity and using only the URL value.
- Added `tests/api/test_api_contracts.py` covering both payload contracts.
- Commits: `f7abef610438b15f7e8a82247777afda77a8c91d`, `3df950962b7f861841f7c1267cb6b6b4dc7e62c8`, `e18d0c2bf43da1111962d28f09ee53f9a0cb4968`.
- This batch does not change UI, RADIUS protocol semantics, or canonical A1.24 source-derived provider behavior.


## Latest verified handoff — 2026-10-10 (runtime lock and ownership)

Canonical A1.24 archive SHA-256 remains `c7117a6a2fd252aa9b8149a1ee6606f9320888da347ee4f839614bb9349d18a8`. Do not substitute guessed semantics for source behavior.

Latest code/test commit: `28d0989c6f43c3fcc8be18b54e5f2caa40dc68f7`. `RadiusRuntimeHandler` now holds the same `SessionRegistry.synchronized()` lock across Accounting-Request dispatch, user/RAS identity resolution, accounting session apply and IP-pool side effects. `atd_radius.main._start_radius_servers` places its exact `NativeRadiusRuntimeState` on `app.state.radius_runtime_state` so the API can share the UDP process's registry when launched through this entry point.

Verification: full CI passed Python 3.11 and 3.12 with **654 passed, 2 warnings** per matrix job (https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38074052515). Python-only: **652 passed, 2 skipped, 2 warnings**; skipped cases are live UDP/PostgreSQL integration tests (https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38074052624).

Limitations are binding: this is process-local only. External ASGI launchers, multi-worker operation and restart recovery do not share/restore authoritative session truth. RAS Disconnect and user deletion remain intentionally unimplemented; deletion also still requires source-compatible mailbox post-commit handling, refund/ledger/IAS/audit transaction behavior, and full dependent-table cleanup. Next work must continue from this checkpoint, trace behavior in the A1.24 archive first, add tests, and update this handoff/status after each cohesive verified batch.


## A1.24 online/deletion guard — source blocker discovered 2026-10-10

The canonical online lifecycle is not just RADIUS Accounting-Start. In A1.24, `core/user/user_pool.py::getUserByID(..., online_flag=True)` checks the user deletion blacklist and marks the loaded user online while the per-user loading lock is held, explicitly protecting login-in-progress. `core/user/online.py` then registers successful logins in `user_onlines[user_id]` and `ras_onlines[(ras_id, unique_id)]`; logout clears the online flag only when the last instance leaves. ATD's current registry learns active sessions from RADIUS accounting, and Access-Accept can occur before Accounting-Start. So the runtime lock/ownership increment is necessary but insufficient to safely expose user deletion or online-user parity. Next work must trace and design the equivalent login-in-progress reservation plus rollback/expiry lifecycle before those endpoints are added. Never use historical connection logs as authoritative online state.

## Latest verified feature handoff — VoIP caller IDs (2026-10-10)

The canonical source IBSng/core/user/plugins/caller_id.py defines CallerIDUserAttrUpdater, checks Admin.canChangeVoIPAttrs for every target, expands MultiStr comma lists/ranges, enforces global uniqueness in caller_id_users, replaces a user's caller-ID rows and records native user audit. The A1.24 source explicitly says the global uniqueness check is not thread-safe. ATD now provides single-user PUT/DELETE /api/v1/users/{username}/caller-ids, native caller_id_users persistence, CHANGE VOIP USER ATTRIBUTES contextual owner-scoped authorization with its native dependency on CHANGE USER ATTRIBUTES, USER_AUDIT_LOG handling and operational audit in the same transaction. Caller IDs are never written into user_attrs.

Latest feature code/test commit: ff29222f03cfacbe9dc7c8ecf143e81f327c7121. Full CI passed Python 3.11/3.12: 662 passed each, 2 warnings (https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38081828572). Python-only: 660 passed, 2 skipped, 2 warnings (https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38081828570). See docs/A1.24-CALLER-ID-AUDIT.md.

Compatibility note: these are single-user endpoints only; do not claim parity for A1.24's multi-user caller-ID allocation behavior. Numeric range expansion is capped at 1,000,000 generated values as a resource guard. Existing major blockers remain: source-equivalent login-in-progress/session reservation, durable cross-process active session truth, user deletion/mailbox cleanup, RAS Disconnect ordering, and broader A1.24 behavior/migration coverage.


## Additional attribute plugin checkpoint — 2026-10-10

`voip_preferred_language` is now enabled in the source-traced generic attribute mutation slice. A1.24 stores it in `user_attrs` through `VoIPPreferredLanguageAttrUpdater`; the updater has no custom permission check or validation override. ATD preserves generic owner-scoped `CHANGE USER ATTRIBUTES` behavior and native user audit. Its source comment says two-letter language codes but does not enforce them, so ATD does not introduce stricter validation. Regression test added. Full CI passed on Python 3.11 and 3.12: 663 passed, 2 warnings per matrix job; see run https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38082360746 and `docs/A1.24-ATTRIBUTE-BEHAVIOR-AUDIT.md`. Commit: `581fd60d87f2e15f6f4dd81cf50e0cbbb3772ed6`.


## Handoff — save_bw_usage marker

The generic user-attribute mutation API now includes A1.24 `save_bw_usage` based on `IBSng/core/user/plugins/save_bw_usage.py`. It is a presence marker persisted in `user_attrs` with an empty string, not a boolean string or numeric value. The current mutation endpoint accepts only `""`; deletion follows generic delete semantics. Generic owner-scoped authorization and native user audit are retained. A focused regression test was added. CI is running; verify it before calling this increment complete. Bandwidth usage accounting still needs consumer integration and parity tests.


## Handoff — fast_dial attribute mutation (2026-10-11)

Canonical source `IBSng/core/user/plugins/fast_dial.py` was read from the pinned A1.24 archive. `FastDialAttrUpdater.changeInit()` requires ten entries, validates each as empty or digit-only, stores a comma-joined string and calls `useGenerateQuery(..., False)`; `deleteInit()` also disables native user audit. ATD now exposes this attribute through the existing generic mutation service with equivalent string validation and audit suppression on both mutation paths. Added three regression tests. Runtime behavior (FASTDIAL_PREFIX called-number conversion, reply redirect-number, fast-dial index state) and the source actions manager are not implemented by this increment. Verification: full CI passed on Python 3.11 and 3.12 with 667 tests passed in each matrix job and 2 warnings per job (https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38126347300). Python-only workflow also passed (https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38126347240).


## Fast-dial runtime source audit — 2026-10-11

The current main branch contains source-backed fast_dial mutation/storage and green CI for the code/test checkpoint. The archive SHA-256 was rechecked as `c7117a6a2fd252aa9b8149a1ee6606f9320888da347ee4f839bb9349d18a8`. Read `docs/A1.24-FAST-DIAL-RUNTIME-AUDIT.md` before implementing the runtime consumer. A1.24's plugin acts on VoIP/RAS messages during login/update: it checks `FASTDIAL_PREFIX`, parses the called-number suffix, rewrites `called_number`, invokes `setRedirectNumber(reply_packet, destination)`, and stores the selected index in instance metadata. The source actions manager also exposes add/get destination methods. None of those runtime/actions-manager semantics should be approximated as generic RADIUS reply attributes. Runtime integration and its source-derived tests remain open. Preserve all previously verified PAP/CHAP/MS-CHAP/MPPE, MultiLogin, Accounting and Persistence behavior.


## Fast-dial runtime foundation — 2026-10-11

A new source-shaped domain helper and regression suite were added: `src/atd_radius/domain/fast_dial.py`, `tests/domain/test_fast_dial.py`. It models A1.24's prefix gate, integer suffix/list-index semantics, instance `fast_dial_index`, and redirect callback; destination editing separately enforces the actions-manager's digit-only destination and 0–9 slot checks. This helper is not yet connected to the production VoIP/RAS message lifecycle; do not claim fast-dial runtime parity. GitHub commits: `318b9b0f`, `8b70ba9b`, `383472b2`.

Checksum issue: the project-provided hash literal `c7117a6a2fd252aa9b8149a1ee6606f9320888da347ee4f839bb9349d18a8` is only 61 hex characters, so it cannot be a SHA-256. The uploaded archive computes to `c7117a6a2fd252aa9b8149a1ee6606f9320888da347ee4f839614bb9349d18a8`. Treat this as a discrepancy requiring reconciliation, not a successful match. Keep all validated authentication, MPPE, session, accounting and persistence behavior frozen.


## Verified checkpoint — 2026-10-11

Latest main HEAD `2dd944de4f8df82792f23912f301d6725263d9ff` passed full CI: 672 tests passed, 2 warnings on Python 3.11; Python 3.12 job also succeeded. See https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38159213377. The fast-dial helper is a tested domain primitive only; the production VoIP/RAS lifecycle and actions-manager endpoints remain unfinished. Preserve the archive checksum discrepancy documented in CURRENT-STATUS; do not claim the malformed 61-character supplied hash matches the 64-character hash computed from the uploaded archive.


## Continuation checkpoint — fast-dial action API (2026-10-12)

Source-of-truth rules unchanged: the IBSng A1.24 archive wins; do not modify the frozen PAP/CHAP/MS-CHAP, MS-CHAP2 response, MPPE, MultiLogin, persistence/accounting semantics without a source trace. The uploaded archive's actual SHA-256 remains `c7117a6a2fd252aa9b8149a1ee6606f9320888da347ee4f839614bb9349d18a8`; the older supplied literal is invalid (61 hex characters).

Implemented a source-backed admin action API for fast-dial slots:
- `src/atd_radius/infrastructure/fast_dial_actions.py` maps the A1.24 actions manager to `user_attrs.fast_dial`.
- `GET /api/v1/users/voip/{voip_username}/fast-dial/{index}` is owner-scoped by GET USER INFORMATION and returns an empty string for unset/out-of-range slots.
- `PUT /api/v1/users/voip/{voip_username}/fast-dial/{index}` requires CHANGE VOIP USER ATTRIBUTES and dependencies, validates destination digits and index 0–9, locks the owning user row, updates one slot, preserves native fast_dial user-audit suppression, and writes operational audit.
- Tests cover storage, slot isolation, index behavior, row lock, owner permission, denied writes, and audit.
- Python-only CI for API/test commit `0807517e0cadfe271dc3a776d41c2c20949a595b` passed. Full CI subsequently passed on commit `44c46a5aadee4ed5087f5789694b03a570b6e2b4` on Python 3.11 and 3.12, including compile, Ruff, PHP syntax and tests: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38179760306. The later `920bf47d` change only documents the live-runtime cache boundary; its CI is still running.

Remaining fast-dial blocker: this API/action-manager slice does not wire the domain helper into the production VoIP/RAS `s_login` and `s_update` lifecycle. Called-number rewrite, redirect-number reply, and authoritative per-instance `fast_dial_index` lifecycle remain incomplete. Next priority is to trace and implement that runtime boundary without routing it through generic RADIUS Access-Accept attributes. Do not mark full fast-dial parity complete.


## Bandwidth snapshot runtime checkpoint — 2026-10-12

A1.24 source trace for `save_bw_usage` followed `core/snapshot/bw_snapshot.py`, `core/snapshot/plugins/internet_bw.py`, `core/snapshot/snapshot_main.py`, `core/snapshot/snapshot_searcher.py`, and the native `internet_bw_snapshot` schema. Added `domain/bandwidth_snapshot.py` aggregation primitive and `infrastructure/bandwidth_snapshot_repository.py`; the RADIUS accounting handler now persists positive counter deltas for normal users with the effective `save_bw_usage` marker. The effective policy uses `UserRepository.policy_attributes()` (group defaults then user overrides). The native table has `(user_id, snp_date)` primary key; writes aggregate into repository interval buckets (default 60 seconds) and accumulate duplicate keys.

Important parity boundary: IBSng periodically polls each active instance and sums per-instance rates at `SNAPSHOT_BW_INTERVAL` (default 60 seconds). ATD's current path is event-driven from RADIUS accounting counters and cannot yet guarantee samples when Interim-Updates are absent. Do not label full bandwidth snapshot parity until source-derived tests cover counter resets, missed updates, provider-specific counter semantics and interval behavior. Latest CI must be checked before claiming this increment green.


Latest verification note (2026-10-12): Python-only CI passed at HEAD `f97af48b94204ac2e7d6065d522c29d2583dc76e` (https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38180272821). Full CI passed on the same implementation after the source-backed localtime fix at `bcb942adf311b3369dbe1a9d1da486bc1b633433` (https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38180263093). Full matrix for the latest test-only commit remains in progress. Bandwidth sampling remains partial parity because event-driven RADIUS deltas cannot guarantee the original periodic per-instance snapshots.


## Mandatory carry-forward — full source and Markdown audit (2026-10-12)

Current repository HEAD at this checkpoint: `f82961255d42b14f5378b69759163d8bdc168d10` (status-ledger refresh; code unchanged). Current main CI for the preceding code/docs checkpoint `f87a63cf46c6b271d6efdcc2a7d80af2d649c760` passed both full and Python-only workflows:
- Full: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38180343444
- Python-only: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38180343421

User instruction reaffirmed: do not stop any workstream. The entire IBSng A1.24 archive and every Markdown file in the ATD repository must be reviewed; an inventory alone is insufficient. The repository tree currently contains 65 Markdown files; all were fetched for a first-pass inventory of headings, dates, TODO/checklist markers and recent checkpoints. Continue with semantic cross-document consistency review, then correct source/status contradictions with evidence. Do not claim the complete content audit is finished merely because files were fetched.

The local canonical archive hash is `c7117a6a2fd252aa9b8149a1ee6606f9320888da347ee4f839614bb9349d18a8`; tar inventory reports 2,477 members, 2,295 regular source files, 453 Python files, 530 PHP files, 284 Smarty templates, and 20 SQL files. Every source review pass must record file/call path, consumers, DB side effects, runtime lifecycle, ATD mapping, tests, and status. Preserve already verified/frozen PAP, CHAP, MS-CHAPv1/v2, MS-CHAP2-Success/AuthResponse, MPPE, MultiLogin, feature/persistence/accounting core unless exact A1.24 source evidence proves a required correction.

Immediate implementation priorities remain parallel, not replacements for one another: Fast Dial production VoIP/RAS lifecycle, bandwidth periodic-sampling parity, billing/accounting settlement, source-compatible login/session-in-progress truth and safe destructive operations, provider interoperability, XML-RPC, schema import/parity, and installation/upgrade/rollback. Each batch must end with regression tests, CI on the resulting HEAD, and status/roadmap/context updates.

## Content-audit reconciliation — 2026-10-12

Direct content review found that some older checkpoint paragraphs still said a later CI run was pending or described already-wired accounting persistence as absent. Those paragraphs are historical; the later explicit corrections in `docs/CURRENT-STATUS.md`, `docs/A1.24-RADIUS-DISPATCH-PARITY.md`, `docs/A1.24-RUNTIME-BATCH-AUDIT.md`, `docs/A1.24-LOGGING-SCHEMA-PARITY.md`, and `docs/A1.24-PERSISTENCE-SQL-AUDIT.md` supersede their current-state interpretation. Full CI passed on code/test HEAD `f97af48b94204ac2e7d6065d522c29d2583dc76e` (694 passed, 2 warnings per Python 3.11/3.12 job), and on docs checkpoint `f87a63cf46c6b271d6efdcc2a7d80af2d649c760`. Subsequent content-audit commits are documentation-only and their exact-HEAD CI must still be checked. The archive and full-parity requirements remain unchanged.


## Verified backend increment — 2026-10-12 (current checkpoint)

Current code HEAD before this status-only commit: `057b69789e9c353a8531d927129e09fafaf3105d`.

Verified on that exact HEAD:
- Full CI: Python 3.11 **720 passed, 2 warnings**; Python 3.12 **720 passed, 2 warnings**. Compile, Ruff, PHP syntax and PostgreSQL integration all passed: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38184422207
- Python-only: **718 passed, 2 skipped, 2 warnings**; the skips are PostgreSQL/UDP integration tests excluded from that workflow: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38184422151

Source-backed work in this increment:
- Added native PostgreSQL VoIP tariff/prefix read and mutation support against `voip_charge_rule_tariff` and `tariff_prefix_list`, including parameterized writes, duplicate prevention, locking, and deletion refusal when a tariff is referenced by `voip_charge_rules`.
- Added `GET/POST/PUT/DELETE /api/v1/voip-tariffs` workflows and prefix add/update/delete endpoints; reads use `SEE VOIP TARIFF`, mutations use `CHANGE VOIP TARIFF`.
- Corrected the native permission chain: `CHANGE CHARGE` depends on `ACCESS ALL CHARGES`; `SEE VOIP TARIFF` and `CHANGE VOIP TARIFF` depend on `CHANGE CHARGE`.
- Added a native `voip_charge_rules` reader preserving `charge_id`, `tariff_id`, `time_limit`, days and ports.
- Corrected A1.24 port semantics: only explicit `_ALL_` is wildcard; an empty port set matches no port. The live PostgreSQL fixture now inserts `_ALL_` where intended.
- Corrected VoIP prefix API ordering to match A1.24's `prefix_name` ascending order.

Still open before UI/installer: VoIP call/RAS lifecycle and charge settlement parity; Fast Dial runtime wiring; periodic bandwidth snapshot parity; authoritative login-in-progress/session state and safe destructive operations; remaining billing administration and rule mutation; XML-RPC/IAS; full database restore/import parity; provider-backed Disconnect/CoA; remaining reports and user/admin workflows. Do not claim backend complete yet. UI and installer remain final-stage workstreams after these backend gates are addressed.


## VoIP charge-rule backend increment — 2026-10-12

Code checkpoint before this documentation update: `2d645d7a08e599e53006d38c4d868987caed0aa8`.

New source-backed work in this increment:
- Added VoIP charge-rule list/create/update/delete API workflows using `CHANGE CHARGE` and `ACCESS ALL CHARGES` permission checks, with transactional operational audit.
- Added native PostgreSQL persistence against inherited `voip_charge_rules`, `charge_rule_day_of_weeks`, and `charge_rule_ports`, using `charge_rules_id_seq`.
- Added validation for native charge type, tariff existence, time/day fields, source-style overlap behavior, RAS existence, and named ports configured for the selected RAS.
- Added `select_effective_voip_rule` to match A1.24 `VoipChargeRule.anytimeAppliable`: a non-empty called number must match a prefix in the candidate tariff; an empty called number remains eligible while the RAS has not supplied it.
- Added mocked CRUD regressions and a real PostgreSQL create/update/delete round-trip test using the CI schema.

CI: the preceding code checkpoint `452b9b67cc060136778f8edeb2b5e7ba0c9813c1` passed full CI with **737 passed, 2 warnings** on both Python 3.11 and 3.12. Python-only for the code checkpoint containing the PostgreSQL round-trip test reported **735 passed, 3 skipped, 2 warnings**; PostgreSQL integration is excluded from that workflow. Full CI for `2d645d7` was still running when this note was written, so do not mark that exact checkpoint verified until its CI finishes.

Still open before UI/installer: the native charge loader/cache reload side effect, production VoIP/RAS call lifecycle, call-time rule transitions, free-second tracking, missed-call behavior, rounding across rule transitions, credit settlement, and broader remaining backend parity. Do not enable destructive user/RAS operations until authoritative session/login-in-progress state and provider-backed termination are safe.


## Source-accurate empty-port persistence — 2026-10-12

A deeper trace of `ChargeActions.__addChargeRulePortsQuery` found that an empty submitted port list is stored as one `charge_rule_ports.ras_port = NULL` row, not as zero child rows. The loader returns that SQL NULL unchanged, and `ChargeRule.anytimeAppliable` still does not treat it as a wildcard; only a literal port match or `_ALL_` applies. The VoIP adapter now preserves this exact storage/mapping behavior and overlap checks distinguish SQL NULL from the string `"None"`.


## Verified billing administration checkpoint — 2026-10-12

Code checkpoint `1e66ad4e9f0b418f46da2568915879ceb8ea292f` passed full CI:
- Python 3.11: **749 passed, 2 warnings**
- Python 3.12: **749 passed, 2 warnings**
- Full CI includes Ruff, Python compilation, PHP syntax checks, and PostgreSQL-backed integration tests: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38189213820
- Python-only workflow: **745 passed, 4 skipped, 2 warnings** (PostgreSQL/UDP integration tests are excluded): https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38189213782

Backend work now includes native VoIP tariff/prefix CRUD, VoIP charge-rule CRUD, Internet charge-rule CRUD, transactional operational audit, RAS/port validation, and real PostgreSQL create/update/delete round trips. Internet rule persistence includes native bandwidth leaf IDs and validates paired leaf names, CPM/CPK, positive assumed KPS, and non-negative bandwidth limit. VoIP rule selection now checks called-number prefixes as A1.24 does. Empty submitted port lists persist the native SQL NULL row and are not treated as wildcard; only literal port match or `_ALL_` applies.

Remaining before UI/installer: runtime reload of charge definitions, Internet bandwidth shaping side effects, production VoIP call lifecycle and credit settlement, VoIP rule transitions/free seconds/missed calls/rounding, periodic bandwidth snapshot parity, authoritative login-in-progress/session state, safe provider-backed Disconnect/CoA, XML-RPC/IAS, and full restore/import/report/workspace parity. Do not unfreeze validated PAP/CHAP/MS-CHAP/MPPE/MultiLogin/accounting persistence behavior without direct source evidence.


## Verified charge administration + bandwidth leaf catalog — 2026-10-12

Code checkpoint `32422e4922a8895e72edcddd4b8b9f85005fe3b9` passed full CI:
- Python 3.11: **752 passed, 2 warnings**
- Python 3.12: **752 passed, 2 warnings**
- Ruff, Python compilation, PHP syntax and PostgreSQL integration all passed: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38189408404
- Python-only: **748 passed, 4 skipped, 2 warnings**: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38189408419

Additional backend work: read-only `GET /api/v1/bandwidth-manager/leaves` and leaf-by-name API now map the native `bw_leaf` fields needed by Internet charge rules. Access uses the A1.24 `CHANGE BANDWIDTH MANAGER → CHANGE CHARGE → ACCESS ALL CHARGES` permission chain. The API is intentionally read-only until bandwidth hierarchy mutations can include native validation and safe loader/tree reload side effects.

Still unfinished before UI/installer: write-side bandwidth manager (interfaces/nodes/leaves/services and loader effects), applying/removing Internet bandwidth limits through real RAS/provider operations, charge loader reload after rule mutations, full VoIP call lifecycle/settlement, periodic bandwidth snapshot parity, authoritative login-in-progress/session state, provider-backed Disconnect/CoA, XML-RPC/IAS and complete import/report/workspace parity.


## Verified charge catalog + user charge assignment — 2026-10-12

Code checkpoint `09044676484684c9400025abe3b7364ed924f33e` passed full CI:
- Python 3.11: **771 passed, 2 warnings**
- Python 3.12: **771 passed, 2 warnings**
- Ruff, Python compilation, PHP syntax and PostgreSQL integration passed: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38189815507
- Python-only: **765 passed, 6 skipped, 2 warnings**: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38189815435

New source-backed functionality:
- Charge catalog list/get/create/update/delete with native `charges_id_seq`, `Internet`/`VoIP` type checks, name validation, audit, and delete guards for user/group assignments; deletion removes associated native rule child rows.
- User `normal_charge` and `voip_charge` assignment/get/delete endpoints store native charge IDs in `user_attrs`, validate the corresponding component and charge type, enforce user-change permissions and A1.24 `canUseCharge` rules (visible-to-all, GOD, ACCESS ALL CHARGES, or CHARGE ACCESS), and preserve native user audit names.
- Integration tests cover real PostgreSQL charge catalog mutation/deletion guard and normal/VoIP user charge assignment round trips.

Still open before UI/installer: bandwidth hierarchy writes and runtime shaping, charge loader/RAS reload effects, complete VoIP call lifecycle/settlement, periodic bandwidth snapshot parity, authoritative login-in-progress/session state, provider-backed Disconnect/CoA, XML-RPC/IAS, and complete import/report/workspace parity. This checkpoint does not certify all backend parity.


## Verified IAS event API increment — 2026-10-12

Code checkpoint `35f23bea970f519f3779a7a5afd548951c94a18f` passed full CI:
- Python 3.11: **778 passed, 2 warnings**
- Python 3.12: **778 passed, 2 warnings**
- Ruff, compilation, PHP syntax and PostgreSQL integration passed: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38190051467
- Python-only workflow passed: https://github.com/PardisMobile/ATD-Radius-Modernized-IBSng/actions/runs/38190051470

Added native IAS event list/delete API with GOD-only authorization, using A1.24 event-type IDs, `event_id > from_event_id`, ordered pagination, and parameterized deletes. The API caps pagination at 3000 rows and rejects the legacy `from == to` edge because A1.24's DB helper accidentally omits LIMIT in that case. PostgreSQL integration verifies IAS event read/delete. IAS event list/delete and user-info REST endpoints are implemented with GOD-only authorization. Source audit found no registered `HANDLE IAS EVENTS` permission class; the native IAS handler methods `lockUser` and `lockAdmin` are defined but not registered, so they are not exposed source methods and should not be treated as missing parity. Native XML-RPC transport/auth compatibility remains open.


## IAS permission source correction — 2026-10-12

Direct inspection of the complete A1.24 `core/admin/perms/` directory found no `HANDLE_IAS_EVENTS.py` permission class. Although `IASHandler` calls `canDo("HANDLE IAS EVENTS")`, the permission loader rejects unregistered permission names; `Admin.canDo` bypasses permission checks only for GOD. Therefore the registered native IAS methods are effectively GOD-only in A1.24. The REST IAS event/user-info routes now enforce GOD rather than inventing a grantable `HANDLE IAS EVENTS` permission. The old permission-catalog entry is corrected accordingly.
