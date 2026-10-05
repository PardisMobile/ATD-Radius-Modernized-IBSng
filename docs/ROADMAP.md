# ATD Radius Modernized IBSng — Roadmap

## Phase 1 — Behavioral foundation
- [x] Typed attribute engine
- [x] Attribute precedence and provenance
- [x] IPv4 IP-pool allocation primitives
- [x] Accounting usage primitives
- [x] Charge/billing primitives
- [ ] Complete A1.24 consumer mapping

## Phase 2 — Database compatibility
- [ ] Inventory every A1.24 table, column, index and constraint
- [ ] Inventory official A1.24 backup/restore behavior
- [ ] Define native/mapped/transformed schema strategy
- [ ] Build lossless importer
- [ ] Build parity report
- [ ] Restore representative real-world IBSng backups

## Phase 3 — RADIUS / AAA
- [ ] PAP/CHAP and existing authentication semantics
- [ ] Access-Accept/Reject policy generation
- [ ] Accounting Start/Interim/Stop
- [ ] RAS lifecycle
- [ ] IP pool assignment integration
- [ ] Session enforcement

## Phase 4 — Billing and policy
- [ ] Normal/VoIP charging parity
- [ ] Credit and expiry semantics
- [ ] Bandwidth accounting
- [ ] Attribute/plugin parity

## Phase 5 — EAP
- [ ] EAP architecture
- [ ] EAP method support selected from requirements
- [ ] RADIUS/EAP integration tests

## Phase 6 — Modern UI
- [ ] Admin parity inventory
- [ ] User portal parity inventory
- [ ] Modern responsive theme
- [ ] Preserve IBSng workflow efficiency
- [ ] Attribute editor
- [ ] Session/accounting/billing views

## Phase 7 — Compatibility release
- [ ] Full A1.24 → ATD compatibility matrix
- [ ] Automated migration/parity suite
- [ ] CI green on supported Python versions
- [ ] Install/upgrade/rollback validation
- [ ] Production deployment documentation

**Definition of done:** ATD is not considered an IBSng modernization until the compatibility matrix and lossless database migration path demonstrate that required A1.24 behavior and data are preserved.
