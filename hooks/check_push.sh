#!/bin/bash
# Check if the tool input contains "git push" and record it
if echo "$CLAUDE_TOOL_INPUT" | grep -q "git push"; then
    SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
    "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/led_ctl.py" push 2>/dev/null &
fi
