# Snoopi — Testing Log

> **Purpose:** Record of all testing performed across milestones for traceability and team reference.
> Updated each session when tests are run. Includes automated tests, manual verification, and integration tests.

---

## Test Summary

| Category | Tests | Status | Date Last Run |
|----------|-------|--------|---------------|
| Backend unit tests (pytest) | 13 | All passing | Mar 3, 2026 |
| Docker container verification | 6 checks | All passing | Feb 25, 2026 |
| Frontend manual smoke tests | 8 checks | All passing | Mar 3, 2026 |
| Rosbridge + mock publisher integration | 4 checks | **In progress** | Mar 5, 2026 |

---

## 1. Docker Container Verification (Milestone 1)

**Date:** Feb 25, 2026
**Environment:** RPi5, Ubuntu Server 24.04, Docker 28.x
**Branch:** `feature/docker-environment-setup`

| # | Test | Command | Expected | Result |
|---|------|---------|----------|--------|
| 1 | Image builds successfully | `docker compose build` | Exit 0, image `snoopi-ros2` created | PASS |
| 2 | Container starts | `docker compose up -d` | Container running, `docker ps` shows `snoopi-ros2` | PASS |
| 3 | ROS2 Humble available | `docker exec snoopi-ros2 ros2 topic list` | Returns `/rosout`, `/parameter_events` | PASS |
| 4 | Nav2 packages installed | `docker exec snoopi-ros2 ros2 pkg list \| grep nav2 \| wc -l` | 30 packages | PASS |
| 5 | go2_ros2_sdk built | `docker exec snoopi-ros2 ros2 pkg list \| grep go2` | Shows `go2_interfaces`, `go2_robot_sdk` | PASS |
| 6 | CycloneDDS configured | `docker exec snoopi-ros2 echo $RMW_IMPLEMENTATION` | `rmw_cyclonedds_cpp` | PASS |

**Notes:**
- Skipped `lidar_processor_cpp` (needs `pcl_ros`, not MVP) and `coco_detector` (needs PyTorch, not MVP)
- Image uses `ros:humble-ros-base-jammy` base with ARM64-compatible pip deps
- Host networking (`network_mode: host`) confirmed working for DDS multicast

---

## 2. Backend Automated Tests (pytest)

**Date:** Mar 3, 2026
**Environment:** RPi5, Python 3.12, venv at `~/snoopi/backend/venv`
**Command:** `cd ~/snoopi/backend && source venv/bin/activate && pytest tests/ -v`
**Framework:** pytest + httpx AsyncClient with ASGITransport

### 2a. Authentication Tests (`tests/test_auth.py` — 6 tests)

| # | Test | Description | Result |
|---|------|-------------|--------|
| 1 | `test_login_success` | POST `/auth/login` with valid creds (john) → 200 + token + user obj | PASS |
| 2 | `test_login_wrong_password` | POST `/auth/login` with wrong password → 401 | PASS |
| 3 | `test_login_unknown_user` | POST `/auth/login` with nonexistent user → 401 | PASS |
| 4 | `test_me_with_valid_token` | GET `/auth/me` with valid Bearer token → 200 + user obj | PASS |
| 5 | `test_me_without_token` | GET `/auth/me` with no Authorization header → 401 | PASS |
| 6 | `test_me_with_bad_token` | GET `/auth/me` with forged token → 401 | PASS |

### 2b. API Endpoint Tests (`tests/test_main.py` — 7 tests)

| # | Test | Description | Result |
|---|------|-------------|--------|
| 7 | `test_health_returns_ok` | GET `/health` → 200 + `{"status": "ok", "rosbridge": "..."}` | PASS |
| 8 | `test_create_walk_task` | POST `/tasks` with `{type: "walk", distance_m: 100}` → 200 + task obj | PASS |
| 9 | `test_invalid_task_type` | POST `/tasks` with `{type: "fly"}` → 400 | PASS |
| 10 | `test_negative_distance_rejected` | POST `/tasks` with `distance_m: -5` → 400 | PASS |
| 11 | `test_get_task_not_found` | GET `/tasks/9999` → 404 | PASS |
| 12 | `test_get_task_after_create` | Create task, then GET by ID → 200 + same task | PASS |
| 13 | `test_estop_returns_status` | POST `/estop` → 200 + `{"status": "..."}` | PASS |

