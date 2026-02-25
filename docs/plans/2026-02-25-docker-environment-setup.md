# Docker Environment Setup — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build and validate the full development environment: Docker container with ROS2 Humble + go2_ros2_sdk, FastAPI backend, React/TypeScript frontend, and a mock robot publisher that lets the entire pipeline run without the physical dog.

**Architecture:** A Docker container (`snoopi-ros2`) runs all ROS2 infrastructure on the RPi5 using `--network=host` for DDS. FastAPI and React run natively on the Ubuntu 24.04 host. Git is the sync mechanism between Windows (where files are authored) and the Pi (where everything executes).

**Tech Stack:** Docker, ROS2 Humble, Nav2, SLAM Toolbox, rosbridge_suite, CycloneDDS, go2_ros2_sdk, FastAPI, uvicorn, pytest, Vite, React, TypeScript, roslibjs (npm: `roslib`)

---

## Workflow Reminder

Every task follows this pattern:
- Steps marked `[WINDOWS]` run on your Windows dev machine
- Steps marked `[PI]` run via SSH on the RPi5
- Steps marked `[PI - container]` run after `docker exec -it snoopi-ros2 bash`
- After each `[WINDOWS]` file creation block: commit, push, then pull on the Pi

---

## Task 1: Project Scaffolding

**Files:**
- Create: `docker/entrypoint.sh`
- Create: `docker/cyclonedds.xml`
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.env`
- Create: `.gitignore` (update)

**Step 1: Create `docker/entrypoint.sh`**

```bash
#!/bin/bash
set -e

# Layer 1: ROS2 base
source /opt/ros/humble/setup.bash

# Layer 2: go2_ros2_sdk workspace (baked into image)
source /opt/go2_ws/install/setup.bash

# Layer 3: user workspace (volume-mounted src/, only source if built)
if [ -f /ros2_ws/install/setup.bash ]; then
    source /ros2_ws/install/setup.bash
fi

exec "$@"
```

**Step 2: Create `docker/cyclonedds.xml`**

```xml
<?xml version="1.0" encoding="UTF-8" ?>
<CycloneDDS xmlns="https://cdds.io/config"
            xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
            xsi:schemaLocation="https://cdds.io/config
            https://raw.githubusercontent.com/eclipse-cyclonedds/cyclonedds/master/etc/cyclonedds.xsd">
  <Domain id="any">
    <General>
      <!-- auto = CycloneDDS picks the best available interface -->
      <!-- When connecting to robot over Ethernet, change to your interface name -->
      <!-- Run 'ip link show' on the Pi to find it (usually eth0 or enp3s0) -->
      <NetworkInterfaceAddress>auto</NetworkInterfaceAddress>
    </General>
    <Discovery>
      <ParticipantIndex>auto</ParticipantIndex>
      <!-- Uncomment and add robot IP when ready to connect:
      <Peers>
        <Peer Address="192.168.123.161"/>
      </Peers>
      -->
    </Discovery>
  </Domain>
</CycloneDDS>
```

**Step 3: Create `Dockerfile`**

Each `RUN` block is a separate Docker layer. Docker caches layers — if you change a line, only that layer and everything below it rebuilds. The go2_ros2_sdk build is near the bottom so earlier layers (apt installs) stay cached.

```dockerfile
FROM osrf/ros:humble-ros-base

# Suppress interactive prompts during apt installs
ENV DEBIAN_FRONTEND=noninteractive

# Layer: system build tools and utilities
RUN apt-get update && apt-get install -y \
    clang \
    portaudio19-dev \
    python3-pip \
    python3-colcon-common-extensions \
    python3-rosdep \
    git \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Layer: ROS2 packages
