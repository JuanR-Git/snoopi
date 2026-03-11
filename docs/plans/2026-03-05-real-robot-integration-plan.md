# Real Robot Data Integration — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prepare all container configuration, ROS2 nodes, and documentation so that connecting the Pi to the Go2 Air in the lab results in a fully populated dashboard with real telemetry.

**Architecture:** The go2_ros2_sdk bridge publishes on the same topics as the mock publisher, so no dashboard changes are needed. We update the Docker entrypoint to auto-launch rosbridge + system_monitor + SDK bridge, add a command translator node for sit/stand/estop, configure CycloneDDS for robot discovery, and write a lab setup guide with placeholder values.

**Tech Stack:** ROS2 Humble (Python), Docker, CycloneDDS, go2_ros2_sdk

**Design Doc:** `docs/plans/2026-03-05-real-robot-integration-design.md`

---

### Task 1: Add `psutil` to container pip dependencies

The system_monitor node imports `psutil` to read CPU load. It's listed in `setup.py` but not in the Docker image's pip requirements — meaning `colcon build` succeeds but the node crashes at runtime.

**Files:**
- Modify: `docker/requirements-arm64.txt`

**Step 1: Add psutil to requirements**

Add `psutil` to the end of `docker/requirements-arm64.txt`:

```
psutil
```

**Step 2: Commit**

```bash
git add docker/requirements-arm64.txt
git commit -m "fix: add psutil to container pip deps for system_monitor"
```

> **Note:** The Docker image must be rebuilt on the Pi for this to take effect:
> `[PI] cd ~/snoopi && docker compose build && docker compose up -d`

---

### Task 2: Add `/sys` volume mount to docker-compose.yml

The system_monitor reads Pi temperature from `/sys/class/thermal/thermal_zone0/temp` and fan status from `/sys/class/thermal/cooling_device0/cur_state`. Since the container doesn't have access to the host `/sys` by default, we mount it read-only.

**Files:**
- Modify: `docker-compose.yml`

**Step 1: Add /sys volume**

Add the `/sys` mount to the existing `volumes:` section in `docker-compose.yml`:

```yaml
    volumes:
      # Your ROS2 node source code — edit on host, build inside container
      - ./src:/ros2_ws/src
      # DDS config — edit without rebuilding the image
      - ./docker/cyclonedds.xml:/ros2_ws/cyclonedds.xml:ro
      # Host /sys for system_monitor (RPi5 temp, fan status) — read-only
      - /sys:/sys:ro
```

**Step 2: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: mount /sys read-only for system_monitor thermal access"
```

---

### Task 3: Update CycloneDDS config with robot peer placeholder

CycloneDDS needs to know the robot's IP address to discover its DDS topics over Ethernet. We uncomment the peers section and add a clearly marked placeholder.

**Files:**
- Modify: `docker/cyclonedds.xml`

**Step 1: Update the Discovery section**

Replace the entire `<Discovery>` block:

```xml
    <Discovery>
      <ParticipantIndex>auto</ParticipantIndex>
      <!--
        ┌─────────────────────────────────────────────────────┐
        │  FILL IN BEFORE LAB: Replace <ROBOT_IP> with the    │
        │  Go2 Air's actual IP address.                        │
        │  Expected: 192.168.123.161 (verify in lab)           │
        │  To find it: connect Ethernet, run `arp -a` on Pi    │
        └─────────────────────────────────────────────────────┘
      -->
      <Peers>
        <Peer Address="192.168.123.161"/>
      </Peers>
    </Discovery>
