# Docker Environment Design
**Date:** 2026-02-25
**Scope:** Milestone 1 — Docker container setup, RPi5 environment, UI/API scaffold
**Status:** Approved — ready for implementation

---

## Context

The RPi5 (companion computer) runs Ubuntu Server 24.04. The project stack targets
ROS2 Humble, which requires Ubuntu 22.04. Rather than downgrade the OS, we run a
Docker container with Ubuntu 22.04 as its base, isolating all ROS2 dependencies
cleanly. The UI and API run natively on the Ubuntu 24.04 host.

---

## 1. Project Structure

```
snoopi/
├── CLAUDE.md
├── docker-compose.yml          ← orchestrates the ROS2 container
├── Dockerfile                  ← builds the snoopi-ros2 image
├── .env                        ← ROS_DOMAIN_ID and other env vars
│
├── docker/
│   └── cyclonedds.xml          ← CycloneDDS config (editable without image rebuild)
│
├── docs/
│   ├── project.md
│   ├── hardware-validation.md
│   └── plans/                  ← design docs and implementation plans
│
├── src/                        ← ROS2 packages (volume-mounted into container)
│   └── (populated per milestone)
│
├── backend/                    ← FastAPI (runs on RPi5 host)
│   ├── main.py
│   ├── requirements.txt
│   └── .env
│
└── ui/                         ← React frontend (runs on RPi5 host)
    ├── package.json
    ├── vite.config.ts
    ├── tsconfig.json
    └── src/
```

---

## 2. Development Workflow

### Sync Loop (every session)
```
1. [WINDOWS]       Claude edits files in the repo
2. [WINDOWS]       git add . && git commit -m "..." && git push
3. [PI]            git pull
4. [PI]            Execute (docker-compose up / colcon build / npm run dev / etc.)
5. [PI]            Verify (ros2 topic list / curl / browser check)
```

No SCP required. Git is the only sync mechanism.

### Command Labeling Convention
| Tag | Meaning |
|---|---|
| `[WINDOWS]` | Run on Windows dev machine |
| `[PI]` | Run via SSH on RPi5 |
| `[PI - inside container]` | Run after `docker exec -it snoopi-ros2 bash` |
| `[BROWSER]` | Open in browser on Windows machine |

### Session Structure
```
GOAL: [what we're accomplishing this session]
STEP N [TAG] — description
...
CHECKPOINT: [what success looks like]
NEXT SESSION: [what comes next]
```

---

## 3. Docker Image

### Base Image
`osrf/ros:humble-ros-base` — official OSRF image, ARM64-compatible, ROS2 apt
repo and GPG keys pre-configured, Python 3.10 included. Ships without GUI tools
(correct for a headless Pi server). rviz2 runs on the dev laptop, not the Pi.

### Image Layers

**Layer 1 — System packages**
- `clang` — go2_ros2_sdk build requirement
- `portaudio19-dev` — go2_ros2_sdk audio support
- `python3-pip`, `python3-colcon-common-extensions`
- `git`, `curl`, `wget`

**Layer 2 — ROS2 packages (via apt)**
- `ros-humble-navigation2`, `ros-humble-nav2-bringup`
- `ros-humble-slam-toolbox`
- `ros-humble-rosbridge-suite`
- `ros-humble-rmw-cyclonedds-cpp`
- `ros-humble-vision-msgs`, `ros-humble-image-tools` (go2_ros2_sdk deps)
- `ros-humble-teleop-twist-keyboard` (Milestone 4: SLAM mapping)
- `ros-humble-xacro`, `ros-humble-robot-state-publisher`

**Layer 3 — go2_ros2_sdk (baked into image)**

Cloned and built at image-build time into `/opt/go2_ws/`. Separate from the
volume-mounted user workspace so the SDK is pre-compiled and never rebuilt
during development.

```
/opt/go2_ws/
├── src/go2_ros2_sdk/    ← cloned from GitHub
└── install/             ← colcon build output (sourced at runtime)
```

