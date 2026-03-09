# Autonomous walking with obstacle detection and bin-based path planning
# Uses LiDAR PointCloud2 for obstacle detection with 21-bin density analysis.
# Odometry-based turning to the safest heading.
# Original authors: Mihir Patel and John Mann
# Adapted for Docker container deployment on RPi5.
# Removed: go2_webrtc_connect (unused), clear_slam_cache (not needed in container).
#
# Usage (inside snoopi-ros2 container):
#   ros2 run snoopi_control autonomous_walk
#
# Requires go2_driver_node to be running (provides /point_cloud2, /odom, cmd_vel_out topics).

#!/usr/bin/env python3
import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from geometry_msgs.msg import Twist
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from sensor_msgs.msg import PointCloud2
import time
import sensor_msgs_py.point_cloud2 as pc2
from rcl_interfaces.srv import SetParameters
from rclpy.parameter import Parameter
import math
from tf2_ros import Buffer, TransformListener
from tf2_sensor_msgs.tf2_sensor_msgs import do_transform_cloud
from nav_msgs.msg import Odometry
import threading


# State machine constants
FORWARD = "forward"
BACKWARD = "backward"
TURNING = "turning"
STOPPED = "stopped"
FORWARD_SAFE = "forward_safe"
STOPPED_SAFE = "stopped_safe"
state = STOPPED
turning_start = None
TURN_MIN_TIME = 0.10
TURN_MAX_TIME = 1.0
OBSTACLE_DIST = 0.75
OBSTACLE_DIST_SAFE = 0.50
TURN_ANGLE_DEG = 15.0
TURN_SPEED = 0.7
TURN_DURATION = math.radians(TURN_ANGLE_DEG) / TURN_SPEED


class ObstacleDetection(Node):
    def __init__(self, lidar_viewer):
        self.lidar = lidar_viewer
        self.obstacle_detected_left = False
        self.obstacle_detected_right = False
        self.obstacle_detected_front = False
        super().__init__('param_controller')
        self.cli = self.create_client(SetParameters, '/go2_driver_node/set_parameters')
        while not self.cli.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('Waiting for /go2_driver_node/set_parameters service...')

    def detect_obstacle(self):
        global state
        self.obstacle_detected_left = False
        self.obstacle_detected_right = False

        if self.lidar.min_dist < OBSTACLE_DIST:
            print(self.lidar.min_dist)
            state = TURNING

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
            if state != STOPPED_SAFE and state != FORWARD_SAFE:
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
        self.cur_angle = 0.0
        self.target_angle = 0.0
        self.angle_match = False
        self.last_update_time = time.time()
        self.angle_lim = 0.0
        self.best_safe_angle = 0.0
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

        bins = 21
        angle_min = -math.radians(45)
        angle_max = math.radians(45)

        bin_amount = [0.0001] * bins
        bin_width = (angle_max - angle_min) / bins

        points = pc2.read_points(cloud, field_names=('x', 'y', 'z'), skip_nans=True)
        closest_point = None

        for x, y, z in points:
            if x <= 0:
                continue

            is_in_vision = (-1.0 <= y <= 1.0)
            if not is_in_vision:
                continue

            if z <= -0.1 or z >= 0.1:
                continue

            if self.angle_match == False:
                self.target_angle = math.atan2(y, x)
                self.cur_angle = math.atan2(y, x)

            if self.target_angle < angle_min or self.target_angle > angle_max:
                continue

            bin_index = int((self.target_angle - angle_min) / bin_width)
            bin_index = min(max(bin_index, 0), bins - 1)

            dist = math.sqrt(x*x + y*y + z*z) - 0.32
            bin_amount[bin_index] += 1.0 / max(dist, 0.1)

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

        min_density = min(bin_amount)
        candidate_indices = [i for i, val in enumerate(bin_amount) if val == min_density]
        center_idx = bins // 2
        least_dense_index = min(candidate_indices, key=lambda idx: abs(idx - center_idx))

        best_angle = angle_min + (least_dense_index + 0.5) * bin_width
        self.best_safe_angle = best_angle

        current_time = time.time()
        if current_time - self.last_update_time >= 4.0:
            self.delayed_angle = self.cur_angle
            self.last_update_time = current_time


