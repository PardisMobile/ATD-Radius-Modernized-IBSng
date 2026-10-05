# IBSng A1.24 Reference Map

This document records the reference behavior being modernized. It is based on the IBSng source/runtime evidence available to the project and must be expanded as each subsystem is parity-tested.

## Runtime

The legacy runtime launches `/usr/local/IBSng/ibs.py`, uses Python 2-era libraries, PostgreSQL, Apache/PHP/Smarty for the web UI, and an XML-RPC service on the local IBSng server port. The runtime evidence also shows RADIUS authentication/accounting on UDP 1812/1813. fileciteturn116file0L12-L45

## Core boundaries

The source layout observed in the reference includes `core/server`, `radius_server`, `interface/IBSng`, `interface/smarty/templates`, and `addons`. XML-RPC requests are dispatched by the core server and legacy clients use `xmlrpclib.ServerProxy`. fileciteturn116file0L44-L110

## User workflow

The legacy admin UI has dedicated add/search/edit/delete/kill/credit/user-info flows and Smarty templates. User attributes include a `normal_username`/Internet Username concept and generated passwords. fileciteturn118file0L10-L42 fileciteturn118file4L359-L370

The new UI must preserve these workflows while replacing the presentation layer with the ATD design system.

## Compatibility rule

Behavior is the reference; obsolete implementation techniques are not. Each migrated behavior must receive a test before being declared complete.
