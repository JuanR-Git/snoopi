# Raspberry Pi 5 Setup Checklist

> **Purpose:** Living document tracking all setup steps performed on the RPi5.
> Updated every session when Pi-related work is done. Push to GitHub after every update.
>
> **Pi Details:** RPi5 16GB, Ubuntu Server 24.04, hostname: `snoopi-pi` (or TBD)
> **Connection:** SSH from dev machine (Windows 11)

---

## 1. Base OS & System

| Step | Status | Date | Notes |
|------|--------|------|-------|
| Flash Ubuntu Server 24.04 to SD card | DONE | ~Feb 2026 | 64-bit ARM image |
| First boot & SSH access configured | DONE | ~Feb 2026 | |
| System updated (`apt update && apt upgrade`) | UNKNOWN | | Verify next session |
| Git installed | DONE | | Repo cloned to `~/snoopi` |
| User account configured | UNKNOWN | | Document username next session |

---

## 2. Docker Environment (Milestone 1 — Completed Feb 25)

| Step | Status | Date | Notes |
|------|--------|------|-------|
| Docker installed | DONE | Feb 25 | |
| Docker Compose installed | DONE | Feb 25 | |
| `docker compose build` successful | DONE | Feb 25 | Image: `snoopi-ros2` |
| `docker compose up -d` runs | DONE | Feb 25 | Host networking for DDS |
| ROS2 Humble verified inside container | DONE | Feb 25 | `ros2 topic list` works |
| Nav2 (30 packages) installed | DONE | Feb 25 | |
| SLAM Toolbox installed | DONE | Feb 25 | |
| rosbridge_suite installed | DONE | Feb 25 | |
| go2_ros2_sdk built | DONE | Feb 25 | go2_interfaces + go2_robot_sdk |
| CycloneDDS configured | DONE | Feb 25 | `docker/cyclonedds.xml` |
| Mock robot publisher built & verified | DONE | Feb 25 | `snoopi_mock` package |

---

## 3. FastAPI Backend (Milestone 1 — Completed Feb 25)

| Step | Status | Date | Notes |
|------|--------|------|-------|
| Python venv created at `~/snoopi/backend/` | DONE | Feb 25 | |
| `pip install -r requirements.txt` | DONE | Feb 25 | |
| `pytest tests/ -v` — all 7 tests pass | DONE | Feb 25 | health, tasks, estop endpoints |

---

## 4. Node.js & React Frontend (Task 6 — In Progress)

| Step | Status | Date | Notes |
|------|--------|------|-------|
| Node.js 20 LTS installed via NodeSource | UNKNOWN | | Was in progress when session crashed |
| `node --version` shows v20.x | UNKNOWN | | **Verify next session** |
| `npm --version` shows 10.x | UNKNOWN | | **Verify next session** |
| `npm create vite@latest ui -- --template react-ts` | NOT DONE | | |
| `npm install` in `ui/` | NOT DONE | | |
| `npm install roslib` | NOT DONE | | |
| `npm install --save-dev @types/roslib` | NOT DONE | | |
| `npm run dev -- --host` starts dev server | NOT DONE | | |
| React components created | NOT DONE | | Files to be written on Windows, pulled on Pi |
| Frontend connects to rosbridge | NOT DONE | | |

---

## 5. Network & Robot Connection (Milestone 2 — Not Started)

| Step | Status | Date | Notes |
|------|--------|------|-------|
| Ethernet cable connected Pi ↔ Go2 Air | NOT DONE | | |
| Static IP configured on Pi (192.168.123.x) | NOT DONE | | Robot subnet |
| `ping 192.168.123.161` (robot) | NOT DONE | | |
| go2_ros2_sdk bridge nodes launched | NOT DONE | | |
| `ros2 topic list` shows robot topics | NOT DONE | | |
| Topic inventory documented | NOT DONE | | |

---

## Design Decisions Log

> Record key decisions made during setup sessions so they aren't lost.

| Date | Decision | Rationale |
|------|----------|-----------|
| Feb 25 | Docker runs ROS2; FastAPI + React run on host | Keeps ROS2 isolated, host apps don't need container overhead |
| Feb 25 | Host networking (`--network=host`) for Docker | Required for DDS multicast discovery |
| Feb 25 | Skipped `lidar_processor_cpp` and `coco_detector` | Missing `pcl_ros` and `torch` on ARM64 — not MVP |
| Feb 25 | Excluded `open3d`, `torch`, `torchvision` from pip | No aarch64 wheels available |
| Feb 25 | Node.js installed on Pi host, not in Docker | Frontend is a host-native app, no need for container |
| Feb 25 | Pi commits `ui/` scaffold (exception to Windows-commits rule) | Vite CLI must run on Pi (ARM64), can't scaffold on Windows |

---

## How To Use This Document

1. **Start of session:** Read this checklist to see current state
2. **During session:** When a Pi task is completed, update the status and date
3. **End of session:** Commit and push changes to this file
4. **Crash recovery:** This file + git history tells you exactly where you left off

### Verification Commands

Quick commands to check what's installed on the Pi:

```bash
# Docker
docker --version
docker compose version
docker ps  # should show snoopi-ros2 if running

# ROS2 (inside container)
docker exec snoopi-ros2 bash -c "source /opt/ros/humble/setup.bash && ros2 topic list"

# FastAPI backend
cd ~/snoopi/backend && source venv/bin/activate && python -m pytest tests/ -v

# Node.js
node --version
npm --version

# Vite dev server (if ui/ exists)
cd ~/snoopi/ui && npm run dev -- --host
```