⚠️ First `docker build` on ARM64 takes 15–25 minutes due to colcon compilation.
Subsequent builds use Docker layer cache and are fast unless earlier layers change.

**Layer 4 — Entrypoint**

`docker/entrypoint.sh` sources all three workspaces in order on container start:
```bash
source /opt/ros/humble/setup.bash           # ROS2 base
source /opt/go2_ws/install/setup.bash       # go2_ros2_sdk
source /ros2_ws/install/setup.bash          # user nodes (if built)
exec "$@"
```

Default `CMD`: `tail -f /dev/null` — keeps container alive for `docker exec`
during development. Replaced with a launch file command for deployment.

### Two-Workspace Architecture
```
Layer 1: /opt/ros/humble/    ← ROS2 base (apt, never touched)
Layer 2: /opt/go2_ws/        ← go2_ros2_sdk (baked into image)
Layer 3: /ros2_ws/           ← your ROS2 nodes (volume-mounted from ./src/)
```
Each layer sources the one below it via the entrypoint script.

### docker-compose.yml

```yaml
services:
  snoopi-ros2:
    build: .
    image: snoopi-ros2:latest
    container_name: snoopi-ros2
    network_mode: host          # essential — DDS multicast does not cross Docker bridge
    restart: unless-stopped     # survives reboots/crashes, respects manual stop
    environment:
      - ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-0}
      - RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
      - CYCLONEDDS_URI=/ros2_ws/cyclonedds.xml
    volumes:
      - ./src:/ros2_ws/src                               # user ROS2 nodes
      - ./docker/cyclonedds.xml:/ros2_ws/cyclonedds.xml:ro  # DDS config
    stdin_open: true
    tty: true
```

### CycloneDDS Config (`docker/cyclonedds.xml`)

`NetworkInterfaceAddress` starts as `auto`. When connecting to robot over
Ethernet, update to the Pi's Ethernet interface name (e.g., `eth0`) and add
the robot's peer IP. No image rebuild needed — file is volume-mounted.

### `.env`
```
ROS_DOMAIN_ID=0
```

---

## 4. Communication Architecture

```
Browser (Windows, hospital WiFi)
├── React → ws://rpi5:9090   (rosbridge)  ← real-time: health, status, topics
└── React → http://rpi5:8000 (FastAPI)    ← commands: task dispatch, e-stop

RPi5 Host
├── FastAPI → ws://localhost:9090 (rosbridge) ← publishes ROS2 commands
└── rosbridge (9090) ↔ snoopi-ros2 container ← all ROS2 traffic

Container (--network=host)
└── rosbridge_suite ↔ ROS2 topics/services
```

### Port Assignments
| Service | Port | Runs On |
|---|---|---|
| rosbridge | 9090 | container (host network) |
| FastAPI | 8000 | RPi5 host |
| React dev server | 5173 | RPi5 host |

### Telemetry vs Commands
- **Robot telemetry** (battery, temperature, IMU, LiDAR): React subscribes
  directly to ROS2 topics via rosbridge WebSocket. Pushed in real-time.
  FastAPI does not handle telemetry.
- **Commands** (task dispatch, e-stop, sit, stand): React calls FastAPI REST
  endpoints. FastAPI forwards to rosbridge as ROS2 service/topic calls.
- **`GET /health`**: Backend health check only (is FastAPI alive, is rosbridge
  reachable). Not robot telemetry.

---

## 5. FastAPI Backend

**Location:** `backend/` — runs on RPi5 host, not in Docker.