**Notes:**
- Tests run against in-process ASGI app (no network, no rosbridge needed)
- Health endpoint reports rosbridge as "unreachable" in test (expected — no rosbridge running)
- Estop test returns `status: "failed"` (expected — no rosbridge to publish to)
- Originally used `anyio` markers — switched to `pytest.mark.asyncio` (fix: commit `beee5b8`)

---

## 3. Frontend Manual Smoke Tests

**Date:** Mar 3, 2026
**Environment:** Windows 11 browser (Chrome), accessing `http://192.168.0.41:5173`
**Backend:** uvicorn on Pi (:8000), Frontend: Vite dev server on Pi (:5173)

| # | Test | Steps | Expected | Result |
|---|------|-------|----------|--------|
| 1 | Login page renders | Navigate to `http://192.168.0.41:5173` | Login form with Snoopi branding | PASS |
| 2 | Valid login | Enter john/snoopi-john-2026, click Sign In | Redirect to dashboard | PASS |
| 3 | Invalid login | Enter wrong password, click Sign In | "Invalid username or password" error | PASS |
| 4 | Dashboard layout | After login | Header, robot selector, health cards, telemetry, controls, alerts, task history all render | PASS |
| 5 | Token persistence | Refresh page after login | Stays logged in (JWT in localStorage) | PASS |
| 6 | Logout | Click logout in header | Returns to login page | PASS |
| 7 | Health cards show dashes | Without rosbridge running | Battery: —, Temp: —, IMU: —, CPU: — | PASS |
| 8 | Connection indicators | Without rosbridge | Pi Connection: Connected (green), rosbridge: Offline (red) | PASS |

**Issues Found & Fixed During Testing:**
- `ERR_CONNECTION_REFUSED` on login — frontend was hitting `localhost:8000` instead of Pi IP → fixed with `ui/.env` (`VITE_API_URL=http://192.168.0.41:8000`)
- Blank page on load — `verbatimModuleSyntax` required `import type` for all type-only imports → fixed in commits `79da48b`, `353685e`
- `roslib` import error — no default export → fixed with `import * as ROSLIB from 'roslib'` (commit `96b4f37`)

---

## 4. Rosbridge + Mock Publisher Integration Test

**Date:** Mar 5, 2026 (in progress)
**Environment:** RPi5, Docker container (`snoopi-ros2`), Windows browser
**Branch:** `feature/docker-environment-setup` (commit `9d3d2b6`)

### Purpose
Verify the full data pipeline: Mock Publisher → ROS2 topics → rosbridge WebSocket → React dashboard

### Prerequisites
- Docker container running with rosbridge + mock publisher
- Frontend `.env` has `VITE_ROSBRIDGE_URL=ws://192.168.0.41:9090`
- Backend running (for health check + task dispatch)

### Fixes Applied Before Test
- Rosbridge message types corrected: `sensor_msgs/BatteryState` → `sensor_msgs/msg/BatteryState` (rosbridge requires the full `/msg/` path)
- Rosbridge URL made configurable via `VITE_ROSBRIDGE_URL` env var (was hardcoded to `ws://localhost:9090`)
- `ui/.env` created on Pi with `VITE_ROSBRIDGE_URL=ws://192.168.0.41:9090`

### Test Plan

| # | Test | Steps | Expected | Status |
|---|------|-------|----------|--------|
| 1 | Mock publisher runs | `[PI - container]` `colcon build --packages-select snoopi_mock && source install/setup.bash && ros2 run snoopi_mock mock_robot_publisher` | "Mock robot publisher started" message, no errors | PENDING |
| 2 | Rosbridge runs | `[PI - container]` `ros2 launch rosbridge_server rosbridge_websocket_launch.xml` | "Rosbridge WebSocket server started on port 9090" | PENDING |
| 3 | Topics visible | `[PI - container]` `ros2 topic list` | `/utlidar/battery`, `/imu/data`, `/joint_states`, `/rosout` | PENDING |
| 4 | Topic data flowing | `[PI - container]` `ros2 topic echo /utlidar/battery --once` | BatteryState msg with percentage ~1.0, temp ~35°C | PENDING |
| 5 | Dashboard rosbridge connects | `[BROWSER]` Check header status indicator | Rosbridge: Connected (green dot) | PENDING |
| 6 | Battery card populates | `[BROWSER]` Check Robot Health card | Battery: ~100%, Temperature: ~35°C | PENDING |
| 7 | IMU card populates | `[BROWSER]` Check Robot Health card | IMU z-accel: ~9.81 m/s² | PENDING |
| 8 | Telemetry graphs populate | `[BROWSER]` Check Telemetry section | Battery + Temp + IMU graphs show data points accumulating over time | PENDING |
| 9 | System Health (no data expected) | `[BROWSER]` Check System Health card | CPU: —, RPi Temp: — (system_monitor not running) | PENDING |
| 10 | Task dispatch | `[BROWSER]` Enter 50m, click Send Task | Task appears in Task History table | PENDING |
| 11 | E-stop button | `[BROWSER]` Click E-STOP | No crash, request sent (may show "failed" if rosbridge publish path differs) | PENDING |

