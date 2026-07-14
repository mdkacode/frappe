# Marzi Bridge

A Frappe app that acts as a **server-side proxy** to the existing Backend-for-org
(marzi) `/v1` and `/v3` APIs. This is **Phase 1** of the admin-dashboard → Frappe
migration: integrate the existing backend APIs into Frappe without changing their
contracts. Frappe provides whitelisted RPC endpoints; the browser never sees the
backend JWT.

## How it works

```
Frappe Desk (admin)
  └─► @frappe.whitelist() proxy method   (marzi_bridge.api.<feature>)
        └─► MarziClient  (attaches per-user Bearer token, refresh + retry)
              └─► Backend-for-org  /v1 & /v3   ← unchanged
```

- **Auth model:** each Frappe admin links their phone once via OTP
  (`marzi_bridge.auth.otp`). Their personal marzi access + refresh JWT is stored
  encrypted in a per-user `Marzi User Link` record and used for their own calls.
- **Token handling:** `marzi_bridge.auth.tokens.get_valid_token()` refreshes
  expiring tokens transparently. `MarziClient` retries once on a `401`.
- **Access control:** every proxy method is gated by `require_marzi` (base role
  `Marzi Admin`). Granular RBAC is a later track.

## Install

```bash
# from your bench directory
bench get-app marzi_bridge /path/to/marzi_bridge
bench --site <site> install-app marzi_bridge
```

Then set the backend base URLs in **Marzi Bridge Settings**.

## License

MIT
