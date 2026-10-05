# IBSng A1.24 User Parity

The A1.24 source does not treat a user as a single username/password row. The normal-user path stores normal credentials in `normal_users`, while the source code explicitly supports multiple Internet usernames and uniqueness checks. The VoIP path has its own credential attributes and plugins.

Source evidence in the indexed A1.24 source shows:

- `normal_users.normal_username` is unique and is not the primary key.
- normal-user creation/update is implemented through `functions.sql` and the `normal_user.py` plugin.
- the normal-user plugin parses multiple usernames and checks all requested usernames for collisions.
- the UI exposes Internet Username/Password as a dedicated editing surface.
- group attributes can participate in effective user behavior, so user attributes cannot be treated independently of group inheritance.

ATD therefore models credential sets separately from the generic User identity and preserves a multi-username representation. The Python implementation is a domain compatibility layer; persistence must still map to the actual A1.24 source columns before the migration is marked verified.

## Parity requirements

- normal users and VoIP users remain distinct user kinds;
- multiple Internet usernames are preserved;
- username uniqueness is enforced before persistence;
- password generation settings remain explicit attributes;
- file-backed username modes remain representable;
- generic/custom user attributes remain lossless;
- group attributes remain available during effective-policy resolution;
- imported IDs and references are not regenerated without a deterministic mapping.

## Status

Domain semantics: implemented.

Database mapping: pending exact A1.24 column-by-column import implementation.

Behavioral verification against a real A1.24 dataset: pending.
