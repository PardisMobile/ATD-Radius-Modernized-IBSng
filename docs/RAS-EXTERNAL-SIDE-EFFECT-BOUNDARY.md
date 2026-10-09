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

- Cisco: SNMP-or-RSH
- Cisco VPDN: RSH interface
- MikroTik: RSH port
- PortMaster: SNMP port
- PortSlave: launcher
- Total Control: SNMP interface
- ChilliSpot: RADIUS Disconnect-Request / provider port
- Quintum Tenor: H323 disconnect-cause path

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