```

**Step 2: Commit**

```bash
git add docker/cyclonedds.xml
git commit -m "feat: enable CycloneDDS peer discovery for robot connection"
```

---

### Task 4: Create the `snoopi_command_bridge` ROS2 package

A new ROS2 Python node that subscribes to `/snoopi/command` (string messages from the dashboard via rosbridge) and translates them to the appropriate robot actions.

**Files:**
- Create: `src/snoopi_command_bridge/package.xml`
- Create: `src/snoopi_command_bridge/setup.py`
- Create: `src/snoopi_command_bridge/setup.cfg`
- Create: `src/snoopi_command_bridge/resource/snoopi_command_bridge`
- Create: `src/snoopi_command_bridge/snoopi_command_bridge/__init__.py`
- Create: `src/snoopi_command_bridge/snoopi_command_bridge/command_bridge.py`

**Step 1: Create package.xml**

```xml
<?xml version="1.0"?>
<?xml-model href="http://download.ros.org/schema/package_format3.xsd" schematypens="http://www.w3.org/2001/XMLSchema"?>
<package format="3">
  <name>snoopi_command_bridge</name>
  <version>0.1.0</version>
  <description>Translates dashboard commands (/snoopi/command) to go2_ros2_sdk actions</description>
  <maintainer email="dev@snoopi.local">snoopi</maintainer>
  <license>MIT</license>

  <exec_depend>rclpy</exec_depend>
  <exec_depend>std_msgs</exec_depend>
  <exec_depend>geometry_msgs</exec_depend>

  <export>
    <build_type>ament_python</build_type>
  </export>
</package>
```

**Step 2: Create setup.py**

```python
from setuptools import find_packages, setup

setup(
    name='snoopi_command_bridge',
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/snoopi_command_bridge']),
        ('share/snoopi_command_bridge', ['package.xml']),
    ],
    install_requires=['setuptools'],
    entry_points={
        'console_scripts': [
            'command_bridge = snoopi_command_bridge.command_bridge:main',
        ],
    },
)
```

**Step 3: Create setup.cfg**

```ini
[develop]
script_dir=$base/lib/snoopi_command_bridge
[install]
install_scripts=$base/lib/snoopi_command_bridge
```

**Step 4: Create resource marker file**

Create empty file at `src/snoopi_command_bridge/resource/snoopi_command_bridge` (required by ament for package discovery).

**Step 5: Create __init__.py**

Create empty file at `src/snoopi_command_bridge/snoopi_command_bridge/__init__.py`.

**Step 6: Create command_bridge.py**

```python
"""
Command bridge: translates dashboard string commands to robot actions.

Subscribes to /snoopi/command (std_msgs/String) from the dashboard via rosbridge.
Translates commands to:
  - "estop" → publishes zero velocity to /cmd_vel (immediate safety stop)
  - "sit"   → calls go2_ros2_sdk sit interface (TBD — see TODO below)
  - "stand" → calls go2_ros2_sdk stand interface (TBD — see TODO below)
"""
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from geometry_msgs.msg import Twist


class CommandBridge(Node):
    def __init__(self):
        super().__init__('command_bridge')

        # Subscribe to dashboard commands (via rosbridge)
        self.create_subscription(String, '/snoopi/command', self._on_command, 10)

        # Publisher for emergency stop — zero velocity to /cmd_vel
        self._cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)

        self.get_logger().info('Command bridge started — listening on /snoopi/command')

    def _on_command(self, msg: String):
        cmd = msg.data.strip().lower()
        self.get_logger().info(f'Received command: "{cmd}"')

        if cmd == 'estop':
            self._execute_estop()
        elif cmd == 'sit':
            self._execute_sit()
        elif cmd == 'stand':
            self._execute_stand()
        else:
            self.get_logger().warn(f'Unknown command: "{cmd}"')

    def _execute_estop(self):
        """Publish zero velocity to /cmd_vel — works regardless of SDK interface."""
        stop = Twist()  # all fields default to 0.0
        self._cmd_vel_pub.publish(stop)
        self.get_logger().info('E-STOP: published zero velocity to /cmd_vel')

    def _execute_sit(self):
        """
        ┌─────────────────────────────────────────────────────────────┐
        │  TODO: Wire to go2_ros2_sdk sit interface.                  │
        │                                                             │
        │  STEPS TO COMPLETE IN LAB:                                  │
        │  1. Run: ros2 topic list                                    │
        │  2. Run: ros2 service list                                  │
        │  3. Find the sit/stand command interface                     │
        │  4. Run: ros2 topic info <topic> -v  (or ros2 service info) │
        │  5. Replace this TODO with the actual publish/service call   │
        │                                                             │
        │  Expected: the SDK may use a topic like /go2_state or a     │
        │  service for mode changes. Check the go2_ros2_sdk README.   │
        └─────────────────────────────────────────────────────────────┘
        """
        self.get_logger().info('SIT command received — SDK interface TBD (see TODO in source)')

    def _execute_stand(self):
        """
        ┌─────────────────────────────────────────────────────────────┐
        │  TODO: Wire to go2_ros2_sdk stand interface.                │
        │  Same discovery steps as _execute_sit() above.              │
        └─────────────────────────────────────────────────────────────┘
        """
        self.get_logger().info('STAND command received — SDK interface TBD (see TODO in source)')


