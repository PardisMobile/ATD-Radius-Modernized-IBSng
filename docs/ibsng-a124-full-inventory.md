# IBSng A1.24 — Full Source Inventory

This inventory is generated from the uploaded `IBSng-A1.24.tar.bz2` reference archive.

## Archive facts

- 2,477 archive members
- 2,295 regular files
- 1,028 files under `core/`
- 1,049 files under `interface/`
- 131 files under `addons/`
- 41 files under `radius_server/`
- 22 files under `docs/`
- 19 files under `db/`
- 453 Python source files
- 530 PHP files
- 284 Smarty templates
- 20 SQL files

The archive also contains Python 2 bytecode (`.pyc`/`.pyo`) and legacy web assets. These are reference artifacts and must not be copied into the modern runtime.

## Major runtime areas

```text
IBSng/
├── core/
│   ├── admin
│   ├── bandwidth_limit
│   ├── charge
│   ├── db
│   ├── event
│   ├── group
│   ├── ias
│   ├── ippool
│   ├── login
│   ├── message
│   ├── plugins
│   ├── ras
│   ├── report
│   ├── snapshot
│   ├── stats
│   ├── threadpool
│   ├── user
│   ├── util
│   └── web_analyzer
├── radius_server/
├── interface/IBSng/
├── interface/smarty/templates/
├── addons/
├── db/
├── scripts/
├── init.d/
└── docs/
```

## User subsystem

The legacy user subsystem is plugin-driven. Important plugins include:

- normal_user
- password
- group
- normal_charge
- credit
- abs_exp / rel_exp / nearest_exp
- multilogin
- ippool / assign_ip
- radius_attrs
- session_timeout / idle_timeout
- periodic_accounting
- save_bw_usage
- terminate_cause
- caller_id / limit_callerid / limit_mac / limit_station_ip
- mschap_end
- plan_user
- voip_user / voip_charge
- email_address / comment / owner / phone-related plugins

Modern ATD will retain this behavioral model but represent capabilities as explicit domain policies and typed attributes rather than Python 2 plugin objects.

## RAS implementations

The reference contains RAS implementations for Cisco, Cisco VPDN, MikroTik, PPPD, Persistent LAN, PortSlave, PortMaster, GnuGK, Asterisk, MVTS, Quintum Tenor, Total Control, BSAE, SER and ChilliSpot.

The modern system will use a provider interface. Initial production parity targets will be Generic RADIUS/NAS, MikroTik, Cisco and PPP/PPPoE; other adapters remain planned compatibility modules.

## RADIUS

The reference contains its own `pyrad`-derived implementation, dictionary files and duplicate-request handling. Authentication and accounting are handled through RAS objects. The modern implementation will preserve packet semantics while replacing the Python 2 networking stack.

Observed packet families include Access-Request/Accept/Reject/Challenge, Accounting-Request/Response and Disconnect-Request/Ack/Nack.

## XML-RPC

IBSng exposes an internal XML-RPC server and dispatches methods through a handler manager. The modern service layer will be authoritative; XML-RPC becomes a compatibility adapter rather than the application architecture.

## UI

The legacy UI consists of PHP controllers, Smarty templates, JavaScript, GIF/PNG assets and separate admin/user areas. Workflow parity is required, but the presentation layer will be rewritten using the ATD design system. No legacy Smarty templates or visual assets are copied wholesale.

## EAP finding

A source-wide search of the uploaded A1.24 archive found no EAP implementation or EAP-named source component. Therefore EAP is an ATD modernization extension, not a claimed IBSng feature. It will be implemented at the RADIUS protocol/authentication boundary and tested independently.

## Migration rule

The archive is the behavioral reference. We port behavior and data semantics, not obsolete runtime techniques. Every subsystem promoted to production must have parity tests and migration notes.
