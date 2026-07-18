# syntax=docker/dockerfile:1
#
# Dev image for the Frappe bench (frappe fork + marzi_bridge).
# Ships the exact runtimes the fork needs: Python 3.14 + Node 24 + wkhtmltopdf.
# The bench itself (env/, sites/, config/) lives in a volume; the app source
# is bind-mounted at runtime so edits are live. See ../DOCKER.md.

FROM python:3.14-slim-bookworm

ARG NODE_MAJOR=24
ARG WKHTMLTOPDF_VERSION=0.12.6.1-3

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# --- system packages: build toolchain, DB/redis clients, wkhtmltopdf runtime deps ---
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        ca-certificates curl wget gnupg git gosu \
        build-essential pkg-config python3-dev \
        default-libmysqlclient-dev libffi-dev libssl-dev \
        mariadb-client redis-tools \
        # wkhtmltopdf (patched-qt) runtime deps
        fontconfig libxrender1 libxext6 libjpeg62-turbo xfonts-75dpi xfonts-base; \
    rm -rf /var/lib/apt/lists/*

# --- Node.js (NodeSource, installed via signed apt repo — not curl|sh) + yarn via corepack ---
RUN set -eux; \
    mkdir -p /etc/apt/keyrings; \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
        | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg; \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_${NODE_MAJOR}.x nodistro main" \
        > /etc/apt/sources.list.d/nodesource.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends nodejs; \
    corepack enable; \
    corepack prepare yarn@stable --activate; \
    rm -rf /var/lib/apt/lists/*

# --- wkhtmltopdf (patched Qt build, matches host arch) ---
RUN set -eux; \
    arch="$(dpkg --print-architecture)"; \
    url="https://github.com/wkhtmltopdf/packaging/releases/download/${WKHTMLTOPDF_VERSION}/wkhtmltox_${WKHTMLTOPDF_VERSION}.bookworm_${arch}.deb"; \
    curl -fSL -o /tmp/wkhtmltox.deb "$url"; \
    apt-get update; \
    apt-get install -y --no-install-recommends /tmp/wkhtmltox.deb; \
    rm -rf /var/lib/apt/lists/* /tmp/wkhtmltox.deb; \
    wkhtmltopdf --version

# --- bench CLI + honcho (process manager) in the system interpreter ---
RUN pip install --no-cache-dir frappe-bench honcho

# --- unprivileged runtime user; bench dir pre-created so its volume inherits ownership ---
RUN useradd --create-home --uid 1000 --shell /bin/bash frappe \
    && mkdir -p /home/frappe/frappe-bench/apps \
    && chown -R frappe:frappe /home/frappe

WORKDIR /home/frappe/frappe-bench

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 8000 9000

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["honcho", "start"]
