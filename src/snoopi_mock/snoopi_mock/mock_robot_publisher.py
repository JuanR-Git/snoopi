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
