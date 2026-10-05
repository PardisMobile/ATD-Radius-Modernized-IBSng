# ATD Design System

## Design principle

ATD is a modernization of IBSng A1.24. The design system must make an experienced IBSng operator immediately productive while removing the visual and interaction constraints of the legacy interface.

Do not reproduce the old red/grey skin, fixed-width desktop layout, oversized empty canvas, or legacy tab/page mechanics. Preserve the information hierarchy and operational concepts, not the obsolete styling.

## Tokens

The theme is token-based so Light/Dark/System, RTL/LTR and future brand adjustments do not require page rewrites.

Core token groups:

- background / surface / elevated surface
- text / muted text / inverse text
- border / focus ring
- accent / accent hover
- success / warning / danger / info
- radius: compact, standard, large
- spacing scale
- typography scale
- table density
- sidebar / topbar dimensions
- chart grid and data visualization tokens

## Layout

Desktop uses a persistent navigation rail/sidebar with a compact topbar and a flexible content workspace. The content area should prioritize operational tables and forms over decorative empty space.

Mobile uses a deliberate navigation mode with an accessible menu/drawer and touch-friendly controls. It is not a shrunken desktop canvas.

## Navigation model

The modern navigation groups IBSng capabilities by operator task:

- Dashboard
- Users
- Groups
- Services
- RAS / NAS
- IP Pools
- Sessions
- Accounting
- Billing
- Reports
- Administration
- Settings

Contextual shortcuts can expose frequent IBSng actions such as Search User, Add User, Online Users, Group List, RAS and IPPool.

## Components

Shell, sidebar, topbar, breadcrumbs, tabs, cards, data table, filters, search, pagination, form field, select, toggle, badge, status dot, alert, toast, modal, drawer, confirmation, empty state, loading state, command/search palette, activity timeline, metric card, utilization indicator, audit/event row, and chart.

## Data-dense surfaces

Users, sessions, accounting records, RAS/NAS, IP pools and audit logs are operational surfaces. Tables should support density controls, sticky headers where useful, column visibility where appropriate, fast filtering, pagination, sorting and row actions.

## Status language

Use semantic status indicators consistently:

- healthy / online / active
- warning / degraded / nearing limit
- offline / disabled / blocked
- unknown / pending

Never rely on color alone; pair status color with text or an icon.

## Charts

Graphs exist to explain operational behavior such as online sessions, bandwidth, connection usage, IP pool utilization and accounting trends. Avoid decorative chart walls.

## Accessibility

Keyboard navigation, visible focus, semantic controls, sufficient contrast, reduced motion support, screen-reader labels, logical RTL navigation order, and touch targets appropriate for mobile are required.

## Localization

Persian and English are first-class. Layout direction, numbers, dates, tables, navigation order, truncation and forms must all work in both RTL and LTR. Text must not be hard-coded into components.
