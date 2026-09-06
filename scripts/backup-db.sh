#!/usr/bin/env bash
set -Eeuo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
# shellcheck source=lib/backup-common.sh
source "$project_root/scripts/lib/backup-common.sh"

env_file="${ENV_FILE:-$project_root/.env.production}"
[ -f "$env_file" ] || fail "Fichier d'environnement absent: $env_file"
command -v docker >/dev/null 2>&1 || fail "Docker est introuvable."
command -v flock >/dev/null 2>&1 || fail "flock est introuvable."

backup_setting="$(setting_value BACKUP_DIR "$env_file" './backups/postgres')"
retention_days="$(setting_value BACKUP_RETENTION_DAYS "$env_file" '14')"
validate_positive_integer "$retention_days" "BACKUP_RETENTION_DAYS"
backup_dir="$(resolve_backup_dir "$project_root" "$backup_setting")"
exec 8>"$backup_dir/.backup.lock"
flock -n 8 || fail "Une autre sauvegarde est déjà en cours."

compose=(
  docker compose --env-file "$env_file"
  -f "$project_root/docker-compose.yml"
  -f "$project_root/compose.production.yml"
)
"${compose[@]}" config --quiet

umask 077
timestamp="$(date -u '+%Y%m%dT%H%M%SZ')"
backup_file="$backup_dir/cs2-$timestamp-$$.dump"
partial_file="$backup_file.partial"
trap 'rm -f -- "$partial_file"' EXIT

"${compose[@]}" exec -T db sh -ceu '
  pg_dump \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    --format custom \
    --create \
    --no-owner \
    --no-privileges
' > "$partial_file"

"${compose[@]}" exec -T db pg_restore --list < "$partial_file" >/dev/null
mv -- "$partial_file" "$backup_file"
trap - EXIT
rotate_backups "$backup_dir" "$retention_days"
printf 'Sauvegarde créée: %s\n' "$backup_file"
