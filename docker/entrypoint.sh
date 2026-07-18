#!/usr/bin/env bash
# Builds the bench around the bind-mounted app source on first run, then hands
# off to the CMD (honcho start). Idempotent: subsequent boots skip finished steps.
set -euo pipefail

BENCH_DIR=/home/frappe/frappe-bench
APPS_DIR="$BENCH_DIR/apps"

# ---------------------------------------------------------------------------
# Stage 1 (root): fix ownership of freshly-created named-volume mountpoints,
# then drop privileges and re-exec ourselves as the frappe user.
# ---------------------------------------------------------------------------
if [ "$(id -u)" = "0" ]; then
    mkdir -p "$APPS_DIR/frappe/node_modules"
    # Only touch the volume mountpoints — never chown -R the bind-mounted host source.
    chown frappe:frappe "$BENCH_DIR" "$APPS_DIR" "$APPS_DIR/frappe/node_modules" 2>/dev/null || true
    exec gosu frappe "$0" "$@"
fi

# ---------------------------------------------------------------------------
# Stage 2 (frappe): initialise the bench, then exec the CMD.
# ---------------------------------------------------------------------------
cd "$BENCH_DIR"

SITE_NAME="${SITE_NAME:?SITE_NAME must be set}"
DB_ROOT_PASSWORD="${DB_ROOT_PASSWORD:?DB_ROOT_PASSWORD must be set}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:?ADMIN_PASSWORD must be set}"
DB_HOST="${DB_HOST:-mariadb}"
DB_PORT="${DB_PORT:-3306}"
WEB_PORT="${WEB_PORT:-8000}"
SOCKETIO_PORT="${SOCKETIO_PORT:-9000}"
BUILD_ASSETS="${BUILD_ASSETS:-1}"

log() { echo -e "\033[1;34m[entrypoint]\033[0m $*"; }

wait_for() {
    local name="$1" cmd="$2" tries=60
    log "waiting for $name ..."
    until eval "$cmd" >/dev/null 2>&1; do
        tries=$((tries - 1))
        [ "$tries" -le 0 ] && { echo "timed out waiting for $name" >&2; exit 1; }
        sleep 2
    done
    log "$name is up"
}

# Bench scaffolding dirs (the named volume starts nearly empty on first run).
# config/pids is one of the markers bench uses to detect a bench directory.
mkdir -p sites logs config/pids apps

wait_for "MariaDB" "mariadb -h '$DB_HOST' -P '$DB_PORT' -u root -p'$DB_ROOT_PASSWORD' -e 'SELECT 1'"
wait_for "redis-cache" "redis-cli -h redis-cache ping"
wait_for "redis-queue" "redis-cli -h redis-queue ping"

# 1. Python virtualenv --------------------------------------------------------
if [ ! -x env/bin/python ]; then
    log "creating virtualenv"
    python -m venv env
    env/bin/pip install --upgrade pip wheel
fi

# 2. Editable app installs ----------------------------------------------------
# NB: check with `pip show`, not `import` — the frappe repo root (mounted at
# apps/frappe) nests a `marzi_bridge/` dir, so `import marzi_bridge` would
# resolve to that namespace shadow and wrongly skip the real install.
if ! env/bin/pip show frappe >/dev/null 2>&1; then
    log "installing frappe (editable) + dependencies"
    env/bin/pip install -e ./apps/frappe
fi
if ! env/bin/pip show marzi_bridge >/dev/null 2>&1; then
    log "installing marzi_bridge (editable)"
    env/bin/pip install -e ./apps/marzi_bridge
fi

# 3. Node dependencies for the framework (asset build + socketio) -------------
if [ ! -d apps/frappe/node_modules/.bin ]; then
    log "installing frappe node dependencies (yarn)"
    (cd apps/frappe && yarn install)
fi

# 4. App registry -------------------------------------------------------------
printf 'frappe\nmarzi_bridge\n' > sites/apps.txt

# 5. Process file (external redis/mariadb, so only bench-owned processes) ------
if [ ! -f Procfile ]; then
    log "writing Procfile"
    cat > Procfile <<'EOF'
web: bench serve --port 8000
socketio: bench socketio
watch: bench watch
schedule: bench schedule
worker: bench worker 1>> logs/worker.log 2>> logs/worker.error.log
EOF
fi

# 6. Base common_site_config (only if absent — preserves generated keys) ------
if [ ! -f sites/common_site_config.json ]; then
    log "writing sites/common_site_config.json"
    cat > sites/common_site_config.json <<EOF
{
 "db_host": "$DB_HOST",
 "db_port": $DB_PORT,
 "redis_cache": "redis://redis-cache:6379",
 "redis_queue": "redis://redis-queue:6379",
 "redis_socketio": "redis://redis-cache:6379",
 "socketio_port": $SOCKETIO_PORT,
 "webserver_port": $WEB_PORT,
 "developer_mode": 1,
 "background_workers": 1,
 "live_reload": true,
 "serve_default_site": true
}
EOF
fi

# 7. Create the site (once) ---------------------------------------------------
if [ ! -d "sites/$SITE_NAME" ]; then
    log "creating site $SITE_NAME"
    bench new-site "$SITE_NAME" \
        --db-root-username root \
        --mariadb-root-password "$DB_ROOT_PASSWORD" \
        --admin-password "$ADMIN_PASSWORD" \
        --db-host "$DB_HOST" \
        --db-port "$DB_PORT" \
        --no-mariadb-socket
    bench use "$SITE_NAME"
fi

# 8. Ensure marzi_bridge is installed on the site (idempotent) ----------------
if ! bench --site "$SITE_NAME" list-apps 2>/dev/null | grep -qw marzi_bridge; then
    log "installing marzi_bridge on $SITE_NAME"
    bench --site "$SITE_NAME" install-app marzi_bridge
fi
bench --site "$SITE_NAME" set-config developer_mode 1 >/dev/null

# 9. Build assets once (Node 24 is available here) ----------------------------
if [ "$BUILD_ASSETS" = "1" ] && [ ! -f sites/.assets-built ]; then
    log "building assets (first run — this takes a few minutes)"
    bench build && touch sites/.assets-built
fi

log "bench ready — starting: $*"
exec "$@"