### Known Limitations for This Test
- **System stats** (`/snoopi/system_stats`) will be empty — the `system_monitor` node needs to be built and run separately from the mock publisher
- **UWB indicators** will show "Offline" — UWB is post-MVP, no mock data published
- **Joint Status** is hardcoded to "Normal" — `RobotHealthCard` does not subscribe to `/joint_states`
- **CPU Load graph** will be empty unless `system_monitor` is also running

---

## 5. Bugs & Issues Log

| # | Date | Severity | Description | Status | Fix |
|---|------|----------|-------------|--------|-----|
| 1 | Mar 3 | High | `ERR_CONNECTION_REFUSED` — frontend calls `localhost:8000` from Windows browser | Fixed | Created `ui/.env` with `VITE_API_URL=http://192.168.0.41:8000` |
| 2 | Mar 3 | High | Blank page — `verbatimModuleSyntax` rejects non-type imports for interfaces | Fixed | Changed all type-only imports to `import type` syntax |
| 3 | Mar 3 | Medium | `roslib` import error — `import ROSLIB from 'roslib'` fails (no default export) | Fixed | Changed to `import * as ROSLIB from 'roslib'` |
| 4 | Mar 3 | Medium | pytest `anyio` marker not found | Fixed | Changed to `@pytest.mark.asyncio` |
| 5 | Mar 5 | High | Rosbridge message types wrong — `sensor_msgs/BatteryState` should be `sensor_msgs/msg/BatteryState` | Fixed | Updated `RobotHealthCard.tsx`, `SystemHealthCard.tsx` (commit `9d3d2b6`) |
| 6 | Mar 5 | High | Rosbridge URL hardcoded to `ws://localhost:9090` — unreachable from Windows browser | Fixed | Made configurable via `VITE_ROSBRIDGE_URL` env var (commit `9d3d2b6`) |
| 7 | Mar 5 | Medium | `ControlsCard.tsx` still uses short message type format (`std_msgs/String`) for publish | Open | Should be `std_msgs/msg/String` for consistency |
| 8 | Mar 5 | Medium | `backend/main.py` uses `std_msgs/String` and `std_msgs/Bool` in publish calls | Open | Should use `/msg/` form |
| 9 | Mar 5 | Medium | `piConnected` stale closure — "Pi connection lost" alert never fires | Open | `useEffect` captures initial `piConnected` value, needs ref |
| 10 | Mar 5 | Low | `LoginPage.tsx` duplicates `API` URL logic instead of importing from `config.ts` | Open | Minor DRY violation |
| 11 | Mar 5 | Low | `/tasks` and `/estop` endpoints have no auth verification on backend | Open | Frontend sends token but backend ignores it |

---

## Appendix: How to Run Tests

### Backend Tests (automated)
```bash
[PI] cd ~/snoopi/backend && source venv/bin/activate && pytest tests/ -v
```

### Full Stack Integration Test (manual)
Requires 3 SSH terminals to Pi + Windows browser:

**Terminal 1 — Docker + ROS2:**
```bash
[PI] cd ~/snoopi && docker compose up -d
[PI] docker exec -it snoopi-ros2 bash
[PI - container] cd /ros2_ws && colcon build --packages-select snoopi_mock && source install/setup.bash
[PI - container] ros2 launch rosbridge_server rosbridge_websocket_launch.xml &
[PI - container] ros2 run snoopi_mock mock_robot_publisher
```

**Terminal 2 — Backend:**
```bash
[PI] cd ~/snoopi/backend && source venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000
```

**Terminal 3 — Frontend:**
```bash
[PI] cd ~/snoopi/ui && npm run dev -- --host 0.0.0.0
```

**Browser (Windows):**
```
http://192.168.0.41:5173
Login: john / snoopi-john-2026
```

### Verify ROS2 Topics (inside container)
```bash
[PI - container] ros2 topic list
[PI - container] ros2 topic echo /utlidar/battery --once
[PI - container] ros2 topic echo /imu/data --once
```
