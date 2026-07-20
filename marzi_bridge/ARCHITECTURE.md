# Marzi Bridge — Architecture & Code Guide

A single, code-level walkthrough of what this app is, how it works end to end, and where
each piece lives. Read this first; the other docs go deeper on specific slices:

- `README.md` — one-paragraph "what & install".
- `SETUP.md` — bootstrap a bench/site, configure the backend, link a phone (OTP).
- `INTEGRATION.md` — Phase-1 status / gaps checklist.
- `FEATURE_API_MATRIX.md` — per-feature API / DB / proxy / DocType matrix (source of truth
  for which dashboard features have a usable backend).

---

## 1. What this app is (in one picture)

Marzi Bridge turns the **Backend-for-org (marzi)** REST APIs into a **Frappe desk UI**,
without copying any data into Frappe. The Frappe admin logs in, links their phone once,
and then browses live backend data (users, events, groups, bookings, …) as ordinary
Frappe **List / Form** screens.

```
Browser (Frappe Desk)
   │  desk UI: List / Form / Workspace
   ▼
Frappe server (this app: marzi_bridge)
   ├─ Virtual DocTypes  ── read-only List/Form backed by the API (no DB table)
   ├─ /api/method proxy ── thin whitelisted endpoints (action-style calls)
   ├─ MarziClient       ── the single outbound HTTP choke point
   ├─ Auth bridge       ── per-user OTP link → stores the user's marzi JWT
   └─ RBAC seam         ── require_marzi() gate on every call
   │  Authorization: Bearer <user's marzi JWT>   (attached server-side)
   ▼
Backend-for-org (marzi)  ── /v1, /v3, publishing, blog, tracking, whatsapp, payments
   ▼
Postgres / DynamoDB      ── the real data (single source of truth)
```

**Design principle:** the browser never sees the backend JWT. Frappe attaches it
server-side, centralises refresh/retry, and enforces its own RBAC before calling out. The
backend contracts are unchanged — Frappe is only a UI shell + secure relay.

---

## 2. Repository layout (what lives where)

