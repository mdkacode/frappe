# Running the Frappe bench in Docker

Everything now runs in containers — MariaDB, Redis, and the full bench
(`web`, `socketio`, `scheduler`, `worker`, asset `watch`). The `frappe` fork and
`marzi_bridge` source are **bind-mounted**, so edits on the host are live. The
image ships **Python 3.14 + Node 24 + wkhtmltopdf**, the versions the fork needs
(and which the host lacked — that's why assets never built before).

## First run

```bash
# .env is generated for you with random dev passwords (gitignored).
# To recreate it:  cp .env.example .env  and fill in the values.
docker compose up --build
```

First boot creates the venv, installs `frappe` + `marzi_bridge` (editable),
runs `yarn install`, creates the site, and builds assets — allow a few minutes.
Subsequent boots skip finished steps and start in seconds.

Then open **http://marzi.localhost:8000** (log in as `Administrator` with the
`ADMIN_PASSWORD` from `.env`). `*.localhost` resolves to loopback in Chrome/Firefox.

## Everyday commands

```bash
docker compose up -d              # start in the background
docker compose logs -f frappe     # tail the bench (web/worker/scheduler/watch)
docker compose down               # stop (data persists in volumes)

# run bench / tests / console inside the running container:
docker compose exec frappe bench --site marzi.localhost console
docker compose exec frappe bench --site marzi.localhost run-tests --app marzi_bridge
docker compose exec frappe bash
```

## What lives where

| Thing | Location |
|-------|----------|
| frappe app source | bind mount → `./` (host repo root) |
| marzi_bridge source | bind mount → `./marzi_bridge` |
| bench (`env/`, `sites/`, `config/`, `logs/`) | `bench` volume |
| node_modules | `frappe-node-modules` volume |
| database | `mariadb-data` volume (also on host port **3308**) |

This is fully separate from the host bench at `~/frappe-bench` and the host
MariaDB on 3307 — nothing collides.

## Reset

```bash
docker compose down -v            # ⚠ deletes DB + bench volumes (fresh site next up)
```

## Config knobs (`.env`)

- `SITE_NAME` — site to create (default `marzi.localhost`)
- `DB_ROOT_PASSWORD` — MariaDB root password
- `ADMIN_PASSWORD` — site Administrator password
- `BUILD_ASSETS=0` (compose env) — skip the initial `bench build`
