# ATD UI Specification

## Product character

ATD is a network/AAA control plane, not a generic SaaS dashboard. The interface should feel operational, dense where useful, calm, fast, and unmistakably ATD.

## Navigation

Dashboard
Users
Groups
Services
RAS / NAS
IP Pools
Sessions
Accounting
Billing
Reports
Administration

## UX rules

- Preserve familiar IBSng workflows and terminology where they are operationally useful.
- Replace legacy multi-page form chains with contextual workspaces, tabs, drawers and inline actions.
- Search and filtering are first-class on operational tables.
- Destructive actions require clear confirmation and audit visibility.
- Every important object has Overview, Attributes/Policy, Activity and Audit where applicable.
- Persian and English are first-class; RTL/LTR must not be a CSS afterthought.
- Light, dark and system modes share one token system.
- Mobile navigation is a deliberate responsive mode, not a collapsed desktop sidebar.

## User workspace

A user page must expose identity, Internet Username, authentication state, group/service assignment, attributes, credit, active sessions, accounting history and audit history without forcing the operator through the legacy page chain.

## Visual system

Use restrained surfaces, strong typography, compact data tables, semantic status indicators and consistent spacing. Avoid template-marketplace aesthetics, excessive gradients, decorative charts, and arbitrary component styling.
