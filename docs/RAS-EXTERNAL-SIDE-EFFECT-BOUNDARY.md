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
