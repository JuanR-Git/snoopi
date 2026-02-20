# Unitree Go2 Air — Hospital Robot Application
## Comprehensive Project Plan (v2)

---

## 1. Project Overview

A custom autonomous robot dog application for a hospital setting, built on the Unitree Go2 Air platform. The system allows operators (nurses at a station) to issue high-level task commands (e.g., "walk patient 200 meters") via a web-based dashboard. The robot executes tasks autonomously using onboard sensors, motor control, and real-time reactive logic. The dashboard provides task management, live health monitoring, and camera feeds.

**MVP Demo Date:** March 5, 2026
**Team:** Multiple humans and AI agents working in parallel

---

## 2. Context & Constraints

| Item | Detail |
|---|---|
| **Hardware** | Unitree Go2 Air robot dog |
| **Confirmed Sensors** | Super-wide-angle 3D LiDAR, front-facing camera, ultrasonic (forward), IMU, foot force sensors |
| **3rd Party Sensors (post-MVP)** | DWM3001CDK UWB ranging modules (for patient proximity tracking) |
| **Companion Computer** | Raspberry Pi 5 16GB (RasTech kit, ordered) — RPi4 2GB available as backup |
| **SDK** | No official consumer SDK — community `go2_ros2_sdk` required |
| **Dev Machine** | Linux (Ubuntu 22.04) |
| **Dev Connection** | Ethernet (MVP must support WiFi deployment) |
| **WiFi Network** | Available for testing |
| **Operator Model** | Nurse dispatches tasks from a station; robot operates autonomously |
| **Deployment Environment** | Hospital setting with real patients |
| **Regulatory** | No formal compliance requirements; safety is a design priority |

---

## 3. System Architecture

### 3.1 Three-Layer Model

```
┌─────────────────────────────────────────────────────────────┐
│                      UI LAYER                                │
│  React Frontend + FastAPI Backend                            │
│  (Runs on: Operator's browser / server at nurse station)     │
│  - Task dispatch & monitoring                                │
│  - Live health dashboard (battery, temp, joint states)       │
│  - Emergency stop button                                     │
│  - Map viewer with safe-stop locations                       │
│  - Camera feed (post-MVP)                                    │
│                          │ WebSocket (rosbridge_suite)        │
├──────────────────────────┼──────────────────────────────────-─┤
│               AUTONOMY LAYER                                 │
│  ROS2 Humble Nodes                                           │
│  (Runs on: Dev laptop during development → RPi4 in deploy)   │
│  - Task Manager Node         - Health Monitor Node           │
│  - Nav2 Stack (planning,     - Emergency Stop Node           │
│    costmap, obstacle avoid)  - SLAM / Map Server             │
│                          │ DDS (CycloneDDS) over Ethernet    │
├──────────────────────────┼──────────────────────────────────-─┤
│              HARDWARE INTERFACE LAYER                         │
│  go2_ros2_sdk bridge                                         │
│  (Runs on: Go2 Air onboard compute)                          │
│  - Exposes: battery, temp, joint states, IMU, LiDAR, camera  │
│  - Accepts: velocity commands, mode commands (sit/stand)      │
└─────────────────────────────────────────────────────────────-─┘
```

### 3.2 Compute Architecture

| Phase | ROS2 Nodes Run On | Connection to Robot | Connection to Operator |
|---|---|---|---|
| **Development** | Dev laptop | Ethernet to Go2 Air | localhost (browser) |
| **Deployment** | Raspberry Pi 4 (mounted on/near robot) | Ethernet to Go2 Air (short cable) | WiFi to nurse station |

**Why a companion computer matters:** In deployment, the RPi4 rides with the robot. Critical control loops (Nav2, obstacle avoidance, emergency stop) run locally on the Pi, connected to the robot over a reliable wired Ethernet link. Only UI/monitoring data travels over WiFi. If WiFi drops, the robot retains its "brain" and can safely stop or navigate to a safe location.

### 3.3 Full Tech Stack

