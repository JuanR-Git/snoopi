"""
Mock robot publisher.
Publishes fake Go2 Air telemetry on the same topics the real SDK uses.
Lets the full UI - rosbridge - ROS2 pipeline run without the physical robot.

Topics match the patched go2_ros2_sdk:
  /snoopi/battery  — std_msgs/String (JSON with soc, power_v, temperature_ntc1, ...)
  /imu             — go2_interfaces/msg/IMU
  /joint_states    — sensor_msgs/JointState
"""
import json
import math
import time

import rclpy
from rclpy.node import Node
from go2_interfaces.msg import IMU
from sensor_msgs.msg import JointState
from std_msgs.msg import String


class MockRobotPublisher(Node):
    def __init__(self):
        super().__init__('mock_robot_publisher')
        self._battery_pub = self.create_publisher(String, '/snoopi/battery', 10)
        self._imu_pub = self.create_publisher(IMU, '/imu', 10)
        self._joint_pub = self.create_publisher(JointState, '/joint_states', 10)
        self._start = time.time()
        # Publish at 1 Hz — matches the real robot's joint state rate
        self.create_timer(1.0, self._publish_all)
        self.get_logger().info('Mock robot publisher started — publishing fake telemetry')

    def _publish_all(self) -> None:
        elapsed = time.time() - self._start

        # Battery: JSON String matching the SDK patch output
        battery = String()
        battery.data = json.dumps({
            'soc': max(80, int(100 - (elapsed / 12.0))),
            'current': -500,
            'cycle': 42,
            'power_v': 25.0 + math.sin(elapsed / 120.0) * 0.5,
            'temperature_ntc1': 35 + int(math.sin(elapsed / 60.0) * 3),
        })
        self._battery_pub.publish(battery)

        # IMU: go2_interfaces/msg/IMU — arrays, not nested objects
        imu = IMU()
        imu.quaternion = [0.0, 0.0, 0.0, 1.0]
        imu.accelerometer = [0.0, 0.0, 9.81]
        imu.gyroscope = [
            math.sin(elapsed) * 0.01,
            math.cos(elapsed) * 0.01,
            0.0,
        ]
        imu.rpy = [0.0, 0.0, 0.0]
        imu.temperature = 35
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
