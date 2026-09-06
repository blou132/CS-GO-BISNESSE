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
wait_seconds="$(setting_value DEPLOY_WAIT_SECONDS "$env_file" '120')"
validate_positive_integer "$wait_seconds" "DEPLOY_WAIT_SECONDS"
health_url="$(setting_value HEALTHCHECK_URL "$env_file" 'http://127.0.0.1:3000/api/health')"

git pull --ff-only
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
