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

This shared-token gate is only the API perimeter; it is not administrator identity. Native admin login is available at `POST /api/v1/admin/login`, and issues a revocable opaque token sent as `X-Admin-Session` to the admin session endpoint. The RAS CRUD routes additionally enforce the source-traced native RAS permissions and audit mutations transactionally. Users/groups CRUD still require only the shared perimeter token and remain pending per-admin authorization. Do not mount destructive RAS disconnect operations until its own permission checks, trusted target-session resolution, and side-effect/audit sequencing are integrated. Do not place the token in source
control or expose it to browser-side code.
