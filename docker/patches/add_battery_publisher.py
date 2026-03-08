"""
Patch go2_ros2_sdk to publish battery/BMS data on /snoopi/battery.

The SDK receives bms_state inside rt/lf/lowstate but only extracts
motor_state for /joint_states.  This patch adds a JSON String publisher
on /snoopi/battery containing soc, current, cycle, power_v, and
temperature_ntc1.

Patches three files:
  1. robot_data_service.py  — store bms_raw, call publish_battery
  2. ros2_publisher.py      — add publish_battery() method
  3. go2_driver_node.py     — create the battery publisher

Each patch uses exact string matching and fails loudly if the expected
anchor text is not found — no silent partial patches.
"""
import sys
from pathlib import Path

SDK_ROOT = Path("/opt/go2_ws/src/go2_ros2_sdk/go2_robot_sdk/go2_robot_sdk")

PATCHES = []


# ── Patch 1a: robot_data_service.py — store BMS data ────────────────
PATCHES.append({
    "file": SDK_ROOT / "application/services/robot_data_service.py",
    "find": """\
            robot_data.joint_data = JointData(
                motor_state=low_state_data['motor_state']
            )""",
    "replace": """\
            robot_data.joint_data = JointData(
                motor_state=low_state_data['motor_state']
            )
            # [snoopi patch] Store BMS data for battery publishing
            robot_data.bms_raw = {
                'bms_state': low_state_data.get('bms_state', {}),
                'power_v': low_state_data.get('power_v', 0.0),
                'temperature_ntc1': low_state_data.get('temperature_ntc1', 0),
            }""",
    "desc": "Store bms_raw in _process_low_state",
})


# ── Patch 1b: robot_data_service.py — call publish_battery ──────────
PATCHES.append({
    "file": SDK_ROOT / "application/services/robot_data_service.py",
    "find": """\
                self._process_low_state(msg, robot_data)
                self.publisher.publish_joint_state(robot_data)""",
    "replace": """\
                self._process_low_state(msg, robot_data)
                self.publisher.publish_joint_state(robot_data)
                self.publisher.publish_battery(robot_data)""",
    "desc": "Call publish_battery after publish_joint_state",
})


# ── Patch 2a: ros2_publisher.py — add json + String import ──────────
PATCHES.append({
    "file": SDK_ROOT / "infrastructure/ros2/ros2_publisher.py",
    "find": """\
import logging""",
    "replace": """\
import json
import logging""",
    "desc": "Add json import to ros2_publisher",
})

PATCHES.append({
    "file": SDK_ROOT / "infrastructure/ros2/ros2_publisher.py",
    "find": """\
from std_msgs.msg import Header""",
    "replace": """\
from std_msgs.msg import Header, String""",
    "desc": "Add String import to ros2_publisher",
})


# ── Patch 2b: ros2_publisher.py — add publish_battery method ────────
# Insert after publish_joint_state method, before publish_robot_state
PATCHES.append({
    "file": SDK_ROOT / "infrastructure/ros2/ros2_publisher.py",
    "find": """\
    def publish_robot_state(self, robot_data: RobotData) -> None:""",
    "replace": """\
    def publish_battery(self, robot_data: RobotData) -> None:
        \"\"\"Publish battery/BMS data as JSON String on /snoopi/battery\"\"\"
        if not hasattr(robot_data, 'bms_raw') or not robot_data.bms_raw:
            return
        try:
            robot_idx = int(robot_data.robot_id)
            bms = robot_data.bms_raw.get('bms_state', {})
            msg = String()
            msg.data = json.dumps({
                'soc': bms.get('soc', 0),
                'current': bms.get('current', 0),
                'cycle': bms.get('cycle', 0),
                'power_v': robot_data.bms_raw.get('power_v', 0.0),
                'temperature_ntc1': robot_data.bms_raw.get('temperature_ntc1', 0),
            })
            self.publishers['battery'][robot_idx].publish(msg)
        except Exception as e:
            logger.error(f"Error publishing battery: {e}")

    def publish_robot_state(self, robot_data: RobotData) -> None:""",
    "desc": "Add publish_battery method to ROS2Publisher",
})


# ── Patch 3: go2_driver_node.py — create battery publisher ──────────
# Add String import
PATCHES.append({
    "file": SDK_ROOT / "presentation/go2_driver_node.py",
    "find": """\
from sensor_msgs.msg import PointCloud2, JointState, Joy, Image, CameraInfo""",
    "replace": """\
from sensor_msgs.msg import PointCloud2, JointState, Joy, Image, CameraInfo
from std_msgs.msg import String""",
    "desc": "Add String import to go2_driver_node",
})

# Add battery to publishers dict and create publisher
PATCHES.append({
    "file": SDK_ROOT / "presentation/go2_driver_node.py",
    "find": """\
            'voxel': []
        }""",
    "replace": """\
            'voxel': [],
            'battery': []
        }""",
    "desc": "Add battery key to publishers dict",
})

PATCHES.append({
    "file": SDK_ROOT / "presentation/go2_driver_node.py",
    "find": """\
            if self.config.publish_raw_voxel:""",
    "replace": """\
            publishers['battery'].append(
                self.create_publisher(String, '/snoopi/battery', qos_profile))

            if self.config.publish_raw_voxel:""",
    "desc": "Create /snoopi/battery publisher",
})


# ── Apply all patches ───────────────────────────────────────────────
def main():
    failed = False
    for patch in PATCHES:
        path = patch["file"]
        if not path.exists():
            print(f"FAIL: {patch['desc']}")
            print(f"  File not found: {path}")
            failed = True
            continue

        content = path.read_text()
        if patch["find"] not in content:
            print(f"FAIL: {patch['desc']}")
            print(f"  Anchor text not found in {path.name}")
            print(f"  Looking for: {patch['find'][:80]}...")
            failed = True
            continue

        count = content.count(patch["find"])
        if count > 1:
            print(f"FAIL: {patch['desc']}")
            print(f"  Anchor text found {count} times (expected 1) in {path.name}")
            failed = True
            continue

        content = content.replace(patch["find"], patch["replace"], 1)
        path.write_text(content)
        print(f"  OK: {patch['desc']}")

    if failed:
        print("\nPATCH FAILED — see errors above")
        sys.exit(1)
    else:
        print("\nAll patches applied successfully")


if __name__ == "__main__":
    main()
