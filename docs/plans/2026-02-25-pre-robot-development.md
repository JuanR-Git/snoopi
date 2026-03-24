# Pre-Robot Development Plan
**Date:** 2026-02-25
**Goal:** Build everything that can be built and tested without the physical Go2 Air, so that when the robot arrives, the only remaining work is plugging it in and testing.
**Status:** Ready for implementation

---

## What's Already Done

| Item | Status |
|------|--------|
| Docker image built on RPi5 (ros:humble-ros-base-jammy) | Done |
| ROS2 Humble, Nav2, SLAM Toolbox, rosbridge, CycloneDDS installed | Done |
| go2_ros2_sdk cloned and built (skipping lidar_processor_cpp, coco_detector) | Done |
| ARM64-curated pip deps (excluding open3d, torch, torchvision) | Done |
| Container verified: `ros2 topic list`, all package checks pass | Done |
| Docker exec `.bashrc` fix for interactive shells | Done |

## What This Plan Covers

Everything below can be completed on the RPi5 **without the robot**:

1. **rosbridge verification** — confirm the WebSocket bridge works
2. **Mock robot publisher** — fake Go2 telemetry on real ROS2 topics
3. **FastAPI backend** — REST API for task dispatch and e-stop
4. **React frontend** — health dashboard, command panel, connection status
5. **Full integration test** — mock data flows from ROS2 → rosbridge → browser

When the robot arrives, the only remaining work is:
- Connect Pi to Go2 over Ethernet/WiFi
- Launch the real SDK instead of the mock publisher
- Map the environment (SLAM)
- Tune Nav2 parameters
- End-to-end testing with real hardware

---

## Workflow Reminder

Every task follows this pattern:
- Steps marked `[WINDOWS]` run on your Windows dev machine (where Claude edits files)
- Steps marked `[PI]` run via SSH on the RPi5
- Steps marked `[PI - container]` run after `docker exec -it snoopi-ros2 bash`
- After each `[WINDOWS]` file creation block: commit, push, then pull on the Pi

---

## Task 1: Launch and Test rosbridge

Validates that the WebSocket bridge between ROS2 and the outside world works
inside the container. This is the communication backbone for the entire UI layer.

**Step 1: Open a shell in the container**

```bash
[PI] docker exec -it snoopi-ros2 bash
```

**Step 2: Launch rosbridge**

```bash
[PI - container] ros2 launch rosbridge_server rosbridge_websocket_launch.xml
```

Expected output ends with:
```
[rosbridge_websocket-1] Rosbridge WebSocket server started on port 9090
```

Leave this running. Open a second SSH terminal for the next step.

**Step 3: Verify port 9090 is open (second terminal)**

```bash
[PI] ss -tlnp | grep 9090
```

Expected: a line showing something listening on `*:9090` or `0.0.0.0:9090`.
Because the container uses `network_mode: host`, port 9090 is directly on
the Pi's network stack — no port mapping needed.

**Step 4: Stop rosbridge**

Go back to the first terminal and press `Ctrl+C`.

**Step 5: Exit the container**

```bash
[PI - container] exit
```

**Checkpoint:** rosbridge starts cleanly and listens on port 9090.

---

## Task 2: Mock Robot Publisher

A ROS2 node that publishes fake Go2 Air telemetry on the same topics the real
SDK uses. This lets the full UI ↔ rosbridge ↔ ROS2 pipeline run without the
physical robot. When the real robot is connected, you simply stop the mock
publisher and start the real SDK — the rest of the system sees no difference.

**Files to create:**
- `src/snoopi_mock/package.xml`
- `src/snoopi_mock/setup.py`
- `src/snoopi_mock/setup.cfg`
- `src/snoopi_mock/snoopi_mock/__init__.py`
- `src/snoopi_mock/snoopi_mock/mock_robot_publisher.py`

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

**Step 4: Create `src/snoopi_mock/snoopi_mock/__init__.py`** (empty file)

**Step 5: Create `src/snoopi_mock/snoopi_mock/mock_robot_publisher.py`**

```python
"""
Mock robot publisher.
Publishes fake Go2 Air telemetry on the same topics the real SDK uses.
Lets the full UI - rosbridge - ROS2 pipeline run without the physical robot.
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

        # Joint states: 12 joints (FL/FR/RL/RR x hip/thigh/calf), all at rest
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

**Step 8: Verify the node runs**

```bash
[PI - container] ros2 run snoopi_mock mock_robot_publisher
```

Expected: `Mock robot publisher started — publishing fake telemetry`

Press `Ctrl+C` to stop, then `exit`.

**Checkpoint:** Mock publisher builds, runs, and publishes to `/utlidar/battery`, `/imu/data`, `/joint_states`.

---

## Task 3: FastAPI Backend

The backend runs natively on the RPi5 host (not inside Docker). It provides
REST endpoints for task dispatch and e-stop, forwarding commands to ROS2
via rosbridge WebSocket.

**Files to create:**
- `backend/requirements.txt`
- `backend/main.py`
- `backend/tests/__init__.py`
- `backend/tests/test_main.py`

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

**Step 2: Create `backend/main.py`**

```python
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

**Step 3: Create `backend/tests/__init__.py`** (empty file)

**Step 4: Create `backend/tests/test_main.py`**

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

**Step 5: Commit and sync**

```bash
[WINDOWS] git add backend/
[WINDOWS] git commit -m "feat: add FastAPI backend with task dispatch, estop, and tests"
[WINDOWS] git push
[PI]      git pull
```

**Step 6: Set up Python venv on the Pi and run tests**

