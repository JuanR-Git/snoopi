# CLAUDE.md

## Project
Hospital robot application on Unitree Go2 Air. See `docs/project.md` for full project plan.

## Current Milestone
Milestone 2 — Hardware Connection & Telemetry
See `docs/project.md` → Section 8, Milestone 2 for full task list.

## Active Tasks
- [ ] Connect dev laptop / RPi5 to Go2 Air over Ethernet
- [ ] Configure network interface (static IP on the robot's subnet)
- [ ] Launch go2_ros2_sdk bridge nodes
- [ ] Run `ros2 topic list` — document all available topics from the robot
- [ ] Subscribe to and verify each relevant topic (battery, temp, joints, IMU, LiDAR)
- [ ] Write a simple Python ROS2 node (health_printer.py) that prints health data
- [ ] Document which topics are available vs. expected but missing

## Completed Milestones
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
- FastAPI + React (UI)
- rosbridge_suite (ROS2 ↔ Web)
- CycloneDDS middleware

## Key Rules
- Always read `docs/project.md` before making architectural decisions
- MVP deadline: March 5, 2026
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
