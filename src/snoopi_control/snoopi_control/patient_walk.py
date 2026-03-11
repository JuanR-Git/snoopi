"""
Patient Walk — integrated walk script combining path tracking, UWB patient
following, LiDAR obstacle avoidance, and e-stop with sit/stand.

State machine:
  IDLE -> WALKING -> COMPLETED
           |  ^
           v  |
      PATIENT_FAR  (UWB distance > patient_max_dist -> stop and wait)
           |  ^
           v  |
      OBSTACLE_DETOUR  (LiDAR obstacle -> turn to safe angle)
           |  ^
           v  |
      RETURNING_TO_PATH  (obstacle cleared -> turn back to path heading)

  Any state -> E_STOPPED  (on /snoopi/estop -> sit down, zero velocity)
  E_STOPPED -> IDLE       (on /snoopi/command "stand" -> stand up)

UWB notes:
  - Sensor spacing is ~30cm, noise is +/-35cm per anchor.
  - Combined noise on anchor difference is +/-70cm, which exceeds the
    30cm spacing, so front/back direction detection is unreliable.
  - Direction detection is DISABLED — speed is based purely on
    triangulated distance.
  - A rolling average (5 samples) smooths out noise on distance readings.
"""

import math
import json
import time
from collections import deque

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import PointCloud2
from std_msgs.msg import String, Bool
from go2_interfaces.msg import WebRtcReq
from tf2_ros import Buffer, TransformListener
from tf2_sensor_msgs.tf2_sensor_msgs import do_transform_cloud
import sensor_msgs_py.point_cloud2 as pc2

# States
IDLE = 'IDLE'
WALKING = 'WALKING'
PATIENT_FAR = 'PATIENT_FAR'
OBSTACLE_DETOUR = 'OBSTACLE_DETOUR'
RETURNING_TO_PATH = 'RETURNING_TO_PATH'
COMPLETED = 'COMPLETED'
E_STOPPED = 'E_STOPPED'

# Default tunable parameters — calibrated for UWB with +/-0.35m noise
# Beside robot = ~1.0m, two steps away = ~2.2m
DEFAULT_PARAMS = {
    'obstacle_dist': 0.40,        # LiDAR trigger distance
    'obstacle_dist_safe': 0.30,   # stricter threshold during detour
    'patient_max_dist': 2.0,      # stop if patient farther than this
    'patient_min_dist': 0.5,      # stop if patient closer than this
    'patient_close_dist': 1.5,    # normal range upper bound
    'max_speed': 0.25,            # normal forward speed
    'min_speed': 0.10,            # slow speed when patient borderline
    'catchup_speed': 0.25,        # disabled (same as max) — direction unreliable
    'max_rotation': 0.7,          # max angular velocity for turns
    'walk_distance': 2.13,        # target path length
}

# Rolling average window for UWB distance smoothing
UWB_SMOOTH_WINDOW = 5


