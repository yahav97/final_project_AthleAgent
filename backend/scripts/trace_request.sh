#!/usr/bin/env bash
# Trace unified AthleAgent system log (backend + Android client events).
#
# Usage:
#   ./backend/scripts/trace_request.sh trace-req-001
#   ./backend/scripts/trace_request.sh --event client_event
#   ./backend/scripts/trace_request.sh --source android

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG_FILE="${ROOT}/logs/athleagent.log"

if [[ ! -f "${LOG_FILE}" ]]; then
  echo "Log file not found: ${LOG_FILE}" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required. Install from https://jqlang.org/" >&2
  exit 1
fi

if [[ "${1:-}" == "--event" ]]; then
  EVENT="${2:?event name required}"
  jq -c "select(.event == \"${EVENT}\")" "${LOG_FILE}"
  exit 0
fi

if [[ "${1:-}" == "--source" ]]; then
  SOURCE="${2:?source required (backend|android)}"
  jq -c "select(.source == \"${SOURCE}\")" "${LOG_FILE}"
  exit 0
fi

REQUEST_ID="${1:?request_id required}"
jq -c "select(.request_id == \"${REQUEST_ID}\")" "${LOG_FILE}"
