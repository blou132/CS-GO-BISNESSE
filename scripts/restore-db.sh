#!/usr/bin/env bash
set -Eeuo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
# shellcheck source=lib/backup-common.sh
source "$project_root/scripts/lib/backup-common.sh"

[ "$#" -eq 1 ] || fail "Usage: $0 /chemin/explicite/sauvegarde.dump"
[ -f "$1" ] || fail "Fichier de sauvegarde introuvable: $1"
[ -t 0 ] || fail "La restauration exige un terminal interactif."
backup_file="$(realpath -- "$1")"
env_file="${ENV_FILE:-$project_root/.env.production}"
[ -f "$env_file" ] || fail "Fichier d'environnement absent: $env_file"
command -v docker >/dev/null 2>&1 || fail "Docker est introuvable."
command -v flock >/dev/null 2>&1 || fail "flock est introuvable."

mkdir -p "$project_root/.deployment"
exec 9>"$project_root/.deployment/operation.lock"
flock -n 9 || fail "Un déploiement ou une restauration est déjà en cours."

export IMAGE_TAG
IMAGE_TAG="$(load_image_tag "$project_root")"
compose=(
  docker compose --env-file "$env_file"
  -f "$project_root/docker-compose.yml"
  -f "$project_root/compose.production.yml"
)
"${compose[@]}" config --quiet
"${compose[@]}" up -d --wait db
"${compose[@]}" exec -T db pg_restore --list < "$backup_file" >/dev/null

printf '%s\n' "ATTENTION: cette restauration remplace intégralement la base PostgreSQL actuelle."
printf 'Archive sélectionnée: %s\n' "$backup_file"
read -r -p 'Saisissez RESTORE pour continuer: ' confirmation
[ "$confirmation" = "RESTORE" ] || fail "Restauration annulée."

"${compose[@]}" stop api web
if ! "${compose[@]}" exec -T db sh -ceu '
  pg_restore \
    --username "$POSTGRES_USER" \
    --dbname postgres \
    --clean \
    --if-exists \
    --create \
    --exit-on-error \
    --no-owner \
    --no-privileges
' < "$backup_file"; then
  fail "La restauration a échoué; API et frontend restent arrêtés."
fi

"${compose[@]}" run --rm --no-deps api alembic upgrade head
"${compose[@]}" up -d --wait api web
printf '%s\n' "Restauration terminée et services redémarrés."
