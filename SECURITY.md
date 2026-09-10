# Security Policy

## Reporting a vulnerability

If you find a security issue in Moneta, please report it privately:

- Email: **kerwil.morales@gmail.com** with the subject `MONETA SECURITY`.
- Do **not** open a public issue for undisclosed vulnerabilities.
- Include steps to reproduce, affected version/commit, and impact.

You will get an acknowledgement within a reasonable time. Please allow time for a
fix before any public disclosure.

## Supported versions

Security fixes target the latest released line. Older packaged copies should
update to the latest release.

## Security posture

Moneta is a self-hosted application. The operator is responsible for deployment
hardening (HTTPS, reverse proxy, backups, OS updates). The codebase provides:

- **Tenant isolation** — every query is scoped to the authenticated user; the MCP
  layer derives the user from the access token and cannot be overridden by
  request fields (`user_id`, `owner_id`, `tenant_id`).
- **Token hashing** — MCP access tokens are stored as HMAC-SHA256 with a pepper;
  the raw token is shown once and never persisted in clear text.
- **Scope model** — MCP tokens grant only `read` and/or `draft`. There is no
  `approve`, no direct transaction creation, no delete, no balance mutation, no
  payment confirmation.
- **Human approval** — externally originated entries land in the Import Queue as
  drafts and only become real transactions after a person approves them in the
  UI. Approval is atomic and rolls back fully on failure.
- **CSRF protection** on all state-changing form posts; write side effects are
  kept out of GET requests.
- **Rate limiting** on MCP tool calls (`settings.MONETA_MCP_RATE_LIMITS`).
- **Audit log** — MCP tool calls are recorded (`MCPAuditEvent`) with secret
  redaction.
- **Login throttling** — atomic account-and-network lockout after repeated
  failures.
- **Deploy checks** — `python manage.py check --deploy` and
  `python manage.py secret_scan` are part of the pre-publish checklist.

## Production checklist

Before exposing an instance:

- `DJANGO_DEBUG=0`
- Strong, private `DJANGO_SECRET_KEY` (50+ chars)
- `DJANGO_ALLOWED_HOSTS` set to the real domain/IP
- `DJANGO_CSRF_TRUSTED_ORIGINS=https://your-domain`
- HTTPS enforced (`DJANGO_SECURE_SSL_REDIRECT=1`, HSTS once HTTPS is stable)
- `/admin/` behind a strong password
- Database backups configured
- MCP HTTP endpoint bound to loopback or behind an authenticating proxy
