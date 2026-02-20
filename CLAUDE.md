# CLAUDE.md

## Project
Hospital robot application on Unitree Go2 Air. See `docs/project.md` for full project plan.

## Current Milestone
Milestone 0 — Validation & Discovery
See `docs/project.md` → Section 8, Milestone 0 for full task list.

## Active Tasks
- [ ] Check Go2 Air firmware version
- [ ] Verify go2_ros2_sdk compatibility
- [ ] Check Raspberry Pi 4 specs

## Completed Milestones
(none yet)

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
- All safety-critical nodes must run on companion computer (RPi4), not over WiFi

## Project Structure
```
├── CLAUDE.md              # This file — active instructions
├── docs/
│   ├── project.md         # Full project plan (v2)
│   └── hardware-validation.md  # Milestone 0 findings (to be created)
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