#!/usr/bin/env bash
set -euo pipefail

PID_FILE="${XDG_RUNTIME_DIR:-/tmp}/polybar-yad-calendar.pid"
DETAILS_FILE="${XDG_RUNTIME_DIR:-/tmp}/polybar-yad-calendar-details.txt"
LIST_FILE="${XDG_RUNTIME_DIR:-/tmp}/polybar-yad-calendar-list.txt"
STATE_FILE="${XDG_RUNTIME_DIR:-/tmp}/polybar-yad-calendar-state"
XID_FILE="${XDG_RUNTIME_DIR:-/tmp}/polybar-yad-calendar.xid"
PYTHON_BIN="$HOME/.config/polybar/scripts/.venv/bin/python"
AGENDA_SCRIPT="$HOME/.config/polybar/scripts/google_agenda_polybar.py"
CAL_OPACITY="${CAL_OPACITY:-0.92}"

apply_opacity() {
  local xid="${1:-}"
  if [[ -z "$xid" ]] || ! command -v xprop >/dev/null 2>&1; then
    return
  fi
  local opacity_hex
  opacity_hex="$(python3 - <<'PY' "$CAL_OPACITY"
import sys
try:
    v=float(sys.argv[1])
except Exception:
    v=0.92
v=max(0.05, min(1.0, v))
print(hex(int(v * 0xFFFFFFFF)))
PY
)"
  xprop -id "$xid" -f _NET_WM_WINDOW_OPACITY 32c -set _NET_WM_WINDOW_OPACITY "$opacity_hex" >/dev/null 2>&1 || true
}

if [[ "${1:-}" == "--toggle-list" ]]; then
  current="1"
  [[ -f "$STATE_FILE" ]] && current="$(cat "$STATE_FILE" 2>/dev/null || echo 1)"
  if [[ "$current" == "1" ]]; then
    echo "0" >"$STATE_FILE"
    notify-send "Calendario" "Coluna de agenda: oculta"
  else
    echo "1" >"$STATE_FILE"
    notify-send "Calendario" "Coluna de agenda: visivel"
  fi
  exit 0
fi

SHOW_LIST="1"
[[ -f "$STATE_FILE" ]] && SHOW_LIST="$(cat "$STATE_FILE" 2>/dev/null || echo 1)"

if [[ -f "$PID_FILE" ]]; then
  mapfile -t old_pids <"$PID_FILE" || true
  still_running=0
  for old_pid in "${old_pids[@]}"; do
    if [[ -n "${old_pid:-}" ]] && kill -0 "$old_pid" 2>/dev/null; then
      kill "$old_pid" 2>/dev/null || true
      still_running=1
    fi
  done
  if [[ "$still_running" -eq 1 ]]; then
    rm -f "$PID_FILE"
    exit 0
  fi
  rm -f "$PID_FILE"
fi

"$PYTHON_BIN" "$AGENDA_SCRIPT" \
  --mode details \
  --details-date-format "%Y-%m-%d" \
  --cache-ttl 1800 >"$DETAILS_FILE" 2>/dev/null || true

"$PYTHON_BIN" "$AGENDA_SCRIPT" \
  --mode list7 \
  --list-max-len 30 \
  --cache-ttl 1800 >"$LIST_FILE" 2>/dev/null || true

KEY="$(date +%s)"

rows=()
if [[ -s "$LIST_FILE" ]]; then
  while IFS=$'\t' read -r date_col desc_col full_col; do
    [[ -z "${date_col:-}" ]] && continue
    rows+=("$date_col" "$desc_col" "$full_col")
  done <"$LIST_FILE"
fi
if [[ "${#rows[@]}" -eq 0 ]]; then
  rows=("—" "Sem eventos nos proximos 7 dias." "Sem eventos nos proximos 7 dias.")
fi

if [[ "$SHOW_LIST" == "1" ]]; then
  yad --plug="$KEY" --tabnum=1 \
    --calendar \
    --date-format="%Y-%m-%d" \
    --details="$DETAILS_FILE" \
    --show-weeks \
    --width=520 \
    --height=520 >/dev/null 2>&1 &
  CAL_PID="$!"

  yad --plug="$KEY" --tabnum=2 \
    --list \
    --column="Data" \
    --column="Evento" \
    --column="Tooltip" \
    --hide-column=3 \
    --tooltip-column=3 \
    --no-click \
    --grid-lines=both \
    --width=300 \
    --height=520 \
    "${rows[@]}" >/dev/null 2>&1 &
  LIST_PID="$!"

  yad --paned \
    --key="$KEY" \
    --orient=hor \
    --splitter=460 \
    --focused=1 \
    --width=760 \
    --height=560 \
    --fixed \
    --title="Calendario + Agenda" \
    --mouse \
    --close-on-unfocus \
    --skip-taskbar \
    --on-top \
    --sticky \
    --print-xid="$XID_FILE" >/dev/null 2>&1 &
  PANED_PID="$!"
  sleep 0.12
  apply_opacity "$(cat "$XID_FILE" 2>/dev/null || true)"
  printf "%s\n%s\n%s\n" "$PANED_PID" "$CAL_PID" "$LIST_PID" >"$PID_FILE"
else
  yad \
    --calendar \
    --date-format="%Y-%m-%d" \
    --details="$DETAILS_FILE" \
    --show-weeks \
    --width=520 \
    --height=560 \
    --fixed \
    --title="Calendario" \
    --mouse \
    --close-on-unfocus \
    --skip-taskbar \
    --on-top \
    --sticky \
    --print-xid="$XID_FILE" >/dev/null 2>&1 &
  CAL_ONLY_PID="$!"
  sleep 0.12
  apply_opacity "$(cat "$XID_FILE" 2>/dev/null || true)"
  printf "%s\n" "$CAL_ONLY_PID" >"$PID_FILE"
fi
