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

The dashboard talks to **seven** upstream services; the proxy mirrors them.
The dev URLs for the four core services are already set on this bench:

| Setting | Dev value | Notes |
|---|---|---|
| `v1_base_url` | `https://dev.marzitech.in/v1` | unified gateway |
| `v3_base_url` | `https://dev.marzitech.in/v3` | tiered ticketing |
| `publishing_base_url` | `https://dev.marzitech.in` | paths add `/v1/publishing/...` |
| `tracking_base_url` | `https://track.marzitech.in` | GANGADHAR live activity |
| `blog_base_url` | *(unset)* | confirm the dev blog host, then set |
| `whatsapp_base_url` | *(unset)* | only a **prod** Lambda is known — set a dev host before use |
| `payments_base_url` | *(unset)* | same as whatsapp; unset avoids hitting prod |

To change them:

```bash
bench --site marzi.localhost console
```
```python
s = frappe.get_single("Marzi Bridge Settings")
s.v1_base_url = "https://dev.marzitech.in/v1"
s.v3_base_url = "https://dev.marzitech.in/v3"
s.publishing_base_url = "https://dev.marzitech.in"
s.tracking_base_url = "https://track.marzitech.in"
# s.blog_base_url = "https://dev-blog.marzitech.in"   # confirm dev host
s.default_tenant_name = "Marzi"
s.save(); frappe.db.commit()
```

Unset services return a clean "base URL is not configured" error (not a crash),
so leaving whatsapp/payments blank in dev is safe.

## 2. Give an admin the base role

Assign the **Marzi Admin** role (created on install) to the Frappe users who
should reach the proxy. `System Manager` also passes.

## 3. Link a phone (OTP)  ← the one step only you can do

Linking is headless in Phase 1 (the UI is Phase 3). It needs a real OTP SMS, so
**you** must run it with your own ADMIN/SUPER_ADMIN phone. From the CLI (runs as
Administrator, who has System Manager and so passes the role gate — this links
the Administrator user):

```bash
# 1. request an OTP (arrives on your phone)
bench --site marzi.localhost execute marzi_bridge.auth.otp.send_otp \
  --kwargs "{'phone': '+9198XXXXXXXX'}"

# 2. link with the code you received
bench --site marzi.localhost execute marzi_bridge.auth.otp.verify_otp \
  --kwargs "{'phone': '+9198XXXXXXXX', 'otp': '123456'}"
# -> {"status": "linked", "role": "SUPER_ADMIN"}

# 3. confirm (never returns tokens)
bench --site marzi.localhost execute marzi_bridge.auth.otp.link_status
```

`verify_otp` refuses to link a phone whose backend role is not ADMIN/SUPER_ADMIN,
and tokens are stored encrypted in your `Marzi User Link` — never returned to the
caller.

## 4. Run the parity smoke test

Once linked, one command calls every read-only proxy endpoint and reports
PASS/FAIL/SKIP — this is the "does it behave like the dashboard" check:

```bash
bench --site marzi.localhost execute marzi_bridge.verify.smoke_test
```

- **PASS** — the proxy reached the dev backend and got data (same route the
  dashboard calls).
- **SKIP `not linked`** — do step 3 first.
- **SKIP `base URL not set`** — configure that service in step 1 (expected for
  blog/whatsapp/payments until you set their dev hosts).
- **FAIL** — shows the upstream HTTP status + message (tokens are never logged).

To compare against the dashboard directly, run the dashboard in dev
(`cd admin-v2 && npm run dev` pointed at the same `dev.marzitech.in`) and diff a
given screen's network response against the matching proxy endpoint.

## Verification checklist

| # | Check | How |
|---|-------|-----|
| 1 | App installs & DocTypes migrate | `bench --site marzi.localhost migrate` is clean; `Marzi Bridge Settings` and `Marzi User Link` exist |
| 2 | Linking works + role gate | `verify_otp` with an admin phone creates a `Marzi User Link` with encrypted tokens; a MEMBER phone is rejected |
| 3 | Pilot call round-trips | `frappe.call("marzi_bridge.api.speakers.list_speakers")` returns live data; token attached server-side |
| 4 | Refresh path | Set `access_expires_at` to the past on your link row, call any proxy method → one silent `/auth/refresh`, call succeeds; a bad refresh raises a clear re-link error |
| 5 | RBAC seam | A user without `Marzi Admin` (or with no link) gets a clean permission error |
| 6 | Fan-out smoke test | `bench --site marzi.localhost execute marzi_bridge.verify.smoke_test` — every read endpoint reports PASS (see §4) |
| 7 | Unit tests | `bench --site marzi.localhost run-tests --app marzi_bridge` |

## Endpoint map

Every method is `@frappe.whitelist()` + `@require_marzi()`, reachable at
`/api/method/marzi_bridge.api.<module>.<function>`.

Each module mirrors the matching dashboard RTK Query slice
(`admin-v2/src/store/api/<x>Api.ts`) endpoint-for-endpoint — **148 whitelisted
proxy endpoints** total, full parity with the dashboard's API surface.

| Module | Service | Dashboard slice |
|--------|---------|-----------------|
| `api/users` | v1 | usersApi |
| `api/events` | v1 | eventsApi (core events) |
| `api/event_library` | v1 + publishing | eventsApi (library) + publishing FAQs |
| `api/bookings` | v1 | bookingsApi |
| `api/groups` | v1 | groupsApi |
| `api/speakers` | v1 | speakersApi |
| `api/testimonies` | v1 | testimoniesApi |
| `api/media` | v1 (+ blog presign) | mediaApi |
| `api/statuses` | v1 | statusesApi |
| `api/moderation` | v1 | moderationApi |
| `api/escalations` | v1 | escalationsApi |
| `api/ticketing` | v3 | ticketingApi (tiered) |
| `api/campaigns` | publishing | campaignApi |
| `api/pages` | publishing | publishingApi (pages) |
| `api/templates` | publishing | publishingApi (templates) |
| `api/blog` | blog | blogApi |
| `api/tracking` | tracking | trackingApi |
| `api/payments` | payments *(unauth)* | paymentsApi |
| `api/whatsapp` | whatsapp *(unauth)* | whatsappApi |

`payments` and `whatsapp` are called **without** a bearer token, matching the
dashboard (which uses a plain `fetchBaseQuery` for those two Lambdas).
