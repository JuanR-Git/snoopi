# Hardware Validation — Milestone 0 Findings

**Date:** February 20, 2026
**Status:** ALL BLOCKERS RESOLVED — READY FOR MILESTONE 1

---

## 1. Raspberry Pi 4 Specs

| Spec | Value | Status |
|---|---|---|
| CPU | 64-bit quad-core ARMv8 (Cortex-A72) | OK |
| RAM | **2GB** | WARNING |
| WiFi | Onboard (802.11ac) | OK |
| Bluetooth | Onboard | OK |
| OS compatibility | Ubuntu 22.04 ARM64, ROS2 Humble | OK |

### RAM Assessment

The project plan recommends 4GB minimum. At 2GB:

- **ROS2 base footprint:** ~20MB per node, ~20MB per launch file, ~40MB for daemon
- **Nav2 full stack (AMCL + costmaps + planner + controller):** ~600–800MB estimated
- **SLAM Toolbox:** Additional ~200–400MB during mapping
- **OS + system overhead:** ~400–500MB

**Verdict:** 2GB is **tight but potentially feasible** for runtime navigation (no SLAM running simultaneously). Will require:
- No visualization tools (rviz2, rqt) on the Pi — run these on the dev laptop
- Reduced Nav2 parameters (smaller costmap, fewer AMCL particles)
- Adding swap space (1–2GB) as a safety net
- SLAM Toolbox runs on dev laptop during mapping phase, not on RPi4
- Careful monitoring of memory usage during integration testing

**Resolution:** RasTech Raspberry Pi 5 16GB Kit ordered. This fully resolves the RAM concern:
- 16GB RAM provides comfortable headroom for Nav2 + SLAM + all custom nodes
- RPi5 has ~2-3x faster CPU than RPi4 (Cortex-A76 vs A72)
- RPi4 2GB will serve as a backup/test board

**Note:** RPi5 runs Ubuntu 24.04 natively. ROS2 Humble targets Ubuntu 22.04 — will need to either:
- Install Ubuntu 22.04 on the RPi5 (confirmed supported)
- Or use ROS2 Jazzy (targets Ubuntu 24.04) — would require verifying go2_ros2_sdk compatibility

---

## 2. Unitree Go2 Air — CRITICAL FINDINGS

### 2.1 LiDAR — CONFIRMED PRESENT

| Finding | Detail |
|---|---|
| LiDAR included? | **YES** — super-wide-angle 3D LiDAR |
| Type | Unitree 4D LiDAR L1 (360x90° FOV, 0.05m min detection) |
| Impact | Nav2 navigation, SLAM mapping, and obstacle avoidance architecture is viable as designed |
| Status | **BLOCKER RESOLVED** — still need to verify SDK topic access in Milestone 2 |

### 2.2 SSH Access — DISABLED ON AIR MODEL

| Finding | Detail |
|---|---|
| SSH available? | **NO** — disabled in firmware (tested on v1.1.2) |
| IP 192.168.123.161 | Responds to ping, but port 22 (SSH) is closed |
| IP 192.168.123.18 | No open ports |
| Docking board | **Not present** on Air model |
| Programming features | **Disabled by default** on Air model |

Per the MyBotShop forum: "The GO2 Air has no docking board, and by default has all programming features disabled. You would need to purchase GO2 EDU or GO2 X to actually SSH access or program on them."

**However:** This does NOT necessarily block SDK usage. The `go2_ros2_sdk` connects to the robot externally via:
- **WebRTC** over the robot's WiFi AP (no SSH needed)
- **CycloneDDS** over Ethernet (no SSH needed)

The SDK runs on the companion computer (dev laptop / RPi4) and communicates with the robot over the network — it does not need to run ON the robot.

### 2.3 Go2 Air Onboard Compute

| Spec | Go2 Air | Go2 Pro | Go2 Edu |
|---|---|---|---|
| Main processor | Allwinner MR813 (quad-core ARM Cortex-A53) | Allwinner MR813 | Jetson Orin Nano/NX |
| RAM | ~1GB | ~1GB + Jetson | 8–16GB (Jetson) |
| OS | Embedded Linux (Unitree proprietary) | Embedded Linux | Ubuntu on Jetson |
| Capability | Locomotion control only | Moderate | Full dev platform |

The Air's Allwinner MR813 is a very low-power embedded chip — it runs Unitree's proprietary locomotion firmware and is NOT a general-purpose computer. You cannot install ROS2 on it. This is exactly why the RPi4 companion computer is necessary.

### 2.4 Go2 Air Sensors (Confirmed Available)

| Sensor | Included on Air? | Notes |
|---|---|---|
| IMU | **Yes** | Onboard, accessible via SDK |
| Front camera | **Yes** | Wide-angle 2D color camera in the head |
| Ultrasonic sensors | **Yes** | Forward-facing on the chin, short range (~few meters) |
| Foot force sensors | **Yes** | Contact/terrain detection |
| LiDAR | **YES** | Super-wide-angle 3D LiDAR (confirmed on this unit) |
| Side/rear cameras | **No** | Pro/Edu only |
| Depth camera | **No** | Edu only (Intel RealSense) |

---

## 3. go2_ros2_sdk Compatibility

| Item | Finding | Status |
|---|---|---|
| Go2 Air support | **Supported** (Air/Pro/Edu all listed) | OK |
| ROS2 Humble | **Supported** (Humble, Iron, Rolling) | OK |
| Tested firmware | v1.1.7 | CHECK |
| Connection methods | WebRTC (WiFi) + CycloneDDS (Ethernet) | OK |
| Maintenance | Active as of research date | OK |
| Stars/Community | Active community with issues and contributions | OK |

### Topics Exposed by SDK

