# IBSng A1.24 UI Page Inventory

## Purpose

This document records the file-level UI inventory extracted from the IBSng A1.24 reference archive. It is a design and parity reference for the ATD modernization. It is **not** a copy of the IBSng UI and the reference archive is not included in this repository.

## Scan result

Reference: `IBSng-A1.24.tar.bz2`

The interface contains:

- 123 PHP files under `interface/IBSng/admin/`
- 18 PHP files under `interface/IBSng/user/`
- 283 Smarty templates under `interface/smarty/templates/`
- 119 plugin templates under `smarty/templates/plugins/`
- Shared shells/templates for admin, user, help, reports, errors and stripped/refresh views
- Report generators and controllers that are implementation files rather than standalone screens

The page inventory below separates operator-facing pages from report generators, image endpoints and helper/controller files.

## Admin application areas

### Home / shell

- `admin/index.php`
- `admin/admin_index.php`
- shared `admin_header.tpl`, `admin_footer.tpl`, `admin_right_sidebar.tpl`, `admin_related_links.tpl`

The legacy home screen is a launch/workspace page. Its information architecture is preserved, but the ATD version should replace the large empty grid with a useful operational dashboard and contextual shortcuts.

### Users — 17 PHP files

- `admin/user/add_new_users.php`
- `admin/user/add_user_save_details.php`
- `admin/user/change_credit.php`
- `admin/user/change_credit_funcs.php`
- `admin/user/check_user_for_add.php`
- `admin/user/del_user.php`
- `admin/user/del_user_funcs.php`
- `admin/user/kill_user.php`
- `admin/user/search_add_user_saves.php`
- `admin/user/search_user.php`
- `admin/user/search_user/search_user_report_creator.php`
- `admin/user/search_user/search_user_report_generator_controller.php`
- `admin/user/search_user/search_user_web_report_generator.php`
- `admin/user/search_user_edit.php`
- `admin/user/search_user_funcs.php`
- `admin/user/user_info.php`
- `admin/user/user_info_funcs.php`

Associated templates include user search, fast search, attribute search, user lists, add-user flow, single-user information, edit/select-attribute views, credit change, delete, kill-session and redirect/header fragments.

**ATD workspace target:** Users becomes one operational workspace with search/filter, create, bulk operations, status, identity, credentials, groups/services, attributes/policy, credit, sessions, accounting and audit. Legacy multi-page transitions become tabs/drawers/inline actions where safe.

### Groups — 3 PHP files

- `admin/group/group_list.php`
- `admin/group/add_new_group.php`
- `admin/group/group_info.php`

Group plugin templates cover policy/limits, IP pool, Radius attributes, charges, expiration, accounting limits, login limits and related group behavior.

**ATD workspace target:** group overview + policy + members + services + attributes + accounting/limits + audit.

### RAS / NAS — 6 PHP files

- `admin/ras/ras_list.php`
- `admin/ras/ras_info.php`
- `admin/ras/add_new_ras.php`
- `admin/ras/add_port.php`
- `admin/ras/edit_port.php`
- `admin/ras/del_port.php`

**ATD workspace target:** NAS registry, type/vendor/provider metadata, ports, secrets, attributes, health/status and linked IP pools/services.

### IP Pools — 3 PHP files

- `admin/ippool/ippool_list.php`
- `admin/ippool/ippool_info.php`
- `admin/ippool/add_new_ippool.php`

**ATD workspace target:** pool overview, CIDR/range, allocation state, addresses, utilization, assignments and operational actions.

### Bandwidth management — 11 PHP files

- `admin/bw/interface_list.php`
- `admin/bw/interface_info.php`
- `admin/bw/interface_info_face.php`
- `admin/bw/add_interface.php`
- `admin/bw/add_node.php`
- `admin/bw/add_leaf.php`
- `admin/bw/add_leaf_service.php`
- `admin/bw/leaf_charges.php`
- `admin/bw/active_leaves.php`
- `admin/bw/add_static_ip.php`
- `admin/bw/static_ip_list.php`

**ATD workspace target:** model bandwidth topology/policy explicitly rather than reproducing the legacy node/leaf page chain. Preserve the capability and relationships.

### Charges / billing — 12 PHP files

- `admin/charge/charge_list.php`
- `admin/charge/charge_info.php`
- `admin/charge/add_new_charge.php`
- `admin/charge/add_internet_charge_rule.php`
- `admin/charge/edit_internet_charge_rule.php`
- `admin/charge/add_voip_charge_rule.php`
- `admin/charge/edit_voip_charge_rule.php`
- `admin/charge/charge_rule_funcs.php`
- `admin/charge/voip_tariff/tariff_list.php`
- `admin/charge/voip_tariff/tariff_info.php`
- `admin/charge/voip_tariff/add_edit_tariff.php`
- `admin/charge/voip_tariff/add_edit_prefix.php`

**ATD workspace target:** charges, rules, tariffs, prefixes, applicability, pricing, credit impact and audit. Internet and VoIP remain separate capability domains but share billing primitives.

### Reports — 36 PHP files

Report areas include:

- Online users
- Connections
- Connection logs
- Connection usages
- Credit changes
- User audit logs
- Admin deposit changes
- Top visited / web analyzer
- Realtime log console
- Realtime web analyzer
- Report cleanup
- Report index and controllers/generators

The report directory contains both UI entry points and report creator/controller/generator implementations. These must not be mistaken for 36 independent screens.

**ATD workspace target:** report catalog + reusable filter builder + result table + export + saved views + realtime views where applicable.

### Graphs / realtime analytics — 17 PHP files

Includes:

