# IBSng A1.24 Reference Map

This document records the reference behavior being modernized. It is based on IBSng source/runtime evidence available to the project and must be expanded as each subsystem is parity-tested.

## Runtime

The legacy runtime launches `/usr/local/IBSng/ibs.py`, uses Python 2-era libraries, PostgreSQL, Apache/PHP/Smarty for the web UI, and an XML-RPC service on the local IBSng server port. The observed runtime also uses RADIUS authentication/accounting on UDP 1812/1813.

## Core boundaries

The reference source layout includes `core/server`, `radius_server`, `interface/IBSng`, `interface/smarty/templates`, and `addons`. XML-RPC requests are dispatched by the core server and legacy clients use `xmlrpclib.ServerProxy`.

## User workflow

The legacy admin UI has dedicated add/search/edit/delete/kill/credit/user-info flows and Smarty templates. User attributes include a `normal_username` / Internet Username concept and generated passwords.

The new UI must preserve these workflows while replacing the presentation layer with the ATD design system.

## Compatibility rule

Behavior is the reference; obsolete implementation techniques are not. Each migrated behavior must receive an automated test before being declared complete.

## Source-review status

The project maintains a growing subsystem inventory from the A1.24 source and runtime evidence. The next required extraction pass is the complete database schema, permission catalog, RADIUS attribute dictionary, XML-RPC method inventory, and page-to-route map.