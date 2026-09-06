#!/usr/bin/env bash
set -Eeuo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
# shellcheck source=../lib/backup-common.sh
source "$project_root/scripts/lib/backup-common.sh"
test_root="$(mktemp -d "$project_root/.backup-test.XXXXXX")"
cleanup() {
  case "$test_root" in
    "$project_root"/.backup-test.*) rm -rf -- "$test_root" ;;
    *) fail "Refus de nettoyer un chemin de test inattendu: $test_root" ;;
  esac
}
trap cleanup EXIT

if resolve_backup_dir "$test_root" / >/dev/null 2>&1; then
  fail "La racine du système ne doit jamais être acceptée."
fi

mkdir "$test_root/not-dedicated"
touch "$test_root/not-dedicated/existing.txt"
if resolve_backup_dir "$test_root" "$test_root/not-dedicated" >/dev/null 2>&1; then
  fail "Un répertoire non vide sans marqueur ne doit jamais être accepté."
fi

backup_dir="$(resolve_backup_dir "$test_root" backups/postgres)"
touch "$backup_dir/cs2-old.dump" "$backup_dir/cs2-recent.dump" "$backup_dir/unrelated.txt"
touch -d '40 days ago' "$backup_dir/cs2-old.dump" "$backup_dir/unrelated.txt"
rotate_backups "$backup_dir" 30
[ ! -e "$backup_dir/cs2-old.dump" ] || fail "Une ancienne sauvegarde devait être supprimée."
[ -e "$backup_dir/cs2-recent.dump" ] || fail "La sauvegarde récente doit être conservée."
[ -e "$backup_dir/unrelated.txt" ] || fail "Un fichier non géré ne doit jamais être supprimé."

if rotate_backups "$backup_dir" invalid >/dev/null 2>&1; then
  fail "Une rétention invalide ne doit jamais être acceptée."
fi

env_file="$test_root/test.env"
printf 'BACKUP_RETENTION_DAYS=21\n' > "$env_file"
[ "$(setting_value BACKUP_RETENTION_DAYS "$env_file" 14)" = "21" ] || \
  fail "La lecture sûre du fichier d'environnement a échoué."
printf '%s\n' "Tests des helpers de sauvegarde réussis."