| Layer | Technology |
|---|---|
| Robot hardware bridge | `go2_ros2_sdk` |
| Middleware | ROS2 Humble (LTS, Ubuntu 22.04) |
| Autonomy & navigation | Nav2 |
| Mapping | SLAM Toolbox (teleoperation mapping for MVP) |
| UI backend | Python + FastAPI |
| UI frontend | React |
| ROS2 ↔ Web bridge | `rosbridge_suite` |
| Camera streaming (post-MVP) | WebRTC or MJPEG via `web_video_server` |
| Patient proximity (post-MVP) | DWM3001CDK UWB modules via RPi4 |

---

## 4. Sensor Strategy

### 4.1 MVP Sensors (Onboard Go2 Air)

| Sensor | Used For | Nav2 Integration |
|---|---|---|
| **LiDAR** | Obstacle detection, SLAM mapping, costmap generation | Primary input to Nav2 costmap — detects walls, furniture, people, obstacles in real-time |
| **Front-facing camera** | Situational awareness, operator camera feed (post-MVP) | Not used for navigation in MVP |
| **IMU** | Orientation, fall detection, tilt monitoring | Used by e-stop node for fall/tilt detection |

### 4.2 Post-MVP Sensors

| Sensor | Used For | Integration Path |
|---|---|---|
| **DWM3001CDK UWB modules** | Patient proximity tracking (range to patient-worn tag) | RPi4 reads UWB range data → publishes to ROS2 topic → consumed by patient-tracking node for walk-beside behavior |

**Important note on UWB vs LiDAR roles:**
- **LiDAR** answers: "What obstacles are around me?" (obstacle avoidance, mapping)
- **UWB** answers: "How far am I from the patient?" (patient tracking, distance maintenance)
- These are complementary. UWB does NOT replace LiDAR for obstacle detection.

### 4.3 Sensors to Investigate

During Milestone 0, confirm what additional sensors the Go2 Air exposes via the SDK:
- Ultrasonic sensors (some Go2 models have them)
- Additional cameras (side, rear)
- Foot force sensors (terrain detection)

---

## 5. Navigation & Mapping Strategy

### 5.1 MVP: Teleoperation Mapping + Nav2 Navigation

**Mapping (one-time setup per environment):**
1. Operator manually drives the robot through the environment using keyboard/joystick teleoperation
2. SLAM Toolbox builds a 2D occupancy grid map from LiDAR data in real-time
3. Operator saves the completed map
4. Operator marks **safe-stop locations** on the saved map via the UI (click-to-mark on the map image)
5. Map + safe-stop locations are loaded by Nav2's map server for all future autonomous operations

**Navigation (during tasks):**
- Nav2 uses the saved map + live LiDAR data for localization (AMCL) and path planning
- The costmap combines the static map with real-time LiDAR readings to detect new/moved obstacles
- The robot plans paths around obstacles and replans dynamically if the environment changes

