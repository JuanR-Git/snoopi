#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# Snoopi Auto-Start Setup
# Run once on the RPi5 to configure:
#   1. Persistent Ethernet IP for robot connection (netplan)
#   2. FastAPI backend systemd service
#   3. React frontend systemd service
#
# Usage:
#   [PI] cd ~/snoopi && sudo bash scripts/setup-pi-autostart.sh
#
# After running, reboot and everything starts automatically.
# ═══════════════════════════════════════════════════════════════════
set -e

# ── Check root ────────────────────────────────────────────────────
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Run with sudo"
    echo "  sudo bash scripts/setup-pi-autostart.sh"
    exit 1
fi

# ── Auto-detect settings ─────────────────────────────────────────
# Find the real user (not root from sudo)
PI_USER="${SUDO_USER:-$(whoami)}"
PI_HOME=$(eval echo "~$PI_USER")

echo "=== Snoopi Auto-Start Setup ==="
echo "  User:      $PI_USER"
echo "  Home:      $PI_HOME"
echo "  Repo:      $PI_HOME/snoopi"
echo ""

# Detect Ethernet interface (not lo, wlan, docker, tailscale, veth)
ETH_IFACE=$(ip -o link show | awk -F': ' '{print $2}' | grep -vE '^(lo|wlan|docker|tailscale|veth|br-)' | head -1)
if [ -z "$ETH_IFACE" ]; then
    echo "ERROR: No Ethernet interface found"
    echo "  Available interfaces:"
    ip -o link show | awk -F': ' '{print "    " $2}'
    exit 1
fi
echo "  Ethernet:  $ETH_IFACE"

# Detect npm path
NPM_PATH=$(which npm 2>/dev/null || echo "")
if [ -z "$NPM_PATH" ]; then
    echo "ERROR: npm not found. Install Node.js first."
    exit 1
fi
echo "  npm:       $NPM_PATH"

# Verify paths exist
if [ ! -f "$PI_HOME/snoopi/backend/venv/bin/uvicorn" ]; then
    echo "ERROR: Backend venv not found at $PI_HOME/snoopi/backend/venv/bin/uvicorn"
    echo "  Create it: cd ~/snoopi/backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi
if [ ! -f "$PI_HOME/snoopi/ui/package.json" ]; then
    echo "ERROR: Frontend not found at $PI_HOME/snoopi/ui/package.json"
    exit 1
fi
echo ""

# ── 1. Netplan — persistent Ethernet IP ──────────────────────────
# Assigns 192.168.123.100/24 to the Ethernet interface so the Pi
# can always reach the Go2 Air robot at 192.168.123.161.
# No gateway — robot subnet is local-only; internet routes via WiFi.
NETPLAN_FILE="/etc/netplan/99-robot-ethernet.yaml"

echo "[1/3] Creating netplan config: $NETPLAN_FILE"
cat > "$NETPLAN_FILE" << EOF
# Snoopi: static IP for Go2 Air robot connection
# Robot is at 192.168.123.161, Pi is at 192.168.123.100
network:
  version: 2
  renderer: networkd
  ethernets:
    $ETH_IFACE:
      addresses:
        - 192.168.123.100/24
      # No gateway — robot subnet is point-to-point only.
      # Internet traffic routes through WiFi (wlan0).
EOF

chmod 600 "$NETPLAN_FILE"
echo "  Applying netplan..."
netplan apply 2>&1 || echo "  WARNING: netplan apply had warnings (usually harmless)"
echo "  Done. $ETH_IFACE will get 192.168.123.100/24 on every boot."
echo ""

# ── 2. systemd — FastAPI backend ─────────────────────────────────
# Starts uvicorn using the venv's binary directly (no shell activation).
BACKEND_SERVICE="/etc/systemd/system/snoopi-backend.service"

echo "[2/3] Creating systemd service: $BACKEND_SERVICE"
cat > "$BACKEND_SERVICE" << EOF
[Unit]
Description=Snoopi FastAPI Backend
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$PI_USER
Group=$PI_USER
WorkingDirectory=$PI_HOME/snoopi/backend
ExecStart=$PI_HOME/snoopi/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
echo "  Done."
echo ""

# ── 3. systemd — React frontend (Vite dev server) ────────────────
# Runs the Vite dev server. For MVP this is simpler than a production
# build + nginx. The Pi has 16GB RAM so the overhead is negligible.
FRONTEND_SERVICE="/etc/systemd/system/snoopi-frontend.service"

echo "[3/3] Creating systemd service: $FRONTEND_SERVICE"
cat > "$FRONTEND_SERVICE" << EOF
[Unit]
Description=Snoopi React Dashboard
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$PI_USER
Group=$PI_USER
WorkingDirectory=$PI_HOME/snoopi/ui
ExecStart=$NPM_PATH run dev -- --host 0.0.0.0
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
echo "  Done."
echo ""

# ── Enable and start services ────────────────────────────────────
echo "Enabling services..."
systemctl daemon-reload
systemctl enable snoopi-backend.service
systemctl enable snoopi-frontend.service

echo "Starting services..."
systemctl start snoopi-backend.service
systemctl start snoopi-frontend.service

echo ""
echo "=== Verification ==="
echo ""

# Check Ethernet IP
echo "Ethernet ($ETH_IFACE):"
ip addr show "$ETH_IFACE" | grep "inet " | awk '{print "  " $2}'
echo ""

# Check services
echo "Services:"
systemctl is-active snoopi-backend.service  | xargs -I{} echo "  snoopi-backend:  {}"
systemctl is-active snoopi-frontend.service | xargs -I{} echo "  snoopi-frontend: {}"
echo ""

# Check Docker
if docker ps --format '{{.Names}}' | grep -q snoopi-ros2; then
    echo "Docker: snoopi-ros2 is running"
else
    echo "Docker: snoopi-ros2 is NOT running (start with: cd ~/snoopi && docker compose up -d)"
fi
echo ""

echo "=== Setup Complete ==="
echo ""
echo "On reboot, all services start automatically:"
echo "  - Ethernet IP 192.168.123.100/24 on $ETH_IFACE (netplan)"
echo "  - FastAPI backend on port 8000 (systemd)"
echo "  - React dashboard on port 5173 (systemd)"
echo "  - Docker container snoopi-ros2 (docker restart policy)"
echo ""
echo "Useful commands:"
echo "  sudo systemctl status snoopi-backend"
echo "  sudo systemctl status snoopi-frontend"
echo "  journalctl -u snoopi-backend -f        # tail backend logs"
echo "  journalctl -u snoopi-frontend -f       # tail frontend logs"
echo "  sudo systemctl restart snoopi-backend   # restart backend"
echo "  sudo systemctl restart snoopi-frontend  # restart frontend"
echo ""
echo "Test with: sudo reboot"
