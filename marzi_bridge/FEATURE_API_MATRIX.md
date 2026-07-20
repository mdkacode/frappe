# Marzi Admin — Feature / API / DB Matrix

Which admin-dashboard sidebar features are backed by a real API and a database, and
which are **not**. Verified against the `Backend-for-org` source (`API_DOC.md` + the
`src/lambdas/*` handlers and `src/db/*Migrations.ts`) and the `admin-v2` dashboard
API-client calls. The last two columns show what the **Frappe `marzi_bridge`** app has
wired so far (proxy module under `marzi_bridge/api/`, Virtual DocType under
`marzi_bridge/marzi_bridge/doctype/`).

> **Key nuance:** three features are served by services that live **outside** the
> `Backend-for-org` repo, so they don't show up in its handlers/migrations even though
> the dashboard calls real endpoints:
> - **Live Activity** → tracking service (`track.marzitech.in`, "GANGADHAR"): Socket.IO `/ops` + REST polling.
> - **WhatsApp** → standalone AWS Lambda (`…execute-api.ap-south-1.amazonaws.com/prod`).
> - **Payments** → the same standalone Lambda (Razorpay records). *(Not a sidebar item in this screenshot, but proxied.)*

Legend: ✅ yes · ⚠️ partial / external / caveat · ❌ no

---

## Summary table

| Section | Feature | API exists? | Persists to DB? | Frappe proxy | Frappe DocType |
|---|---|:--:|:--:|:--:|:--:|
| Operations | **Live Activity** | ⚠️ external tracking svc | ⚠️ real-time / ephemeral | ✅ `tracking.py` | ❌ |
| Operations | **Device Health** | ✅ `Backend-for-org` | ✅ `user_devices` | ❌ | ❌ |
| User Management | **Users** | ✅ | ✅ `users` | ✅ `users.py` | ✅ `marzi_user` |
| Event Management | **Events** | ✅ | ✅ `events` (+tiers) | ✅ `events.py` | ✅ `marzi_event` |
| Event Management | **Event Library** | ✅ | ✅ `event_library_*`, `event_gallery` | ✅ `event_library.py` | ❌ (nested) |
| Event Management | **Bookings** | ✅ | ✅ `bookings` / `v2_orders` | ✅ `bookings.py` | ✅ `marzi_booking` |
| Communities | **Groups** | ✅ | ✅ `groups`, `memberships` | ✅ `groups.py` | ✅ `marzi_group` |
| Communities | **WhatsApp** | ⚠️ external Lambda | ⚠️ external (not in repo) | ✅ `whatsapp.py` | ❌ |
| Communities | **Notifications** | ❌ no admin API | ✅ internal-only tables | ❌ | ❌ |
| Communities | **Escalations** | ✅ | ✅ `escalations` | ✅ `escalations.py` | ❌ |
| Communities | **Moderation** | ✅ (UI-gated "coming soon") | ✅ `blocked_content`, `moderation_rules` | ✅ `moderation.py` | ❌ |
| App Configuration | **Statuses** | ✅ | ✅ `statuses` | ✅ `statuses.py` | ❌ |
| App Configuration | **Testimonies** | ✅ | ✅ `testimonies` | ✅ `testimonies.py` | ✅ `marzi_testimony` |
| App Configuration | **Speakers** | ✅ | ✅ `speakers` | ✅ `speakers.py` | ✅ `marzi_speaker` |
| Content | **Blog** | ✅ (separate blog svc) | ✅ `blog_posts`, `blog_*` | ✅ `blog.py` | ✅ `marzi_blog_post` |
| Content | **Pages** | ✅ (publishing) | ✅ `publishing_pages` | ✅ `pages.py` | ✅ `marzi_page` |
| Content | **Campaigns** | ✅ (publishing) | ✅ `campaign_*` | ✅ `campaigns.py` | ❌ |
| Content | **Templates** | ✅ (publishing) | ✅ `publishing_templates` | ✅ `templates.py` | ❌ |
| Asset Management | **Media** | ✅ | ✅ `media_assets` (S3) | ✅ `media.py` | ✅ `marzi_media` |

---

## The features WITHOUT a usable admin API

These are the ones to flag — everything else has a real API + DB.

### ❌ Notifications — no admin-facing API
The notification engine is **internal / scheduler-driven** (EventBridge 1-min loop:
`communityNotificationAggregator.ts`, `communityNotificationDispatcher.ts`). It persists
to internal tables (`community_notification_aggregate` / `_dispatch` / `_dedupe`) and
pushes via device tokens (`user_devices.push_token`), but there are **no REST routes** to
list/create/manage notifications. To surface Notifications in the admin, new backend
endpoints would have to be built first — there is nothing to proxy today.

### ⚠️ Live Activity — API exists but lives on a separate service, data is ephemeral
Not in `Backend-for-org`. Served by the tracking service (`track.marzitech.in`) over
Socket.IO (`/ops` namespace) with a REST polling fallback (`/v1/events`, `/v1/presence`,
`/v1/users/{id}/events`). Presence is **real-time / ephemeral**, not a durable admin
table. The Frappe proxy (`tracking.py`) exists but this maps poorly to a List/Form
DocType — treat it as a live dashboard widget, not a table.

### ⚠️ WhatsApp — API exists but on an external Lambda
Not in `Backend-for-org` (the repo's "moderation" covers group posts/comments, not
WhatsApp). Conversations/messages come from a standalone AWS Lambda
(`GET /dashboard/conversations`, `GET /dashboard/messages`, `POST /dashboard/messages/send`).
Proxy `whatsapp.py` exists; persistence is owned by that external service.

### 🟡 Device Health — API + DB exist, but not yet wired into Frappe
`Backend-for-org` **does** expose it: `POST /users/me/devices`,
`DELETE /users/me/devices/{id}`, and admin `GET /admin/devices/stats`, persisting to
`user_devices` (+ `device_tier`). But there is **no proxy module** in `marzi_bridge`
and no DocType yet — this is the one feature with a ready backend that the bridge hasn't
picked up.

---

## Reading the "Frappe" columns

- **Proxy = ✅ / DocType = ✅** → fully surfaced today as a Frappe List/Form (live data).
- **Proxy = ✅ / DocType = ❌** → the API is reachable through the bridge (callable via
  `frappe.call` / `@frappe.whitelist`), but not yet mapped to a browsable List/Form.
  Deferred either because the shape is nested/config-heavy (Event Library, Campaigns,
  Templates) or action-oriented rather than a table (Moderation, Escalations, Statuses,
  WhatsApp).
- **Proxy = ❌** → nothing in the bridge yet (Device Health has a backend to add;
  Notifications has no backend to add).

## Suggested next steps (by effort)

1. **Device Health** — backend is ready; add a `devices.py` proxy + optionally a
   read-only `Marzi Device` DocType off `GET /admin/devices/stats`. Lowest-hanging fruit.
2. **Statuses / Escalations / Moderation / Campaigns / Templates** — proxies already
   exist; add read-only DocTypes where a flat List/Form fits (Statuses and Campaigns are
   the most table-like).
3. **Live Activity / WhatsApp** — keep as bespoke pages/widgets, not DocTypes.
4. **Notifications** — blocked on backend: needs new admin endpoints before any Frappe work.
