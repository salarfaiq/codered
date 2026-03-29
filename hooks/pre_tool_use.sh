#!/bin/bash
echo "$(date): PRE_TOOL_USE FIRED" >> /tmp/claude-led-debug.log
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TAB_HINT="$(basename "$PWD")"
"$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/led_ctl.py" show "$TAB_HINT" >> /tmp/claude-led-debug.log 2>&1
