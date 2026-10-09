# API Authentication Boundary

The API now supports a configurable shared bearer token as an initial deployment
safety boundary.

## Configuration

- Set `ATD_API_BEARER_TOKEN` to a long, random secret.
- Set `ATD_ENVIRONMENT=production` (or another non-development environment).
- Send API requests with `Authorization: Bearer <token>`.
- `/health` remains available without authentication for health checks.

When a token is configured, API routes require it in every environment. When no
token is configured, development/test remain usable; other environments fail
closed with HTTP 503 rather than exposing the API unauthenticated.

## Scope and limitations

This is a shared-token gate, not full administrator identity, role-based access
control, or a durable audit trail. Do not treat it as the finished authorization
system. Before mounting destructive RAS disconnect operations or other privileged
actions, implement per-user permissions and durable audit records, and resolve the
target session from trusted server-side state. Do not place the token in source
control or expose it to browser-side code.
