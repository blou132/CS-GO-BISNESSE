#!/usr/bin/env bash
set -Eeuo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
# shellcheck source=lib/backup-common.sh
source "$project_root/scripts/lib/backup-common.sh"
cd "$project_root"

env_file="${ENV_FILE:-$project_root/.env.production}"
[ -f "$env_file" ] || fail "Copiez .env.example vers .env.production et configurez-le."
for executable in git docker curl flock; do
  command -v "$executable" >/dev/null 2>&1 || fail "$executable est introuvable."
done
[ -z "$(git status --porcelain)" ] || fail "Le dépôt contient des modifications ou fichiers non suivis."

mkdir -p "$project_root/.deployment"
exec 9>"$project_root/.deployment/operation.lock"
flock -n 9 || fail "Un déploiement ou une restauration est déjà en cours."

environment_name="$(setting_value ENVIRONMENT "$env_file" '')"
[ "$environment_name" = "production" ] || fail "ENVIRONMENT doit valoir production."
postgres_password="$(setting_value POSTGRES_PASSWORD "$env_file" '')"
[ -n "$postgres_password" ] || fail "POSTGRES_PASSWORD est absent ou vide."
[ "$postgres_password" != "replace-with-local-password" ] || fail "Remplacez le mot de passe d'exemple."
case "$postgres_password" in
  *[!A-Za-z0-9._~-]*) fail "POSTGRES_PASSWORD doit être URL-safe (A-Z, a-z, 0-9, . _ ~ -)." ;;
esac
admin_username="$(setting_value ADMIN_USERNAME "$env_file" '')"
admin_password_hash="$(setting_value ADMIN_PASSWORD_HASH "$env_file" '')"
session_secret="$(setting_value SESSION_SECRET "$env_file" '')"
for variable_name in admin_username admin_password_hash session_secret; do
  value="${!variable_name}"
  case "$value" in
    \"*\") value="${value#\"}"; value="${value%\"}" ;;
    \'*\') value="${value#\'}"; value="${value%\'}" ;;
  esac
  printf -v "$variable_name" '%s' "$value"
done
[ -n "$admin_username" ] || fail "ADMIN_USERNAME est absent ou vide."
[ "${#admin_username}" -le 64 ] || fail "ADMIN_USERNAME dépasse 64 caractères."
[[ "$admin_password_hash" =~ ^scrypt\$16384\$8\$1\$[A-Za-z0-9_-]{22}\$[A-Za-z0-9_-]{86}$ ]] || \
  fail "ADMIN_PASSWORD_HASH doit provenir de scripts/generate-admin-password-hash.py."
[ "${#session_secret}" -ge 32 ] || fail "SESSION_SECRET doit contenir au moins 32 caractères."
session_ttl_seconds="$(setting_value SESSION_TTL_SECONDS "$env_file" '28800')"
login_limit_attempts="$(setting_value LOGIN_RATE_LIMIT_MAX_ATTEMPTS "$env_file" '5')"
login_limit_window="$(setting_value LOGIN_RATE_LIMIT_WINDOW_SECONDS "$env_file" '900')"
validate_positive_integer "$session_ttl_seconds" "SESSION_TTL_SECONDS"
validate_positive_integer "$login_limit_attempts" "LOGIN_RATE_LIMIT_MAX_ATTEMPTS"
validate_positive_integer "$login_limit_window" "LOGIN_RATE_LIMIT_WINDOW_SECONDS"
(( session_ttl_seconds >= 300 && session_ttl_seconds <= 604800 )) || \
  fail "SESSION_TTL_SECONDS doit être compris entre 300 et 604800."
(( login_limit_attempts >= 1 && login_limit_attempts <= 50 )) || \
  fail "LOGIN_RATE_LIMIT_MAX_ATTEMPTS doit être compris entre 1 et 50."
(( login_limit_window >= 60 && login_limit_window <= 86400 )) || \
  fail "LOGIN_RATE_LIMIT_WINDOW_SECONDS doit être compris entre 60 et 86400."
cookie_secure="$(setting_value SESSION_COOKIE_SECURE "$env_file" 'false')"
case "${cookie_secure,,}" in
  0|1|false|true|no|yes|off|on) ;;
  *) fail "SESSION_COOKIE_SECURE doit être un booléen explicite." ;;
esac
wait_seconds="$(setting_value DEPLOY_WAIT_SECONDS "$env_file" '120')"
validate_positive_integer "$wait_seconds" "DEPLOY_WAIT_SECONDS"
health_url="$(setting_value HEALTHCHECK_URL "$env_file" 'http://127.0.0.1:3000/api/health')"

export IMAGE_TAG
IMAGE_TAG="$(git rev-parse --short=12 HEAD)"
compose=(
  docker compose --env-file "$env_file"
  -f "$project_root/docker-compose.yml"
  -f "$project_root/compose.production.yml"
)

"${compose[@]}" config --quiet
"${compose[@]}" build
"${compose[@]}" up -d --wait --wait-timeout "$wait_seconds" db
ENV_FILE="$env_file" "$project_root/scripts/backup-db.sh"
"${compose[@]}" run --rm --no-deps api alembic upgrade head
"${compose[@]}" up -d --remove-orphans --wait --wait-timeout "$wait_seconds"
health_payload="$(curl --fail --silent --show-error --max-time 10 "$health_url")"
printf '%s' "$health_payload" | grep -Eq '"api"[[:space:]]*:[[:space:]]*"healthy"' || \
  fail "Le contrôle final ne confirme pas la disponibilité de l'API."
printf '%s' "$health_payload" | grep -Eq '"database"[[:space:]]*:[[:space:]]*"healthy"' || \
  fail "Le contrôle final ne confirme pas la disponibilité de PostgreSQL."

mkdir -p "$project_root/.deployment"
printf '%s\n' "$IMAGE_TAG" > "$project_root/.deployment/current-image-tag.tmp"
mv "$project_root/.deployment/current-image-tag.tmp" \
  "$project_root/.deployment/current-image-tag"
printf 'Déploiement %s terminé; état: %s\n' "$IMAGE_TAG" "$health_url"
