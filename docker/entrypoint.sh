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

# 4. go2_ros2_sdk bridge — robot telemetry and control
#    This launches the full SDK bridge (driver, LiDAR, camera, etc.)
#    It will fail gracefully if the robot is not connected via Ethernet.
echo "[entrypoint] Starting go2_ros2_sdk bridge..."
ros2 launch go2_robot_sdk robot.launch.py \
    > /ros2_ws/logs/go2_sdk.log 2>&1 &

echo ""
echo "============================================"
echo "  snoopi-ros2 container is running"
echo "  rosbridge:      ws://localhost:9090"
echo "  system_monitor:  /snoopi/system_stats"
echo "  command_bridge:  /snoopi/command"
echo "  go2_sdk:        /utlidar/battery, /imu/data, ..."
echo "  Logs:           /ros2_ws/logs/"
echo "============================================"
echo ""

# Keep container alive and show combined logs
# If 'docker exec' commands are passed, run them instead
if [ $# -gt 0 ]; then
    exec "$@"
else
    tail -f /ros2_ws/logs/*.log
fi
