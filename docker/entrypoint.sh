#!/bin/bash
set -e

# ── Source ROS2 workspaces ──────────────────────────────────────
# Layer 1: ROS2 base
source /opt/ros/humble/setup.bash

# Layer 2: go2_ros2_sdk workspace (baked into image)
source /opt/go2_ws/install/setup.bash

# ── Build user workspace ────────────────────────────────────────
# Packages in /ros2_ws/src/ (volume-mounted from host ./src/)
cd /ros2_ws
if [ -d "src" ] && [ "$(ls -A src/)" ]; then
    echo "[entrypoint] Building user workspace..."
    colcon build --symlink-install 2>&1 | tail -5
    source /ros2_ws/install/setup.bash
    echo "[entrypoint] User workspace built successfully"
else
    echo "[entrypoint] No user packages found in /ros2_ws/src/"
fi

# ── Create log directory ────────────────────────────────────────
mkdir -p /ros2_ws/logs

# ── Launch services ─────────────────────────────────────────────

# 1. rosbridge — WebSocket bridge for React dashboard
echo "[entrypoint] Starting rosbridge on port 9090..."
ros2 launch rosbridge_server rosbridge_websocket_launch.xml \
    > /ros2_ws/logs/rosbridge.log 2>&1 &

# 2. system_monitor — RPi5 CPU, temperature, fan stats
echo "[entrypoint] Starting system_monitor..."
ros2 run snoopi_system_monitor system_monitor \
    > /ros2_ws/logs/system_monitor.log 2>&1 &

# 3. command_bridge — translates dashboard commands to robot actions
echo "[entrypoint] Starting command_bridge..."
ros2 run snoopi_command_bridge command_bridge \
    > /ros2_ws/logs/command_bridge.log 2>&1 &

# 4. go2_ros2_sdk driver — managed by watchdog (see below)
#    The watchdog pings the robot before launching, retries if unreachable,
#    and restarts the driver if it crashes (WebRTC drops).

# ── Robot connection watchdog ─────────────────────────────────
ROBOT_STATUS_FILE="/ros2_ws/logs/robot_status.json"
DRIVER_PID=""

write_robot_status() {
    local reachable="$1"
    local driver_running="$2"
    local message="$3"
    echo "{\"robot_reachable\": $reachable, \"driver_running\": $driver_running, \"message\": \"$message\", \"timestamp\": \"$(date -Iseconds)\"}" > "$ROBOT_STATUS_FILE"
}

start_driver() {
    echo "[watchdog] Starting go2_driver_node (ROBOT_IP=${ROBOT_IP})..."
    ros2 run go2_robot_sdk go2_driver_node --ros-args \
        -p robot_ip:="${ROBOT_IP}" \
        -p conn_type:="${CONN_TYPE:-webrtc}" \
        -p enable_video:=false \
        > /ros2_ws/logs/go2_sdk.log 2>&1 &
    DRIVER_PID=$!
    write_robot_status true true "Driver started (PID $DRIVER_PID)"
    echo "[watchdog] go2_driver_node started (PID $DRIVER_PID)"
}

robot_watchdog() {
    local check_interval=10
    while true; do
        if ping -c 1 -W 2 "${ROBOT_IP}" > /dev/null 2>&1; then
            # Robot is reachable
            if [ -z "$DRIVER_PID" ] || ! kill -0 "$DRIVER_PID" 2>/dev/null; then
                # Driver not running — start it
                if [ -n "$DRIVER_PID" ]; then
                    echo "[watchdog] Driver (PID $DRIVER_PID) died — restarting..."
                    write_robot_status true false "Driver crashed, restarting..."
                    sleep 5
                fi
                start_driver
            else
                # All good — driver running, robot reachable
                write_robot_status true true "Connected"
            fi
        else
            # Robot not reachable
            if [ -n "$DRIVER_PID" ] && kill -0 "$DRIVER_PID" 2>/dev/null; then
                echo "[watchdog] Robot unreachable — stopping driver (PID $DRIVER_PID)"
                kill "$DRIVER_PID" 2>/dev/null
                wait "$DRIVER_PID" 2>/dev/null || true
                DRIVER_PID=""
                write_robot_status false false "Robot unreachable, driver stopped"
            else
                DRIVER_PID=""
                write_robot_status false false "Robot unreachable"
            fi
        fi
        sleep "$check_interval"
    done
}

# Write initial status and start watchdog
write_robot_status false false "Starting up..."
echo "[entrypoint] Starting robot connection watchdog (ROBOT_IP=${ROBOT_IP:-not set})..."
robot_watchdog &

echo ""
echo "============================================"
echo "  snoopi-ros2 container is running"
echo "  rosbridge:       ws://localhost:9090"
echo "  system_monitor:  /snoopi/system_stats"
echo "  command_bridge:  /snoopi/command"
echo "  robot watchdog:  checks every 10s"
echo "  Logs:            /ros2_ws/logs/"
echo "============================================"
echo ""

# Keep container alive and show combined logs
# If 'docker exec' commands are passed, run them instead
if [ $# -gt 0 ]; then
    exec "$@"
else
    tail -f /ros2_ws/logs/*.log
fi
