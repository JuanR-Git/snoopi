# Autonomous walking with sit/stand on obstacle detection
# When an obstacle is detected, the robot sits down, waits, then stands back up.
# Uses LiDAR PointCloud2 for obstacle detection.
# Original authors: Mihir Patel, Karm Desai, John Mann
# Adapted for Docker container deployment on RPi5.
# Rewritten: sit/stand commands now go through /snoopi/command topic (handled by
# command_bridge) instead of direct WebRTC. The go2_driver_node already holds
# the WebRTC connection — only one client can connect at a time.
#
# Usage (inside snoopi-ros2 container):
#   ros2 run snoopi_control sit_stand
#
# Requires: go2_driver_node and command_bridge to be running.

#!/usr/bin/env python3
import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from geometry_msgs.msg import Twist
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from sensor_msgs.msg import PointCloud2
from std_msgs.msg import String
import time
import sensor_msgs_py.point_cloud2 as pc2
from rcl_interfaces.srv import SetParameters
from rclpy.parameter import Parameter
import math
from tf2_ros import Buffer, TransformListener
from tf2_sensor_msgs.tf2_sensor_msgs import do_transform_cloud
import threading


# State machine constants
FORWARD = "forward"
BACKWARD = "backward"
TURNING = "turning"
STOPPED = "stopped"
state = STOPPED
turning_start = None
TURN_MIN_TIME = 0.10
TURN_MAX_TIME = 1.0
OBSTACLE_DIST = 0.75


class ObstacleDetection(Node):
    def __init__(self, lidar_viewer):
        self.lidar = lidar_viewer
        self.obstacle_detected_left = False
        self.obstacle_detected_right = False
        super().__init__('param_controller')
        self.cli = self.create_client(SetParameters, '/go2_driver_node/set_parameters')
        while not self.cli.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('Waiting for /go2_driver_node/set_parameters service...')

    def detect_obstacle(self):
        global state
        self.obstacle_detected_left = False
        self.obstacle_detected_right = False

        if self.lidar.min_dist < OBSTACLE_DIST:
            state = STOPPED
            if self.lidar.y < 0.12 and self.lidar.y >= 0:
                self.obstacle_detected_left = True
            elif self.lidar.y > -0.16 and self.lidar.y < 0:
                self.obstacle_detected_right = True
            else:
                if self.lidar.y_max <= 0:
                    self.obstacle_detected_right = True
                else:
                    self.obstacle_detected_left = True
        else:
            state = FORWARD


class LidarViewer(Node):
    def __init__(self):
        super().__init__('closest_point_checker')
        self.min_dist = float('inf')
        self.max_dist = -float('inf')
        self.tf_buffer = Buffer()
        self.x = float('inf')
        self.y = float('inf')
        self.x_max = float('inf')
        self.y_max = float('inf')
        self.angle_lim = 0.0
        self.tf_listener = TransformListener(self.tf_buffer, self)

        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE
        )

        self.subscription = self.create_subscription(
            PointCloud2,
            '/point_cloud2',
            self.pointcloud_callback,
            qos
        )

    def pointcloud_callback(self, msg):
        self.min_dist = float('inf')
        self.max_dist = -float('inf')
        self.x = float('inf')
        self.y = float('inf')
        self.x_max = float('inf')
        self.y_max = float('inf')
        try:
            transform = self.tf_buffer.lookup_transform(
                'base_link',
                msg.header.frame_id,
                rclpy.time.Time(),
                timeout=rclpy.duration.Duration(seconds=0.1)
            )
        except Exception as e:
            self.get_logger().warn(f"TF transform failed: {e}")
            return

        cloud = do_transform_cloud(msg, transform)

        points = pc2.read_points(cloud, field_names=('x', 'y', 'z'), skip_nans=True)
        closest_point = None

        for x, y, z in points:
            if x <= 0:
                continue

            if y > 0.12 or y < -0.16:
                continue

            if z <= -0.1 or z >= 0.1:
                continue

            dist = math.sqrt(x*x + y*y + z*z) - 0.32
            if dist < self.min_dist:
                self.min_dist = dist
                closest_point = (x, y, z)
                self.x = closest_point[0]
                self.y = closest_point[1]

            if dist > self.max_dist:
                furthest_point = (x, y, z)
                self.max_dist = dist
                self.x_max = furthest_point[0]
                self.y_max = furthest_point[1]

        if closest_point:
            self.get_logger().info(
                f"Closest object at {closest_point} distance {self.min_dist:.2f}"
            )
        else:
            self.get_logger().info("No valid forward obstacles.")


