#!/usr/bin/env bash
# =============================================================================
# update.sh — Pull latest changes, apply migrations and restart services
#
# Usage:
#   1. Ensure .env exists next to this script (see .env.example).
#   2. Run as root: sudo bash update.sh
# =============================================================================

set -euo pipefail

log() { echo "[update] $*"; }
die() { echo "[update] ERROR: $*" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"

[[ $EUID -eq 0 ]] || die "This script must be run as root (use sudo)."
[[ -f "${ENV_FILE}" ]] || die ".env file not found at ${ENV_FILE}. Copy .env.example and fill in your values."

set -o allexport
# shellcheck disable=SC1090
source <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "${ENV_FILE}")
set +o allexport

DEPLOY_DIR="${DEPLOY_DIR:-/var/www/swimming_association}"
VENV_DIR="${VENV_DIR:-${DEPLOY_DIR}/.venv}"
SYSTEMD_SERVICE="${SYSTEMD_SERVICE:-swimming_association}"
NGINX_SERVICE="${NGINX_SERVICE:-nginx}"

[[ -d "${DEPLOY_DIR}/.git" ]] || die "Git repository not found at ${DEPLOY_DIR}."
[[ -x "${VENV_DIR}/bin/python" ]] || die "Python interpreter not found at ${VENV_DIR}/bin/python."

log "Pulling latest changes in ${DEPLOY_DIR} ..."
git -C "${DEPLOY_DIR}" pull --ff-only

log "Installing Python dependencies ..."
"${VENV_DIR}/bin/pip" install --upgrade -r "${DEPLOY_DIR}/requirements.txt"

log "Applying Django migrations ..."
(cd "${DEPLOY_DIR}" && "${VENV_DIR}/bin/python" manage.py migrate --noinput)

log "Collecting static files ..."
(cd "${DEPLOY_DIR}" && "${VENV_DIR}/bin/python" manage.py collectstatic --noinput)

log "Restarting services: ${SYSTEMD_SERVICE}, ${NGINX_SERVICE} ..."
systemctl restart "${SYSTEMD_SERVICE}"
systemctl restart "${NGINX_SERVICE}"

log "Update complete."