**📚 ROS2 Learning Points:**
- Understand the difference between a static map (from SLAM) and a live costmap (static map + real-time sensor data)
- Learn how AMCL (Adaptive Monte Carlo Localization) works — it answers "where am I on the map?"
- Learn how Nav2's planner and controller work — planner creates a path, controller follows it while avoiding obstacles
- Key tutorials: [Nav2 Getting Started](https://docs.nav2.org/getting_started/index.html), [SLAM Toolbox](https://github.com/SteveMacenski/slam_toolbox)

### 5.2 Post-MVP: Autonomous Exploration Mapping

Replace the teleoperation mapping step with frontier-based autonomous exploration:
- Robot autonomously identifies unexplored areas (frontiers) on the map edge
- Robot navigates to frontiers to expand the map
- Uses `explore_lite` or similar ROS2 exploration package
- Operator monitors progress and can intervene

### 5.3 Post-MVP: Automatic Safe-Stop Detection

Replace manual safe-stop marking with automatic detection:
- Analyze the completed map for alcoves, wide areas, dead-ends
- Score locations by: distance from main corridors, available space, accessibility
- Present suggested locations to operator for confirmation

---

## 6. Task Model

### 6.1 MVP Task: "Walk Patient X Meters"

**Preconditions:**
- Environment has been pre-mapped (teleoperation SLAM)
- Safe-stop locations have been marked on the map
- Robot is physically placed next to the patient by staff
- Robot's starting position is set (either manually or via AMCL localization)

**Task Flow:**
1. Nurse dispatches task from UI: "Walk patient 200 meters"
2. Task Manager node receives command, records starting position
3. Robot begins navigating forward along the corridor (Nav2 goal-based navigation)
4. Robot navigates around obstacles using Nav2's local planner + LiDAR costmap
5. Robot tracks total distance traveled
6. When target distance is reached, robot turns around
7. Robot navigates back to the recorded starting position
8. Task Manager reports task complete to UI

**During task, the UI displays:**
- Task status (in progress, distance remaining, returning)
- Live health stats (battery, temperature)
- Any alerts or warnings

**MVP Patient Model: Robot Leads, Patient Follows**
- The robot walks ahead of the patient at a controlled speed
- The patient follows behind the robot
- This avoids the need for lateral person tracking, which requires the UWB sensors (post-MVP)

### 6.2 Post-MVP Task Enhancements

| Feature | Dependency |
|---|---|
| Walk beside patient | DWM3001CDK UWB sensors + patient tracking node |
| Follow patient | Person detection (camera) or UWB tracking |
| Patrol route | Multiple waypoints on pre-mapped route |
| Navigate to patient room | Full map with room labels + autonomous navigation |
| Return to charging station | Docking behavior + known station location |

---

## 7. Safety Architecture

### 7.1 Emergency Stop (E-Stop) — Software-Only

Since there is no physical e-stop button, the software e-stop must be robust and multi-layered.

**E-Stop Trigger Conditions:**

| Trigger | Source | Response |
|---|---|---|
| Operator presses e-stop in UI | UI → rosbridge → E-Stop Node | Immediate stop, sit down |
| Obstacle within critical threshold | LiDAR → costmap → E-Stop Node | Immediate stop, hold position |
| Robot tilt exceeds safe angle | IMU → E-Stop Node | Immediate stop, sit down |
| Battery below critical threshold | Health Monitor → E-Stop Node | Navigate to nearest safe-stop, sit down |
| Temperature exceeds safe threshold | Health Monitor → E-Stop Node | Navigate to nearest safe-stop, sit down |
| Communication loss (WiFi drop) | Heartbeat timeout → E-Stop Node | See WiFi loss behavior below |
| Nav2 planner failure (no valid path) | Nav2 → Task Manager → E-Stop Node | Stop, report to operator (if connected) |

**E-Stop Behavior:**
1. **Immediate stop**: Cancel all velocity commands, zero all motors
2. **Sit down**: Command the robot to sit (stable, low center of gravity, not blocking as much space)
3. **Report**: Send status to UI if connection is available
4. **Hold**: Remain in stopped state until operator sends explicit resume command

**📚 ROS2 Learning Points:**
- ROS2 node lifecycle management (how to make a node that monitors other nodes)
- QoS (Quality of Service) settings — the e-stop node should use "reliable" QoS to ensure messages are delivered
- ROS2 topic priorities — how to ensure e-stop commands override navigation commands

### 7.2 WiFi Loss Behavior

**Architecture advantage:** Because critical ROS2 nodes run on the RPi4 (companion computer) connected to the robot over Ethernet, WiFi loss only affects communication with the operator UI. The robot retains full autonomy.

**Behavior on WiFi loss:**
1. Heartbeat between UI backend and ROS2 nodes (via rosbridge) — if heartbeat times out (e.g., 3 seconds), WiFi is considered lost
2. Robot completes its current motion safely (does not jerk to a stop)
3. Robot navigates to the **nearest safe-stop location** on the pre-mapped map
4. Robot sits down at the safe-stop location
5. Robot continuously attempts to reconnect
6. On reconnection, robot reports its status and location to the UI
7. Operator must send explicit resume command to continue the task

### 7.3 Speed & Proximity Limits

| Parameter | MVP Value | Notes |
|---|---|---|
| Maximum walking speed | 0.5 m/s | Conservative for hospital corridors. Tune during testing. |
| Obstacle stop distance | 0.5 m | Robot stops if any obstacle is within this range |
| Obstacle slow-down distance | 1.5 m | Robot reduces speed when obstacles are detected in this range |
| Maximum tilt angle | 15° | E-stop triggers if robot tilts beyond this |
| Low battery warning | 20% | Alert sent to operator |
| Critical battery (auto-stop) | 10% | Robot navigates to safe-stop and sits down |

### 7.4 Post-MVP Safety Enhancements

- Human-specific detection (distinguish people from objects using camera + ML)
- Patient-specific proximity maintenance via UWB
- Physical e-stop button / kill switch accessible to nearby staff (hardware modification)
- Behavior on robot fall (detect via IMU, alert operator, wait for assistance)

---

## 8. Development Milestones

### Milestone 0 — Validation & Discovery (Days 1–2)
> **Goal:** Confirm that the foundation will work before building on it.

**Tasks:**
- [ ] Check Go2 Air firmware version (via Unitree app or robot's web interface)
- [ ] Check `go2_ros2_sdk` GitHub repo: is firmware version compatible? Is repo actively maintained? When was last commit?
- [ ] Check Raspberry Pi 4 model and RAM (run `cat /proc/cpuinfo` and `free -h`)
- [ ] Confirm RPi4 can run ROS2 Humble (ARM64 support — it can, but confirm storage/RAM is adequate; 4GB RAM minimum recommended)
- [ ] Attempt to SSH into Go2 Air to understand onboard compute capabilities
- [ ] Document all findings in a `hardware-validation.md` file

**Risk gate:** If `go2_ros2_sdk` does not support the Go2 Air firmware:
- **Fallback Option A:** Check if firmware can be updated to a supported version
- **Fallback Option B:** Use `unitree_sdk2_python` as the hardware interface and write a custom ROS2 wrapper node that translates between the Python SDK and ROS2 topics. This adds ~2-3 days but preserves the rest of the architecture.

**Checkpoint:** Green/red decision on SDK viability. Hardware specs documented.

---

### Milestone 1 — Environment Setup (Days 2–4)
> **Goal:** A working ROS2 development environment.

**Tasks:**
- [ ] Install Ubuntu 22.04 on development machine (if not already installed)
- [ ] Install ROS2 Humble (full desktop install)
  - Follow: https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html
- [ ] Install Nav2: `sudo apt install ros-humble-navigation2 ros-humble-nav2-bringup`
- [ ] Install SLAM Toolbox: `sudo apt install ros-humble-slam-toolbox`
- [ ] Install rosbridge_suite: `sudo apt install ros-humble-rosbridge-suite`
- [ ] Clone and build `go2_ros2_sdk` per its README
- [ ] Install CycloneDDS: `sudo apt install ros-humble-rmw-cyclonedds-cpp`
- [ ] Set environment: `export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp` (add to `.bashrc`)
- [ ] Verify installation: launch a basic ROS2 node, confirm `ros2 topic list` works

**📚 ROS2 Learning Points:**
- Complete the official ROS2 Humble tutorials (Beginner: CLI Tools + Client Libraries): https://docs.ros.org/en/humble/Tutorials.html
- Key concepts to understand: nodes, topics, publishers, subscribers, services, actions, launch files
- Understand what DDS is and why CycloneDDS is specified (it's the DDS implementation that `go2_ros2_sdk` expects)

**Checkpoint:** `ros2 topic list` returns topics. Nav2, SLAM Toolbox, rosbridge are installed.

---

### Milestone 2 — Hardware Connection & Telemetry (Days 4–6)
> **Goal:** Live data streaming from the robot to the dev machine.

**Tasks:**
- [ ] Connect dev laptop to Go2 Air over Ethernet
- [ ] Configure network interface (static IP on the robot's subnet)
- [ ] Launch `go2_ros2_sdk` bridge nodes
- [ ] Run `ros2 topic list` — document all available topics from the robot
- [ ] Subscribe to and verify each relevant topic:
  - Battery level
  - Internal temperature
  - Joint states
  - IMU data
  - LiDAR scan data (`/scan` or similar)
- [ ] Write a simple Python ROS2 node (`health_printer.py`) that subscribes to health topics and prints formatted output to terminal
- [ ] Document which topics are available vs. expected but missing (sensor investigation from Section 4.3)

**📚 ROS2 Learning Points:**
- Writing a ROS2 Python subscriber node
- Understanding ROS2 message types (`sensor_msgs/LaserScan`, `sensor_msgs/Imu`, `sensor_msgs/BatteryState`, etc.)
- Using `ros2 topic echo <topic>` to inspect live data
- Using `rviz2` to visualize LiDAR data (important for debugging later)

**Checkpoint:** Battery percentage, temperature, and LiDAR scans streaming to terminal from live robot. LiDAR visible in rviz2.

---

### Milestone 3 — Basic Motion Commands (Days 6–8)
> **Goal:** Operator can command the robot to sit, stand, and walk from the terminal.

**Tasks:**
- [ ] Identify the command interface exposed by `go2_ros2_sdk` (velocity commands via `cmd_vel`? mode commands via service calls?)
- [ ] Write a ROS2 node (`basic_commander.py`) that publishes velocity commands to make the robot walk forward, turn, and stop
- [ ] Implement sit and stand commands (likely mode/service calls)
- [ ] Test all commands over Ethernet
- [ ] Configure WiFi connection to Go2 Air
- [ ] Configure DDS for WiFi (may need to set specific peer addresses instead of multicast discovery if network has restrictions)
- [ ] Repeat all command tests over WiFi
- [ ] Measure and document WiFi command latency

**📚 ROS2 Learning Points:**
- Writing a ROS2 publisher node
- Understanding `geometry_msgs/Twist` (the standard velocity command message)
- ROS2 services vs. topics (commands that need acknowledgment vs. continuous data)
- DDS discovery mechanisms (multicast vs. unicast peer lists)

**Checkpoint:** Robot sits, stands, and walks on command from terminal. Works over both Ethernet and WiFi.

---

### Milestone 4 — SLAM Mapping (Days 8–10)
> **Goal:** Generate a map of the test environment by teleoperating the robot.

**Tasks:**
- [ ] Launch SLAM Toolbox in mapping mode alongside the robot's LiDAR feed
- [ ] Use keyboard teleoperation (`teleop_twist_keyboard`) to drive the robot around the test corridor
- [ ] Monitor map building in real-time via rviz2
- [ ] Drive slowly and cover all areas of the test environment (corridor + room with table)
- [ ] Save the completed map (`ros2 run nav2_map_server map_saver_cli -f test_map`)
- [ ] Verify saved map files: `test_map.yaml` + `test_map.pgm`
- [ ] Repeat for any additional test areas

**📚 ROS2 Learning Points:**
- How SLAM works conceptually (simultaneous localization and mapping)
- SLAM Toolbox configuration parameters (resolution, range thresholds)
- How occupancy grid maps work (the `.pgm` image + `.yaml` metadata)
- Using rviz2 to visualize the map being built

**Checkpoint:** A saved occupancy grid map of the test corridor. Map looks accurate when viewed in rviz2.

---

### Milestone 5 — Autonomous Navigation with Nav2 (Days 10–14)
> **Goal:** Robot autonomously navigates to goals on the map while avoiding obstacles.

**Tasks:**
- [ ] Configure Nav2 for the Go2 Air platform:
  - Set robot footprint (dimensions of the Go2)
  - Configure costmap parameters (obstacle layer from LiDAR, inflation layer for safety margins)
  - Set planner parameters (path planning algorithm)
  - Set controller parameters (how the robot follows the planned path — max speed, acceleration, turning)
- [ ] Launch Nav2 with the saved map
- [ ] Verify AMCL localization: robot knows where it is on the map
- [ ] Send a navigation goal via rviz2 (click a point on the map, robot navigates to it)
- [ ] Place cardboard box obstacles in the corridor — verify the robot plans around them
- [ ] Move obstacles while robot is navigating — verify dynamic replanning
- [ ] Tune speed limits (max 0.5 m/s as per safety parameters)
- [ ] Tune obstacle avoidance distances (stop at 0.5m, slow at 1.5m)

**📚 ROS2 Learning Points:**
- Nav2 architecture: planner server, controller server, behavior server, costmap
- How costmaps work: static layer (from map) + obstacle layer (from live LiDAR) + inflation layer (safety buffer)
- AMCL: how the robot localizes itself on a known map
- Nav2 behavior trees: how Nav2 sequences its planning and recovery behaviors
- Key reference: https://docs.nav2.org/configuration/index.html

**Checkpoint:** Robot autonomously navigates to a goal point in the corridor, avoiding both static and dynamic obstacles. Operator can set goals via rviz2.

---

### Milestone 6 — UI Foundation (Days 10–14, parallel track)
> **Goal:** A browser-based dashboard showing live health stats with basic command buttons.

> ⚡ **This milestone can be developed in parallel with Milestone 5** by a different team member or agent, since it only requires rosbridge + the health topics from Milestone 2.

**Tasks:**
- [ ] Scaffold FastAPI backend:
  - WebSocket endpoint proxying to rosbridge
  - REST endpoints for task dispatch and status
  - Backend holds no ROS2 state — it's a passthrough to rosbridge (single source of truth is ROS2)
- [ ] Scaffold React frontend:
  - Health dashboard panel: battery %, temperature, joint status, connection status
  - Command buttons: sit, stand, emergency stop
  - Task dispatch panel (placeholder for Milestone 7)
- [ ] Launch rosbridge_suite: `ros2 launch rosbridge_server rosbridge_websocket_launch.xml`
- [ ] Connect React frontend to rosbridge via WebSocket (`roslibjs`)
- [ ] Display live health data updating in real-time
- [ ] Wire sit/stand/e-stop buttons to ROS2 commands via rosbridge

**📚 ROS2 Learning Points:**
- How rosbridge_suite works (translates ROS2 topics/services to JSON over WebSocket)
- `roslibjs` JavaScript library for ROS2 communication in the browser
- ROS2 QoS compatibility (rosbridge may need specific QoS settings to match the robot's topics)

**Checkpoint:** Browser dashboard shows live battery and temperature. Sit/stand buttons work. E-stop button stops the robot.

---

### Milestone 7 — Task Manager & MVP Task (Days 14–18)
> **Goal:** Operator dispatches "walk X meters" from the UI. Robot executes autonomously and returns.

**Tasks:**
- [ ] Implement Task Manager ROS2 node:
  - Accepts task commands (task type, parameters) via ROS2 service or action
  - Records starting position when task begins
  - Sends Nav2 goals to execute the task
  - Tracks distance traveled (odometry integration)
  - When target distance reached: sends Nav2 goal back to starting position
  - Reports task status (pending, in progress, distance remaining, returning, complete, failed) on a ROS2 topic
- [ ] Wire Task Manager into the UI:
  - Task dispatch form: task type selector, distance input, start button
  - Task status display: current state, distance progress bar, elapsed time
  - Cancel task button (sends cancellation to Task Manager → cancels Nav2 goal)
- [ ] Implement E-Stop node:
  - Subscribes to: LiDAR (obstacle proximity), IMU (tilt), Health Monitor (battery, temp), UI (manual e-stop)
  - On trigger: cancels active Nav2 goal, sends zero velocity, commands sit
  - Publishes e-stop status to UI
- [ ] Implement Health Monitor node:
  - Aggregates battery, temperature, joint health from robot topics
  - Publishes consolidated health status
  - Triggers alerts at configurable thresholds (battery < 20% warning, < 10% critical)

**📚 ROS2 Learning Points:**
- ROS2 Actions (long-running tasks with feedback — Nav2 uses actions for navigation goals)
- How to cancel a Nav2 goal programmatically
- ROS2 node composition (multiple nodes working together)
- Odometry messages and distance tracking

**Checkpoint:** Full MVP loop works — nurse dispatches "walk 50 meters" from browser, robot walks the corridor avoiding obstacles, returns to start, task shows complete in UI. E-stop works from UI and from automatic triggers.

---

### Milestone 8 — Safe-Stop Locations & WiFi Loss Handling (Days 18–20)
> **Goal:** Robot handles WiFi loss gracefully using pre-marked safe-stop locations.

**Tasks:**
- [ ] Add safe-stop marking to the UI:
  - Display the saved map in the browser
  - Allow operator to click on the map to mark safe-stop locations
  - Save safe-stop locations as a list of map coordinates (stored as a YAML/JSON config file)
- [ ] Implement WiFi loss detection:
  - Heartbeat mechanism between UI backend and a ROS2 heartbeat node
  - If heartbeat times out (3 seconds), trigger WiFi-loss behavior
- [ ] Implement safe-stop navigation:
  - On WiFi loss: find nearest safe-stop location from current position
  - Send Nav2 goal to that location
  - Sit down on arrival
  - Continue attempting reconnection
  - On reconnection: report status to UI, wait for operator resume command
- [ ] Test: disconnect WiFi mid-task, verify robot navigates to safe-stop and sits

**Checkpoint:** Robot reliably navigates to a safe-stop location when WiFi is disconnected during a task.

---

### Milestone 9 — Integration Testing & Demo Prep (Days 20–24)
> **Goal:** End-to-end system is stable and demoable.

**Tasks:**
- [ ] End-to-end workflow testing:
  - Complete task cycle: dispatch → walk → avoid obstacles → return → complete
  - E-stop from UI during task
  - WiFi loss and recovery during task
  - Low battery simulation and response
- [ ] Obstacle avoidance tuning in test corridor:
  - Static obstacles (cardboard boxes)
  - Dynamic obstacles (person walking into path)
  - Narrow passage navigation
- [ ] WiFi reliability testing:
  - Sustained operation over WiFi (30+ minutes)
  - Reconnection behavior
  - Latency measurement for UI responsiveness
- [ ] UI polish:
  - Clean layout, clear status indicators
  - Error states displayed clearly
  - Connection status indicator
- [ ] Demo scenario scripting:
  - Define exact demo steps
  - Identify and practice fallback procedures if something fails during demo
- [ ] Bug fixes and stabilization

**Checkpoint:** The system can reliably demo the full MVP workflow without intervention.

---

## 9. MVP Definition (March 5, 2026)

### Must Have (Demo Blockers)
- [x] Live health monitoring dashboard (battery, temperature, status)
- [x] Operator sends "walk X meters" task from web UI
- [x] Robot executes task autonomously (Nav2 navigation)
- [x] Robot avoids obstacles during task (LiDAR costmap)
- [x] Robot returns to starting position when task completes
- [x] Emergency stop from UI
- [x] Automatic e-stop on critical conditions (obstacle too close, tilt, low battery)

### Should Have (High Value, Include if Time Allows)
- [ ] WiFi loss → safe-stop navigation
- [ ] Safe-stop location marking on map via UI
- [ ] Map visualization in UI
- [ ] Health alert thresholds with visual warnings

### Nice to Have (Post-MVP)
- [ ] Camera feed in UI
- [ ] Autonomous exploration mapping
- [ ] Automatic safe-stop detection
- [ ] Walk-beside patient (UWB sensors)
- [ ] DWM3001CDK UWB integration on RPi4
- [ ] Patient tracking and proximity maintenance
- [ ] Multiple task types (patrol, follow, navigate to room)
- [ ] Logging and telemetry
- [ ] Gazebo simulation environment

---

## 10. Parallel Workstream Plan

Given multiple humans and agents are available, here is how work can be parallelized:

```
Days 1-2:   [ALL]        Milestone 0 — Validation & Discovery
Days 2-4:   [ALL]        Milestone 1 — Environment Setup
Days 4-8:   [Team A]     Milestone 2 — Hardware Connection
            [Team A]     Milestone 3 — Basic Motion Commands
Days 8-14:  [Team A]     Milestone 4 — SLAM Mapping
            [Team A]     Milestone 5 — Nav2 Navigation
            [Team B]     Milestone 6 — UI Foundation (parallel)
Days 14-18: [Team A]     Milestone 7 — Task Manager (ROS2 side)
            [Team B]     Milestone 7 — Task Manager (UI side, parallel)
Days 18-20: [All]        Milestone 8 — Safe-Stop & WiFi Loss
Days 20-24: [All]        Milestone 9 — Integration & Demo Prep
```

**Team A** = Whoever is working with the physical robot and ROS2
**Team B** = Can work on UI independently using mock ROS2 data (rosbridge with simulated topics)

---

## 11. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `go2_ros2_sdk` doesn't support Go2 Air firmware | Medium | High | Milestone 0 validates this first. Fallback: custom ROS2 wrapper around `unitree_sdk2_python` (+2-3 days) |
| ~~RPi4 insufficient for ROS2 + Nav2~~ | Resolved | — | RPi5 16GB ordered. Original RPi4 2GB was below 4GB minimum. |
| Go2 Air LiDAR data not accessible via SDK | Low | Critical | LiDAR hardware confirmed present (super-wide-angle 3D LiDAR). Validate data access in Milestone 2. Fallback: external USB LiDAR on RPi4. |
| Hospital WiFi blocks DDS multicast | Medium | Medium | Configure CycloneDDS with unicast peer list. Test in Milestone 3. |
| Nav2 tuning takes longer than expected | Medium | Medium | Start with conservative parameters. Tuning is iterative — basic functionality should work with defaults. |
| March 5th deadline is tight | High | High | Strict MVP scope. UI can be simplified. Demo in controlled corridor is acceptable. |

---

## 12. Key Assumptions

1. The `go2_ros2_sdk` community repository is compatible with the Go2 Air firmware version in use (validated in Milestone 0).
2. The Go2 Air exposes LiDAR data over DDS/ROS2 topics via the SDK.
3. The Raspberry Pi 4 has sufficient resources (4GB+ RAM recommended) to run ROS2 Humble and Nav2.
4. The testing WiFi network does not block DDS multicast or the ports required for DDS communication.
5. The Go2 Air's velocity command interface (`cmd_vel` or equivalent) allows smooth speed control for Nav2's controller.

---

## 13. Post-MVP Roadmap

### Phase 1: Patient Proximity (UWB Integration)
- Mount DWM3001CDK anchors on robot (via RPi4 USB/UART)
- Provide UWB tag for patient to wear
- Write ROS2 driver node on RPi4 that publishes range data
- Implement patient tracking node that maintains fixed distance
- Enable "walk beside patient" task mode

### Phase 2: Enhanced Autonomy
- Autonomous exploration mapping (frontier-based)
- Automatic safe-stop location detection
- Multiple task types: patrol route, follow patient, navigate to room
- Return to charging station behavior

### Phase 3: Perception & Intelligence
- Camera feed streaming to UI (WebRTC or MJPEG)
- Person detection via camera (human-specific obstacle handling)
- Patient identification (distinguish patient from other people)
- Voice announcements ("Arriving at destination")

### Phase 4: Production Hardening
- Gazebo simulation for automated testing
- Comprehensive logging and telemetry
- ROS2 bag recording for incident review
- Network resilience (mesh networking, 5G fallback)
- Security (encrypted DDS communication, authenticated UI access)
- Physical e-stop button installation

---

## 14. Reference Links

| Resource | URL |
|---|---|
| ROS2 Humble Installation | https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html |
| ROS2 Tutorials (start here) | https://docs.ros.org/en/humble/Tutorials.html |
| Nav2 Documentation | https://docs.nav2.org/ |
| Nav2 Getting Started | https://docs.nav2.org/getting_started/index.html |
| SLAM Toolbox | https://github.com/SteveMacenski/slam_toolbox |
| go2_ros2_sdk | https://github.com/abizovnuralem/go2_ros2_sdk |
| rosbridge_suite | https://github.com/RobotWebTools/rosbridge_suite |
| roslibjs (JS ROS2 client) | https://github.com/RobotWebTools/roslibjs |
| CycloneDDS Configuration | https://cyclonedds.io/docs/ |
| DWM3001CDK Datasheet | https://www.qorvo.com/products/p/DWM3001CDK |
| teleop_twist_keyboard | https://github.com/ros2/teleop_twist_keyboard |