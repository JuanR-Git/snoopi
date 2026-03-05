# Real Robot Data Integration — Design Document

**Date:** March 5, 2026
**Milestone:** 2 — Hardware Connection & Telemetry
**Branch:** `feature/docker-environment-setup`

---

## 1. Goal

Prepare all code and configuration so that when the Pi is connected to the Go2 Air via Ethernet in the lab, the dashboard populates with real robot telemetry — and the Pi's own health stats (CPU, temp, fan) also appear. The aim is to minimize lab debugging by getting everything ready on the dev side first.

## 2. Current State

| Component | Status |
|---|---|
| Mock publisher (`snoopi_mock`) | Working — publishes fake battery, IMU, joint data on real topic names |
| System monitor (`snoopi_system_monitor`) | Code exists but never built/run in container |
| Dashboard subscriptions | Working — subscribes to `/utlidar/battery`, `/imu/data`, `/snoopi/system_stats` via rosbridge |
| go2_ros2_sdk | Baked into Docker image at `/opt/go2_ws/` — never launched |
| Command bridge | Does not exist — dashboard publishes to `/snoopi/command` but nothing translates to SDK |
| CycloneDDS | Configured for auto-discovery, no robot peer specified |
| Container startup | Entrypoint sources workspaces but launches nothing automatically |

## 3. Key Design Decision

The mock publisher was intentionally built to publish on the **same topic names** with the **same message types** as the real robot SDK. This means **zero dashboard code changes** are needed for telemetry. The work is entirely on the container/ROS2 side.

## 4. What We're Building

### 4.1 Container Auto-Launch (entrypoint.sh)

Update the Docker entrypoint to automatically start three background processes:

1. **rosbridge** — WebSocket bridge (always needed)
2. **system_monitor** — Pi health stats (always needed)
3. **go2_ros2_sdk bridge** — Robot telemetry (launched for real robot)

All processes log to `/ros2_ws/logs/`. The entrypoint foreground process tails the logs so `docker logs snoopi-ros2` shows combined output.

The mock publisher is **not** auto-launched — run it manually for dev testing only. Real SDK and mock publisher never run simultaneously (they publish on the same topics).

### 4.2 System Monitor in Container

The `snoopi_system_monitor` node reads Pi hardware stats:
- **CPU:** `psutil.cpu_percent()`
- **Temperature:** `/sys/class/thermal/thermal_zone0/temp`
- **Fan:** `/sys/class/thermal/cooling_device0/cur_state`

Requirements:
- `psutil` must be installed in the container (verify in `docker/requirements-arm64.txt`)
- `/sys` must be accessible — add `/sys:/sys:ro` volume mount in `docker-compose.yml`
- Node is built via `colcon build` during container startup (user workspace)

### 4.3 Command Translator Node (New)

**Package:** `snoopi_command_bridge`

A ROS2 Python node that:
- Subscribes to `/snoopi/command` (`std_msgs/msg/String`)
- Parses command: `"sit"`, `"stand"`, `"estop"`
- For e-stop: immediately publishes zero velocity to `/cmd_vel` (`geometry_msgs/msg/Twist`)
- For sit/stand: calls the go2_ros2_sdk interface (exact topic/service TBD — see placeholder section below)
- Logs all commands received and actions taken

**Why scaffold now:** The node structure, error handling, and e-stop logic can all be written without the robot. Only the `execute_sit()` and `execute_stand()` functions need the real SDK interface, which we'll discover with `ros2 topic list` / `ros2 service list` in the lab.

### 4.4 CycloneDDS Peer Configuration

Update `docker/cyclonedds.xml` to include the robot as a DDS peer:
```xml
<Peers>
  <Peer Address="<ROBOT_IP>"/>
</Peers>
```

`<ROBOT_IP>` is a placeholder — fill in after confirming the Go2 Air's IP in the lab (expected: `192.168.123.161` based on SDK docs, but must be verified).

### 4.5 Network Setup Guide

A documented step-by-step for the lab visit covering:
1. Physical Ethernet connection (Pi ↔ Go2 Air)
2. Static IP configuration on Pi's Ethernet interface
3. Connectivity verification (ping)
4. CycloneDDS peer update
5. Container restart and topic discovery
6. Dashboard verification

