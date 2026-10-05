# Architecture

```text
                    ATD Radius
                        |
          +-------------+-------------+
          |                           |
      Python 3 Core              PHP 8+ Web UI
          |                           |
          +-------------+-------------+
                        |
                   Application Layer
                        |
                    PostgreSQL
                        |
          +-------------+-------------+
          |             |             |
        RADIUS         REST        XML-RPC
          |
         EAP
```

## Layers

1. Domain: IBSng A1.24 concepts including User, Group, RAS, IPPool, attributes, online/session state, Connection Logs, Connection Usages, Charge, permissions and audit.
2. Application layer: explicit use cases mapped to IBSng A1.24 workflows; adapters never contain business rules.
3. Protocol/API adapters: RADIUS, REST and XML-RPC; EAP is a later protocol-boundary extension after source-first protocol analysis.
4. Presentation: modern PHP implementation of the IBSng A1.24 web interface, with responsive presentation and accessibility improvements.

IBSng A1.24 is the reference for behavior. Its obsolete implementation details are not automatically preserved.