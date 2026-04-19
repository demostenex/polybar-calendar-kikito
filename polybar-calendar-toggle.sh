#!/usr/bin/env bash
# Abre/fecha a janela GTK do calendário.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
[ -x "$PYTHON_BIN" ] || PYTHON_BIN="$(command -v python3)"

JANELA="$SCRIPT_DIR/janela_calendario.py"
PID_FILE="${XDG_RUNTIME_DIR:-/tmp}/polybar-calendar.pid"

# Fecha janela se já estiver aberta
if [[ -f "$PID_FILE" ]]; then
  mapfile -t pids <"$PID_FILE" || true
  em_execucao=0
  for pid in "${pids[@]}"; do
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      em_execucao=1
    fi
  done
  rm -f "$PID_FILE"
  [[ "$em_execucao" -eq 1 ]] && exit 0
fi

# Abre a janela GTK
NO_AT_BRIDGE=1 "$PYTHON_BIN" "$JANELA" &
echo "$!" > "$PID_FILE"
