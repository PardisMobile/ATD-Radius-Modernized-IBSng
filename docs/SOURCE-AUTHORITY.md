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
- MS-CHAPv1 authentication is implemented by `Packet.checkMSChapPassword()` and is part of the normal password plugin path.
- MS-CHAPv2 authentication is implemented by `Packet.checkMSChap2Password()`.
- MS-CHAPv1 consumes an 8-byte `MS-CHAP-Challenge` and compares the 24-byte NT-Response at `MS-CHAP-Response[0][26:]`.
- MS-CHAPv2 uses `MS-CHAP2-Response[0][2:18]` as Peer-Challenge and `[0][26:]` as NT-Response.
- A1.24's MS-CHAPv2 implementation does not validate the Flags or Reserved fields before comparing the NT-Response, and its challenge hash implementation uses the username string supplied by the caller without stripping a domain prefix.
- `generateMSChap2AuthenticatorResponse()` emits Ident + `S=...` for `MS-CHAP2-Success`.
- `MSChapEndPlugin` adds MS-CHAP/MPPE response attributes at login-hook priority 9.
- A1.24 MS-CHAPv1 MPPE emits `MS-CHAP-MPPE-Keys` containing the first 8 bytes of the LM hash, the 16-byte hash-of-NT-hash, and 8 zero bytes; it protects that VSA with the same RADIUS password obfuscation algorithm used by `PwCrypt()`.
- A1.24 MS-CHAPv1 also emits `MS-MPPE-Encryption-Policy` = 0x00000001 and `MS-MPPE-Encryption-Types` = 0x00000006.
- A1.24 MS-CHAPv2 MPPE derives server send/receive keys in `core/lib/mschap/mppe.py`, then encrypts the MPPE key attributes using the Access-Request authenticator and per-key salts.
- A1.24 generates MPPE salts randomly with the high bit set and ensures the Send and Receive salts differ; the salts are not deterministic counters.
- `multi_login` defaults to 1 when the user has no explicit attribute.
- User instance count is incremented before `USER_LOGIN` hooks; the MultiLogin plugin rejects when `instances > multi_login`.
- RAS-specific `multi_login` behavior is supplied by individual RAS implementations; it is not a single universal RAS attribute.
- The RADIUS duplicate request key is exactly `(source_ip, source_port, packet_id, packet_code)`.
- A1.24's RADIUS dictionary contains `Message-Authenticator` (attribute 80), but the inspected request-processing path does not implement Message-Authenticator verification. Any ATD implementation of that verification must therefore be described as modern/RFC hardening unless later source inspection finds another path that performs it.


## MultiLogin source trace (A1.24)

The A1.24 `core/user/plugins/multilogin.py` path is directly traced end-to-end:

- `MultiLogin.__setMultiLogin()` initializes `self.multi_login = 1`.
- It changes that default only when the user attribute `multi_login` exists; then it performs `int(user_attrs["multi_login"])`.
- Therefore **attribute absent = default limit 1**.
- **attribute explicitly present as `0` = limit 0**, not default 1.
- `MultiLoginAttrUpdater.changeInit()` accepts integer values from 0 through 255, so zero is a valid stored attribute value.
- During `USER_LOGIN`, `User.login()` increments `user_obj.instances` before calling the plugin hooks.
- MultiLogin rejects when `user_obj.instances > self.multi_login`.
- Consequently an explicit `multi_login=0` rejects even the first login, while an absent attribute permits one instance.
- RAS capability is a separate `ras_msg["multi_login"]` boolean. The plugin keeps one capability value per login instance and rejects when a disallowing RAS is involved and `instances > 1`.

This distinction is important: **defaulting an absent attribute to 1 is not the same as treating an explicit zero as 1.**

## Direct source trace — Attribute / Group / DB linkage

The canonical A1.24 source and SQL were also traced for the MultiLogin attribute path:

- db/tables.sql defines groups, group_attrs, users, normal_users, voip_users, and user_attrs as separate structures. group_attrs and user_attrs both use (scope_id, attr_name) as their primary key and store attr_value as text.
- UserLoader.__createUserAttrs() constructs UserAttributes(user_attrs_dic, basic_user.getGroupID()).
- UserAttributes.getAttr() first checks the explicit user attribute; when absent it delegates to the user's group object.
- UserAttributes.hasAttr() is likewise true when the attribute exists at either user or group scope.
- Therefore a group-level multi_login is an effective user setting unless explicitly overridden by a user-level multi_login.
- MultiLogin.__setMultiLogin() consumes this effective UserAttributes view, so its default-1 behavior applies only when neither user nor group provides the attribute.
- AttributeManager is the source registration/update/parse/search layer; MultiLoginAttrHandler registers multi_login for change/delete/search, and the updater persists it as an attribute rather than as a dedicated users-table column.
- User.login() increments instances before invoking USER_LOGIN, so session admission must evaluate the incoming instance as existing + 1.

This trace confirms that the current ATD architecture should preserve user-over-group precedence and group inheritance before applying the MultiLogin limit. A change that only reads a user-local dictionary would be a regression.
