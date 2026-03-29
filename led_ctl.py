#!/usr/bin/env python3
import socket, sys, os

SOCKET_PATH = "/tmp/claude-approval-led.sock"

def send(cmd):
    if not os.path.exists(SOCKET_PATH):
        sys.exit(0)
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(SOCKET_PATH)
        s.sendall(cmd.encode())
        s.close()
    except ConnectionRefusedError:
        os.unlink(SOCKET_PATH)

if len(sys.argv) < 2:
    sys.exit(1)
cmd = sys.argv[1]
if cmd == "show" and len(sys.argv) > 2:
    send(f"show {' '.join(sys.argv[2:])}")
elif cmd in ("hide", "quit", "push", "approve", "stats"):
    send(cmd)
else:
    send(cmd)