```bash
[PI] cd ~/snoopi/backend
[PI] python3 -m venv venv
[PI] source venv/bin/activate
[PI] pip install -r requirements.txt
```

Create the backend `.env` (gitignored, create manually):

```bash
[PI] echo "ROSBRIDGE_URL=ws://localhost:9090" > ~/snoopi/backend/.env
```

Run the tests:

```bash
[PI] cd ~/snoopi/backend
[PI] source venv/bin/activate
[PI] python -m pytest tests/ -v
```

Expected: all 7 tests pass. `/health` and `/estop` tests will show
`rosbridge: unreachable` — correct since rosbridge isn't running. The
important thing is the status codes and response shapes are correct.

**Checkpoint:** All 7 FastAPI tests pass on the RPi5.

---

## Task 4: React Frontend

The frontend runs natively on the RPi5 host. It connects directly to
rosbridge via WebSocket for real-time telemetry and to FastAPI for commands.

**Step 1: Install Node.js 20 LTS on the Pi**

```bash
[PI] curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
[PI] sudo apt-get install -y nodejs
[PI] node --version
```

Expected: `v20.x.x`

**Step 2: Scaffold the Vite + React + TypeScript project**

```bash
[PI] cd ~/snoopi
[PI] npm create vite@latest ui -- --template react-ts
```

**Step 3: Install dependencies**

```bash
[PI] cd ~/snoopi/ui
[PI] npm install
[PI] npm install roslib
[PI] npm install --save-dev @types/roslib
```

**Step 4: Commit the scaffold from the Pi** (one-time reverse sync)

```bash
[PI] cd ~/snoopi
[PI] git add ui/
[PI] git commit -m "feat: scaffold Vite + React + TypeScript frontend"
[PI] git push
[WINDOWS] git pull
```

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
      <p>Temperature: {temp !== null ? `${temp} C` : 'Waiting...'}</p>
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

Note: E-STOP is always enabled — it goes through FastAPI, not rosbridge directly.

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
[WINDOWS] git commit -m "feat: add React frontend with health dashboard and command panel"
[WINDOWS] git push
[PI]      git pull
```

**Checkpoint:** `npm run dev -- --host` starts without errors on the Pi.

---

## Task 5: Full Integration Test

All three services run together. Mock data flows from ROS2 through rosbridge
to the browser. This is the milestone checkpoint.

**Step 1: Start the ROS2 container (if not already running)**

```bash
[PI] cd ~/snoopi
[PI] docker compose up -d
```

**Step 2: Start rosbridge (Terminal 1)**

```bash
[PI] docker exec -it snoopi-ros2 bash
[PI - container] ros2 launch rosbridge_server rosbridge_websocket_launch.xml
```

Leave running.

**Step 3: Start the mock publisher (Terminal 2)**

```bash
[PI] docker exec -it snoopi-ros2 bash
[PI - container] ros2 run snoopi_mock mock_robot_publisher
```

Expected: `Mock robot publisher started — publishing fake telemetry`

**Step 4: Verify topics are publishing (Terminal 3)**

```bash
[PI] docker exec -it snoopi-ros2 bash
[PI - container] ros2 topic list
```

Expected: `/utlidar/battery`, `/imu/data`, `/joint_states` in the list.

```bash
[PI - container] ros2 topic echo /utlidar/battery --once
```

Expected: battery message with `percentage`, `voltage`, `temperature` fields.

```bash
[PI - container] exit
```

**Step 5: Start FastAPI backend (Terminal 3)**

```bash
[PI] cd ~/snoopi/backend
[PI] source venv/bin/activate
[PI] uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Step 6: Verify backend health**

```bash
[PI] curl http://localhost:8000/health
```

Expected: `{"status":"ok","rosbridge":"reachable"}`

**Step 7: Start React dev server (Terminal 4)**

```bash
[PI] cd ~/snoopi/ui
[PI] npm run dev -- --host
```

**Step 8: Open the dashboard in your browser**

```
[BROWSER] http://<pi-ip>:5173
```

Replace `<pi-ip>` with the RPi5's IP (find with `hostname -I` on the Pi).

**Checkpoint — what you should see:**
- Green dot: "ROS2 Connected"
- Battery percentage updating every ~1 second (starting near 100%)
- Temperature value oscillating slightly
- IMU z-acceleration showing ~9.81
- Sit / Stand buttons enabled
- E-STOP button always enabled

**Step 9: Test E-STOP manually**

```bash
[PI] curl -X POST http://localhost:8000/estop
```

Expected: `{"status":"sent","rosbridge_reachable":true}`

---

## Task 6: Update CLAUDE.md

After all integration tests pass, update CLAUDE.md:
- Note that the full mock pipeline is validated
- Update active tasks to reflect what's left (robot-dependent work only)

---

## What's Left After This Plan (Robot Required)

These items require the physical Go2 Air:

| Milestone | Work |
|-----------|------|
| **M2: Hardware Connection** | Connect Pi to Go2, launch real SDK, verify live topics |
| **M3: Basic Motion** | Send cmd_vel commands, test sit/stand/walk over Ethernet and WiFi |
| **M4: SLAM Mapping** | Teleoperate robot through environment, save occupancy grid map |
| **M5: Nav2 Navigation** | Load map, send nav goals, tune obstacle avoidance parameters |
| **M7: Task Manager** | Wire task dispatch to Nav2 goals, implement distance tracking |
| **M8: Safe-Stop** | WiFi loss detection, navigate to safe-stop location |
| **M9: Integration** | End-to-end testing, demo prep |

The mock publisher + UI + backend pipeline we built today means Milestone 6
(UI Foundation) is effectively complete. When the robot arrives, you swap
the mock publisher for the real SDK and everything else works.
