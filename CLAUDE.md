# CLAUDE.md

## Project
Hospital robot application on Unitree Go2 Air. See `docs/project.md` for full project plan.

## Current Milestone
Milestone 1 — Environment Setup
See `docs/project.md` → Section 8, Milestone 1 for full task list.

## Active Tasks
- [ ] Install Ubuntu 22.04 on development machine (if not already installed)
- [ ] Install ROS2 Humble (full desktop install)
- [ ] Install Nav2, SLAM Toolbox, rosbridge_suite
- [ ] Clone and build go2_ros2_sdk
- [ ] Install and configure CycloneDDS
- [ ] Verify installation (ros2 topic list works)

## Completed Milestones
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
- ROS2 Humble on Ubuntu 22.04
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

## Hardware
- **Robot:** Unitree Go2 Air (HW V2.0, FW V1.1.7)
- **Sensors:** Super-wide-angle 3D LiDAR, front camera, ultrasonic, IMU, foot force sensors
- **Companion computer:** Raspberry Pi 5 16GB (ordered) — RPi4 2GB as backup
- **Dev machine:** Linux (Ubuntu 22.04)

## Project Structure
```
├── CLAUDE.md              # This file — active instructions
├── docs/
│   ├── project.md         # Full project plan (v2)
│   └── hardware-validation.md  # Milestone 0 findings
├── src/                   # ROS2 packages (to be created)
├── ui/                    # React frontend (to be created)
└── backend/               # FastAPI backend (to be created)
```

## Update Protocol
When a milestone is completed:
1. Move it to "Completed Milestones" with the date
2. Update "Current Milestone" to the next one
3. Update "Active Tasks" with the new milestone's tasks
4. If any scope changes or new learnings occurred, update `docs/project.md` accordingly
