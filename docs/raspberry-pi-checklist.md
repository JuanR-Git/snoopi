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

## 3. FastAPI Backend

| Step | Status | Date | Notes |
|------|--------|------|-------|
| Python venv created at `~/snoopi/backend/venv` | DONE | Feb 25 | Ubuntu 24.04 requires venv (PEP 668) |
| `pip install -r requirements.txt` | DONE | Mar 3 | Includes bcrypt, python-jose for auth |
| `pytest tests/ -v` — all 13 tests pass | DONE | Mar 3 | 7 original + 6 auth (login, me, token) |
| JWT authentication endpoints working | DONE | Mar 3 | `/auth/login`, `/auth/me` |
| 3 users configured (john, juan, mihir) | DONE | Mar 3 | bcrypt-hashed passwords in users.json |

---

## 4. Node.js & React Frontend

| Step | Status | Date | Notes |
|------|--------|------|-------|
| Node.js installed (v24.14.0) | DONE | Mar 1 | Official nodejs.org install (not NodeSource) |
| npm installed (v11.9.0) | DONE | Mar 1 | Came with Node.js |
| Vite 7.3 + React 19 + TypeScript scaffolded | DONE | Mar 1 | `npm create vite@latest` on Pi |
| Tailwind CSS v4 configured | DONE | Mar 1 | `@tailwindcss/vite` plugin |
| Recharts installed | DONE | Mar 3 | For time-series telemetry graphs |
| roslib installed | DONE | Mar 3 | `roslib` + `@types/roslib` |
| `.env` configured with `VITE_API_URL` | DONE | Mar 3 | Points to `http://192.168.0.41:8000` |
| Login page working | DONE | Mar 3 | JWT auth, 3 users |
| Dashboard page loading | DONE | Mar 3 | All components render |
| `npm run dev -- --host 0.0.0.0` serves app | DONE | Mar 3 | Accessible from Windows browser |
| Frontend connects to rosbridge | NOT DONE | | Next step — needs rosbridge running |

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
| Mar 1 | Node.js v24.14.0 from nodejs.org (not apt/NodeSource) | Vite 7.x requires Node 20.19+ or 22.12+; apt only has v18 |
| Mar 3 | `.env` file for Vite API URL | Browser runs on Windows, so `localhost:8000` doesn't work — must use Pi's LAN IP |
| Mar 3 | `verbatimModuleSyntax: true` requires `import type` | Vite 7 / TS 5.8 default; all type-only imports must use `import type { X }` syntax |

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