class Go2Mover(Node):
    def __init__(self, obs_det):
        super().__init__('go2_mover')
        self.publisher_ = self.create_publisher(Twist, 'cmd_vel_out', 10)
        self.cmd_pub = self.create_publisher(String, '/snoopi/command', 10)
        self.startup_scan_done = False
        self.scan_start_time = None
        self.obs = obs_det

    def send_command(self, command):
        """Send a command to the command_bridge via /snoopi/command topic."""
        msg = String()
        msg.data = command
        self.cmd_pub.publish(msg)
        self.get_logger().info(f"Sent command: {command}")

    def sit_down(self):
        self.send_command("sit")

    def stand_up(self):
        self.send_command("stand")

    def fullStop(self):
        stop_msg = Twist()
        try:
            if rclpy.ok():
                stop_msg.linear.x = 0.0
                stop_msg.linear.y = 0.0
                stop_msg.angular.z = 0.0
                self.publisher_.publish(stop_msg)
        except Exception as exc:
            print(f"[WARNING] Could not send stop command (ROS shutting down): {exc}")

    def move(self):
        msg = Twist()
        global state, turning_start
        scan_duration = 4.5
        scan_angular_speed = 0.85

        while rclpy.ok():
            rclpy.spin_once(self.obs.lidar, timeout_sec=0.01)
            self.obs.detect_obstacle()

            cur_time = time.time()
            if not self.startup_scan_done:
                if self.scan_start_time is None:
                    self.scan_start_time = time.time()

                elapsed = time.time() - self.scan_start_time

                if elapsed < 9.675:
                    msg.linear.x = 0.0
                    msg.angular.z = 0.85
                else:
                    msg.angular.z = 0.0
                    self.startup_scan_done = True

                self.publisher_.publish(msg)
                time.sleep(0.05)
                continue

            if state == FORWARD:
                msg.linear.x = 0.325
                msg.linear.y = 0.0
                msg.angular.z = 0.0

            elif state == TURNING:
                if turning_start is None:
                    turning_start = cur_time

                elapsed_time = cur_time - turning_start

                if self.obs.obstacle_detected_left and not self.obs.obstacle_detected_right:
                    msg.angular.z = -0.85
                    msg.linear.x = 0.0
                    msg.linear.y = 0.0
                elif self.obs.obstacle_detected_right and not self.obs.obstacle_detected_left:
                    msg.angular.z = 0.85
                    msg.linear.x = 0.0
                    msg.linear.y = 0.0

                if elapsed_time > TURN_MIN_TIME and not self.obs.obstacle_detected_left and not self.obs.obstacle_detected_right:
                    state = FORWARD
                    turning_start = None

                if elapsed_time > TURN_MAX_TIME:
                    turning_start = None

            elif state == BACKWARD:
                msg.linear.x = -0.2
                msg.linear.y = 0.0
                msg.angular.z = 0.0

            elif state == STOPPED:
                msg.linear.x = 0.0
                msg.linear.y = 0.0
                msg.angular.z = 0.0
                self.sit_down()
                time.sleep(7.5)
                self.stand_up()

            self.publisher_.publish(msg)


def main(args=None):
    print("SNOOPI Starting (sit/stand mode)...")
    rclpy.init(args=args)
    lidar = LidarViewer()
    obs_det = ObstacleDetection(lidar)
    mover = Go2Mover(obs_det)

    executor = MultiThreadedExecutor()
    executor.add_node(lidar)
    executor.add_node(obs_det)
    executor.add_node(mover)

    try:
        mover.get_logger().info('Moving forward with sit/stand on obstacle...')
        move_thread = threading.Thread(target=mover.move, daemon=True)
        move_thread.start()
        executor.spin()

    except KeyboardInterrupt:
        state = STOPPED
        mover.fullStop()
        print("Keyboard Interrupt")

    mover.get_logger().info('Movement demo complete.')
    mover.destroy_node()
    obs_det.destroy_node()
    lidar.destroy_node()

    if rclpy.ok():
        rclpy.shutdown()


if __name__ == '__main__':
    main()