**Runtime:**
```bash
[PI] cd ~/snoopi/backend
[PI] python3 -m venv venv
[PI] source venv/bin/activate
[PI] pip install -r requirements.txt
[PI] uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Structure (flat for MVP):**
```
backend/
├── main.py          ← FastAPI app + all routes
├── requirements.txt ← fastapi, uvicorn, websockets, python-dotenv
└── .env             ← ROSBRIDGE_URL=ws://localhost:9090
```

**Routes:**
```
GET  /health       ← is FastAPI up, is rosbridge reachable?
POST /tasks        ← dispatch task {type: "walk", distance_m: 200}
GET  /tasks/{id}   ← task status
POST /estop        ← emergency stop command
```

Expand to routers/services/models when complexity warrants it (post-MVP).

---

## 6. React Frontend

**Location:** `ui/` — runs on RPi5 host, not in Docker.

**Stack:** Vite + React + TypeScript.
Next.js was considered and rejected: the system is a local-network application.
Vercel hosting conflicts with rosbridge requiring LAN access. SSR adds complexity
with no benefit for a WebSocket-driven real-time dashboard.

**Runtime:**
```bash
[PI] cd ~/snoopi/ui
[PI] npm install
[PI] npm run dev -- --host   # --host exposes on Pi's IP, not just localhost
```

**Structure:**
```
ui/
├── package.json
├── vite.config.ts
├── tsconfig.json
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── hooks/
    │   └── useRosbridge.ts    ← manages rosbridge WebSocket lifecycle
    └── components/
        ├── ConnectionStatus.tsx
        ├── HealthDashboard.tsx  ← battery %, temperature, joint status
        └── CommandPanel.tsx     ← sit, stand, e-stop buttons
```

`useRosbridge` is the central hook — wraps `roslibjs`, manages connection state,
exposes `subscribe` and `publish` to all components.

---

## 7. Mock Publisher (Testing Without the Robot)

A ROS2 node `mock_robot_publisher.py` lives in `src/` and publishes fake
telemetry on the same topics the real go2_ros2_sdk uses:
- `/battery_state` (sensor_msgs/BatteryState)
- `/imu` (sensor_msgs/Imu)
- `/joint_states` (sensor_msgs/JointState)

Lets the full UI ↔ rosbridge ↔ ROS2 pipeline be validated before the robot
arrives. Swap in the real SDK launch file — the UI sees no difference.

---

## 8. What Can Be Done Without the Robot

| Work Item | Completable? |
|---|---|
| Build and validate Docker image | ✅ 100% |
| ROS2 smoke tests inside container | ✅ 100% |
| CycloneDDS configuration | ✅ 100% |
| FastAPI backend (all endpoints with mock responses) | ✅ 100% |
| React frontend (all components with mock data) | ✅ 100% |
| Full UI ↔ rosbridge ↔ mock publisher pipeline | ✅ 100% |
| go2_ros2_sdk build validation (ARM64) | ✅ build only |
| Hardware connection and SDK live test | ❌ needs robot |
| SLAM mapping | ❌ needs robot |
| Nav2 real-world tuning | ❌ needs robot |

---

## Decisions Log

| Decision | Choice | Reason |
|---|---|---|
| OS mismatch resolution | Docker (Ubuntu 22.04 base) | Cleaner than downgrading Pi OS |
| Image base | `osrf/ros:humble-ros-base` | ARM64 support, pre-configured apt repo |
| SDK workspace | Baked into image (`/opt/go2_ws/`) | Pre-compiled, not rebuilt on every start |
| User workspace | Volume-mounted (`./src → /ros2_ws/src`) | Edit on host, no image rebuild needed |
| DDS networking | `network_mode: host` | Multicast discovery fails on Docker bridge |
| Restart policy | `unless-stopped` | Survives reboots, respects manual stop |
| UI hosting | RPi5 host (not Vercel) | Local network system; Vercel conflicts with rosbridge LAN access |
| UI framework | Vite + React + TypeScript | TypeScript for type safety; Vite over Next.js (no SSR needed, no Vercel) |
| UI ↔ ROS2 | roslibjs direct to rosbridge | Lower latency for real-time data than proxying through FastAPI |
| Camera feed | Post-MVP | Not in MVP scope per project.md |