| Topic | Message Type | Rate | Notes |
|---|---|---|---|
| Joint states | sensor_msgs/JointState | 1 Hz | Slow due to firmware changes |
| IMU | sensor_msgs/Imu | Real-time | |
| LiDAR point cloud | sensor_msgs/PointCloud2 | 7 Hz | **Only if LiDAR hardware is present** |
| Laser scan | sensor_msgs/LaserScan | ~7 Hz | **Only if LiDAR hardware is present** |
| Front camera | sensor_msgs/Image | Real-time | |
| Odometry | nav_msgs/Odometry | Real-time | |
| Robot state | Custom | Real-time | Mode, gait info |
| cmd_vel | geometry_msgs/Twist | Input | Velocity commands |

### Known Limitations
- Must close Unitree mobile app before connecting via SDK (app holds exclusive connection)
- Joint states at 1 Hz (firmware limitation) — URDF visualization will lag
- Map distortion possible in long corridors (Nav2 routing affected)
- WiFi latency for real-time control

### Dependencies
- Python 3.10+
- ROS2 Humble + standard message packages
- vision-msgs, image-tools
- clang, portaudio19-dev (audio support)
- pip packages from requirements.txt

---

## 4. Firmware — CONFIRMED COMPATIBLE

| Item | Detail |
|---|---|
| Hardware version | **V2.0** |
| Software/firmware version | **V1.1.7** |
| SDK tested firmware | v1.1.7 |
| Compatibility | **EXACT MATCH** — go2_ros2_sdk targets v1.1.7 |

**DO NOT update firmware** via the Unitree app — newer versions could break SDK compatibility.

Known v1.1.7 limitation: joint states arrive at 1 Hz (URDF visualization lag). This is cosmetic and does not affect navigation or control.

---

## 5. Risk Assessment Summary

### CRITICAL (Blockers)

1. ~~**LiDAR may not be present on the Go2 Air**~~ — **RESOLVED**: Super-wide-angle 3D LiDAR confirmed present on this unit.

2. ~~**RPi4 has only 2GB RAM (below 4GB recommendation)**~~ — **RESOLVED**: Raspberry Pi 5 16GB Kit ordered (RasTech). Development continues on dev laptop until RPi5 arrives.

### MEDIUM (Manageable)

3. **SSH disabled on Go2 Air** — Not a blocker since SDK connects externally
4. **Firmware version mismatch** — Check and update if needed
5. **1 Hz joint state updates** — Cosmetic issue, doesn't affect navigation

### LOW

6. **Foot force sensor availability** — Nice to have, not needed for MVP
7. **WiFi latency** — Mitigated by RPi4 wired Ethernet architecture

---

## 6. LiDAR Fallback Options (if not present)

If the Go2 Air does not have LiDAR, these are the options ranked by recommendation:

### Option A: External USB LiDAR on RPi4 (RECOMMENDED)

| LiDAR | Approx Cost | FOV | Range | ROS2 Driver |
|---|---|---|---|---|
| YDLIDAR X4 | ~$70 | 360° | 10m | `ydlidar_ros2_driver` |
| RPLiDAR A1 | ~$99 | 360° | 12m | `rplidar_ros` |
| RPLiDAR A2 | ~$200 | 360° | 18m | `rplidar_ros` |

- Mount on top of the robot, connect to RPi4 via USB
- Preserves the entire existing architecture (SLAM Toolbox, Nav2, costmaps all work as-is)
- Excellent ROS2 support, widely used in the community
- **This is the simplest path to keep the MVP plan intact**

### Option B: Depth Camera → LaserScan Conversion

- Add an Intel RealSense D435 (~$300) or OAK-D Lite (~$150) to the RPi4
- Use `depthimage_to_laserscan` ROS2 package to generate synthetic LaserScan
- Narrower FOV (~87° vs 360°) — less reliable for SLAM and navigation
- Higher compute cost on the 2GB RPi4

### Option C: Use only ultrasonic + camera (NOT recommended)

- Very limited range and FOV for obstacle detection
- Cannot run SLAM Toolbox or Nav2 costmaps as designed
- Would require custom obstacle avoidance logic — significantly more development effort

---

## 7. Milestone 0 Conclusion

All validation checks passed. No blockers remain.

| Check | Result |
|---|---|
| LiDAR present | YES — super-wide-angle 3D LiDAR |
| Firmware compatible | YES — V1.1.7 (exact SDK target) |
| go2_ros2_sdk supports Air | YES — Humble, Iron, Rolling |
| Companion computer | RPi5 16GB ordered (resolves RPi4 2GB limitation) |
| SSH access needed | NO — SDK connects externally via WebRTC/CycloneDDS |

**Proceed to Milestone 1 — Environment Setup.**

**Reminder:** DO NOT update the Go2 firmware via the Unitree app. V1.1.7 is the confirmed compatible version.

---

## Sources

- [go2_ros2_sdk GitHub](https://github.com/abizovnuralem/go2_ros2_sdk)
- [Go2 Air SSH disabled — MyBotShop Forum](https://forum.mybotshop.de/t/unitree-go2-air-ssh-access-disabled/1690)
- [Go2 Air Specs — Robots International](https://www.robotsinternational.com/Unitree-Go2-Air-Quadruped.htm)
- [go2_firmware_tools](https://github.com/legion1581/go2_firmware_tools)
- [Unitree Go2 Comparison — RobotShop](https://community.robotshop.com/blog/show/comprehensive-unitree-go2-robot-comparison)
- [ROS2 on RPi4 — ROS Answers](https://answers.ros.org/question/410598/ros-2-on-raspberry-pi-4b-1gb/)
- [Nav2 on RPi4 — Raspberry Pi Forums](https://forums.raspberrypi.com/viewtopic.php?t=366667)
- [Unitree Developer Docs](https://support.unitree.com/home/en/developer)