def main():
    rclpy.init()
    node = CommandBridge()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
```

**Step 7: Commit**

```bash
git add src/snoopi_command_bridge/
git commit -m "feat: add command_bridge node — translates dashboard commands to robot actions"
```

---

### Task 5: Update entrypoint to auto-launch services

The entrypoint currently only sources workspaces and runs `exec "$@"`. We need it to:
1. Build user packages (`colcon build`)
2. Launch rosbridge (background)
3. Launch system_monitor (background)
4. Launch go2_ros2_sdk bridge (background)
5. Launch command_bridge (background)
6. Tail logs so `docker logs` shows everything

**Files:**
- Modify: `docker/entrypoint.sh`

**Step 1: Rewrite entrypoint.sh**

```bash
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
```

**Step 2: Commit**

```bash
git add docker/entrypoint.sh
git commit -m "feat: entrypoint auto-launches rosbridge, system_monitor, command_bridge, SDK"
```

---

### Task 6: Update docker-compose CMD

The current `CMD ["tail", "-f", "/dev/null"]` in the Dockerfile keeps the container alive. With our new entrypoint handling the tail, we need docker-compose to not override the entrypoint behavior.

**Files:**
- Modify: `docker-compose.yml`

**Step 1: Remove the default CMD override if present, and add healthcheck**

The `docker-compose.yml` doesn't currently specify a `command:`, so the Dockerfile `CMD` applies. However, the Dockerfile has `CMD ["tail", "-f", "/dev/null"]` which gets passed as arguments to the entrypoint. Our new entrypoint checks `if [ $# -gt 0 ]` and runs the CMD. We need to remove the Dockerfile CMD so the entrypoint's `else` branch (tail logs) runs instead.

Update `docker-compose.yml` to explicitly set an empty command:

```yaml
    # Override Dockerfile CMD — entrypoint handles lifecycle (auto-launches services + tails logs)
    command: []
```

**Step 2: Commit**

```bash
git add docker-compose.yml
git commit -m "fix: clear Dockerfile CMD so entrypoint manages container lifecycle"
```

---

### Task 7: Write the lab setup guide

A step-by-step document for the lab visit with all placeholder values clearly marked.

**Files:**
- Create: `docs/lab-setup-guide.md`

**Step 1: Write the guide**

```markdown
# Lab Setup Guide — Connecting Pi to Go2 Air

> **Purpose:** Step-by-step instructions for connecting the RPi5 to the Go2 Air
> robot in the lab and verifying the full telemetry pipeline.

---

## Placeholder Values

**Fill these in when you're in the lab.** All placeholders are marked with angle brackets.

| Placeholder | Expected Value | Actual Value |
|---|---|---|
| `<ROBOT_IP>` | `192.168.123.161` (from SDK docs) | __________ |
| `<ROBOT_SUBNET>` | `192.168.123.0/24` | __________ |
| `<PI_ROBOT_SUBNET_IP>` | `192.168.123.100` (pick any unused) | __________ |
| `<PI_ETH_INTERFACE>` | `eth0` or `enx...` (run `ip link show`) | __________ |
| `<PI_WIFI_IP>` | `192.168.0.41` (current home network) | __________ |

---

## Prerequisites

- RPi5 powered on and accessible via SSH over WiFi
- Go2 Air powered on (wait for startup sound to finish)
- Ethernet cable connecting Pi to Go2 Air
- Windows laptop on the same WiFi network as the Pi

---

## Step 1: Identify the Pi's Ethernet Interface

```bash
[PI] ip link show
```

Look for an interface that is NOT `lo` (loopback) or `wlan0` (WiFi). It will likely be `eth0` or `enxXXXXXX`. This is your `<PI_ETH_INTERFACE>`.

---

## Step 2: Configure Static IP on the Robot's Subnet

The Go2 Air uses the `192.168.123.0/24` subnet. The Pi needs an IP on this subnet to communicate.

```bash
[PI] sudo ip addr add <PI_ROBOT_SUBNET_IP>/24 dev <PI_ETH_INTERFACE>
[PI] sudo ip link set <PI_ETH_INTERFACE> up
```

**Example (with expected values):**
```bash
[PI] sudo ip addr add 192.168.123.100/24 dev eth0
[PI] sudo ip link set eth0 up
```

> **Note:** This is temporary — it resets on reboot. To make it permanent,
> create a netplan config (documented at the end of this guide).

---

## Step 3: Verify Connectivity

```bash
[PI] ping <ROBOT_IP> -c 3
```

**Expected:** 3 replies with low latency (<1ms for Ethernet).

**If ping fails:**
- Check cable is plugged in on both ends
- Run `ip addr show <PI_ETH_INTERFACE>` — confirm IP is assigned
- Try `arp -a` to see what devices are on the network
- The robot IP might differ from expected — check go2_ros2_sdk docs

---

## Step 4: Update CycloneDDS Peer (if needed)

If `<ROBOT_IP>` differs from `192.168.123.161`, edit the DDS config:

```bash
[PI] nano ~/snoopi/docker/cyclonedds.xml
```

Change the peer address to match the actual robot IP:
```xml
<Peer Address="<ROBOT_IP>"/>
```

---

## Step 5: Rebuild and Start the Container

```bash
[PI] cd ~/snoopi
[PI] git pull
[PI] docker compose build
[PI] docker compose up -d
```

Wait 30-60 seconds for all services to start, then check logs:

```bash
[PI] docker logs snoopi-ros2
```

**Expected:** Messages showing rosbridge, system_monitor, command_bridge, and go2_sdk all starting. The SDK may show errors if the robot connection isn't established yet — that's normal, it will retry.

---

## Step 6: Verify ROS2 Topic Discovery

```bash
[PI] docker exec -it snoopi-ros2 ros2 topic list
```

**Expected topics from the robot:**
```
/utlidar/battery
/imu/data
/joint_states
/scan
/cloud
/camera/image_raw
/odometry/filtered
```

**Expected topics from snoopi nodes:**
```
/snoopi/system_stats
/snoopi/command
/cmd_vel
```

**If robot topics are missing:**
- Check `docker logs snoopi-ros2` for SDK errors
- Verify Ethernet ping still works: `ping <ROBOT_IP>`
- Check DDS config: `docker exec snoopi-ros2 cat /ros2_ws/cyclonedds.xml`
- Try restarting: `docker compose restart`

---

## Step 7: Verify Topic Data

```bash
[PI - container] ros2 topic echo /utlidar/battery --once
[PI - container] ros2 topic echo /imu/data --once
[PI - container] ros2 topic echo /snoopi/system_stats --once
```

Each should print one message. If `/utlidar/battery` shows real battery data (not the mock's 100% drain pattern), the real robot is connected.

---

## Step 8: Start the Backend and Frontend

```bash
# Terminal 2
[PI] cd ~/snoopi/backend && source venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000

# Terminal 3
[PI] cd ~/snoopi/ui && npm install && npm run dev -- --host 0.0.0.0
```

---

## Step 9: Verify Dashboard

```
[BROWSER] http://<PI_WIFI_IP>:5173
Login: john / snoopi-john-2026
```

**Check each card:**

| Card | Expected |
|---|---|
| Battery | Real battery % (should be 80-100% if robot is charged) |
| Temperature | Real robot internal temp |
| IMU | Z-acceleration ~9.81 m/s² (if robot is standing still) |
| System Health | Pi CPU %, Pi temperature, fan status |
| Telemetry graphs | All 4 graphs accumulating data points |
| rosbridge indicator | Connected (green) |

---

## Step 10: Document Findings

Run these commands and save the output:

```bash
[PI - container] ros2 topic list > /ros2_ws/logs/topic_list.txt
[PI - container] ros2 topic info /utlidar/battery -v > /ros2_ws/logs/battery_info.txt
[PI - container] ros2 service list > /ros2_ws/logs/service_list.txt
```

**Important for command_bridge:** Note any topics or services that look like they control robot mode (sit/stand). Look for:
- `/go2_state` or similar
- Any service with "mode" or "command" in the name
- Check: `ros2 service type <service_name>` for the message type

---

## Appendix: Make Static IP Permanent (Netplan)

To survive reboots, create a netplan config:

```bash
[PI] sudo nano /etc/netplan/99-robot-ethernet.yaml
```

```yaml
network:
  version: 2
  ethernets:
    <PI_ETH_INTERFACE>:
      addresses:
        - <PI_ROBOT_SUBNET_IP>/24
      # No gateway — robot subnet is local only, internet goes through WiFi
```

```bash
[PI] sudo netplan apply
```

---

## Troubleshooting

| Problem | Likely Cause | Fix |
|---|---|---|
| No robot topics in `ros2 topic list` | DDS can't discover robot | Check Ethernet, ping, CycloneDDS peer config |
| SDK launch crashes | Robot not reachable or firmware mismatch | Check logs: `cat /ros2_ws/logs/go2_sdk.log` |
| System monitor shows 0 CPU | psutil not installed | Rebuild image: `docker compose build` |
| System monitor shows 0 temp | /sys not mounted | Check `docker inspect snoopi-ros2` for volumes |
| Dashboard shows dashes | rosbridge not connected | Check `ws://<PI_WIFI_IP>:9090` is reachable |
| Graphs not updating | Data not flowing through rosbridge | Check `ros2 topic echo` inside container first |
```

**Step 2: Commit**

```bash
git add docs/lab-setup-guide.md
git commit -m "docs: add lab setup guide with placeholder values for robot connection"
```

---

### Task 8: Final verification — build test on Pi

After pushing all changes, verify that the container builds and starts correctly on the Pi (without the robot connected).

**Step 1: Push all changes**

```bash
[WINDOWS] git push
```

**Step 2: Pull and rebuild on Pi**

```bash
[PI] cd ~/snoopi && git pull
[PI] docker compose build
[PI] docker compose up -d
```

**Step 3: Check container logs**

```bash
[PI] docker logs snoopi-ros2
```

**Expected output:**
- `[entrypoint] Building user workspace...` — should succeed
- `[entrypoint] Starting rosbridge on port 9090...` — should start
- `[entrypoint] Starting system_monitor...` — should start
- `[entrypoint] Starting command_bridge...` — should start
- `[entrypoint] Starting go2_ros2_sdk bridge...` — may show errors (no robot connected) — this is expected
- `snoopi-ros2 container is running` banner

**Step 4: Verify system_monitor is publishing**

```bash
[PI] docker exec snoopi-ros2 ros2 topic echo /snoopi/system_stats --once
```

**Expected:** JSON with real Pi CPU %, temperature, and fan status.

**Step 5: Verify command_bridge is listening**

```bash
[PI] docker exec snoopi-ros2 ros2 topic list | grep snoopi
```

**Expected:**
```
/snoopi/command
/snoopi/system_stats
```

**Step 6: Verify dashboard system health**

```
[BROWSER] http://192.168.0.41:5173
```

System Health card should now show real Pi CPU % and temperature instead of dashes.

**Step 7: Commit verification results**

After confirming everything works, update `docs/testing-log.md` with results.
