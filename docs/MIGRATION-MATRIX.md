# IBSng A1.24 → ATD Migration Matrix

This is the master parity checklist. Implemented means ATD code exists; Verified requires behavior/data parity tests against A1.24. No row may be marked Verified by inspection alone.

| IBSng subsystem | A1.24 source area | ATD target | Status |
|---|---|---|---|
| Admin/auth | admins, admin_perms | A1.24 ADMIN implementation | Schema native / runtime pending |
| RAS | ras, ras_ports, ras_attrs | A1.24 RAS implementation | Schema native / runtime lifecycle pending |
| RAS schema | ras, ras_attrs, ras_ports, ras_ippools | RAS repository + runtime registry | Native / runtime registry implemented; mutation reload integration pending |
| IP pools | ippool, ippool_ips, ras_ippools | IP allocation service | Native ippool/ippool_ips repository + runtime state implemented / RAS binding and live session lifecycle integration pending |
| Users | users, normal_users, voip_users | A1.24 USER implementation | Schema native / USER API refactor in progress |
| Groups | groups, group_attrs | A1.24 GROUP implementation | Schema native / runtime pending |
| Attribute system | user_attrs, group_attrs, ras_attrs | typed compatibility attribute engine | Implemented boundary / parity pending |
| Caller ID | caller_id_users | authentication policy | Inventory |
| Persistent LAN | persistent_lan_users | session/address policy | Inventory |
| Sessions | connection_log, online user lifecycle | A1.24 online/session lifecycle | Runtime implemented / persistence and source parity pending |
| Accounting | connection_log, ias_event, ias_event_extended | A1.24 accounting implementation | Runtime implemented / live connection-log persistence pending |
| Bandwidth | bw_* | A1.24 Bandwidth Management implementation | Inventory |
| Charges | charges | A1.24 Charge implementation | Implemented boundary / persistence and parity pending |
| Internet billing | charge_rules, internet_charge_rules | A1.24 Internet Charge Rule implementation | Implemented boundary / source parity and persistence pending |
| VoIP billing | voip_charge_rules, tariffs, prefixes | A1.24 VoIP Charge Rule / VoIP Tariff implementation | Implemented boundary / source parity and persistence pending |
| Audit | user_audit_log, web_analyzer_log | A1.24 audit/log implementation | Inventory |
| RADIUS | AAA/auth/accounting paths | A1.24 RADIUS boundary and runtime | Runtime implemented / full UDP, persistence and protocol parity pending |
| EAP | protocol boundary | ATD protocol extension after A1.24 protocol audit | Planned |
| Admin UI | legacy web/admin | modern responsive IBSng A1.24 UI | In progress |
| User UI | legacy user interface | modern responsive IBSng user UI | Partial |
| Installer | A1.24 legacy install | modern deployment | Planned |
| Backup/restore | PostgreSQL dump/restore semantics | compatibility importer/exporter | Planned |

## Completion rule
The project is complete only when every required subsystem reaches Verified and the database parity suite demonstrates that a representative A1.24 backup can be imported without loss of required behavior or data.
