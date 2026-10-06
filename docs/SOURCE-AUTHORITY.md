# IBSng A1.24 Source Authority

## Non-negotiable authority rule

**The actual IBSng A1.24 source archive is the sole behavioral authority for this project.**

Canonical source:
- `Source of Truth/IBSng-A1.24.tar.bz2`
- SHA-256: `c7117a6a2fd252aa9b8149a1ee6606f9320888da347ee4f839614bb9349d18a8`

Parity documents, inventories, matrices, notes, tests, and current ATD code are **guides, records, or validation artifacts only**. They must never be used to override, substitute for, or establish IBSng behavior when the source is available.

For every source-sensitive change:
1. Inspect the actual A1.24 source implementation.
2. Trace the call path and consumers, not just a symbol or documentation mention.
3. Record the source-derived behavior.
4. Implement the modern ATD equivalent without unnecessary architectural coupling to the legacy implementation.
5. Add tests for the behavior.
6. Do not label behavior "Verified" unless the source/integration evidence supports it.

If a parity document conflicts with the source archive, **the source archive wins**.

## Direct source inspection access

The repository archive is binary, so the GitHub text API cannot decode it directly. For source inspection, the canonical archive was extracted in a temporary GitHub Actions runner and downloaded as an artifact. The extracted A1.24 tree contains 2,295 files and is the same repository archive content; it is not a substitute source.

No external IBSng mirror is authoritative.

## Initial source-derived findings

Direct inspection has confirmed:

- CHAP authentication is implemented by `Packet.checkChapPassword()`.
- MS-CHAPv1 authentication is implemented by `Packet.checkMSChapPassword()`.
- MS-CHAPv2 authentication is implemented by `Packet.checkMSChap2Password()`.
- MS-CHAPv2 uses `MS-CHAP2-Response[0][2:18]` as Peer-Challenge and `[0][26:]` as NT-Response.
- `generateMSChap2AuthenticatorResponse()` emits Ident + `S=...` for `MS-CHAP2-Success`.
- `MSChapEndPlugin` adds MS-CHAP/MPPE response attributes at login-hook priority 9.
- A1.24 MS-CHAPv2 MPPE derives server send/receive keys in `core/lib/mschap/mppe.py`, then encrypts the MPPE key attributes using the Access-Request authenticator and per-key salts.
- `multi_login` defaults to 1 when the user has no explicit attribute.
- User instance count is incremented before `USER_LOGIN` hooks; the MultiLogin plugin rejects when `instances > multi_login`.
- RAS-specific `multi_login` behavior is supplied by individual RAS implementations; it is not a single universal RAS attribute.
- The RADIUS duplicate request key is exactly `(source_ip, source_port, packet_id, packet_code)`.
- A1.24's RADIUS dictionary contains `Message-Authenticator` (attribute 80), but the inspected request-processing path does not implement Message-Authenticator verification. Any ATD implementation of that verification must therefore be described as modern/RFC hardening unless later source inspection finds another path that performs it.
