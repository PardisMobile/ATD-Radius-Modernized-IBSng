# Project Scope

## Goal
Modernize IBSng A1.24 without losing its proven AAA behavior and operational model.

## In scope
- Python 3 core and domain services
- PostgreSQL schema and migrations
- RADIUS authentication/accounting
- EAP support
- Users, groups, services, RAS/NAS, IP pools, attributes, sessions, charging, credit, permissions and reports
- PHP 8+ modern web panel
- ATD design system with RTL/LTR and light/dark modes
- REST API
- XML-RPC compatibility layer
- IBSng data migration/import tooling
- modern Linux installer and systemd deployment
- licensing architecture

## Out of scope for the initial core
Telegram, WooCommerce, mobile applications, Kubernetes, microservices, and unrelated product integrations.

## Non-negotiable
The public repository must not contain secrets or production data. The old Go repository is a separate historical project and is not imported here.