#!/usr/bin/env bash

fail() {
  printf 'Erreur: %s\n' "$1" >&2
  return 1
}

read_env_value() {
  local key="$1"
  local env_file="$2"
  [ -f "$env_file" ] || return 1
  awk -v key="$key" '
    index($0, key "=") == 1 {
      value = substr($0, length(key) + 2)
      sub(/\r$/, "", value)
      found = 1
    }
    END { if (found) print value; else exit 1 }
  ' "$env_file"
}

setting_value() {
  local key="$1"
  local env_file="$2"
  local default_value="$3"
  local value="${!key-}"
  if [ -z "$value" ]; then
    value="$(read_env_value "$key" "$env_file" 2>/dev/null || true)"
  fi
  printf '%s\n' "${value:-$default_value}"
}

validate_positive_integer() {
  case "$1" in
    ''|*[!0-9]*|0) fail "$2 doit être un entier strictement positif." ;;
    *) return 0 ;;
  esac
}

resolve_backup_dir() {
  local project_root="$1"
  local requested="$2"
  local candidate resolved
  [ -n "$requested" ] || fail "BACKUP_DIR ne peut pas être vide." || return 1
  case "$requested" in
    /*) candidate="$requested" ;;
    *) candidate="$project_root/$requested" ;;
  esac
  if [ -d "$candidate" ] && [ ! -f "$candidate/.cs2-arbitrage-backups" ] && \
    [ -n "$(find "$candidate" -mindepth 1 -maxdepth 1 -print -quit)" ]; then
    fail "BACKUP_DIR existe, n'est pas vide et ne possède pas le marqueur de sécurité."
    return 1
  fi
  mkdir -p -- "$candidate"
  resolved="$(cd "$candidate" && pwd -P)"
  case "$resolved" in
    /|"$project_root") fail "BACKUP_DIR doit désigner un sous-répertoire dédié." || return 1 ;;
  esac
  if [ ! -f "$resolved/.cs2-arbitrage-backups" ]; then
    printf '%s\n' 'Répertoire réservé aux dumps CS2 Arbitrage Hub.' > \
      "$resolved/.cs2-arbitrage-backups"
  fi
  printf '%s\n' "$resolved"
}

rotate_backups() {
  local backup_dir="$1"
  local retention_days="$2"
  validate_positive_integer "$retention_days" "BACKUP_RETENTION_DAYS" || return 1
  [ -f "$backup_dir/.cs2-arbitrage-backups" ] || {
    fail "Marqueur de sécurité absent dans le répertoire de sauvegarde."
    return 1
  }
  find "$backup_dir" -maxdepth 1 -type f -name 'cs2-*.dump' \
    -mtime "+$retention_days" -delete
}

load_image_tag() {
  local project_root="$1"
  if [ -n "${IMAGE_TAG:-}" ]; then
    printf '%s\n' "$IMAGE_TAG"
  elif [ -f "$project_root/.deployment/current-image-tag" ]; then
    cat "$project_root/.deployment/current-image-tag"
  else
    printf 'current\n'
  fi
}
