# Marzi Bridge — Setup & Verification

Phase 1 of the admin-dashboard → Frappe migration: integrate the existing
Backend-for-org `/v1` & `/v3` APIs into Frappe via a server-side proxy.

The app code is complete and self-contained. Because this machine has **no bench**
yet (and the framework fork wants Python 3.14 / Node 24 while this box has 3.13 /
22), the bench bootstrap below is meant to be run by you — a couple of steps are
interactive (DB root + Administrator passwords).

> Tip: run interactive commands from the Claude prompt with a leading `!` so their
> output lands here, e.g. `! bench new-site marzi.localhost`.

## 0. Environment bootstrap

```bash
# install the bench CLI if needed
pipx install frappe-bench            # or: pip install --user frappe-bench

# build a bench off the local framework fork
bench init frappe-bench --frappe-path /Users/prabhaskalyan/frappe --python python3
cd frappe-bench

# create the dev site (prompts for MariaDB root + a new Administrator password)
bench new-site marzi.localhost

# add this app to the bench and install it onto the site
bench get-app marzi_bridge /Users/prabhaskalyan/frappe/marzi_bridge
bench --site marzi.localhost install-app marzi_bridge

bench start
```

If `bench init` rejects Python 3.13, point `--python` at a 3.14 interpreter
(e.g. `pyenv install 3.14 && pyenv local 3.14`) — the app itself only needs 3.10+,
but the framework fork's `pyproject.toml` pins 3.14.

## 1. Configure the backend connection

Open **Marzi Bridge Settings** (or via console) and set the base URLs:

```bash
bench --site marzi.localhost console
```
```python
s = frappe.get_single("Marzi Bridge Settings")
s.v1_base_url = "https://api.marzi.life/v1"       # REPLACE_ME with your env
s.v3_base_url = "https://api.marzi.life/v1/v3"    # REPLACE_ME
s.default_tenant_name = "Marzi"
s.save(); frappe.db.commit()
```

## 2. Give an admin the base role

Assign the **Marzi Admin** role (created on install) to the Frappe users who
should reach the proxy. `System Manager` also passes.

## 3. Link a phone (OTP)

Linking is headless in Phase 1 (the UI is Phase 3). As the target Frappe user:

```python
from marzi_bridge.auth import otp
otp.send_otp("+919876543210")          # REPLACE_ME with a real ADMIN/SUPER_ADMIN phone
otp.verify_otp("+919876543210", "1234")  # -> {"status": "linked", "role": "SUPER_ADMIN"}
otp.link_status()                        # -> {"linked": True, ...}  (never returns tokens)
```

`verify_otp` refuses to link a phone whose backend role is not ADMIN/SUPER_ADMIN.

## Verification checklist

| # | Check | How |
|---|-------|-----|
| 1 | App installs & DocTypes migrate | `bench --site marzi.localhost migrate` is clean; `Marzi Bridge Settings` and `Marzi User Link` exist |
| 2 | Linking works + role gate | `verify_otp` with an admin phone creates a `Marzi User Link` with encrypted tokens; a MEMBER phone is rejected |
| 3 | Pilot call round-trips | `frappe.call("marzi_bridge.api.speakers.list_speakers")` returns live data; token attached server-side |
| 4 | Refresh path | Set `access_expires_at` to the past on your link row, call any proxy method → one silent `/auth/refresh`, call succeeds; a bad refresh raises a clear re-link error |
| 5 | RBAC seam | A user without `Marzi Admin` (or with no link) gets a clean permission error |
| 6 | Fan-out smoke test | One read per module returns 2xx (e.g. `users.list_users`, `events.list_events`, `groups.list_groups`, `bookings.list_bookings`, `blog.list_posts`, `pages.list_pages`) |
| 7 | Unit tests | `bench --site marzi.localhost run-tests --app marzi_bridge` |

## Endpoint map

Every method is `@frappe.whitelist()` + `@require_marzi()`, reachable at
`/api/method/marzi_bridge.api.<module>.<function>`.

| Module | Feature |
|--------|---------|
| `api/speakers` | Speakers (pilot) |
| `api/users` | Users |
| `api/events` | Events (+ v3 tiered admin) |
| `api/bookings` | Bookings |
| `api/payments` | Payments (search by phone) |
| `api/groups` | Groups / Communities |
| `api/testimonies` | Testimonies |
| `api/campaigns` | Campaigns |
| `api/blog` | Blog |
| `api/pages` | Pages |
| `api/event_library` | Event Library (FAQ library; info-chips TODO) |
| `api/templates` | Templates (page templates; dedicated CRUD TODO) |
| `api/media` | Media (presigned upload URLs) |

`event_library` and `templates` have `# TODO` markers where API_DOC.md did not
document a crisp backend route — those are left to confirm against the live
backend rather than guessed.
