# Simple movement demo: forward, stop, backward
# Uses LaserScan for basic obstacle distance logging.
# Original authors: team (Oct 5th base code)
# Adapted for Docker container deployment on RPi5.
# Fixed: removed double super().__init__ bug from original.
#
# Usage (inside snoopi-ros2 container):
#   ros2 run snoopi_control sample_move
#
# Note: This script uses LaserScan on /scan. The go2_ros2_sdk may publish
# PointCloud2 on /point_cloud2 instead. If /scan is not available, use
# safe_space or autonomous_walk instead (they use PointCloud2).

#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from sensor_msgs.msg import LaserScan
import time
from rcl_interfaces.srv import SetParameters
from rclpy.parameter import Parameter
import math


class ParamController(Node):
    def __init__(self):
        super().__init__('param_controller')
        self.cli = self.create_client(SetParameters, '/go2_driver_node/set_parameters')
        while not self.cli.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('Waiting for /go2_driver_node/set_parameters service...')

    def set_obstacle_avoidance(self, value: bool):
        param = Parameter('obstacle_avoidance', Parameter.Type.BOOL, value)
        req = SetParameters.Request()
        req.parameters = [param.to_parameter_msg()]
        future = self.cli.call_async(req)
        rclpy.spin_until_future_complete(self, future)
        if future.result() is not None:
            self.get_logger().info(f"Set obstacle_avoidance = {value}")
        else:
            self.get_logger().error("Failed to set parameter")


class Go2Mover(Node):
    def __init__(self):
        super().__init__('go2_mover')
        self.publisher_ = self.create_publisher(Twist, 'cmd_vel', 10)
        self.obstacle_detected = False

        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE
        )

        self.subscription = self.create_subscription(
            LaserScan,
            '/scan',
            self.scan_callback,
            qos
        )

    def scan_callback(self, msg: LaserScan):
        if not hasattr(self, 'debug_count'):
            self.debug_count = 0
        if self.debug_count % 10 == 0:
            self.get_logger().info(
                f"Scan info: len={len(msg.ranges)}, "
                f"angle_min={math.degrees(msg.angle_min):.1f}, "
                f"angle_max={math.degrees(msg.angle_max):.1f}, "
                f"angle_inc={math.degrees(msg.angle_increment):.3f}"
            )
            sample = msg.ranges[len(msg.ranges)//2 - 5 : len(msg.ranges)//2 + 5]
            self.get_logger().info(f"Sample center readings: {[round(x, 2) for x in sample]}")
        self.debug_count += 1

        front_angle_deg = 22.5
        front_angle_rad = math.radians(front_angle_deg)
        center_idx = len(msg.ranges) // 2
        front_idx_range = int(front_angle_rad / msg.angle_increment)
        front_indices = range(center_idx - front_idx_range, center_idx + front_idx_range)

        valid_ranges = [
            msg.ranges[i] for i in front_indices
            if msg.ranges[i] > 0.05 and not math.isinf(msg.ranges[i])
        ]

        if valid_ranges:
            min_distance = min(valid_ranges)
            self.get_logger().info(f"Closest object ahead: {min_distance:.2f} m")
            self.obstacle_detected = min_distance < 0.5
        else:
            self.get_logger().info("No valid readings in front.")
            self.obstacle_detected = False

    def move(self, linear_x=0.0, linear_y=0.0, angular_z=0.0, duration=1.0):
        end_time = self.get_clock().now().nanoseconds / 1e9 + duration
        msg = Twist()

        while rclpy.ok() and self.get_clock().now().nanoseconds / 1e9 < end_time:
            rclpy.spin_once(self, timeout_sec=0.01)
            msg.linear.y = linear_y
            msg.linear.x = linear_x
            msg.angular.z = angular_z
            self.publisher_.publish(msg)
            time.sleep(0.1)


def main(args=None):
    print("Sample movement demo starting...")

    rclpy.init(args=args)
    mover = Go2Mover()
    param = ParamController()

    param.set_obstacle_avoidance(False)

    # Step forward
    mover.get_logger().info('Moving forward...')
    mover.move(linear_x=0.4, duration=3)

    # Stop briefly
    mover.move(linear_x=0.0, duration=0.75)

    # Step backward
    mover.get_logger().info('Moving backward...')
    mover.move(linear_x=-0.4, duration=1.5)

    # Stop
    mover.move(linear_x=0.0, duration=0.5)

    param.set_obstacle_avoidance(False)

    mover.get_logger().info('Movement demo complete.')
    mover.destroy_node()
    param.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
