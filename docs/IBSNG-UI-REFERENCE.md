# IBSng A1.24 UI Reference

## Purpose

This document records the information architecture visible in the supplied IBSng A1.24 home-screen screenshot. It is a reference for modernization, not a visual reproduction target.

## Observed legacy shell

The screenshot shows a fixed desktop-oriented shell with:

- IBS branding and Free Edition / Version A1.24 marker
- top-level navigation: HOME, USER, GROUP, REPORT, GRAPH, ADMIN, SETTING
- current user/session controls at the top right
- breadcrumb/current-section area
- a large central home workspace
- right-side Related Links, ShortCuts & Links, and Page Help panels
- footer links

## Observed home modules

### User

- User Information
- Search User
- Add New User
- Add Users Saver

### Setting

- Charge
- RAS
- IPPool
- Bandwidth Management
- VoIP Tariff
- Clean Reports

### Group

- Group List
- Add New Group

### Admin

- Admin List
- Add New Admin
- Messages

### Report

- Online Users
- Connection Logs
- Connection Usages
- Credit Changes
- Deposit Changes
- User Audit Logs
- Log Console
- Web Analyzer Logs
- Realtime Web Analyzer

### Graph

- All Onlines Realtime Graph
- Internet Onlines Realtime Graph
- VoIP Onlines Realtime Graph
- Internet BW Realtime Graph
- Onlines Graph
- Connections Analysis

## Modernization interpretation

The home page should not preserve the old visual arrangement or its large empty areas. Instead, these same operational capabilities should become:

- persistent primary navigation
- contextual quick actions
- operational dashboard cards
- searchable command palette
- task-oriented reports
- object-centric workspaces
- collapsible secondary panels
- responsive mobile navigation

The right-side shortcuts/help behavior is particularly useful conceptually and should become contextual actions/help rather than a fixed legacy sidebar.

## Preservation rule

The source code remains the authority for the complete feature set. Screenshots are used to validate information architecture, terminology, discoverability and operator workflow. If a source-code workflow is not visible in this screenshot, it must still be preserved when the corresponding IBSng subsystem is implemented.

## Future screenshots

Additional screenshots can be attached for individual areas such as User, Group, RAS, IPPool, Reports, Graphs and Administration. They should refine this document and the corresponding page specifications without changing the modernization principle unless explicitly decided.
