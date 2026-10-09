# RAS External Side-Effect Boundary Checkpoint — 2026-10-08

This checkpoint advances the open A1.24 RAS side-effect work without inventing provider commands.

## Implemented

Added `src/atd_radius/domain/ras_external.py` with:

- transport-neutral `ProviderOperationRequest`;
- explicit operation families for SNMP, RSH, launcher, RADIUS Disconnect, Asterisk Manager, H323 and SIP;
- a deterministic `RecordingExternalTransport` fake;
- source-audit-backed disconnect strategy classification;
- conservative request construction: strategies with multiple alternatives (for example Cisco SNMP-or-RSH) are not collapsed into a guessed implementation.

Added `tests/test_ras_external.py` covering the operation families, unknown-strategy safety, multi-operation safety, request construction and the fake transport.

## Source-of-truth boundary

The canonical A1.24 archive remains authoritative. The current repository's binary archive cannot be decoded through the GitHub text-content API, so this batch does **not** invent SNMP OIDs, RSH command strings, launcher arguments, Asterisk Manager commands, H323 operations, SIP daemon operations, or RADIUS Disconnect-Request wire details.

The next concrete provider adapters must be built only after exact canonical source evidence for those operation parameters is available.

## Providers represented by already source-traced strategy metadata

- Cisco: SNMP-or-RSH (intentionally unresolved)
- Cisco VPDN: RSH interface (source-derived command builder added below)
- MikroTik: RSH wrapper (source-derived command variants added below)
- PortMaster: SNMP port
- PortSlave: launcher
- PPPD: launcher
- Total Control: SNMP interface
- ChilliSpot: RADIUS Disconnect-Request / provider port
- Quintum Tenor: no generic kill operation; disconnect-cause is accounting Stop metadata

This checkpoint does not modify any frozen authentication, MultiLogin, attribute, persistence, accounting core, or provider identity behavior.

CI must be independently observed before this batch is described as CI-green.


## Adapter wiring checkpoint — 2026-10-08

Provider adapter objects now expose the already-audited disconnect strategy without executing external I/O. Covered: ChilliSpot, Cisco VPDN, MikroTik, PortMaster, PortSlave, Total Control, Quintum Tenor and Cisco.

Cisco intentionally remains unresolved at request-building level because its source-traced strategy has two alternatives. No parameter names or values are synthesized; callers must provide source-derived parameters.

The accidental literal-escape import corruption in the RAS adapter module was corrected and the current main file was re-read successfully. Frozen behavior was not changed.

## ChilliSpot request-envelope implementation — 2026-10-09

Added a provider-specific, transport-neutral request builder for the directly
source-traced ChilliSpot disconnect path. It requires the configured
disconnect_ip, disconnect_port, and subscriber User-Name, validates the endpoint
port, and emits the RADIUS-disconnect operation envelope. It does not claim to
encode or send the RADIUS Disconnect-Request; wire construction and network
I/O remain open until connected to the existing source-backed RADIUS transport.
Regression tests cover the exact envelope and invalid inputs.

## Outbound control-request encoding — 2026-10-09

The RADIUS codec now has a separate encode_control_request() path for
outbound Disconnect-Request and CoA-Request packets. It computes the RFC 5176
request authenticator independently from the existing response-authenticator
path and recalculates Message-Authenticator when the attribute is present.
Regression tests verify the generated request with the existing control-request
verifier and reject non-control packet codes. This is protocol plumbing only;
provider-specific network dispatch and exact A1.24 per-provider fields remain
separate work.

The ChilliSpot path now also exposes a datagram builder that returns the
configured destination and an authenticated Disconnect-Request wire packet.
It includes only the source-audited User-Name selector and does not open a
socket or perform network I/O. The caller remains responsible for transport,
timeouts/retries and interpreting Disconnect-ACK/NAK; those details are not
claimed complete by this increment.


## Authenticated control-response and UDP transport boundary — 2026-10-09