Everything is under `marzi_bridge/marzi_bridge/` (the app's Python package). App root
`marzi_bridge/` holds docs and `scripts/`.

| Path | Responsibility |
|---|---|
| `client.py` | `MarziClient` — builds URLs per upstream service, attaches the Bearer token, 401-retry, error normalisation. **Every** outbound call goes through here. |
| `auth/otp.py` | Whitelisted OTP linking flow (`send_otp`, `verify_otp`, `link_status`). |
| `auth/tokens.py` | Token manager: `get_valid_token()`, refresh, `NotLinkedError`, JWT decode. |
| `permissions.py` | `require_marzi()` decorator (RBAC gate) + `check_app_permission()`. |
| `api_document.py` | `ApiDocument` — the reusable base class for all API-backed **Virtual DocTypes**. The heart of the data layer. |
| `api/*.py` | One thin proxy module per feature (`users.py`, `events.py`, …) — `@frappe.whitelist()` methods that delegate to `MarziClient`. Used for actions/lookups that aren't a plain List/Form. |
| `scripts/gen_doctypes.py` | Declarative generator that emits the Virtual DocType JSON + controllers from `SPECS`/`CHILD_SPECS`. |
| `branding.py` | Desk branding + the left-sidebar navigation (Workspace Sidebar) + home screen. |
| `public/images/`, `public/css/` | Marzi logo/favicon + `marzi_branding.css`. |
| `verify.py` | Runtime smoke tests (`smoke_test`, `check_doctypes`, `probe_details`). |
| `hooks.py` | App metadata, branding hooks, fixtures, apps-screen tile. |
| `marzi_bridge/doctype/marzi_*` | The generated Virtual DocTypes (see §5). |

---

## 3. The request path, end to end

Take "open the Users list" as the worked example:

1. **Desk** routes to the `Marzi User` list → Frappe calls the controller's
   `get_list` static method.
2. `MarziUser.get_list` → `ApiDocument._api_list` → `_fetch_collection()`.
3. `_fetch_collection` calls `MarziClient().get("/users", params={"limit": 50})`.
4. **`MarziClient`** (`client.py`):
   - resolves the base URL for the service (here `v1` → `Marzi Bridge Settings.v1_base_url`),
   - calls `tokens.get_valid_token()` → loads the caller's `Marzi User Link`, refreshes
     the JWT if near expiry, returns the access token,
   - sends `GET {base}/users?limit=50` with `Authorization: Bearer <jwt>`,
   - on `401` refreshes once and retries; normalises backend error envelopes into a
     `frappe.throw` with the upstream status.
5. The JSON envelope comes back; `ApiDocument` unwraps it, maps backend keys → Frappe
   fieldnames, and returns rows to the desk.

Actions (create/update/delete, or non-tabular lookups) skip the DocType layer and call an
`api/<feature>.py` method directly via `/api/method/marzi_bridge.api.users.<fn>` — same
`MarziClient` + `require_marzi()` underneath.

---

## 4. `ApiDocument` — the data-layer engine (`api_document.py`)

Frappe **Virtual DocTypes** (`is_virtual = 1`) have no database table; the controller
implements the persistence contract itself. `ApiDocument(Document)` implements that
contract **once**, against `MarziClient`, so each concrete entity is just a declarative
subclass.

### 4.1 What a subclass declares

```python
class MarziUser(ApiDocument):
    DOCTYPE       = "Marzi User"
    api_endpoint  = "/users"          # list route
    api_detail_endpoint = "/users"    # GET /users/<id> (when richer than the list)
    api_id_field  = "userId"          # backend key that identifies a record → docname
    api_service   = "v1"              # which upstream (v1/v3/publishing/blog/…)
    api_list_key  = "items"           # envelope key holding the array (dotted ok: "data.items")
    api_item_key  = None              # envelope key on a single-item response
    api_field_aliases = {"firstName": "first_name", ...}  # backend key → Frappe fieldname
    # …plus the pagination / child-table / merge knobs below
```

### 4.2 Key mechanisms (why the Forms are "full")

| Concern | How `ApiDocument` handles it |
|---|---|
| **List** | `_api_list` → `_fetch_collection()` → map each object with `_to_row`. Slices locally to the page the desk asked for. |
| **Open a record** | `load_from_db()` calls the detail endpoint (`api_detail_endpoint or api_endpoint` + `/<name>`), unwraps the item, maps it, and sets it on the doc. If `api_single_from_list` is set (no GET-by-id exists), it finds the record inside the collection instead. |
| **Field mapping** | `_map_obj(doctype, obj, aliases, id_field)` copies only keys that exist as fields. **Nested dict/list values destined for a `Code`/`JSON`/`Long Text` field are `json.dumps`-ed** so nested data displays instead of being dropped. |
| **Images** | Stored as a `Data` URL field + a companion `Image` field whose `options` points at it (renders an external URL). The DocType `image_field` drives the list thumbnail. |
| **Nested collections** | `api_child_tables` maps a child-table field → `{doctype, source, item_key/list_key, aliases}`. `source="item"` reads an array already on the detail object; a sub-route string like `"/groups/{id}/members"` triggers a second GET. Each is **best-effort** (a failed sub-fetch logs and leaves an empty grid, so the Form still opens). |
| **Merge sibling keys** | `api_merge_keys` folds sibling envelope keys onto the item — e.g. blog detail returns `{post, tags}`, so `tags` is merged onto `post`. |
| **Detail ⊂ list** | `api_detail_merge_list=True` merges the **list row underneath the detail object** (detail wins). Needed where GET-by-id returns a subset — e.g. `GET /users/{id}` has no phone/email/role; those come from the list row. |
| **Cursor pagination** | When `api_cursor_key` is set (e.g. `"nextCursor"`), `_fetch_collection` walks pages (sending the cursor back as `api_cursor_param`, `api_list_params` for page size) until it has the rows needed, the cursor runs out, or `api_max_pages` is hit. |
| **Count** | `_api_count` walks the collection; for cursor-paginated entities the result is **cached 120s** (walking every page is expensive). |

### 4.3 Worked example — the whole `Marzi User` controller

This is the *entire* generated controller. Everything is declaration; behaviour is
inherited from `ApiDocument`:

```python
# marzi_bridge/doctype/marzi_user/marzi_user.py   (auto-generated)
from marzi_bridge.api_document import ApiDocument

class MarziUser(ApiDocument):
    DOCTYPE = "Marzi User"
    api_endpoint = "/users"              # list route
    api_detail_endpoint = "/users"       # GET /users/<id>
    api_id_field = "userId"              # docname = this backend key
    api_service = "v1"
    api_list_key = "items"               # envelope: {"items": [...], "nextCursor": ...}
    api_field_aliases = {                # backend key → Frappe fieldname
        "firstName": "first_name", "lastName": "last_name",
        "accountStatus": "account_status", "profilePicUrl": "profile_pic_url", ...
    }
    api_child_tables = {                 # relational grids on the Form
        "bookings":     {"doctype": "Marzi User Booking",     "source": "item",
                         "item_key": "events",       "aliases": {"eventTitle": "event_title", ...}},
        "transactions": {"doctype": "Marzi User Transaction", "source": "item",
                         "item_key": "transactions", "aliases": {"promoCode": "promo_code", ...}},
    }
    api_list_params = {"limit": 50}      # backend page size (max 50)
    api_cursor_key = "nextCursor"        # → walk cursor pages
    api_detail_merge_list = True         # detail is a subset → merge list row underneath

    # The only non-declarative part: Frappe demands these be real staticmethods.
    @staticmethod
    def get_list(**kwargs):  return MarziUser._api_list(**kwargs)
    @staticmethod
    def get_count(**kwargs): return MarziUser._api_count(**kwargs)
    @staticmethod
    def get_stats(**kwargs): return {}
```

### 4.4 Worked example — how each mechanism runs (real `ApiDocument` code)

**Field mapping + nested-data serialization** (`_map_obj`) — this is why nested objects
now *show* instead of being dropped:

```python
@staticmethod
def _map_obj(doctype, obj, aliases, id_field=None):
    fieldtypes = {df.fieldname: df.fieldtype for df in frappe.get_meta(doctype).fields}
    row = frappe._dict()
    for key, value in (obj or {}).items():
        target = aliases.get(key, key)          # rename backend key → Frappe field
        ftype = fieldtypes.get(target)
        if ftype is None:
            continue                            # field not declared → skip (don't crash)
        if ftype in _JSON_FIELDTYPES and isinstance(value, (dict, list)):
            value = json.dumps(value, indent=2, default=str)   # nested blob → JSON text
        row[target] = value
    if id_field:
        row["name"] = (obj or {}).get(id_field)
    return row
```

**Cursor pagination** (`_fetch_collection`) — walks `nextCursor` pages only as far as needed:

```python
@classmethod
def _fetch_collection(cls, need=None):
    rows, cursor, pages = [], None, 0
    while True:
        params = dict(cls.api_list_params or {})
        if cursor:
            params[cls.api_cursor_param] = cursor        # send cursor back
        data  = MarziClient().get(cls.api_endpoint, service=cls.api_service, params=params or None)
        batch = cls._unwrap_list(data)
        rows.extend(batch)
        pages += 1
        cursor = cls._dig(data, cls.api_cursor_key) if cls.api_cursor_key else None
        if not cursor or not batch or pages >= cls.api_max_pages \
           or (need is not None and len(rows) >= need):     # stop early once we have enough
            return rows
```

**Opening a record** (`load_from_db`) — detail fetch, merge-keys, detail⊂list merge, and
best-effort child tables, all in one place:

```python
def load_from_db(self):
    ...
    obj = self._unwrap_item(data)                       # GET /users/<id>
    for mk in self.api_merge_keys:                      # fold siblings (blog {post,tags})
        sibling = self._dig(data, mk)
        if sibling is not None: obj = {**obj, mk: sibling}
    if self.api_detail_merge_list:                      # detail subset → list row underneath
        list_row = self._find_in_list(self.name)
        if list_row: obj = {**list_row, **obj}          # detail wins on conflicts
    row = self._to_row(obj)
    for fieldname, spec in (self.api_child_tables or {}).items():
        try:
            child_objs = self._fetch_child_rows(obj, spec)   # inline array OR sub-route GET
            row[fieldname] = [self._map_obj(spec["doctype"], o, spec.get("aliases", {}))
                              for o in child_objs]
        except Exception:
            frappe.log_error(...)                        # a failed grid never breaks the Form
            row[fieldname] = []
    super(Document, self).__init__(row)
```

### 4.5 Frappe contract gotcha

Frappe (`frappe.model.virtual_doctype.validate_controller`) requires `get_list`,
`get_count`, `get_stats` to be **actual `@staticmethod`s**. Static methods can't see the
subclass, so each generated controller adds three one-line staticmethods that delegate to
the classmethod helpers (`_api_list` / `_api_count`). Everything else is inherited.

---

## 5. The DocType generator (`scripts/gen_doctypes.py`)

Rather than hand-write ~27 DocTypes, they're generated from declarative `SPECS`
(parents) and `CHILD_SPECS` (child tables). Run it, then migrate:

```bash
python3 marzi_bridge/scripts/gen_doctypes.py          # pure file generation
docker exec -u frappe frappe-frappe-1 bash -lc \
  "cd /home/frappe/frappe-bench && bench --site marzi.localhost migrate"
```

Each parent spec emits, under `marzi_bridge/marzi_bridge/doctype/<scrubbed>/`:
`<scrubbed>.json` (the `is_virtual` DocType) + `<scrubbed>.py` (controller) + `__init__.py`.

**Spec building blocks** (helpers at the top of the file):
- Field tuple: `(fieldname, label, fieldtype, options, in_list_view, read_only)`.
- Layout: `tab()`, `sec()`, `col()` → Tab/Section/Column breaks.
- `img(name, label, url_field)` → an `Image` field rendering an external URL.
- `jsonf(name, label)` → a read-only `Code`(JSON) field for nested blobs.
- `table(name, label, child_doctype)` → a child-table grid.
- `image_field`, `detail_endpoint`, `child_tables`, `merge_keys`, `list_params`,
  `cursor_key`, `detail_merge_list` → passed straight through to the controller attrs.

**Worked example — the `Marzi User` spec** (in `SPECS`). This one declaration produces the
controller in §4.3, the DocType JSON, and its layout:

```python
{
    "doctype": "Marzi User",
    "endpoint": "/users", "detail_endpoint": "/users", "service": "v1",
    "id_field": "userId", "list_key": "items",
    "single_from_list": False,
    "list_params": {"limit": 50}, "cursor_key": "nextCursor",   # cursor pagination
    "detail_merge_list": True,                                  # detail ⊂ list → merge
    "image_field": "profile_pic_url",                           # list thumbnail
    "aliases": {"firstName": "first_name", "profilePicUrl": "profile_pic_url", ...},
    "child_tables": {
        "bookings":     {"doctype": "Marzi User Booking",     "source": "item", "item_key": "events", ...},
        "transactions": {"doctype": "Marzi User Transaction", "source": "item", "item_key": "transactions", ...},
    },
    "fields": [
        tab("tab_overview", "Overview"),
        img("avatar", "Avatar", "profile_pic_url"),             # Image field → external URL
        f("first_name", "First Name", "Data", None, 1),         # (…, in_list_view=1)
        f("phone", "Phone", "Data", None, 1),
        f("role", "Role", "Select", "\nSUPER_ADMIN\nADMIN\nMEMBER", 1),
        sec("sec_stats", "Stats"),
        f("total_events", "Events", "Int"), f("total_transactions", "Transactions", "Int"),
        tab("tab_bookings", "Bookings"),
        table("bookings", "Bookings", "Marzi User Booking"),    # child-table grid
        tab("tab_transactions", "Transactions"),
        table("transactions", "Transactions", "Marzi User Transaction"),
    ],
}
```

**Worked example — a feature proxy** (`api/speakers.py`, the reference pattern every
`api/*.py` module follows). Used for actions/lookups, not List/Form:

```python
@frappe.whitelist()          # framework entry point → /api/method/marzi_bridge.api.speakers.list_speakers
@require_marzi()             # RBAC gate: must hold the "Marzi Admin" role + a valid link
def list_speakers():
    return MarziClient().get("/speakers", params=request_params())   # forwards query args, returns JSON

@frappe.whitelist()
@require_marzi()
def create_speaker():
    return MarziClient().post("/speakers", json_body=request_params())   # no business logic here
```

**Read-only by design:** permissions grant only `read` to `Marzi Admin` + `System
Manager`, and each field is `read_only`. Write flows differ per entity and are enabled
case by case (Speaker is the hand-built CRUD pilot and is intentionally NOT regenerated).

> GOTCHA (documented in code): do **not** set top-level `read_only` on the DocType JSON —
> Frappe drops such a doctype from `can_read`, and the desk router then can't route its
> slug ("Page not found"). Enforce read-only via permissions + field-level `read_only`.

### The entities (27 DocTypes)

**Parents (19)** grouped as in the dashboard sidebar:
Configuration (Settings, User Link) · Event Management (Event, Booking, FAQ Group, Info
Item) · Communities (Group, WhatsApp Conversation, Escalation, Blocked Message) · App
Configuration (Status, Testimony, Speaker) · Content (Blog Post, Page, Campaign,
Template) · Users & Assets (User, Media).

**Children (8, `istable`)**: Event Attendee, Event Tier, Group Member, Group Post, User
Booking, User Transaction, Blog Tag, FAQ Item — populated by their parent's
`load_from_db`.

Entities **with a rich detail endpoint** (`single_from_list=False`): Event, Group, User,
Blog Post, Page, Media. The rest load a single record from the collection.

---

## 6. Auth bridge & the client

- **Linking** (`auth/otp.py`): `send_otp(phone)` → `/v1/auth/send-otp`; `verify_otp(phone,
  otp)` → `/v1/auth/verify-otp`, then rejects non-admin roles and upserts the caller's
  `Marzi User Link` with the returned access/refresh JWT (stored as encrypted `Password`
  fields). Raw tokens are never returned to the browser.
- **Tokens** (`auth/tokens.py`): `get_valid_token()` loads the link, refreshes when near
  expiry, raises `NotLinkedError` ("link your phone first") when there's no link.
- **Client** (`client.py`): `MarziClient().get/post/put/patch/delete(path, service=…,
  auth=…, params=…, json_body=…)`. Resolves the base URL from `Marzi Bridge Settings`
  per service, attaches the Bearer token (unless `auth=False`, e.g. the unauthenticated
  WhatsApp/payments Lambdas), does one 401-retry, normalises errors, never logs tokens.
- **RBAC** (`permissions.py`): `@require_marzi()` requires the `Marzi Admin` role (+ a
  valid link) on every proxy method — the seam where granular RBAC will tighten later.

**The 401-retry, in code** (`client.py`) — the single place refresh/retry lives:

```python
token = get_valid_token(self.user)                    # load link, refresh if near expiry
response = raw_request(method, path, service=svc, params=params, token=token)
if response.status_code == 401:                       # token rejected despite local check
    token = force_refresh(self.user)                  # refresh ONCE
    response = raw_request(method, path, service=svc, params=params, token=token)
return self._handle(response, method, path)           # 2xx → JSON; else log (no token) + frappe.throw
```

> **Tokens are environment-bound.** The JWT is minted per environment; the backend
> tenant-scopes queries by the token's `tid`. If a base URL changes between envs, re-run
> the OTP link (and `frappe.db.commit()` if doing it from a bench console — the console
> doesn't auto-commit), or tenant-scoped endpoints like `/users` silently return empty.

---

## 7. Desk branding & navigation (`branding.py`, `hooks.py`, `public/`)

**Logo / favicon / splash — declared in `hooks.py`** (loaded at boot, no build needed for
`/assets/...` paths):

```python
app_logo_url = "/assets/marzi_bridge/images/marzi-logo.png"          # navbar + login
website_context = {                                                  # favicon + splash
    "favicon": "/assets/marzi_bridge/images/marzi-favicon.png",
    "splash_image": "/assets/marzi_bridge/images/marzi-logo.png",
}
app_include_css = "/assets/marzi_bridge/css/marzi_branding.css"      # desk CSS (below)
```

**Sidebar header logo — the native way** (`branding.py::apply_desk_branding`). Frappe's
`SidebarHeader.set_header_icon()` paints a generated gray initials avatar ("M") **unless**
a `Desktop Icon` matching the workspace label carries a `logo_url` — then it renders
`<img src=logo_url>`. So we create that record:

```python
icon.update({
    "label": "Marzi Bridge", "standard": 1,
    "icon_type": "Link", "link_type": "Workspace Sidebar", "link_to": "Marzi Bridge",
    "logo_url": "/assets/marzi_bridge/images/marzi-favicon.png",   # ← the Marzi mark
})
```

**Left side-nav = all APIs** (`branding.py::setup_sidebar`). One `Workspace Sidebar` doc
drives the whole left nav; `child=1` nests a link under the preceding Section Break:

```python
for section_label, entries in SECTIONS:            # Configuration, Event Management, …
    rows.append({"label": section_label, "type": "Section Break"})
    for label, doctype, icon in entries:
        rows.append({"label": label, "link_to": doctype, "link_type": "DocType",
                     "type": "Link", "icon": icon, "child": 1})
...
for row in _rows():
    doc.append("items", row)     # append() → idx in order; doc.items=[...] leaves idx=0 (scrambles!)
```

**Home screen = the Marzi User list** (`apply_desk_branding`) — three levers so *every*
entry point lands on the API-backed users, and Frappe's own User doctype is hidden:

```python
frappe.db.set_value("Desktop Icon", {"label": "Users", "app": "frappe"}, "hidden", 1)   # hide Frappe Users
frappe.db.set_single_value("System Settings", "default_app", "marzi_bridge")            # login → this app
# + sidebar "Home" item link_to="Marzi User"; hooks add_to_apps_screen.route="/desk/marzi-user"
```

**Notifications removed** — the sidebar item only appears when the user's `notifications`
desk property is on, so `apply_desk_branding` sets it to `0` for all System Users.

**The CSS backstop** (`public/css/marzi_branding.css`) — hides the notification item and
paints the logo box even before the Desktop Icon resolves:

```css
.sidebar-header .header-logo {                       /* swap the gray "M" avatar box */
    background-image: url("/assets/marzi_bridge/images/marzi-favicon.png");
    background-size: contain; width: 32px; height: 32px; border-radius: 8px;
}
.sidebar-header .header-logo > * { visibility: hidden; }   /* hide generated initials */
.sidebar-notification            { display: none !important; }   /* remove Notification */
```

Re-apply after changes: `bench --site <site> execute marzi_bridge.branding.setup_sidebar`
and `… marzi_bridge.branding.apply_desk_branding`.

---

## 7b. Styling & UX evolution (beginning → now)

How the desk went from a stock Frappe app to a Marzi-branded admin, in the order it
happened:

| Stage | Before | After | Where |
|---|---|---|---|
| **1. Data visible** | Nothing — bare app | Entities as read-only Lists (list columns only) | generator + `ApiDocument` |
| **2. Full detail** | Clicking a row → near-empty Form (only list columns; images as raw text) | Forms show *all* fields, inline images, nested JSON, and child-table grids (attendees/members/bookings/…) | `_map_obj` JSON handling, `Image` fields, `api_child_tables`, `api_detail_endpoint` |
| **3. Brand marks** | Frappe logo (navbar/login), Frappe favicon | Marzi wordmark on navbar+login, Marzi "M" favicon, splash | `hooks.py` (`app_logo_url`, `website_context`) + assets under `public/images` |
| **4. Left navigation** | Cards inside the workspace body; entities buried | Every entity in the **left side nav**, grouped into 6 sections | `setup_sidebar()` → Workspace Sidebar |
| **5. Sidebar polish** | Gray "M" initials box; a "Notification" row | Marzi logo mark in the header; Notification removed | Desktop Icon `logo_url` + `marzi_branding.css` + `notifications=0` |
| **6. Home = Users** | Landed on the workspace card page; "Users" ambiguous (Frappe vs Marzi) | Login lands on the API-backed **Marzi Users** list; Frappe's Users icon hidden | `default_app`, apps-screen route, hidden Desktop Icon |
| **7. Users fully wired** | `/users` returned one page of 50; Form missing phone/role/status | Cursor-paged (all users), Form merges list+detail, bookings/transactions grids | `api_cursor_key`, `api_detail_merge_list`, cached count |

**Why CSS is a *backstop*, not the primary mechanism:** an early attempt branded the
sidebar purely with CSS `::before` on the wrong container and didn't render reliably. The
durable fix uses Frappe's own data model (Desktop Icon `logo_url`, the `notifications`
desk property, Workspace Sidebar) — the CSS remains only as a belt-and-suspenders layer.
Net rule learned: **prefer the framework's native data model over CSS/JS overrides**, and
never fork the framework templates.

---

## 7c. Recipe — add a new API-backed entity

The workflow you'll reach for most:

1. **Add a spec** to `SPECS` in `scripts/gen_doctypes.py` (copy the closest existing one).
   Set `endpoint`, `service`, `id_field`, `list_key`, `aliases`, and the `fields` list.
   Add `detail_endpoint` if a richer GET-by-id exists; `child_tables` for relational
   collections; `cursor_key`/`list_params` if paginated.
2. **Generate**: `python3 marzi_bridge/scripts/gen_doctypes.py`.
3. **Migrate**: `bench --site marzi.localhost migrate` (in the container, §9).
4. **Add to the nav**: drop `("Label", "Marzi <Entity>", "icon")` into the right section
   of `SECTIONS` in `branding.py`, then
   `bench … execute marzi_bridge.branding.setup_sidebar`.
5. **Verify**: add the entity to `verify.py`'s probe and run
   `bench … execute marzi_bridge.verify.probe_details`.

No hand-written Python is needed unless the entity has non-standard behaviour (then
override a method on the generated controller, as the hand-built `Marzi Speaker` does).

---

## 8. Verifying it works (`verify.py`)

Run as a linked admin inside the container:

```bash
docker exec -u frappe frappe-frappe-1 bash -lc \
  "cd /home/frappe/frappe-bench && bench --site marzi.localhost execute marzi_bridge.verify.<fn>"
```

- `check_doctypes` — every DocType synced, virtual, staticmethods intact.
- `probe_details` — opens one record per entity; prints scalar count, image-field value,
  and child-table row counts (proves detail loading + child tables).
- `smoke_test` — calls every read-only proxy endpoint once; PASS/FAIL/SKIP report.

---

## 9. Runtime environment (quick reference)

Runs in Docker (not native bench). App bind-mounted into the frappe container.

```bash
# bench, migrate, execute, console:
docker exec -u frappe frappe-frappe-1 bash -lc \
  "cd /home/frappe/frappe-bench && bench --site marzi.localhost <cmd>"
```

Containers: `frappe-frappe-1`, `frappe-mariadb-1`, `frappe-redis-cache-1`,
`frappe-redis-queue-1`. Site: `marzi.localhost` (multi-tenant — use
`Host: marzi.localhost` when curling). Backend is **production** — lists show live
customer PII; keep off shared screens/exports.

---

## 10. Mental model in three sentences

1. **`ApiDocument` + the generator** turn declarative specs into read-only Frappe
   List/Form screens backed live by the marzi API — no data is copied.
2. **`MarziClient` + the auth bridge** are the single, secure outbound path: per-user
   JWT attached server-side, refreshed automatically, RBAC-gated.
3. **`branding.py` + hooks** make the desk look and navigate like the Marzi admin
   dashboard, landing on the API-backed Users list.
