#!/usr/bin/env bash
# =============================================================================
# deploy.sh — Deploy swimming_association Django site on CentOS
#
# Usage:
#   1. Place this script on the target server.
#   2. Create a .env file next to the script (see .env.example for reference).
#      At minimum the file must contain REPO_URL and DOMAIN.
#   3. Run as root:  sudo bash deploy.sh
# =============================================================================

set -euo pipefail

# ── Helpers ───────────────────────────────────────────────────────────────────

log()  { echo "[deploy] $*"; }
die()  { echo "[deploy] ERROR: $*" >&2; exit 1; }

# ── Paths & defaults ─────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"
DEPLOY_DIR="/var/www/swimming_association"
VENV_DIR="${DEPLOY_DIR}/.venv"
GUNICORN_SOCKET="/run/swimming_association.sock"
SYSTEMD_SERVICE="swimming_association"
SERVICE_USER="swimming_association"

# ── Step 0: sanity checks ─────────────────────────────────────────────────────

[[ $EUID -eq 0 ]] || die "This script must be run as root (use sudo)."
[[ -f "${ENV_FILE}" ]] || die ".env file not found at ${ENV_FILE}. Copy .env.example and fill in your values."

# ── Step 1: load .env ─────────────────────────────────────────────────────────

log "Loading ${ENV_FILE} ..."

# Export all non-comment, non-empty KEY=VALUE lines
set -o allexport
# shellcheck disable=SC1090
source <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "${ENV_FILE}")
set +o allexport

[[ -n "${REPO_URL:-}" ]] || die "REPO_URL is not set in ${ENV_FILE}."
[[ -n "${DOMAIN:-}" ]]   || die "DOMAIN is not set in ${ENV_FILE}."

# ── Step 2: create dedicated service user ────────────────────────────────────

if ! id "${SERVICE_USER}" &>/dev/null; then
    log "Creating system user '${SERVICE_USER}' ..."
    useradd --system --no-create-home --shell /sbin/nologin "${SERVICE_USER}"
fi

# ── Step 3: install system packages ──────────────────────────────────────────

log "Installing system dependencies ..."
yum install -y epel-release
yum install -y \
    git \
    nginx \
    python3 \
    python3-pip \
    python3-devel \
    gcc \
    postgresql-devel \
    libpq-devel

# ── Step 4: clone or update the repository ───────────────────────────────────

if [[ -d "${DEPLOY_DIR}/.git" ]]; then
    log "Repository already exists — pulling latest changes ..."
    git -C "${DEPLOY_DIR}" pull --ff-only
else
    log "Cloning ${REPO_URL} into ${DEPLOY_DIR} ..."
    git clone "${REPO_URL}" "${DEPLOY_DIR}"
fi

# ── Step 5: copy / update .env inside the project ────────────────────────────

log "Copying .env to ${DEPLOY_DIR}/.env ..."
cp -f "${ENV_FILE}" "${DEPLOY_DIR}/.env"

# Append variables that should be present in production if not already in the file.
# Add more key=default_value pairs as needed.
declare -A REQUIRED_VARS=(
    [DEBUG]="False"
    [DB_HOST]="${DB_HOST:-127.0.0.1}"
    [DB_PORT]="${DB_PORT:-5432}"
    [DB_NAME]="${DB_NAME:-swimming_association}"
    [DB_USER]="${DB_USER:-postgres}"
    [ALLOWED_HOSTS]="${DOMAIN}"
)

for key in "${!REQUIRED_VARS[@]}"; do
    if ! grep -qE "^${key}=" "${DEPLOY_DIR}/.env"; then
        log "  Appending ${key} to .env ..."
        echo "${key}=${REQUIRED_VARS[$key]}" >> "${DEPLOY_DIR}/.env"
    fi
done

# Reload env from the updated project .env so later steps pick up any appended values
set -o allexport
# shellcheck disable=SC1090
source <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "${DEPLOY_DIR}/.env")
set +o allexport

# ── Step 6: set up Python virtual environment ─────────────────────────────────

log "Setting up Python virtual environment at ${VENV_DIR} ..."
python3 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/pip" install --upgrade pip

log "Installing Python dependencies ..."
"${VENV_DIR}/bin/pip" install -r "${DEPLOY_DIR}/requirements.txt"

# gunicorn is needed to serve the Django application
"${VENV_DIR}/bin/pip" install gunicorn

# ── Step 7: Django setup ──────────────────────────────────────────────────────

log "Running Django migrations ..."
(cd "${DEPLOY_DIR}" && "${VENV_DIR}/bin/python" manage.py migrate --noinput)

log "Collecting static files ..."
(cd "${DEPLOY_DIR}" && "${VENV_DIR}/bin/python" manage.py collectstatic --noinput)

# ── Step 8: create systemd service for gunicorn ───────────────────────────────

log "Creating systemd service /etc/systemd/system/${SYSTEMD_SERVICE}.service ..."
cat > "/etc/systemd/system/${SYSTEMD_SERVICE}.service" <<EOF
[Unit]
Description=Gunicorn daemon for swimming_association
After=network.target

[Service]
User=${SERVICE_USER}
Group=${SERVICE_USER}
WorkingDirectory=${DEPLOY_DIR}
EnvironmentFile=${DEPLOY_DIR}/.env
ExecStart=${VENV_DIR}/bin/gunicorn \\
    --workers 3 \\
    --bind unix:${GUNICORN_SOCKET} \\
    swimming_association.wsgi:application
ExecReload=/bin/kill -s HUP \$MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

chown -R "${SERVICE_USER}:${SERVICE_USER}" "${DEPLOY_DIR}"

systemctl daemon-reload
systemctl enable  "${SYSTEMD_SERVICE}"
systemctl restart "${SYSTEMD_SERVICE}"

# ── Step 9: create nginx config ───────────────────────────────────────────────

NGINX_CONF="/etc/nginx/conf.d/${DOMAIN}.conf"
log "Writing nginx config to ${NGINX_CONF} ..."
cat > "${NGINX_CONF}" <<EOF
# Redirect www → non-www
server {
    listen 80;
    server_name www.${DOMAIN};
    return 301 \$scheme://${DOMAIN}\$request_uri;
}

server {
    listen 80;
    server_name ${DOMAIN};

    client_max_body_size 20M;

    location /static/ {
        alias ${DEPLOY_DIR}/staticfiles/;
    }

    location /media/ {
        alias ${DEPLOY_DIR}/media/;
    }

    location / {
        proxy_pass http://unix:${GUNICORN_SOCKET};
        proxy_set_header Host              \$host;
        proxy_set_header X-Real-IP         \$remote_addr;
        proxy_set_header X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

# ── Step 10: start nginx ──────────────────────────────────────────────────────

log "Testing nginx configuration ..."
nginx -t

log "Enabling and restarting nginx ..."
systemctl enable  nginx
systemctl restart nginx

# ── Done ──────────────────────────────────────────────────────────────────────

log "Deployment complete!"
log "  Site URL  : http://${DOMAIN}"
log "  Project   : ${DEPLOY_DIR}"
log "  Venv      : ${VENV_DIR}"
log "  Nginx conf: ${NGINX_CONF}"
log "  Service   : ${SYSTEMD_SERVICE}"
