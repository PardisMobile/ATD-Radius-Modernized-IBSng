# IBSng A1.24 Source of Truth

## Canonical source

The canonical IBSng A1.24 implementation source for this project is:

- Source of Truth/IBSng-A1.24.tar.bz2
- Archive SHA-256: c7117a6a2fd252aa9b8149a1ee6606f9320888da347ee4f839614bb9349d18a8

## Mandatory rule

ATD is IBSng A1.24 modernized. Existing and future IBSng-related documentation, implementation decisions, schema mappings, compatibility claims, UI mappings, and parity tests must be grounded in this archive unless a document explicitly identifies a newer verified source.

Do not infer missing IBSng behavior from table names, memory, screenshots, or a simplified model when the A1.24 source can answer the question.

## Verification rule

- Source-mapped means the behavior was located in the A1.24 source.
- Implemented means ATD code exists.
- Verified means automated or reproducible parity evidence exists against A1.24.

These states must not be conflated.

## Related documents

See the IBSng source inventory, schema parity, migration matrix, attribute consumer map, UI inventory, and database compatibility documents under docs/. All should treat this archive as their source authority.

## Binary preservation

The archive itself must not be replaced by generated or reconstructed source. Any replacement requires a new SHA-256 and an explicit source-version decision.
