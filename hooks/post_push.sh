#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
"$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/led_ctl.py" push 2>/dev/null &
