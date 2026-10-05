# IBSng A1.24 Reference Inventory

Source archive: `IBSng-A1.24.tar.bz2`

Verified SHA-256: `c7117a6a2fd252aa9b8149a1ee6606f9320888da347ee4f839614bb9349d18a8`

Verified archive contents: 2,477 members, 182 directories, 2,295 files.

## Major areas

| Area | Files | Role |
|---|---:|---|
| `core/` | 1,028 | AAA/business core |
| `interface/` | 1,049 | PHP/Smarty web UI and XML-RPC |
| `addons/` | 131 | NAS/RAS integrations and utilities |
| `radius_server/` | 41 | RADIUS protocol server and request handling |
| `docs/` | 22 | installation, API, RAS and operational documentation |
| `db/` | 19 | database/bootstrap SQL |

## Core subsystem inventory

- `core/user/`: user model, plugins, attributes, sessions, authentication-facing behavior.
- `core/group/`: group definitions and inherited policy.
- `core/ras/`: RAS/NAS abstractions and providers.
- `core/ippool/`: address pool and allocation behavior.
- `core/charge/`: charging rules and credit/usage behavior.
- `core/report/`: operational and accounting reports.
- `core/bandwidth_limit/`: bandwidth policy/limits.
- `core/snapshot/`: state/snapshot support.
- `core/ias/`: internal service/API boundary used by legacy interfaces.
- `core/server/`: long-running server/runtime pieces.
- `radius_server/`: packet processing, request-list/duplicate handling and RADIUS dictionaries.
- `interface/IBSng/`: PHP application controllers and presentation glue.
- `interface/smarty/`: 284 Smarty templates in the archive.
- `interface/xmlrpc/`: legacy XML-RPC interface.

## Addons/RAS inventory

Notable addon families include Asterisk, MikroTik, Cisco, Chilli/PPPoE-related clients, Squid analyzer, poptop, portsla​ve and other RAS helpers. These are compatibility targets, not code to copy wholesale.

## UI inventory

The legacy UI is PHP + Smarty. ATD will preserve the workflows and data concepts while replacing presentation, templating, navigation, accessibility and responsive behavior with the new ATD design system.

## EAP finding

No EAP implementation was found in the archive. EAP is therefore an ATD extension. The implementation must integrate with the RADIUS request lifecycle and must not be represented as an A1.24 feature.

## Modernization rule

The archive is the behavioral reference. ATD does not copy the legacy runtime, Python 2 assumptions, PHP/Smarty implementation or installer. Each subsystem is classified as **preserve behavior**, **rewrite**, **compatibility adapter**, or **retire**.
