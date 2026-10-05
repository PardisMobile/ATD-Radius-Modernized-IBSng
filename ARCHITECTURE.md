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

1. Domain: users, groups, services, RAS/NAS, IP pools, attributes, sessions, accounting, charging, permissions.
2. Application services: explicit use cases; interfaces never contain business rules.
3. Protocol/API adapters: RADIUS, EAP, REST, XML-RPC, CLI.
4. Presentation: modern PHP web panel and ATD design system.

IBSng A1.24 is the reference for behavior. Its obsolete implementation details are not automatically preserved.