Added response-authenticator and optional Message-Authenticator verification
for Disconnect/CoA responses, plus a UDP client that sends outbound control
requests and accepts only authenticated replies from the configured endpoint.
The client supports bounded retries/timeouts and is tested through a fake socket;
no live provider is contacted by tests. ChilliSpot packet construction remains
limited to the source-audited User-Name selector. The code does not claim
production deployment validation against a real ChilliSpot RAS.


## ChilliSpot operation wiring — 2026-10-09

Added ChilliSpotDisconnectClient to connect the source-derived packet factory
to the authenticated UDP control client. It sends to the configured
disconnect endpoint, identifies the target with User-Name, and returns the
authenticated Disconnect-ACK/NAK to the caller. Tests use a fake UDP socket;
a live ChilliSpot integration test is still outstanding.


## Control transport regression hardening — 2026-10-09

Expanded fake-socket coverage for the shared Disconnect/CoA UDP client:
CoA-ACK/NAK and Disconnect-NAK response handling, wrong-peer rejection,
retry-after-timeout behavior, and invalid timeout/retry bounds. These tests
validate the common protocol transport independently of any provider-specific
operation. No frozen authentication, MultiLogin, accounting, or persistence
behavior was changed.


## IPv4 destination and retry-bound hardening — 2026-10-09

The shared RADIUS control UDP client now validates that its configured destination is a literal IPv4 address before creating a socket, validates the UDP port as a non-boolean integer in range, and rejects non-finite/non-positive timeouts or non-integer retry counts. This matches the implementation's explicit AF_INET transport and prevents hostname resolution from creating a peer-comparison mismatch.

The ChilliSpot disconnect envelope applies the same IPv4-only contract and stores the canonical IPv4 representation. Regression tests cover hostnames, IPv6, malformed IPv4, invalid ports, NaN/infinite/boolean timeouts, and non-integer retry counts. No live network calls are used by these tests.


## Full control-request attribute validation — 2026-10-09

The RFC 5176 control-request verifier now validates the entire attribute stream when checking Message-Authenticator, rather than stopping at the first such attribute. This rejects duplicate Message-Authenticator attributes and malformed attributes trailing the authenticator, even when the packet's request authenticator and first Message-Authenticator are otherwise valid. Regression fixtures construct correctly signed malformed packets so the tests exercise parser validation rather than merely failing an authentication check.


## Strict packet-length checks — 2026-10-09

RADIUS Accounting-Request, Disconnect/CoA request, and Disconnect/CoA response authentication checks now require the datagram length to exactly match the RADIUS Length field. Trailing bytes beyond the declared packet are rejected rather than silently ignored. Regression tests cover validly signed packets with an appended byte, and control-request tests also cover duplicate Message-Authenticator attributes and malformed attributes after Message-Authenticator.


## Immutable provider-operation envelopes — 2026-10-09

Provider operation requests now snapshot their parameter mapping and expose it as read-only data. This prevents a caller from changing source-derived port/interface/user values after the request envelope has been constructed but before a transport consumes it. Empty provider/action identifiers are rejected. This is a transport-boundary integrity measure only; it does not supply or infer provider-specific operation parameters.


## Complete control-request attribute validation — 2026-10-09

The RFC 5176 control-request verifier now uses the shared complete attribute-stream parser when checking Message-Authenticator. It no longer stops scanning immediately after finding the first Message-Authenticator, so malformed trailing attributes and duplicate Message-Authenticator attributes are rejected. It also requires the declared RADIUS packet length to match the received datagram exactly.

Regression coverage includes malformed trailing attribute length, duplicate Message-Authenticator, and trailing bytes beyond the declared packet length. These are malformed-packet checks only; no provider command/OID assumptions or frozen authentication/accounting behavior changed.


## RFC 5176 packet-length and padding semantics — 2026-10-09

Control-request and control-response verification now follows RFC 5176 section 2.3: the declared packet length must be at least 20, no greater than 4096, and no greater than the received datagram length. Bytes after the declared packet length are padding and are ignored; a datagram shorter than the declared packet is rejected. The earlier strict equality check was corrected because RFC 5176 explicitly permits padding.

Regression tests cover valid trailing padding, truncation, and packets above the 4096-byte maximum for both requests and responses. Reference: https://www.rfc-editor.org/rfc/rfc5176.html


