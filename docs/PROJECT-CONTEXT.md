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