class PatientWalk(Node):
    """Single node that orchestrates the entire patient walk."""

    def __init__(self):
        super().__init__('patient_walk')

        # --- Tunable parameters ---
        self.params = dict(DEFAULT_PARAMS)

        # --- State machine ---
        self.state = IDLE
        self.start_x = 0.0
        self.start_y = 0.0
        self.distance_walked = 0.0
        self.path_heading = 0.0       # yaw when walk started (straight path direction)
        self.current_yaw = 0.0
        self.locked_angle = None      # target yaw during turns
        self.pre_detour_heading = 0.0

        # --- UWB state ---
        self.patient_distance = None  # smoothed triangulated distance
        self.uwb_raw_buffer = deque(maxlen=UWB_SMOOTH_WINDOW)
        self.uwb_update_count = 0     # count for rate tracking
        self.uwb_rate_time = time.time()
        self.uwb_rate_hz = 0.0

        # --- LiDAR state (integrated from LidarViewer) ---
        self.lidar_min_dist = float('inf')
        self.best_safe_angle = 0.0
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # --- LiDAR diagnostics ---
        self.pc_recv_count = 0        # total pointcloud messages received
        self.pc_tf_fail_count = 0     # TF lookup failures
        self.pc_processed_count = 0   # successfully processed
        self.pc_path_points = 0       # points in walking path (last scan)
        self.pc_total_points = 0      # total forward points (last scan)
        self.pc_frame_id = ''         # frame_id of point cloud

        # --- Odom state ---
        self.odom_x = 0.0
        self.odom_y = 0.0
        self.odom_received = False

        # --- Logging ---
        self.last_log_time = 0.0
        self.current_speed = 0.0

        # --- Publishers ---
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel_out', 10)
        self.webrtc_pub = self.create_publisher(WebRtcReq, '/webrtc_req', 10)
        self.walk_status_pub = self.create_publisher(String, '/snoopi/walk_status', 10)

        # --- Subscribers ---
        lidar_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.create_subscription(PointCloud2, '/point_cloud2', self._pointcloud_callback, lidar_qos)
        self.create_subscription(Odometry, '/odom', self._odom_callback, 10)
        self.create_subscription(String, '/snoopi/uwb_status', self._uwb_callback, 10)
        self.create_subscription(Bool, '/snoopi/estop', self._estop_callback, 10)
        self.create_subscription(String, '/snoopi/params', self._params_callback, 10)
        self.create_subscription(String, '/snoopi/task_command', self._task_callback, 10)
        # Listen for "stand" command to recover from E_STOPPED
        self.create_subscription(String, '/snoopi/command', self._command_callback, 10)

        # --- Timers ---
        self.create_timer(0.01, self._control_loop)   # 100 Hz
        self.create_timer(0.5, self._log_status)       # 2 Hz
        self.create_timer(1.0, self._publish_status)   # 1 Hz

        self.get_logger().info('PatientWalk node started — waiting in IDLE')

    # ------------------------------------------------------------------ #
    #  Callbacks                                                          #
    # ------------------------------------------------------------------ #

    def _odom_callback(self, msg):
        q = msg.pose.pose.orientation
        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        self.current_yaw = math.atan2(siny_cosp, cosy_cosp)

        self.odom_x = msg.pose.pose.position.x
        self.odom_y = msg.pose.pose.position.y
        self.odom_received = True

        if self.state in (WALKING, PATIENT_FAR, OBSTACLE_DETOUR, RETURNING_TO_PATH):
            dx = self.odom_x - self.start_x
            dy = self.odom_y - self.start_y
            self.distance_walked = math.sqrt(dx * dx + dy * dy)

    def _uwb_callback(self, msg):
        try:
            data = json.loads(msg.data)
            dist = data.get('triangulated_distance_m', -1)
            if dist > 0:
                self.uwb_raw_buffer.append(dist)
                # Rolling average for smoothing
                self.patient_distance = sum(self.uwb_raw_buffer) / len(self.uwb_raw_buffer)

            # Track UWB update rate
            self.uwb_update_count += 1
            now = time.time()
            elapsed = now - self.uwb_rate_time
            if elapsed >= 2.0:
                self.uwb_rate_hz = self.uwb_update_count / elapsed
                self.uwb_update_count = 0
                self.uwb_rate_time = now
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    def _estop_callback(self, msg):
        if msg.data and self.state != E_STOPPED:
            self.get_logger().fatal('E-STOP triggered — sitting down')
            self.state = E_STOPPED
            self._send_velocity(0.0, 0.0)
            self._send_sit()

    def _command_callback(self, msg):
        """Listen for 'stand' to recover from E_STOPPED."""
        cmd = msg.data.strip().lower()
        if cmd == 'stand' and self.state == E_STOPPED:
            self.get_logger().info('Stand received — recovering from E_STOPPED')
            self._send_stand()
            self.state = IDLE

    def _params_callback(self, msg):
        try:
            updates = json.loads(msg.data)
            for key, val in updates.items():
                if key in self.params:
                    self.params[key] = float(val)
                    self.get_logger().info(f'Param updated: {key} = {self.params[key]}')
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            self.get_logger().warn(f'Invalid params message: {e}')

    def _task_callback(self, msg):
        try:
            data = json.loads(msg.data)
            task_type = data.get('type', '').lower()
            if task_type == 'walk' and self.state == IDLE:
                # Optionally override walk distance from task
                dist = data.get('distance_m')
                if dist is not None and float(dist) > 0:
                    self.params['walk_distance'] = float(dist)
                self._start_walk()
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            self.get_logger().warn(f'Invalid task_command: {e}')

    def _pointcloud_callback(self, msg):
        """LiDAR processing — adapted from LidarViewer in following.py.

        Diagnostic counters track each failure mode so the log shows
        exactly why obstacle detection might not be working.
        """
        self.pc_recv_count += 1

        # Log frame_id on first receipt
        if not self.pc_frame_id:
            self.pc_frame_id = msg.header.frame_id
            self.get_logger().info(
                f'LiDAR: first point cloud received — frame_id="{msg.header.frame_id}"'
            )

        # TF lookup — log failures instead of silently returning
        try:
            transform = self.tf_buffer.lookup_transform(
                'base_link',
                msg.header.frame_id,
                rclpy.time.Time(),
                timeout=rclpy.duration.Duration(seconds=0.1),
            )
        except Exception as e:
            self.pc_tf_fail_count += 1
            if self.pc_tf_fail_count <= 3 or self.pc_tf_fail_count % 50 == 0:
                self.get_logger().warn(
                    f'LiDAR TF failed ({self.pc_tf_fail_count}x): '
                    f'"{msg.header.frame_id}" -> "base_link": {e}'
                )
            return

        cloud = do_transform_cloud(msg, transform)

        min_dist = float('inf')
        bins = 21
        angle_min = -math.radians(45)
        angle_max = math.radians(45)
        bin_amount = [0.0001] * bins
        bin_width = (angle_max - angle_min) / bins

        # Diagnostic counters for this scan
        total_points = 0
        forward_points = 0
        z_pass_points = 0
        path_points = 0

        for x, y, z in pc2.read_points(cloud, field_names=('x', 'y', 'z'), skip_nans=True):
            total_points += 1

            if x <= 0:
                continue
            forward_points += 1

            is_in_path = (-0.16 <= y <= 0.12)
            is_in_vision = (-1.0 <= y <= 1.0)

            if not is_in_vision:
                continue

            # Z-filter: keep points near robot body height.
            # Widened from [-0.1, 0.1] to [-0.25, 0.25] to catch low obstacles
            # (boxes, legs) that were being filtered out.
            if z <= -0.25 or z >= 0.25:
                continue
            z_pass_points += 1

            angle = math.atan2(y, x)
            if angle < angle_min or angle > angle_max:
                continue

            dist = math.sqrt(x * x + y * y + z * z) - 0.32

            # Bin density for pathfinding
            bin_index = int((angle - angle_min) / bin_width)
            bin_index = min(max(bin_index, 0), bins - 1)
            bin_amount[bin_index] += 1.0 / max(dist, 0.1)

            # Only count points in robot's walking path for obstacle distance
            if is_in_path and dist < min_dist:
                min_dist = dist
                path_points += 1

        self.lidar_min_dist = min_dist
        self.pc_total_points = forward_points
        self.pc_path_points = path_points
        self.pc_processed_count += 1

        # Log first successful scan with point counts for debugging
        if self.pc_processed_count == 1:
            self.get_logger().info(
                f'LiDAR: first scan processed — '
                f'total={total_points}, forward={forward_points}, '
                f'z_pass={z_pass_points}, path={path_points}, '
                f'min_dist={min_dist:.2f}m'
            )

        # Find least-dense bin closest to center for safe turning angle
        min_density = min(bin_amount)
        candidates = [i for i, val in enumerate(bin_amount) if val == min_density]
        center = bins // 2
        best_idx = min(candidates, key=lambda idx: abs(idx - center))
        self.best_safe_angle = angle_min + (best_idx + 0.5) * bin_width

    # ------------------------------------------------------------------ #
    #  Control loop                                                       #
    # ------------------------------------------------------------------ #

    def _control_loop(self):
        if self.state == IDLE or self.state == COMPLETED:
            return

        if self.state == E_STOPPED:
            self._send_velocity(0.0, 0.0)
            return

        # Check walk distance completion
        if self.distance_walked >= self.params['walk_distance']:
            self.state = COMPLETED
            self._send_velocity(0.0, 0.0)
            self.get_logger().info(
                f'Walk completed! Distance: {self.distance_walked:.2f}/{self.params["walk_distance"]:.2f}m'
            )
            return

        # --- OBSTACLE_DETOUR ---
        if self.state == OBSTACLE_DETOUR:
            if self.lidar_min_dist > self.params['obstacle_dist']:
                # Obstacle cleared — return to path heading
                self.locked_angle = self.path_heading
                self.state = RETURNING_TO_PATH
                return

            # Turn to safe angle, then creep forward
            if self.locked_angle is not None:
                error = self._angle_error(self.locked_angle, self.current_yaw)
                if abs(error) < 0.15:
                    # Pointed in safe direction — creep forward
                    self._send_velocity(self.params['min_speed'], 0.0)
                else:
                    ang_z = max(-self.params['max_rotation'],
                               min(self.params['max_rotation'], error * 1.5))
                    self._send_velocity(0.0, ang_z)
            return

        # --- RETURNING_TO_PATH ---
        if self.state == RETURNING_TO_PATH:
            error = self._angle_error(self.path_heading, self.current_yaw)
            if abs(error) < 0.15:
                self.locked_angle = None
                self.state = WALKING
            else:
                ang_z = max(-self.params['max_rotation'],
                           min(self.params['max_rotation'], error * 1.5))
                self._send_velocity(0.0, ang_z)
            return

        # --- Check for obstacle entering WALKING or PATIENT_FAR ---
        if self.state in (WALKING, PATIENT_FAR):
            if self.lidar_min_dist < self.params['obstacle_dist']:
                self.pre_detour_heading = self.current_yaw
                self.locked_angle = self.current_yaw + self.best_safe_angle
                # Normalize locked_angle to [-pi, pi]
                self.locked_angle = math.atan2(
                    math.sin(self.locked_angle), math.cos(self.locked_angle)
                )
                self.state = OBSTACLE_DETOUR
                self._send_velocity(0.0, 0.0)
                return

        # --- WALKING / PATIENT_FAR: UWB distance-only speed control ---
        speed = self._compute_speed()
        if speed is None:
            self.state = PATIENT_FAR
            self._send_velocity(0.0, 0.0)
        else:
            if self.state == PATIENT_FAR and speed > 0:
                self.state = WALKING
            self.current_speed = speed
            self._send_velocity(speed, 0.0)

    # ------------------------------------------------------------------ #
    #  Helpers                                                            #
    # ------------------------------------------------------------------ #

    def _start_walk(self):
        self.start_x = self.odom_x
        self.start_y = self.odom_y
        self.distance_walked = 0.0
        self.path_heading = self.current_yaw
        self.locked_angle = None
        self.uwb_raw_buffer.clear()
        self.state = WALKING
        self.get_logger().info(
            f'Walk started — target: {self.params["walk_distance"]:.2f}m, '
            f'heading: {self.path_heading:.2f} rad'
        )

    def _compute_speed(self):
        """Return speed based on smoothed UWB distance, or None for PATIENT_FAR.

        Speed zones (distance-only, direction detection disabled):
          0 ── patient_min_dist ── patient_close_dist ── patient_max_dist ──→
           STOP      max_speed           min_speed            STOP (FAR)
        """
        if self.patient_distance is None:
            # No UWB data — walk at max_speed (patient might not have tag on yet)
            return self.params['max_speed']

        if self.patient_distance < self.params['patient_min_dist']:
            return 0.0
        elif self.patient_distance < self.params['patient_close_dist']:
            return self.params['max_speed']
        elif self.patient_distance < self.params['patient_max_dist']:
            return self.params['min_speed']
        else:
            return None  # patient too far

    @staticmethod
    def _angle_error(target, current):
        """Compute shortest angular error in [-pi, pi]."""
        error = target - current
        return (error + math.pi) % (2 * math.pi) - math.pi

    def _send_velocity(self, linear_x, angular_z):
        msg = Twist()
        msg.linear.x = float(linear_x)
        msg.angular.z = float(angular_z)
        self.cmd_vel_pub.publish(msg)
        self.current_speed = linear_x

    def _send_sit(self):
        msg = WebRtcReq()
        msg.api_id = 1005
        msg.topic = 'rt/api/sport/request'
        msg.parameter = ''
        msg.priority = 0
        self.webrtc_pub.publish(msg)

    def _send_stand(self):
        msg = WebRtcReq()
        msg.api_id = 1004
        msg.topic = 'rt/api/sport/request'
        msg.parameter = ''
        msg.priority = 0
        self.webrtc_pub.publish(msg)

    # ------------------------------------------------------------------ #
    #  Logging & status                                                   #
    # ------------------------------------------------------------------ #

    def _log_status(self):
        now = time.time()
        if now - self.last_log_time < 0.5:
            return
        self.last_log_time = now

        ts = time.strftime('%H:%M:%S')
        dist_str = f'{self.distance_walked:.2f}/{self.params["walk_distance"]:.2f}m'
        uwb_str = f'{self.patient_distance:.2f}m' if self.patient_distance else 'N/A'
        uwb_hz = f'{self.uwb_rate_hz:.1f}Hz'

        # LiDAR diagnostic string
        if self.pc_recv_count == 0:
            lidar_str = 'NO_DATA'
        elif self.pc_tf_fail_count > 0 and self.pc_processed_count == 0:
            lidar_str = f'TF_FAIL({self.pc_tf_fail_count}x)'
        elif self.lidar_min_dist < 100:
            lidar_str = f'{self.lidar_min_dist:.2f}m({self.pc_path_points}pts)'
        else:
            lidar_str = f'clear({self.pc_total_points}fwd,{self.pc_path_points}path)'

        if self.state == IDLE:
            print(
                f'[WALK {ts}] State: IDLE | LiDAR: {lidar_str} | '
                f'PC: recv={self.pc_recv_count} ok={self.pc_processed_count} '
                f'tf_fail={self.pc_tf_fail_count} | Waiting for task command...'
            )
        elif self.state == COMPLETED:
            print(f'[WALK {ts}] State: COMPLETED | Dist: {dist_str} | Walk finished!')
        elif self.state == E_STOPPED:
            print(f'[WALK {ts}] State: E_STOPPED | Dist: {dist_str} | Emergency stop — sitting down')
        elif self.state == PATIENT_FAR:
            print(
                f'[WALK {ts}] State: PATIENT_FAR | Dist: {dist_str} | '
                f'UWB: {uwb_str} ({uwb_hz}) | Speed: 0.00 | LiDAR: {lidar_str} | Waiting...'
            )
        elif self.state == OBSTACLE_DETOUR:
            target = f'{self.locked_angle:.2f}rad' if self.locked_angle is not None else 'N/A'
            print(
                f'[WALK {ts}] State: OBSTACLE_DETOUR | Dist: {dist_str} | '
                f'UWB: {uwb_str} | Speed: {self.current_speed:.2f} | '
                f'LiDAR: {lidar_str} | Turning to {target}'
            )
        elif self.state == RETURNING_TO_PATH:
            print(
                f'[WALK {ts}] State: RETURNING_TO_PATH | Dist: {dist_str} | '
                f'UWB: {uwb_str} | Heading: {self.path_heading:.2f}rad'
            )
        else:
            print(
                f'[WALK {ts}] State: {self.state} | Dist: {dist_str} | '
                f'UWB: {uwb_str} ({uwb_hz}) | Speed: {self.current_speed:.3f} | '
                f'LiDAR: {lidar_str} | Heading: {self.current_yaw:.2f}rad'
            )

    def _publish_status(self):
        status = {
            'state': self.state,
            'distance_walked': round(self.distance_walked, 2),
            'walk_distance': self.params['walk_distance'],
            'patient_distance': round(self.patient_distance, 2) if self.patient_distance else None,
            'speed': round(self.current_speed, 3),
            'lidar_min_dist': round(self.lidar_min_dist, 2) if self.lidar_min_dist < 100 else None,
            'heading': round(self.current_yaw, 2),
            'uwb_rate_hz': round(self.uwb_rate_hz, 1),
        }
        msg = String()
        msg.data = json.dumps(status)
        self.walk_status_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = PatientWalk()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('Keyboard interrupt — stopping')
        node._send_velocity(0.0, 0.0)
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
