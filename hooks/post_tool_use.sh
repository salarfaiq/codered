#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
echo "$(date): HOOK FIRED - hide" >> /tmp/claude-led-debug.log
"$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/led_ctl.py" hide >> /tmp/claude-led-debug.log 2>&1 &