- Graph index
- Online graphs
- Bandwidth graphs
- Realtime graphs
- Connection analysis
- Duration analysis
- Successful counts
- User/group/RAS usage analysis
- VoIP disconnect-cause analysis
- Graph image/rendering helpers

**ATD workspace target:** operational analytics cards and charts embedded in the relevant workspace, plus a dedicated Analytics/Reports area for deeper analysis. Avoid decorative charts.

### Administrators / permissions — 9 PHP files

- `admin/admins/admin_list.php`
- `admin/admins/admin_info.php`
- `admin/admins/add_new_admin.php`
- `admin/admins/admin_perms_list.php`
- `admin/admins/change_password.php`
- `admin/admins/change_deposit.php`
- `admin/admins/show_perms.php`
- `admin/admins/show_perm_categories.php`
- `admin/admins/show_permtemplate_perms.php`

The source also contains templates for admin locking and permission templates.

**ATD workspace target:** administrators, roles/permission templates, explicit permissions, security events and audit.

### Messages — 2 PHP files

- `admin/message/view_messages.php`
- `admin/message/post_message_to_user.php`

**ATD target:** notification/message center with contextual user communication and audit trail.

### Settings — 1 PHP entry point

- `admin/setting/index.php`

The setting area is a shell for configuration capabilities and should become a structured Settings workspace rather than one long legacy page.

### Plugins / misc — 4 PHP files

- `admin/plugins/edit.php`
- `admin/plugins/edit_funcs.php`
- `admin/misc/core_statistics.php`
- `admin/misc/show_ibs_defs.php`

These expose runtime/plugin/core diagnostic capabilities and should be separated into Administration / Diagnostics / Extensions in ATD.

## End-user portal — 18 PHP files

### User portal

- `user/index.php`
- `user/home.php`
- `user/change_pass.php`
- `user/connection_log.php`
- `user/credit_log.php`
- `user/bw_graph.php`
- `user/bw_graph_img.php`
- `user/post_message_to_admin.php`
- `user/view_messages.php`

### User report helpers

- `user/connection_logs/user_connection_logs_report_creator.php`
- `user/connection_logs/user_connection_logs_report_generator_controller.php`
- `user/connection_logs/user_connection_logs_web_report_generator.php`

### Dialer / VoIP portal

- `user/dialer/dialer_auth.php`
- `user/dialer/dialer_changepass.php`
- `user/dialer/dialer_extra.php`
- `user/dialer/dialer_message.php`
- `user/dialer/dialer_userinfo.php`
- `user/dialer/dialer_userreport.php`

**ATD target:** a modern subscriber portal with account overview, credentials, services, credit, sessions, usage/accounting, messages, password/security and optional VoIP/dialer capabilities.

## Template architecture

The Smarty template inventory shows that IBSng has a genuine component/plugin architecture rather than only static PHP pages.

### Shared shells

- `header.tpl`, `footer.tpl`
- `admin_header.tpl`, `admin_footer.tpl`
- `user_header.tpl`, `user_footer.tpl`
- `admin_right_sidebar.tpl`
- `admin_related_links.tpl`
- `admin_right_sidebar_hidden.tpl`
- `refresh_header.tpl`
- `stripped_header.tpl`, `stripped_footer.tpl`
- `report_foot.tpl`
- help and error shells

### Admin templates

Approximately 110 templates are under `smarty/templates/admin/`, covering the page families above.

### User templates

26 templates are under `smarty/templates/user/`, including separate English and Persian portal templates.

### Plugin templates

119 templates are under `smarty/templates/plugins/`. The most important plugin families are:

- `plugins/user/edit/*`
- `plugins/user/view/*`
- `plugins/group/edit/*`
- `plugins/group/view/*`
- `plugins/search/*`

The plugin structure is especially important for ATD: these are evidence that user/group policy is extensible and should not be flattened into one hard-coded user table.

## Design decisions derived from the scan

1. **Do not reproduce the old page count.** Many PHP files are controllers, report generators or image endpoints. ATD should expose cohesive workspaces instead.
2. **Preserve workflow semantics.** User search/edit, group policy, RAS configuration, IP pool management, accounting, credit, reports and admin permissions are real operational workflows.
3. **Preserve extensibility.** The plugin template architecture means user/group/search attributes and policy modules must remain extensible in the modern design.
4. **Preserve bilingual behavior.** The reference contains Persian and English user templates; ATD must make both first-class.
5. **Preserve contextual navigation.** The old related-links and shortcuts concept should become contextual actions, command/search navigation and workspace-local links.
6. **Reports are a platform capability.** Report generators/controllers should become reusable query/report infrastructure, not one-off pages.
7. **Graphs are operational.** Realtime online/bandwidth/connection views belong in the operational experience and must remain useful on mobile.
8. **Admin security is first-class.** Permissions, permission templates, admin state, password and audit capabilities require a dedicated security/administration model.

## Screenshot reference

The supplied IBSng home screenshot confirms the legacy information architecture: top-level Home/User/Group/Report/Graph/Admin/Setting navigation, a shortcut/related-links rail, and grouped launch panels. ATD will preserve the discoverability and operational grouping while replacing the legacy visual language with the ATD design system.

## Next UI implementation order

1. Application shell and navigation
2. Dashboard / home workspace
3. Users: search/list → user workspace → create/edit → attributes → sessions/accounting/audit
4. Groups: list → group workspace → policy/attributes/members
5. RAS/NAS
6. IP pools
7. Services and charges
8. Sessions/accounting
9. Reports and realtime analytics
10. Administration/permissions
11. Subscriber portal
12. Optional VoIP/dialer modules

This ordering follows operational dependency rather than the legacy menu order.
