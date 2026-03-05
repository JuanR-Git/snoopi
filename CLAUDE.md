# CLAUDE.md

## Project
Hospital robot application on Unitree Go2 Air. See `docs/project.md` for full project plan.

## Current Milestone
Milestone 2 — Hardware Connection & Telemetry
See `docs/project.md` → Section 8, Milestone 2 for full task list.

## Active Tasks
- [ ] Test dashboard with rosbridge + mock publisher (verify graphs populate)
- [ ] Connect RPi5 to Go2 Air over Ethernet in the lab
- [ ] Configure network interface (static IP on the robot's subnet)
- [ ] Launch go2_ros2_sdk bridge nodes
- [ ] Run `ros2 topic list` — document all available topics from the robot
- [ ] Subscribe to and verify each relevant topic (battery, temp, joints, IMU, LiDAR)
- [ ] Wire real robot topics into the dashboard (replace mock data)

## Session Handoff (2026-03-05)
Active branch: `feature/docker-environment-setup`

**What's working:**
- Docker container with ROS2 Humble, Nav2, rosbridge, go2_ros2_sdk — all verified on Pi
- FastAPI backend with JWT auth (3 users), health/tasks/estop endpoints — 13 tests passing
- React dashboard with login page, health cards, Grafana-style telemetry graphs, controls, alerts, task history
- Telemetry graphs: nice-number Y-axis, sliding clock-aligned X-axis, range-aware time format, no animation jank
- Full stack runs: backend (uvicorn:8000) + frontend (vite:5173), accessible from Windows browser

**How to start the stack on Pi (3 terminals):**
1. Backend: `cd ~/snoopi/backend && source venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000`
2. Frontend: `cd ~/snoopi/ui && npm install && npm run dev -- --host 0.0.0.0`
3. Docker (optional): `cd ~/snoopi && docker compose up -d && docker exec -it snoopi-ros2 bash`

**Errors encountered & fixed (Mar 5):**
- `recharts` imported but missing from `package.json` → added to dependencies
- `@tailwindcss/vite` and `tailwindcss` imported but missing from `package.json` → surfaced when npm reshuffled `node_modules` after adding recharts. **Lesson:** always verify every import has a `package.json` entry — transitive deps can silently disappear.

**Next steps:**
1. Test with rosbridge running (start Docker container + rosbridge + mock publisher, verify graphs populate)
2. Take Pi to lab, connect to Go2 Air via Ethernet, discover real robot topics
3. Wire real topics into the dashboard

**Pi IP:** 192.168.0.41
**Login creds:** john/snoopi-john-2026, juan/snoopi-juan-2026, mihir/snoopi-mihir-2026

Delete this section once picked up.

## Completed Milestones
- **Milestone 6 — UI Foundation** (Mar 5, 2026)
  - FastAPI backend with JWT auth (3 users), 13 tests passing
  - React 19 + TypeScript + Tailwind CSS v4 + Recharts frontend
  - Login page, dashboard: health cards, Grafana-style telemetry graphs, controls, alerts, task history
  - rosbridge hook for real-time ROS2 data, system monitor node for Pi metrics
  - Accessible from Windows browser at `http://192.168.0.41:5173`
- **Milestone 1 — Environment Setup** (Feb 25, 2026)
  - ROS2 Humble running in Docker on RPi5 (ros:humble-ros-base-jammy)
  - RPi5 host OS: Ubuntu Server 24.04, Docker containers run Ubuntu 22.04
  - Nav2 (30 packages), SLAM Toolbox, rosbridge suite all installed and verified
  - go2_ros2_sdk built (go2_interfaces + go2_robot_sdk); skipped lidar_processor_cpp (needs pcl_ros) and coco_detector (needs torch)
  - CycloneDDS configured as ROS middleware
  - Curated ARM64 pip deps: excluded open3d (no aarch64 wheel), torch/torchvision (not MVP)
  - Docker image uses host networking for DDS multicast discovery
  - Verification: `ros2 topic list`, all package checks passed
- **Milestone 0 — Validation & Discovery** (Feb 20, 2026)
  - Go2 Air firmware V1.1.7 — exact match for go2_ros2_sdk
  - Hardware version V2.0 — no compatibility concerns
  - Super-wide-angle 3D LiDAR confirmed present
  - go2_ros2_sdk supports Air/Pro/Edu on ROS2 Humble
  - RPi4 2GB RAM insufficient → RPi5 16GB Kit ordered
  - SSH disabled on Air — not a blocker (SDK connects externally)
  - DO NOT update robot firmware — V1.1.7 is the confirmed compatible version
  - Full findings: `docs/hardware-validation.md`

## Tech Stack
- ROS2 Humble on Ubuntu 22.04 (via Docker on RPi5)
- Docker (ros:humble-ros-base-jammy) — containerized ROS2 environment
- go2_ros2_sdk (hardware bridge)
- Nav2 (navigation) + SLAM Toolbox (mapping)
- FastAPI + React 19 + TypeScript + Tailwind CSS v4 + Recharts (UI)
- rosbridge_suite (ROS2 ↔ Web)
- CycloneDDS middleware

## Key Rules
- Always read `docs/project.md` before making architectural decisions
- MVP deadline: March 12, 2026
- MVP scope: health dashboard, task dispatch UI, Nav2 navigation, obstacle avoidance, e-stop
- Robot-leads-patient model for MVP (walk-beside is post-MVP)
- Teleoperation mapping for MVP (autonomous exploration is post-MVP)
- Manual safe-stop marking for MVP (auto-detection is post-MVP)
- Max robot speed: 0.5 m/s
- All safety-critical nodes must run on companion computer (RPi5), not over WiFi
- DO NOT update Go2 Air firmware — V1.1.7 is confirmed compatible
- Do NOT add Co-Authored-By lines to git commits

## Hardware
- **Robot:** Unitree Go2 Air (HW V2.0, FW V1.1.7)
- **Sensors:** Super-wide-angle 3D LiDAR, front camera, ultrasonic, IMU, foot force sensors
- **Companion computer:** Raspberry Pi 5 16GB — running Ubuntu Server 24.04, ROS2 via Docker
- **Dev machine:** Linux (Ubuntu 22.04)

## Project Structure
```
├── CLAUDE.md              # This file — active instructions
├── Dockerfile             # ROS2 Humble environment (ARM64-compatible)
├── docker-compose.yml     # Container orchestration (host networking for DDS)
├── .env.example           # Environment template (ROS_DOMAIN_ID)
├── docker/
│   ├── entrypoint.sh      # Sources ROS2 base, SDK, and user workspaces
│   ├── cyclonedds.xml     # DDS middleware config (interface, discovery)
│   └── requirements-arm64.txt  # Curated pip deps (excludes open3d, torch)
├── docs/
│   ├── project.md         # Full project plan (v2)
│   ├── hardware-validation.md  # Milestone 0 findings
│   └── raspberry-pi-checklist.md  # Pi setup progress (update every session)
├── src/                   # ROS2 packages (to be created)
├── ui/                    # React frontend (to be created)
└── backend/               # FastAPI backend (to be created)
```

## Raspberry Pi Checklist (MANDATORY)
- **File:** `docs/raspberry-pi-checklist.md` — living document tracking all Pi setup progress
- **Rule:** Every session that involves Pi-related work MUST update this checklist before ending
- When a task is performed on the Pi and the user provides output, update the checklist status, date, and notes
- When a design decision is made, add it to the Design Decisions Log table
- Remind the user to commit and push the updated checklist at the end of each session
- On session start, read this file to understand current Pi setup state

## Update Protocol
When a milestone is completed:
1. Move it to "Completed Milestones" with the date
2. Update "Current Milestone" to the next one
3. Update "Active Tasks" with the new milestone's tasks
4. If any scope changes or new learnings occurred, update `docs/project.md` accordingly