class Go2Mover(Node):
    def __init__(self, obs_det):
        super().__init__('go2_mover')
        self.publisher_ = self.create_publisher(Twist, 'cmd_vel_out', 10)
        self.startup_scan_done = False
        self.scan_start_time = None
        self.obs = obs_det
        self.turn_end_time = None
        self.turn_direction = 0.0
        self.turn_completed = False
        self.locked_angle = None
        self.odom_sub = self.create_subscription(Odometry, '/odom', self.odom_callback, 10)
        self.current_yaw = 0.0

    def odom_callback(self, msg):
        q = msg.pose.pose.orientation
        siny_cosp = 2 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
        self.current_yaw = math.atan2(siny_cosp, cosy_cosp)

    def move(self):
        msg = Twist()

        global state, turning_start

        while rclpy.ok():
            time.sleep(0.01)

            rclpy.spin_once(self.obs.lidar, timeout_sec=0.01)
            self.obs.detect_obstacle()
            print("State: ", state)

            if state == FORWARD:
                msg.linear.x = 0.325
                msg.angular.z = 0.0

            elif state == STOPPED:
                self.locked_angle = None
                msg.linear.x = 0.0
                msg.linear.y = 0.0
                msg.angular.z = 0.0
                self.publisher_.publish(msg)

            elif state == TURNING:
                self.angle_match = True
                target_angle = self.obs.lidar.best_safe_angle
                msg.linear.x = 0.0
                self.publisher_.publish(msg)

                if self.locked_angle is None:
                    self.locked_angle = self.current_yaw + target_angle

                error = self.locked_angle - self.current_yaw
                error = (error + math.pi) % (2 * math.pi) - math.pi
                if abs(error) < 0.15:
                    msg.angular.z = 0.0
                    self.publisher_.publish(msg)
                    print("Min Distance: ", self.obs.lidar.min_dist)
                    if OBSTACLE_DIST < self.obs.lidar.min_dist:
                        self.get_logger().info("Clear! Moving Forward.")
                        self.locked_angle = None
                        state = FORWARD
                    else:
                        self.locked_angle = None
                        state = STOPPED
                else:
                    msg.angular.z = error * 1.5

            elif state == STOPPED_SAFE:
                self.angle_match = True
                target_angle = self.obs.lidar.best_safe_angle
                msg.linear.x = 0.0
                self.publisher_.publish(msg)
                print("Target: ", abs(target_angle))

                if self.locked_angle is None:
                    self.locked_angle = self.current_yaw + target_angle

                error = self.locked_angle - self.current_yaw
                error = (error + math.pi) % (2 * math.pi) - math.pi
                print("current error term: ", error)
                print("current yaw value: ", self.current_yaw)
                if abs(error) < 0.15:
                    msg.angular.z = 0.0
                    self.publisher_.publish(msg)
                    print("Min Distance: ", self.obs.lidar.min_dist)
                    if OBSTACLE_DIST_SAFE < self.obs.lidar.min_dist:
                        self.get_logger().info("Clear! Moving Forward.")
                        self.locked_angle = None
                        state = FORWARD_SAFE
                    else:
                        self.locked_angle = None
                        state = STOPPED
                else:
                    msg.angular.z = error * 1.5

            elif state == FORWARD_SAFE:
                self.locked_angle = None
                msg.linear.x = 0.325
                if self.obs.lidar.min_dist <= OBSTACLE_DIST_SAFE:
                    msg.linear.x = 0.0
                    state = STOPPED
                self.publisher_.publish(msg)

            self.publisher_.publish(msg)


def main(args=None):
    print("SNOOPI Starting...")
    rclpy.init(args=args)
    lidar = LidarViewer()
    obs_det = ObstacleDetection(lidar)
    mover = Go2Mover(obs_det)

    executor = MultiThreadedExecutor()
    executor.add_node(lidar)
    executor.add_node(obs_det)
    executor.add_node(mover)

    try:
        move_thread = threading.Thread(target=mover.move, daemon=True)
        move_thread.start()
        executor.spin()

    except KeyboardInterrupt:
        state = STOPPED
        print("Keyboard Interrupt")

    mover.get_logger().info('Movement demo complete.')
    mover.destroy_node()
    obs_det.destroy_node()
    lidar.destroy_node()

    if rclpy.ok():
        rclpy.shutdown()


if __name__ == '__main__':
    main()