## Provider envelope immutability — 2026-10-09

ProviderOperationRequest now recursively snapshots and freezes common nested containers (mappings, lists, tuples and sets), not only the top-level parameter mapping. This prevents a caller from mutating nested provider parameters after the request has crossed the side-effect boundary. ChilliSpot username inputs are explicitly type-checked and rejected unless they are non-empty strings.


## Outbound control encoder bounds — 2026-10-09

Outbound Disconnect/CoA encoding now validates the Identifier as a non-boolean integer in the one-octet range and rejects encoded control packets larger than the RFC 5176 4096-byte maximum. These checks are scoped to the control-request encoder; generic authentication/accounting encoding paths remain unchanged.


## Operation-envelope schema validation — 2026-10-09

ProviderOperationRequest now validates its runtime boundary as well as its annotations: operation must be an ExternalOperation, and parameters must be a mapping before snapshotting/freezing. This prevents arbitrary operation strings or malformed parameter containers from crossing the external-side-effect boundary. Regression tests cover invalid operation values, invalid parameter container types, and nested mutation isolation. This is envelope validation only; it does not execute provider I/O or infer any A1.24 command/OID/launcher behavior.


## External request builder input-boundary batch — 2026-10-09

The generic disconnect builders now reject non-mapping parameter containers before any conversion. This closes a subtle permissiveness gap where false-y malformed values such as an empty list could be silently converted to an empty parameter dictionary, and where iterable key/value pairs could be accepted accidentally. An explicitly empty mapping remains valid. The provider-specific builder validates source_parameters with the same rule.

Regression coverage also enumerates the currently source-traced external disconnect strategies: ChilliSpot RADIUS control, Cisco VPDN RSH, MikroTik RSH, PortMaster SNMP, PortSlave launcher, Total Control SNMP, and Quintum Tenor H323. Cisco's two-path SNMP-or-RSH strategy intentionally remains unresolved rather than selecting a path. Providers without an audited disconnect strategy (Asterisk, BSAE, GnuGk, MVTS, Persistent LAN, PPPD, SER) must not receive a guessed external operation through the generic adapter.

No real provider I/O is performed by these tests. Exact provider commands, OIDs, launcher arguments, and telephony operation sequences remain gated on direct canonical-source evidence.

## PortMaster / Total Control concrete SNMP request envelopes — 2026-10-09

The canonical A1.24 archive was re-extracted and its recorded SHA-256 verified before tracing the exact killUser() paths.

- PortMaster now builds the source-defined SNMP SET request using ifIndex = int(NAS-Port) + 2, IF-MIB ifAdminStatus OID .1.3.6.1.2.1.2.2.1.7.<ifIndex>, ASN type i, value 2, SNMP v1, UDP/161, and the A1.24 defaults (community public, timeout 10, retries 3).
- Total Control now builds the exact ordered SET sequence on the source-derived interface_index: value 2 (down), followed by value 1 (up), on the same IF-MIB ifAdminStatus OID. Defaults are community public, timeout 10, retries 3, UDP/161 and SNMP version 1.
- Provider adapter methods expose these source-derived envelopes. Input identity and endpoint/settings are validated; nested operation parameters are immutable snapshots.
- These are request-construction boundaries only. They do not execute SNMP or claim live-device interoperability. Exact source evidence and tests are recorded in docs/A1.24-RAS-PROVIDER-AUDIT.md.

No frozen authentication, CHAP/MS-CHAPv2, MPPE, MultiLogin, attribute inheritance, persistence or accounting-core behavior was changed.

## Canonical-source correction — PPPD and Quintum Tenor — 2026-10-09

A further direct inspection of the verified A1.24 archive corrected the earlier provider list:

