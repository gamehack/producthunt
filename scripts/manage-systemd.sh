#!/usr/bin/env bash
# Install/status/uninstall the standalone Product Hunt daily timer.
set -euo pipefail

action="${1:-}"
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
service="producthunt-daily.service"
timer="producthunt-daily.timer"
unit_dir="/etc/systemd/system"
schedule="*-*-* 17:00:00 Asia/Shanghai"

usage() {
  echo "Usage: sudo bash scripts/manage-systemd.sh {install|status|uninstall}" >&2
  exit 2
}
[[ "$action" == "install" || "$action" == "status" || "$action" == "uninstall" ]] || usage

if (( EUID != 0 )); then
  echo "Please run with sudo." >&2
  exit 2
fi

case "$action" in
  install)
    if [[ ! "$project_dir" =~ ^/[a-zA-Z0-9_./-]+$ ]]; then
      echo "Unsupported project path." >&2
      exit 2
    fi
    run_user="${PRODUCTHUNT_RUN_USER:-${SUDO_USER:-ubuntu}}"
    if ! [[ "$run_user" =~ ^[a-z_][a-z0-9_-]*[$]?$ ]] ||
       [[ "$run_user" == "root" ]] || ! id "$run_user" >/dev/null 2>&1; then
      echo "Choose an existing non-root service user." >&2
      exit 2
    fi
    [[ -f "$project_dir/.env" && ! -L "$project_dir/.env" ]] || {
      echo "Missing private .env." >&2; exit 2;
    }
    chmod 600 "$project_dir/.env"
    for executable in systemctl systemd-analyze docker flock runuser sed; do
      command -v "$executable" >/dev/null || { echo "Missing executable: $executable" >&2; exit 2; }
    done
    systemd-analyze calendar "$schedule" >/dev/null
    runuser -u "$run_user" -- test -r "$project_dir/.env"
    runuser -u "$run_user" -- docker info >/dev/null
    runuser -u "$run_user" -- docker compose version >/dev/null
    mkdir -p "$project_dir/data" "$project_dir/output"
    chown "$run_user:$run_user" "$project_dir/data" "$project_dir/output"
    chmod 700 "$project_dir/data" "$project_dir/output"
    runuser -u "$run_user" -- test -w "$project_dir/data"
    runuser -u "$run_user" -- test -w "$project_dir/output"
    sed -e "s|@PROJECT_DIR@|$project_dir|g" -e "s|@RUN_USER@|$run_user|g" \
      "$project_dir/deploy/systemd/$service.in" > "$unit_dir/$service"
    install -m 0644 "$project_dir/deploy/systemd/$timer" "$unit_dir/$timer"
    chmod 0644 "$unit_dir/$service"
    systemd-analyze verify "$unit_dir/$service" "$unit_dir/$timer"
    systemctl daemon-reload
    systemctl enable --now "$timer"
    systemctl list-timers --all "$timer" --no-pager
    echo "Timer installed. No immediate production run was requested."
    ;;
  status)
    systemctl status "$timer" --no-pager --full || true
    systemctl list-timers --all "$timer" --no-pager
    systemctl status "$service" --no-pager --full || true
    ;;
  uninstall)
    systemctl disable --now "$timer" || true
    if systemctl is-active --quiet "$service"; then
      echo "A production run is active; future triggers disabled without interrupting it."
    fi
    rm -f "$unit_dir/$timer" "$unit_dir/$service"
    systemctl daemon-reload
    systemctl reset-failed "$service" || true
    echo "Timer removed. .env, database and article output were left untouched."
    ;;
esac