# Each package installs into /opt/ros/humble/ alongside the base install
RUN apt-get update && apt-get install -y \
    ros-humble-navigation2 \
    ros-humble-nav2-bringup \
    ros-humble-slam-toolbox \
    ros-humble-rosbridge-suite \
    ros-humble-rmw-cyclonedds-cpp \
    ros-humble-vision-msgs \
    ros-humble-image-tools \
    ros-humble-teleop-twist-keyboard \
    ros-humble-xacro \
    ros-humble-robot-state-publisher \
    ros-humble-joint-state-publisher \
    && rm -rf /var/lib/apt/lists/*

# Layer: clone go2_ros2_sdk into its own workspace at /opt/go2_ws/
# This workspace is separate from /ros2_ws/ (your nodes) so the SDK
# is pre-compiled in the image and never rebuilt during development.
WORKDIR /opt/go2_ws
RUN mkdir src && \
    git clone https://github.com/abizovnuralem/go2_ros2_sdk.git src/go2_ros2_sdk

# Layer: SDK Python dependencies (WebRTC, async libs, etc.)
RUN pip3 install --no-cache-dir \
    -r /opt/go2_ws/src/go2_ros2_sdk/requirements.txt

# Layer: build the SDK workspace with colcon
# This is the slow step (~15-25 min on ARM64 first time).
# source the ROS2 base first so colcon knows about ROS2 message types.
RUN /bin/bash -c "source /opt/ros/humble/setup.bash && \
    colcon build \
    --symlink-install \
    --cmake-args -DCMAKE_BUILD_TYPE=Release"

# Create the user workspace mount point
# ./src on the host is mounted here at runtime via docker-compose volumes
RUN mkdir -p /ros2_ws/src

# Copy entrypoint script
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set ROS middleware to CycloneDDS
# CYCLONEDDS_URI points to the config file (volume-mounted at runtime)
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
ENV CYCLONEDDS_URI=/ros2_ws/cyclonedds.xml

WORKDIR /ros2_ws

ENTRYPOINT ["/entrypoint.sh"]
# Default: keep container alive so you can docker exec into it
CMD ["tail", "-f", "/dev/null"]
```

**Step 4: Create `docker-compose.yml`**

```yaml
services:
  snoopi-ros2:
    build: .
    image: snoopi-ros2:latest
    container_name: snoopi-ros2
    # host networking: container shares the Pi's network stack directly.
    # Required for CycloneDDS multicast discovery to work.
    network_mode: host
    # unless-stopped: restart on reboot/crash, but NOT after manual docker stop
    restart: unless-stopped
    environment:
      - ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-0}
      - RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
      - CYCLONEDDS_URI=/ros2_ws/cyclonedds.xml
    volumes:
      # Your ROS2 node source code — edit on host, build inside container
      - ./src:/ros2_ws/src
      # DDS config — edit without rebuilding the image
      - ./docker/cyclonedds.xml:/ros2_ws/cyclonedds.xml:ro
    # Keep stdin/tty open so docker exec works cleanly
    stdin_open: true
    tty: true
```

**Step 5: Create `.env`**

```
ROS_DOMAIN_ID=0
```

**Step 6: Update `.gitignore`**

Add these lines (create the file if it doesn't exist):

```
# Python
backend/venv/
backend/__pycache__/
backend/.env
**/__pycache__/
*.pyc

# Node
ui/node_modules/
ui/dist/