- PPPD overrides killUser() and invokes its configured launcher command with arguments ordered as RAS-IP then port. Its source default is the IBS_ADDONS-relative pppd/kill command. ATD now exposes a launcher request builder for that exact argument contract.
- Quintum Tenor does not override killUser(); it inherits the base no-op. Quintum-h323-disconnect-cause is accounting Stop metadata, not a kill operation. The earlier h323-cause-to-H323 strategy mapping was incorrect and has been removed.
- The active single-family disconnect request builders now cover ChilliSpot RADIUS Disconnect, Cisco VPDN RSH (strategy envelope only), MikroTik RSH (strategy envelope only), PortMaster SNMP, PortSlave launcher, Total Control SNMP, and PPPD launcher. Cisco remains intentionally ambiguous at the generic strategy layer. Quintum Tenor remains a VoIP identity/accounting adapter, not a generic kill adapter.

The PPPD builder does not execute the configured launcher; live external execution and provider integration tests remain open. The source audit documents the correction and supersedes earlier Tenor/PPPD strategy statements.



## Cisco VPDN / MikroTik source-derived request builders — 2026-10-09

The canonical archive digest measured from the checked-in bytes is `c7117a6a2fd252aa9b8149a1ee6606f9320888da347ee4f839614bb9349d18a8`; the previously recorded checksum in the handoff was mistyped, not the archive.

- Cisco VPDN now has a `show caller user <username>` lookup request builder, a pure parser implementing the source regex and optional username + remote-IP match, and a separate `clear interface <resolved-interface>` request builder. The lookup → parse → disconnect orchestration and live RSH execution remain unimplemented.
- MikroTik request builder now emits the source-derived wrapper argument order and the correct hotspot-vs-PPP command branch. Username input is constrained to a conservative CLI-token allowlist to avoid unsafe unquoted interpolation; RouterOS escaping is not guessed.
- Tests cover both command variants, exact wrapper argument order, invalid endpoints/interfaces, missing wrapper settings, and unsafe username tokens.
- Both builders create immutable request envelopes only. They do not execute RSH wrappers or contact live RAS hardware.


## Cisco VPDN discovery/parser increment — 2026-10-09

- The lookup request emits the source-defined `show caller user <username>` command through the configured wrapper and source-default concurrency limit.
- The parser follows the source regex and selection rule: first interface when no remote IP is supplied; exact username + remote-IP match when it is supplied; no match returns `None` for the caller to handle.
- Regression tests cover lookup command construction, first-match selection, remote-IP disambiguation, no-match and invalid/unsafe input.
- No real RSH transport or live-device integration is claimed.


## Cisco configured SNMP/RSH branch — 2026-10-09

Cisco's strategy is now source-resolved at request-construction level: default SNMP branch maps the port description through IF-MIB ifDescr and SETs Cisco OID `.1.3.6.1.4.1.9.2.1.76.0` to the resolved ifIndex (SNMP v2c/public/10s/3 retries/UDP161). When `cisco_kill_use_snmp=0`, Async ports use `clear line <suffix>`, Serial ports use `clear interface <port>`, and unsupported port names yield no request. The five-hour SNMP port-map refresh and real transport execution are not implemented here. The generic strategy remains `snmp-or-rsh` because branch selection depends on the configured source attribute.


## Bounded SNMP SET transport — 2026-10-09

ATD now includes `atd_radius.infrastructure.snmp_transport.SnmpV1V2cSetTransport`, a standard-library UDP transport for the exact integer SET envelopes emitted by the audited Cisco, PortMaster and Total Control builders. It encodes SNMPv1/v2c BER messages, validates peer endpoint, request ID, version/community, response PDU, requested OID and ASN type, agent error status and exception values, applies finite per-attempt timeouts and bounded retries, and preserves the ordered Total Control down/up SET sequence. For a failed later SET, `SnmpTransportError.completed_responses` exposes successful earlier steps so partial side effects are not hidden.

The transport also implements a bounded SNMP GETNEXT walk for the audited Cisco IF-MIB ifDescr subtree, stops safely at subtree/end-of-table boundaries, rejects non-advancing/repeated OIDs and enforces a maximum varbind count. `CiscoSnmpDisconnectService` now orchestrates the ifDescr walk → port-description/ifIndex resolution → source-derived Cisco SNMP SET. Transport tests use injected fake sockets; no live router was contacted. RSH wrapper and launcher execution remain unimplemented. The Total Control down/up sequence is inherently two operations and can partially succeed if the second SET fails; callers must handle that explicitly.