All network values use clear `<PLACEHOLDER>` markers.

## 5. Placeholder Values

These values must be determined in the lab and filled in:

| Placeholder | Where Used | How to Determine |
|---|---|---|
| `<ROBOT_IP>` | `cyclonedds.xml`, network guide | Check go2_ros2_sdk docs or `arp -a` after connecting Ethernet |
| `<ROBOT_SUBNET>` | Pi network config | Same subnet as `<ROBOT_IP>` (expected: `192.168.123.0/24`) |
| `<PI_ROBOT_SUBNET_IP>` | Pi Ethernet interface config | Pick unused IP on `<ROBOT_SUBNET>` (e.g., `192.168.123.100`) |
| `<PI_ETH_INTERFACE>` | Pi network config | Run `ip link show` on Pi to find Ethernet interface name (likely `eth0` or `enx...`) |
| `<SDK_LAUNCH_CMD>` | entrypoint.sh | Determined from go2_ros2_sdk README / `ros2 launch` inspection |
| `<SDK_COMMAND_TOPIC>` | command_bridge node | Run `ros2 topic list` with SDK running to find command interface |
| `<SDK_COMMAND_MSG_TYPE>` | command_bridge node | Run `ros2 topic info <topic>` to find message type |

## 6. Topic Map (After Integration)

```
Real Robot (Go2 Air)                    Docker Container (snoopi-ros2)
========================               ================================
/utlidar/battery ──────── DDS ────────> rosbridge ──── WS ───> Dashboard
/imu/data ─────────────── DDS ────────> rosbridge ──── WS ───> Dashboard
/joint_states ─────────── DDS ────────> rosbridge ──── WS ───> Dashboard

                                        snoopi_system_monitor
                                        /snoopi/system_stats ── WS ───> Dashboard

                                        snoopi_command_bridge
Dashboard ── WS ──> rosbridge ────────> /snoopi/command ──> command_bridge
                                                              ├─ /cmd_vel (estop: zero velocity)
                                                              └─ <SDK_COMMAND_TOPIC> (sit/stand)
```

## 7. Files to Create/Modify

| File | Action | Purpose |
|---|---|---|
| `docker/entrypoint.sh` | Modify | Auto-launch rosbridge, system_monitor, SDK bridge |
| `docker-compose.yml` | Modify | Add `/sys:/sys:ro` volume mount |
| `docker/cyclonedds.xml` | Modify | Add robot peer with `<ROBOT_IP>` placeholder |
| `docker/requirements-arm64.txt` | Verify/modify | Ensure `psutil` is listed |
| `src/snoopi_command_bridge/` | Create | New ROS2 package — command translator node |
| `src/snoopi_command_bridge/package.xml` | Create | ROS2 package manifest |
| `src/snoopi_command_bridge/setup.py` | Create | Python package setup |
| `src/snoopi_command_bridge/setup.cfg` | Create | Entry point config |
| `src/snoopi_command_bridge/snoopi_command_bridge/__init__.py` | Create | Package init |
| `src/snoopi_command_bridge/snoopi_command_bridge/command_bridge.py` | Create | Main node |
| `docs/lab-setup-guide.md` | Create | Step-by-step lab instructions with placeholders |

## 8. What This Does NOT Cover

- **Nav2 launch/configuration** — Milestone 5 (requires a map first)
- **LiDAR visualization** — Not needed for telemetry dashboard
- **Camera feed** — Post-MVP
- **UWB integration** — Post-MVP
- **Task manager node** — Milestone 7
- **WiFi loss handling** — Milestone 8

## 9. Success Criteria

When connected to the real robot in the lab:
1. `ros2 topic list` inside the container shows SDK topics (`/utlidar/battery`, `/imu/data`, `/joint_states`, `/scan`)
2. Dashboard Battery card shows real battery percentage
3. Dashboard Temperature card shows real robot temperature
4. Dashboard IMU card shows real accelerometer data
5. Dashboard System Health card shows Pi CPU %, temperature, fan status
6. Telemetry graphs accumulate real data over time
7. E-stop button sends zero velocity to `/cmd_vel`
8. Sit/stand commands are logged (full SDK wiring TBD after topic discovery)
