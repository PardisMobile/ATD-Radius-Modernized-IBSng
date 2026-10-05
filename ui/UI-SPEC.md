# ATD UI Specification

## Product character

ATD is a modernized IBSng control plane, not a generic SaaS dashboard. The interface should feel operational, dense where useful, calm, fast, and unmistakably ATD.

The modernization rule is:

> Preserve IBSng's operational model and discoverability; replace its presentation, navigation mechanics, visual language, and legacy page chains.

## IBSng reference information architecture

The supplied IBSng A1.24 home screen confirms the legacy top-level operator model:

- Home
- User
- Group
- Report
- Graph
- Admin
- Setting

The home screen also exposes shortcut/work areas for:

- User Information
- Search User
- Add New User
- Add Users Saver
- Group List
- Add New Group
- Charge
- RAS
- IPPool
- Bandwidth Management
- VoIP Tariff
- Clean Reports
- Admin List
- Add New Admin
- Messages
- Online Users
- Connection Logs
- Connection Usages
- Credit Changes
- Deposit Changes
- User Audit Logs
- Log Console
- Web Analyzer Logs
- Realtime Web Analyzer
- Realtime graphs and connection analysis

ATD must retain these capabilities where they exist in the IBSng source, but reorganize them into modern object-centric workspaces.

## Navigation

Primary navigation:

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
Settings

Legacy IBSng labels remain available through contextual labels, search, documentation, and compatibility terminology where useful. We do not require operators to relearn core concepts merely because the UI is modernized.

## UX rules

- Preserve familiar IBSng workflows and terminology where they are operationally useful.
- Replace legacy multi-page form chains with contextual workspaces, tabs, drawers and inline actions.
- Search and filtering are first-class on operational tables.
- High-frequency actions are visible without requiring deep navigation.
- Destructive actions require clear confirmation and audit visibility.
- Every important object has Overview, Attributes/Policy, Activity and Audit where applicable.
- Reports and graphs remain operational tools, not decorative dashboard charts.
- Persian and English are first-class; RTL/LTR must not be a CSS afterthought.
- Light, dark and system modes share one token system.
- Mobile navigation is a deliberate responsive mode, not a collapsed desktop sidebar.

## Dashboard / Home

The modern home replaces the large empty legacy canvas with a useful operations overview while preserving the same mental map.

Recommended regions:

1. Global status and quick actions.
2. Authentication/session health.
3. Online users and active sessions.
4. RAS/NAS health.
5. IP pool utilization.
6. Recent accounting/billing activity.
7. Alerts and audit events.
8. Frequently used IBSng actions.

Charts are used only when they answer an operational question.

## User workspace

A user page must expose identity, Internet Username, authentication state, group/service assignment, attributes, credit, active sessions, accounting history and audit history without forcing the operator through the legacy page chain.

The user list must support fast search, filters, status, group/service, online state and high-frequency actions.

## Group / Service workspace

Groups and services are first-class policy objects. Their pages must show:

- membership/assignments
- effective attributes/policy
- inherited attributes
- usage/limits
- status
- audit history

## RAS / IP Pool workspace

RAS/NAS and IP pools must be operationally visible. Operators should be able to understand availability, health, assignments, address utilization and related policy without navigating through unrelated pages.

## Reports / Graphs

The legacy Report and Graph areas are preserved as functional domains. Realtime graphs, connection analysis, usage reports and audit reports should be organized by task and data source rather than reproduced as separate legacy pages.

## Administration

Administration includes administrators, permissions, messages, audit visibility, system settings and maintenance operations. Permission-sensitive actions must be explicit and auditable.

## Visual system

Use restrained surfaces, strong typography, compact data tables, semantic status indicators and consistent spacing. Avoid template-marketplace aesthetics, excessive gradients, decorative charts, and arbitrary component styling.
