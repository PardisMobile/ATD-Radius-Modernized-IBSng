# EAP

EAP is a first-class requirement of ATD Radius.

## Design

EAP is handled at the RADIUS protocol boundary and then delegated to an authentication service. No EAP method is allowed to contain database or UI logic.

Initial implementation:

- strict EAP packet encode/decode
- identifier preservation
- length validation
- RADIUS/EAP Message-Authenticator primitive
- test vectors before enabling methods in production

Supported EAP methods will be added only after the exact RADIUS attribute and state-machine behavior is tested.
