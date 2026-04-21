# Domain Pack: B2B SaaS / RBAC

Read this when testing workspace, organization, membership, permission, role, invitation, audit log, or admin settings features.

## Common Role Dimensions

- owner
- admin
- editor
- viewer
- billing admin
- suspended user
- invited user
- external guest

## Role Matrix

Always model permissions as:

```text
actor_role x action x resource_state x ownership_context
```

Ownership context examples:

- own resource
- other user's resource
- same workspace
- cross workspace
- last owner
- delegated admin

## Common Risk Hotspots

- unauthorized privilege escalation
- last owner removal or downgrade
- stale permission after role change
- invitation state treated as active membership
- audit log missing actor, target, before, or after values
- billing or security settings exposed to non-admin users
- cross-tenant data access

## Suggested Observations

- Owner/admin/viewer/editor differences for each sensitive action.
- Last-owner boundary.
- Invited, suspended, and removed users.
- Immediate permission refresh after role change.
- Audit evidence as gray support, not the only acceptance oracle.