## PPPD / PortSlave launcher execution — 2026-10-09

ATD now includes `ConfiguredLauncherTransport` for the two source-audited launcher providers only: `pppd` and `portslave`. It accepts only explicit `LAUNCHER` disconnect envelopes, requires an absolute configured executable path, tokenizes configured command options with `shlex`, appends the source-derived argument sequence without a shell, uses `stdin=DEVNULL`, `close_fds=True`, a bounded timeout, and returns the actual exit status plus truncated output. Timeouts and OS launch failures are explicit errors; a non-zero return code is not reported as success. Other provider families, RSH operations and non-disconnect actions are rejected.

Tests monkeypatch subprocess execution and cover argv order, `shell=False`, timeout, non-zero exit, output truncation and unsafe/unsupported requests. No real launcher or RAS was invoked in CI. The transport is available for explicit integration but is not yet wired into the accounting/disconnect runtime.

## Explicit transport dispatcher — 2026-10-09

Added `src/atd_radius/infrastructure/ras_external_dispatcher.py` as the first shared dispatch boundary for already-built, source-derived requests:

- SNMP `walk` requests go to the bounded GETNEXT text-mapping operation; SNMP `disconnect` requests go to the existing SET transport.
- PPPD and PortSlave launcher envelopes go only to the existing shell-free, allowlisted launcher transport.
- ChilliSpot's RADIUS Disconnect request goes to the authenticated control UDP client. The shared secret and identifier are explicit call arguments and are not stored in the immutable operation envelope.
- RSH, Asterisk Manager, H323, and SIP requests fail closed with `UnsupportedExternalOperation`; the dispatcher never turns their command fields into shell commands.

Regression tests use fake transports and cover dispatch routing, ChilliSpot secret separation, invalid identifiers, and fail-closed RSH behavior. This establishes a reusable execution boundary; it does **not** yet wire the dispatcher to an admin/API endpoint or accounting lifecycle, and no live RAS device is contacted. The next integration step must provide source-derived request parameters from the RAS configuration and session context, then define authorization/audit semantics before exposing disconnect actions to users.

Dispatcher hardening follow-up: SNMP dispatch now validates provider/action and source-audited OID families before opening the transport. Cisco is limited to the audited ifDescr walk and Cisco disconnect OID; PortMaster/Total Control are limited to IF-MIB ifAdminStatus SETs. A regression test verifies an unrelated Cisco OID is rejected before transport execution. This is defense-in-depth around the internal boundary, not a replacement for authorization at a future API layer.

## Source-audited RSH wrapper transport — 2026-10-09

Canonical archive excerpts were re-read from the successful A1.24 source-audit workflow for `core/lib/rsh.py`, `core/script_launcher/launcher.py`, Cisco VPDN and MikroTik. The source RSH client passes the configured wrapper plus `[host, *args]` through the script launcher; Cisco VPDN uses `show caller user <username>` and `clear interface <interface>`; MikroTik passes `[ssh_username, ssh_password, RouterOS command]` and chooses the hotspot or PPP removal command from NAS-Port-Type.

ATD now adds `src/atd_radius/infrastructure/rsh_transport.py` and routes RSH requests through it in the shared dispatcher. It uses an absolute configured wrapper, `subprocess.run(..., shell=False)`, a 20-second default timeout, bounded output and concurrency, literal IPv4 targets, and provider-specific command grammars that reject unexpected shell metacharacters before process creation. It does not reconstruct the legacy shell-assembled script-wrapper command; it preserves the audited argv boundary with direct bounded execution.

Tests use a mocked subprocess only. No real RSH/SSH wrapper or RAS device has been contacted. The transport is not yet invoked by an authenticated API/admin action or automatic accounting kill lifecycle. Authorization, audit-event persistence, wrapper deployment/permissions, source-specific operational error mapping and live device interoperability remain release blockers. The earlier statement that RSH had no executable transport is superseded for the three allowlisted providers (Cisco, Cisco VPDN, MikroTik); other RSH providers remain unsupported.

