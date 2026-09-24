# Admin runbook (internal)

Restricted to the support_lead role. Do not share this article's contents with
support_agent or billing_admin accounts - point them at
[Roles and permissions](roles-and-permissions.md) instead.

## Force-deactivating a compromised account

If a user's account is compromised, a support_lead can flip their `is_active` flag
directly, bypassing the normal deactivation review a support_agent would otherwise
need to request. Only do this when immediate action is required.

## Escalation

For anything beyond a routine account deactivation, page the on-call platform lead
before making any direct account changes.