# ROS2 build artifacts (these live on the Pi, not in the repo)
src/*/build/
src/*/install/
src/*/log/

# Docker
.env
```

Note: `.env` is gitignored. Each machine (Windows dev, Pi) has its own copy.
Create `.env` manually on the Pi after pulling.

**Step 7: Commit and sync**

```bash
[WINDOWS] git add docker/ Dockerfile docker-compose.yml .gitignore
[WINDOWS] git commit -m "feat: add docker scaffolding (Dockerfile, compose, CycloneDDS, entrypoint)"
[WINDOWS] git push
[PI]      git pull
```

---

## Task 2: Build the Docker Image

This task runs entirely on the Pi. No file changes.

**Step 1: Verify Docker is installed**

```bash
[PI] docker --version
[PI] docker-compose --version
```

Expected: Docker 24+ and Docker Compose 2+. If not installed:
```bash
[PI] sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2
[PI] sudo usermod -aG docker $USER   # run docker without sudo
[PI] newgrp docker                   # apply group change without logout
```

**Step 2: Build the image**

```bash
[PI] cd ~/snoopi
[PI] docker-compose build
```

Expected: long output showing each apt install, pip install, and colcon build.
The colcon build step (go2_ros2_sdk) takes 15–25 minutes on ARM64. This is normal.
Final line: `Successfully tagged snoopi-ros2:latest`

If the build fails mid-way, Docker will use its cache on the next attempt and
skip already-completed layers. You only retry from the failed layer.

**Step 3: Verify the image exists**

```bash
[PI] docker images | grep snoopi
```

Expected output:
```
snoopi-ros2   latest   <hash>   <timestamp>   ~2.5GB
```

---

## Task 3: Smoke Test the Container

**Step 1: Start the container**

```bash
[PI] cd ~/snoopi
[PI] docker-compose up -d
```

`-d` means detached (runs in background). The container starts and keeps alive
via `tail -f /dev/null`.

**Step 2: Verify the container is running**

```bash
[PI] docker ps
```

Expected: one row with `snoopi-ros2`, status `Up`.

**Step 3: Open a shell inside the container**

```bash
[PI] docker exec -it snoopi-ros2 bash
```

You're now inside the container. The prompt will change. All remaining steps in
this task run inside.

**Step 4: Verify ROS2 environment**

```bash
[PI - container] echo $RMW_IMPLEMENTATION
```
Expected: `rmw_cyclonedds_cpp`

```bash
[PI - container] ros2 --version
```
Expected: `ros2 library version X.X.X`

```bash
[PI - container] ros2 topic list
```
Expected: `/parameter_events` and `/rosout` (these are always present). No errors.

**Step 5: Verify go2_ros2_sdk is built**

```bash
[PI - container] ls /opt/go2_ws/install/
```
Expected: directories for each go2_ros2_sdk package (go2_interfaces, go2_robot_state_publisher, etc.)

**Step 6: Verify Nav2 is installed**

```bash
[PI - container] ros2 pkg list | grep nav2
```
Expected: several `nav2_*` packages listed.

**Step 7: Verify rosbridge is installed**

```bash
[PI - container] ros2 pkg list | grep rosbridge
```
Expected: `rosbridge_server`, `rosbridge_library`, `rosbridge_msgs`

**Step 8: Exit the container shell**

```bash
[PI - container] exit
```

No commit needed for this task — it's validation only.

---

## Task 4: Launch and Test rosbridge

rosbridge is the WebSocket server that lets the React frontend communicate with ROS2.
This task verifies it starts correctly inside the container.

**Step 1: Open a shell in the container**

```bash
[PI] docker exec -it snoopi-ros2 bash
```

**Step 2: Launch rosbridge**

```bash
[PI - container] ros2 launch rosbridge_server rosbridge_websocket_launch.xml
```

Expected: output ending with:
```
[rosbridge_websocket-1] Rosbridge WebSocket server started on port 9090
```

Leave this running. Open a second terminal for the next step.

**Step 3: Verify port 9090 is open (second terminal)**

```bash
[PI] ss -tlnp | grep 9090
```

Expected: a line showing something listening on `0.0.0.0:9090` or `*:9090`.
Because the container uses `--network=host`, port 9090 is directly on the Pi's
network stack — no port mapping needed.

**Step 4: Stop rosbridge**

Go back to the first terminal and press `Ctrl+C`.

**Step 5: Exit the container**

```bash
[PI - container] exit
```

---

## Task 5: FastAPI Backend

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/.env`
- Create: `backend/main.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_main.py`

**Step 1: Create `backend/requirements.txt`**

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
websockets==13.0
python-dotenv==1.0.0
httpx==0.27.0
pytest==8.3.0
pytest-asyncio==0.24.0
anyio==4.4.0
```

**Step 2: Create `backend/.env`**

This file is gitignored. Each developer creates it manually.
Document its required contents here so it's not lost:

```
ROSBRIDGE_URL=ws://localhost:9090
```

**Step 3: Write the failing tests first**

Create `backend/tests/__init__.py` (empty file).

Create `backend/tests/test_main.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture
def app():
    from main import app
    return app


@pytest.mark.asyncio
async def test_health_returns_ok(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "rosbridge" in response.json()


@pytest.mark.asyncio
async def test_create_walk_task(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/tasks", json={"type": "walk", "distance_m": 100})
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "walk"
    assert data["distance_m"] == 100
    assert "id" in data
    assert "status" in data


@pytest.mark.asyncio
async def test_invalid_task_type(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/tasks", json={"type": "fly", "distance_m": 100})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_negative_distance_rejected(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/tasks", json={"type": "walk", "distance_m": -5})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_task_not_found(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/tasks/9999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_task_after_create(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create = await client.post("/tasks", json={"type": "walk", "distance_m": 50})
        task_id = create.json()["id"]
        get = await client.get(f"/tasks/{task_id}")
    assert get.status_code == 200
    assert get.json()["id"] == task_id


@pytest.mark.asyncio
async def test_estop_returns_status(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/estop")
    assert response.status_code == 200
    assert "status" in response.json()
```

**Step 4: Commit tests before writing implementation**

```bash
[WINDOWS] git add backend/
[WINDOWS] git commit -m "test: add FastAPI endpoint tests (red)"
[WINDOWS] git push
```

**Step 5: Create `backend/main.py`**

```python
import asyncio
import json
import os
from contextlib import asynccontextmanager

import websockets
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

ROSBRIDGE_URL = os.getenv("ROSBRIDGE_URL", "ws://localhost:9090")

# MVP: in-memory task store. Replaced with persistent store post-MVP.
_tasks: dict[str, dict] = {}
_task_counter = 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Snoopi API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten for production
    allow_methods=["*"],
    allow_headers=["*"],
)


class TaskRequest(BaseModel):
    type: str
    distance_m: float


class TaskResponse(BaseModel):
    id: str
    type: str
    distance_m: float
    status: str


async def _publish(topic: str, msg_type: str, data: dict) -> bool:
    """Send a single publish message to rosbridge and close the connection."""
    try:
        async with websockets.connect(ROSBRIDGE_URL, open_timeout=3) as ws:
            await ws.send(json.dumps({
                "op": "publish",
                "topic": topic,
                "type": msg_type,
                "msg": data,
            }))
        return True
    except Exception:
        return False


@app.get("/health")
async def health():
    """Backend health check. Reports whether rosbridge is reachable."""
    try:
        async with websockets.connect(ROSBRIDGE_URL, open_timeout=2):
            rosbridge_status = "reachable"
    except Exception:
        rosbridge_status = "unreachable"
    return {"status": "ok", "rosbridge": rosbridge_status}


@app.post("/tasks", response_model=TaskResponse)
async def create_task(req: TaskRequest):
    global _task_counter
    if req.type != "walk":
        raise HTTPException(status_code=400, detail="Only 'walk' tasks supported in MVP")
    if req.distance_m <= 0:
        raise HTTPException(status_code=400, detail="distance_m must be positive")

    _task_counter += 1
    task_id = str(_task_counter)
    _tasks[task_id] = {
        "id": task_id,
        "type": req.type,
        "distance_m": req.distance_m,
        "status": "pending",
    }

    await _publish(
        topic="/snoopi/task_command",
        msg_type="std_msgs/String",
        data={"data": json.dumps({"type": req.type, "distance_m": req.distance_m, "task_id": task_id})},
    )
    _tasks[task_id]["status"] = "dispatched"
    return _tasks[task_id]


@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return _tasks[task_id]


@app.post("/estop")
async def estop():
    """Publish emergency stop command to ROS2 via rosbridge."""
    ok = await _publish(
        topic="/snoopi/estop",
        msg_type="std_msgs/Bool",
        data={"data": True},
    )
    return {"status": "sent" if ok else "failed", "rosbridge_reachable": ok}
```

**Step 6: Set up Python environment on the Pi and run tests**

```bash
[PI] cd ~/snoopi/backend
[PI] git pull
[PI] python3 -m venv venv
[PI] source venv/bin/activate
[PI] pip install -r requirements.txt
```

Create the backend `.env` on the Pi (gitignored, so create manually):
```bash
[PI] echo "ROSBRIDGE_URL=ws://localhost:9090" > ~/snoopi/backend/.env
```

Run the tests:
```bash
[PI] cd ~/snoopi/backend
[PI] source venv/bin/activate
[PI] python -m pytest tests/ -v
```

Expected: all 7 tests pass. The `/health` and `/estop` tests will show
`rosbridge: unreachable` — this is correct since rosbridge isn't running yet.
The important thing is the status codes are all correct.

**Step 7: Commit**

```bash
[WINDOWS] git add backend/main.py
[WINDOWS] git commit -m "feat: add FastAPI backend with task dispatch and estop endpoints"
[WINDOWS] git push
```

---

## Task 6: React Frontend Scaffold

**Files:**
- Create: `ui/` (via Vite CLI on Pi)
- Modify: `ui/src/App.tsx`
- Create: `ui/src/hooks/useRosbridge.ts`
- Create: `ui/src/components/ConnectionStatus.tsx`
- Create: `ui/src/components/HealthDashboard.tsx`
- Create: `ui/src/components/CommandPanel.tsx`

**Step 1: Install Node.js 20 LTS on the Pi**

Ubuntu 24.04's default Node might be outdated. Install Node 20 LTS:

```bash
[PI] curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
[PI] sudo apt-get install -y nodejs
[PI] node --version
```

Expected: `v20.x.x`

**Step 2: Scaffold the Vite + React + TypeScript project**

Run from the repo root so `ui/` is created in the right place:

```bash
[PI] cd ~/snoopi
[PI] npm create vite@latest ui -- --template react-ts
```

When prompted, confirm the target directory is `ui/`.

**Step 3: Install dependencies**

```bash
[PI] cd ~/snoopi/ui
[PI] npm install
[PI] npm install roslib
[PI] npm install --save-dev @types/roslib
```

`roslib` is the npm package name for roslibjs.

**Step 4: Commit the scaffolded ui/ directory**

```bash
[WINDOWS] git pull   # pull the ui/ scaffold the Pi just created via npm create
```

Wait — the scaffold was created on the Pi, not Windows. Reverse the sync:

```bash
[PI] cd ~/snoopi
[PI] git add ui/
[PI] git commit -m "feat: scaffold Vite + React + TypeScript frontend"
[PI] git push
[WINDOWS] git pull
```

This is the one case where the Pi commits instead of Windows.

**Step 5: Create `ui/src/hooks/useRosbridge.ts`**

```typescript
import { useEffect, useRef, useState, useCallback } from 'react';
import ROSLIB from 'roslib';

interface RosbridgeHook {
  connected: boolean;
  subscribe: <T>(topic: string, msgType: string, callback: (msg: T) => void) => () => void;
  publish: (topic: string, msgType: string, msg: object) => void;
}

export function useRosbridge(url: string): RosbridgeHook {
  const rosRef = useRef<ROSLIB.Ros | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const ros = new ROSLIB.Ros({ url });
    rosRef.current = ros;

    ros.on('connection', () => setConnected(true));
    ros.on('error', () => setConnected(false));
    ros.on('close', () => setConnected(false));

    return () => {
      ros.close();
      setConnected(false);
    };
  }, [url]);

  const subscribe = useCallback(<T>(
    topic: string,
    msgType: string,
    callback: (msg: T) => void,
  ) => {
    if (!rosRef.current) return () => {};
    const t = new ROSLIB.Topic({ ros: rosRef.current, name: topic, messageType: msgType });
    t.subscribe((msg) => callback(msg as T));
    return () => t.unsubscribe();
  }, []);

  const publish = useCallback((topic: string, msgType: string, msg: object) => {
    if (!rosRef.current) return;
    const t = new ROSLIB.Topic({ ros: rosRef.current, name: topic, messageType: msgType });
    t.publish(new ROSLIB.Message(msg));
  }, []);

  return { connected, subscribe, publish };
}
```

**Step 6: Create `ui/src/components/ConnectionStatus.tsx`**

```tsx
interface Props {
  connected: boolean;
}

export function ConnectionStatus({ connected }: Props) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{
        width: 12,
        height: 12,
        borderRadius: '50%',
        backgroundColor: connected ? '#22c55e' : '#ef4444',
      }} />
      <span>{connected ? 'ROS2 Connected' : 'ROS2 Disconnected'}</span>
    </div>
  );
}
```

**Step 7: Create `ui/src/components/HealthDashboard.tsx`**

```tsx
import { useEffect, useState } from 'react';

interface BatteryState {
  percentage: number;
  voltage: number;
  temperature: number;
}

interface Imu {
  linear_acceleration: { x: number; y: number; z: number };
}

interface Props {
  subscribe: <T>(topic: string, msgType: string, callback: (msg: T) => void) => () => void;
}

export function HealthDashboard({ subscribe }: Props) {
  const [battery, setBattery] = useState<BatteryState | null>(null);
  const [imu, setImu] = useState<Imu | null>(null);

  useEffect(() => {
    const unsubBattery = subscribe<BatteryState>(
      '/utlidar/battery',
      'sensor_msgs/BatteryState',
      setBattery,
    );
    const unsubImu = subscribe<Imu>(
      '/imu/data',
      'sensor_msgs/Imu',
      setImu,
    );
    return () => { unsubBattery(); unsubImu(); };
  }, [subscribe]);

  const batteryPct = battery ? Math.round(battery.percentage * 100) : null;
  const temp = battery ? battery.temperature.toFixed(1) : null;

  return (
    <div>
      <h2>Health Monitor</h2>
      <p>Battery: {batteryPct !== null ? `${batteryPct}%` : 'Waiting...'}</p>
      <p>Temperature: {temp !== null ? `${temp}°C` : 'Waiting...'}</p>
      <p>IMU z-accel: {imu ? imu.linear_acceleration.z.toFixed(2) : 'Waiting...'}</p>
    </div>
  );
}
```

**Step 8: Create `ui/src/components/CommandPanel.tsx`**

```tsx
const API = 'http://localhost:8000';

interface Props {
  publish: (topic: string, msgType: string, msg: object) => void;
  connected: boolean;
}

export function CommandPanel({ publish, connected }: Props) {
  const sit = () => publish('/snoopi/command', 'std_msgs/String', { data: 'sit' });
  const stand = () => publish('/snoopi/command', 'std_msgs/String', { data: 'stand' });
  const estop = () => fetch(`${API}/estop`, { method: 'POST' });

  return (
    <div>
      <h2>Commands</h2>
      <button onClick={sit} disabled={!connected}>Sit</button>
      <button onClick={stand} disabled={!connected}>Stand</button>
      <button
        onClick={estop}
        style={{ backgroundColor: '#ef4444', color: 'white', marginLeft: 16 }}
      >
        E-STOP
      </button>
    </div>
  );
}
```

Note: E-STOP is intentionally always enabled (not gated on `connected`) — it goes
through FastAPI, which can attempt the rosbridge call regardless of UI state.

**Step 9: Replace `ui/src/App.tsx`**

```tsx
import { useRosbridge } from './hooks/useRosbridge';
import { ConnectionStatus } from './components/ConnectionStatus';
import { HealthDashboard } from './components/HealthDashboard';
import { CommandPanel } from './components/CommandPanel';

const ROSBRIDGE_URL = 'ws://localhost:9090';

function App() {
  const { connected, subscribe, publish } = useRosbridge(ROSBRIDGE_URL);

  return (
    <div style={{ fontFamily: 'sans-serif', padding: 24 }}>
      <h1>Snoopi — Hospital Robot Dashboard</h1>
      <ConnectionStatus connected={connected} />
      <hr />
      <HealthDashboard subscribe={subscribe} />
      <hr />
      <CommandPanel publish={publish} connected={connected} />
    </div>
  );
}

export default App;
```

**Step 10: Commit and sync**

```bash
[WINDOWS] git add ui/src/
[WINDOWS] git commit -m "feat: add React frontend scaffold with health dashboard and command panel"
[WINDOWS] git push
[PI]      git pull
```

---

## Task 7: Mock Robot Publisher

This ROS2 node publishes fake telemetry so the full pipeline can be tested
without the physical robot.

**Files:**
- Create: `src/snoopi_mock/package.xml`
- Create: `src/snoopi_mock/setup.py`
- Create: `src/snoopi_mock/setup.cfg`
- Create: `src/snoopi_mock/snoopi_mock/__init__.py`
- Create: `src/snoopi_mock/snoopi_mock/mock_robot_publisher.py`

**Step 1: Create `src/snoopi_mock/package.xml`**

```xml
<?xml version="1.0"?>
<?xml-model href="http://download.ros.org/schema/package_format3.xsd" schematypens="http://www.w3.org/2001/XMLSchema"?>
<package format="3">
  <name>snoopi_mock</name>
  <version>0.1.0</version>
  <description>Mock robot publisher for testing without the physical Go2 Air</description>
  <maintainer email="dev@snoopi.local">snoopi</maintainer>
  <license>MIT</license>

  <exec_depend>rclpy</exec_depend>
  <exec_depend>sensor_msgs</exec_depend>
  <exec_depend>std_msgs</exec_depend>

  <export>
    <build_type>ament_python</build_type>
  </export>
</package>
```

**Step 2: Create `src/snoopi_mock/setup.cfg`**

```ini
[develop]
script_dir=$base/lib/snoopi_mock
[install]
install_scripts=$base/lib/snoopi_mock
```

**Step 3: Create `src/snoopi_mock/setup.py`**

```python
from setuptools import find_packages, setup

setup(
    name='snoopi_mock',
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    install_requires=['setuptools'],
    entry_points={
        'console_scripts': [
            'mock_robot_publisher = snoopi_mock.mock_robot_publisher:main',
        ],
    },
)
```

**Step 4: Create `src/snoopi_mock/snoopi_mock/__init__.py`** (empty)

**Step 5: Create `src/snoopi_mock/snoopi_mock/mock_robot_publisher.py`**

```python
"""
Mock robot publisher.
Publishes fake Go2 Air telemetry on the same topics the real SDK uses.
Lets the full UI ↔ rosbridge ↔ ROS2 pipeline run without the physical robot.
"""
import math
import time

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import BatteryState, Imu, JointState


class MockRobotPublisher(Node):
    def __init__(self):
        super().__init__('mock_robot_publisher')
        self._battery_pub = self.create_publisher(BatteryState, '/utlidar/battery', 10)
        self._imu_pub = self.create_publisher(Imu, '/imu/data', 10)
        self._joint_pub = self.create_publisher(JointState, '/joint_states', 10)
        self._start = time.time()
        # Publish at 1 Hz — matches the real robot's joint state rate
        self.create_timer(1.0, self._publish_all)
        self.get_logger().info('Mock robot publisher started — publishing fake telemetry')

    def _publish_all(self) -> None:
        elapsed = time.time() - self._start

        # Battery: starts at 100%, drains slowly to 80% over 20 minutes
        battery = BatteryState()
        battery.percentage = max(0.8, 1.0 - (elapsed / 1200.0))
        battery.voltage = 25.0
        battery.temperature = 35.0 + math.sin(elapsed / 60.0) * 3.0
        self._battery_pub.publish(battery)

        # IMU: stationary with tiny oscillations to look realistic
        imu = Imu()
        imu.linear_acceleration.x = 0.0
        imu.linear_acceleration.y = 0.0
        imu.linear_acceleration.z = 9.81
        imu.angular_velocity.x = math.sin(elapsed) * 0.01
        imu.angular_velocity.y = math.cos(elapsed) * 0.01
        imu.angular_velocity.z = 0.0
        self._imu_pub.publish(imu)

        # Joint states: 12 joints (FL/FR/RL/RR × hip/thigh/calf), all at rest
        joint = JointState()
        joint.name = [
            'FL_hip_joint', 'FL_thigh_joint', 'FL_calf_joint',
            'FR_hip_joint', 'FR_thigh_joint', 'FR_calf_joint',
            'RL_hip_joint', 'RL_thigh_joint', 'RL_calf_joint',
            'RR_hip_joint', 'RR_thigh_joint', 'RR_calf_joint',
        ]
        joint.position = [0.0] * 12
        joint.velocity = [0.0] * 12
        joint.effort = [0.0] * 12
        self._joint_pub.publish(joint)


def main() -> None:
    rclpy.init()
    node = MockRobotPublisher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
```

**Step 6: Commit and sync**

```bash
[WINDOWS] git add src/snoopi_mock/
[WINDOWS] git commit -m "feat: add mock robot publisher for pipeline testing without hardware"
[WINDOWS] git push
[PI]      git pull
```

**Step 7: Build the mock package inside the container**

```bash
[PI] docker exec -it snoopi-ros2 bash
[PI - container] cd /ros2_ws
[PI - container] colcon build --symlink-install --packages-select snoopi_mock
[PI - container] source install/setup.bash
```

Expected: `Finished <<< snoopi_mock`

**Step 8: Verify the node is executable**

```bash
[PI - container] ros2 pkg list | grep snoopi
```

Expected: `snoopi_mock`

```bash
[PI - container] exit
```

---

## Task 8: Full Integration Test

This is the milestone checkpoint. All three services run together and data flows
from the mock publisher through rosbridge to the browser.

**Step 1: Start the ROS2 container (if not already running)**

```bash
[PI] cd ~/snoopi
[PI] docker-compose up -d
[PI] docker ps   # confirm snoopi-ros2 is Up
```

**Step 2: Start rosbridge (Terminal 1 on Pi)**

```bash
[PI] docker exec -it snoopi-ros2 bash
[PI - container] ros2 launch rosbridge_server rosbridge_websocket_launch.xml
```

Leave this running.

**Step 3: Start the mock publisher (Terminal 2 on Pi)**

```bash
[PI] docker exec -it snoopi-ros2 bash
[PI - container] ros2 run snoopi_mock mock_robot_publisher
```

Expected: `Mock robot publisher started — publishing fake telemetry`

**Step 4: Verify topics are publishing (Terminal 3 on Pi)**

```bash
[PI] docker exec -it snoopi-ros2 bash
[PI - container] ros2 topic list
```

Expected: `/utlidar/battery`, `/imu/data`, `/joint_states` appear in the list.

```bash
[PI - container] ros2 topic echo /utlidar/battery --once
```

Expected: battery message with `percentage`, `voltage`, `temperature` fields.

**Step 5: Start the FastAPI backend (Terminal 3, after exiting container)**

```bash
[PI - container] exit
[PI] cd ~/snoopi/backend
[PI] source venv/bin/activate
[PI] uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Step 6: Verify the backend health endpoint**

```bash
[PI] curl http://localhost:8000/health
```

Expected: `{"status":"ok","rosbridge":"reachable"}`

**Step 7: Start the React dev server (Terminal 4 on Pi)**

```bash
[PI] cd ~/snoopi/ui
[PI] npm run dev -- --host
```

Expected output includes:
```
Local:   http://localhost:5173/
Network: http://<pi-ip>:5173/
```

**Step 8: Open the dashboard in your browser**

```
[BROWSER] http://<pi-ip>:5173
```

Replace `<pi-ip>` with the RPi5's IP address (find it with `hostname -I` on the Pi).

**Checkpoint — what you should see:**
- Green dot: "ROS2 Connected"
- Battery percentage updating every ~1 second (starting near 100%)
- Temperature value oscillating slightly
- IMU z-acceleration showing ~9.81
- Sit / Stand buttons enabled
- E-STOP button always enabled

**Step 9: Test the E-STOP endpoint manually**

```bash
[PI] curl -X POST http://localhost:8000/estop
```

Expected: `{"status":"sent","rosbridge_reachable":true}`

---

## Task 9: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Update CLAUDE.md**

Move Milestone 1 to Completed Milestones with today's date.
Update Current Milestone to Milestone 2.
Update Active Tasks to Milestone 2's task list.
Add a note that the dev environment uses Docker (Ubuntu 22.04 container)
on an Ubuntu 24.04 host, and that the sync workflow is git push/pull.

**Step 2: Commit**

```bash
[WINDOWS] git add CLAUDE.md
[WINDOWS] git commit -m "milestone: complete Milestone 1 — Docker environment validated"
[WINDOWS] git push
[PI]      git pull
```

---

## Milestone 1 Complete

**Evidence of completion:**
- `docker images` shows `snoopi-ros2:latest`
- `ros2 topic list` works inside the container
- Browser dashboard at `http://<pi-ip>:5173` shows live mock telemetry
- `curl http://localhost:8000/health` returns `rosbridge: reachable`
- All 7 FastAPI pytest tests pass

**Next:** Milestone 2 — Hardware Connection (requires physical robot)
