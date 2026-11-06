#!/usr/bin/env bash
# Execute one Product Hunt -> OmniRoute -> verified Notion READY production run.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
if [[ ! -f .env || -L .env ]]; then
  echo "Missing private .env file." >&2
  exit 2
fi
chmod 600 .env

for arg in "$@"; do
  case "$arg" in
    --demo|--fixture|--write-draft|--publish|sync-cms)
      echo "Unsupported production mode or channel-delivery command." >&2
      exit 2
      ;;
  esac
done

# Find the unique user-defined network attached to the existing OmniRoute container.
if [[ -z "${PRODUCTHUNT_OMNIROUTE_NETWORK:-}" ]]; then
  docker_networks="$(docker inspect --type container omniroute \
    --format '{{range $name, $_ := .NetworkSettings.Networks}}{{println $name}}{{end}}')"
  candidates=()
  while IFS= read -r network; do
    if [[ -n "$network" && "$network" != "bridge" && "$network" != "host" && "$network" != "none" ]]; then
      candidates+=("$network")
    fi
  done <<< "$docker_networks"
  if (( ${#candidates[@]} != 1 )); then
    echo "Cannot choose a unique Docker network attached to OmniRoute." >&2
    exit 2
  fi
  PRODUCTHUNT_OMNIROUTE_NETWORK="${candidates[0]}"
fi
export PRODUCTHUNT_OMNIROUTE_NETWORK
docker network inspect "$PRODUCTHUNT_OMNIROUTE_NETWORK" >/dev/null

mkdir -p data output
if [[ ! -w data || ! -w output ]]; then
  echo "Service user cannot write data/ or output/." >&2
  exit 2
fi

# Prevent overlapping timer/manual runs and concurrent Notion writes.
exec 9>data/.producthunt-run.lock
if ! flock -n 9; then
  echo "Another Product Hunt run is active; skipping overlap." >&2
  exit 75
fi

compose=(docker compose -f compose.yaml -f compose.omniroute.yaml)
# Images are built only during deployment, never in the daily timer.
"${compose[@]}" run --rm --no-deps producthunt run "$@"
