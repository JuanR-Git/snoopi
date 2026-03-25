
import math
import json
import time
from collections import deque

import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from rcl_interfaces.srv import SetParameters
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import PointCloud2
from std_msgs.msg import String, Bool
from go2_interfaces.msg import WebRtcReq
from tf2_ros import Buffer, TransformListener
from tf2_sensor_msgs.tf2_sensor_msgs import do_transform_cloud
import sensor_msgs_py.point_cloud2 as pc2

# --- Global States ---
IDLE = 'IDLE'
WALKING = 'WALKING'
PATIENT_FAR = 'PATIENT_FAR'
OBSTACLE_DETOUR = 'OBSTACLE_DETOUR'
RETURNING_TO_PATH = 'RETURNING_TO_PATH'
COMPLETED = 'COMPLETED'
E_STOPPED = 'E_STOPPED'

state = IDLE

# --- Shared Configuration ---
DEFAULT_PARAMS = {
    'obstacle_dist': 0.40,        # LiDAR trigger distance
    'obstacle_dist_safe': 0.30,   # stricter threshold during detour
    'patient_max_dist': 2.0,      # stop if patient farther than this
    'patient_min_dist': 0.5,      # stop if patient closer than this
    'patient_close_dist': 1.5,    # normal range upper bound
    'max_speed': 0.25,            # normal forward speed
    'min_speed': 0.10,            # slow speed when patient borderline
    'catchup_speed': 0.25,        # disabled (same as max)
    'max_rotation': 0.7,          # max angular velocity for turns
    'walk_distance': 2.13,        # target path length
}

UWB_SMOOTH_WINDOW = 5

class UserInterface(Node):
    def __init__(self, params):
        super().__init__('user_interface')
        self.params = params
        self.create_subscription(String, '/snoopi/params', self._params_callback, 10)
        self.create_subscription(String, '/snoopi/task_command', self._task_callback, 10)
    
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
        global state
        try:
            data = json.loads(msg.data)
            task_type = data.get('type', '').lower()
            if task_type == 'walk' and state == IDLE:
                # Optionally override walk distance from task
                dist = data.get('distance_m')
                if dist is not None and float(dist) > 0:
                    self.params['walk_distance'] = float(dist)
                state = WALKING
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            self.get_logger().warn(f'Invalid task_command: {e}')

class Following(Node):
    def __init__(self):
        super().__init__('follower')
        self.uwb_raw_buffer = deque(maxlen=UWB_SMOOTH_WINDOW)
        self.uwb_update_count = 0
        self.uwb_rate_time = time.time()
        self.uwb_rate_hz = 0.0
        self.patient_distance = None 
        self.create_subscription(String, '/snoopi/uwb_status', self._uwb_callback, 10)
        
    
    def _uwb_callback(self, msg):
        try:
            data = json.loads(msg.data)
            dist = data.get('triangulated_distance_m', -1)
            if dist > 0:
                self.uwb_raw_buffer.append(dist)
                self.patient_distance = sum(self.uwb_raw_buffer) / len(self.uwb_raw_buffer)

            self.uwb_update_count += 1
            now = time.time()
            elapsed = now - self.uwb_rate_time
            if elapsed >= 2.0:
                self.uwb_rate_hz = self.uwb_update_count / elapsed
                self.uwb_update_count = 0
                self.uwb_rate_time = now
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

class LidarViewer(Node):
    def __init__(self):
        super().__init__('closest_point_checker')
        self.lidar_min_dist = 1.0
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.pc_recv_count = 0
        self.pc_tf_fail_count = 0
        self.pc_processed_count = 0
        self.pc_path_points = 0
        self.pc_total_points = 0
        self.pc_frame_id = ''
        self.best_safe_angle = 0.0
        self.lidar_str = "NO_DATA"

        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE
        )
        self.subscription = self.create_subscription(PointCloud2, '/point_cloud2', self._pointcloud_callback, qos)

    def _pointcloud_callback(self, msg):
        self.pc_recv_count += 1
        if not self.pc_frame_id:
            self.pc_frame_id = msg.header.frame_id
        
        try:
            transform = self.tf_buffer.lookup_transform('base_link', msg.header.frame_id, rclpy.time.Time(), timeout=rclpy.duration.Duration(seconds=0.1))
        except Exception:
            self.pc_tf_fail_count += 1
            return

        cloud = do_transform_cloud(msg, transform)
        min_dist = float('inf')
        bins = 21
        angle_min, angle_max = -math.radians(45), math.radians(45)
        bin_amount = [0.0001] * bins
        bin_width = (angle_max - angle_min) / bins
        path_points = 0
        forward_points = 0

        for x, y, z in pc2.read_points(cloud, field_names=('x', 'y', 'z'), skip_nans=True):
            if x <= 0: continue
            forward_points += 1 ###seems unneceassry
            
            if z <= -0.1 or z >= 0.1: continue  ###larger bounds here
            
            is_in_vision = (-1.0 <= y <= 1.0)
            if not is_in_vision: continue

            ###in-vision for y does not exist here
            angle = math.atan2(y, x)
            angle_cur = math.atan2(y, x)
            if angle < angle_min or angle > angle_max: continue  ###no target angle vs current angle relation
            
            dist = math.sqrt(x*x + y*y + z*z) - 0.32
            bin_index = min(max(int((angle - angle_min) / bin_width), 0), bins - 1)
            bin_amount[bin_index] += 1.0 / max(dist, 0.1)

            ###doesnt have closest and furthest point lines

            if dist < self.lidar_min_dist:
                self.lidar_min_dist = dist
                closest_point = (x, y, z)
                self.x = closest_point[0]
                self.y = closest_point[1]
        self.pc_total_points = forward_points
        self.pc_path_points = path_points
        self.pc_processed_count += 1

        min_density = min(bin_amount)
        candidates = [i for i, val in enumerate(bin_amount) if val == min_density]
        best_idx = min(candidates, key=lambda idx: abs(idx - (bins // 2)))
        self.best_safe_angle = angle_min + (best_idx + 0.5) * bin_width
        self.lidar_str = f'{self.lidar_min_dist:.2f}m({self.pc_path_points}pts)' if self.lidar_min_dist < 50 else "clear"

        ### no current time if condition

class ObstacleAvoidance(Node):
    def __init__(self, lidar, follower, params):
        super().__init__('obstacle_avoidance')
        self.lidar = lidar
        self.follower = follower
        self.params = params
        self.cli = self.create_client(SetParameters, '/go2_driver_node/set_parameters')

    def detect_obstacle(self, current_yaw):
        global state
        if self.lidar.lidar_min_dist > self.params['obstacle_dist']:
            if state == OBSTACLE_DETOUR:
                state = RETURNING_TO_PATH
            return None
        else:
            state = OBSTACLE_DETOUR
            target = current_yaw + self.lidar.best_safe_angle
            return math.atan2(math.sin(target), math.cos(target))

class Go2Mover(Node):
    def __init__(self, lidar, follower, obs, params):
        super().__init__('go2_mover')
        self.lidar = lidar
        self.sat = False
        self.walk_started = False
        self.follower = follower
        self.obs = obs
        self.params = params
        self.publisher_ = self.create_publisher(Twist, '/cmd_vel_out', 10)
        self.webrtc_pub = self.create_publisher(WebRtcReq, '/webrtc_req', 10)
        self.walk_status_pub = self.create_publisher(String, '/snoopi/walk_status', 10)

        self.create_subscription(Odometry, '/odom', self._odom_callback, 10)
        self.create_subscription(Bool, '/snoopi/estop', self._estop_callback, 10)
        
        self.current_yaw = 0.0
        self.odom_x = 0.0
        self.odom_y = 0.0
        self.start_x = 0.0
        self.start_y = 0.0
        self.distance_walked = 0.0
        self.path_heading = 0.0
        self.locked_angle = None
        self.last_log_time = time.time()

    def _odom_callback(self, msg):
        q = msg.pose.pose.orientation
        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        self.current_yaw = math.atan2(siny_cosp, cosy_cosp)
        self.odom_x = msg.pose.pose.position.x
        self.odom_y = msg.pose.pose.position.y
        if state in [WALKING, PATIENT_FAR, OBSTACLE_DETOUR, RETURNING_TO_PATH]:
            dx = self.odom_x - self.start_x
            dy = self.odom_y - self.start_y
            self.distance_walked = math.sqrt(dx*dx + dy*dy)

    def _send_sit(self):
        msg = WebRtcReq()
        msg.api_id = 1005
        msg.topic = 'rt/api/sport/request'
        msg.parameter = ''
        msg.priority = 0
        self.webrtc_pub.publish(msg)

    def _estop_callback(self, msg):
        global state
        if msg.data and state != E_STOPPED:
            self.get_logger().fatal('E-STOP triggered — sitting down')
            state = E_STOPPED
            stop_msg = Twist()
            self.publisher_.publish(stop_msg)
            self._send_sit()

    def move(self):
        global state
        while rclpy.ok():
            time.sleep(0.05)
            now = time.time()
            

            # Simple control loop logic
            if state in (WALKING, PATIENT_FAR, OBSTACLE_DETOUR, RETURNING_TO_PATH):
                new_locked = self.obs.detect_obstacle(self.current_yaw)
                if new_locked is not None:
                    self.locked_angle = new_locked

            dist = self.follower.patient_distance
            if dist is None:
                speed = self.params['max_speed']
            elif dist < self.params['patient_min_dist']:
                speed = 0.0
            elif dist < self.params['patient_close_dist']:
                speed = self.params['max_speed']
            elif dist < self.params['patient_max_dist']:
                speed = self.params['min_speed']
            else:
                speed = None

            msg = Twist()
            ts = time.strftime("%H:%M:%S")

            if state == IDLE:
                # Placeholder: change state to WALKING to start testing
                # state = WALKING
                msg.linear.x = 0.0
                msg.angular.z = 0.0

            elif state == E_STOPPED:
                msg.linear.x = 0.0
                msg.angular.z = 0.0
                if not self.sat:
                    self._send_sit()
                    self.sat = True

            elif state == PATIENT_FAR:
                if speed is not None and speed > 0:
                    state = WALKING
                    msg.linear.x = speed
                else:
                    msg.linear.x = 0.0
                    msg.angular.z = 0.0

            elif state == WALKING:
                if not self.walk_started:
                    self.start_x = self.odom_x
                    self.start_y = self.odom_y
                    self.path_heading = self.current_yaw
                    self.distance_walked = 0.0
                    self.walk_started = True
                if speed is None:
                    state = PATIENT_FAR
                else:
                    msg.linear.x = speed
                    if self.distance_walked >= self.params['walk_distance']:
                        state = COMPLETED
                        self.walk_started = False

            elif state == OBSTACLE_DETOUR:
                self.angle_match = True
                target_angle = self.obs.lidar.best_safe_angle
                msg.linear.x = 0.0
                self.publisher_.publish(msg)

                if self.locked_angle is None:
                    self.locked_angle = self.current_yaw + target_angle

                if self.locked_angle is not None:
                    error = (self.locked_angle - self.current_yaw + math.pi) % (2 * math.pi) - math.pi
                    if abs(error) < 0.15:
                        msg.angular.z = 0.0
                        self.publisher_.publish(msg) #Immediate
                        msg.linear.x = self.params['min_speed']
                        if self.params['obstacle_dist'] < self.obs.lidar.lidar_min_dist:
                            self.get_logger().info("Clear! Moving Forward.")
                            self.locked_angle = None
                            state = RETURNING_TO_PATH
                        else:
                            self.locked_angle = None
                            state = OBSTACLE_DETOUR
                    else:
                        msg.angular.z = max(-self.params['max_rotation'], min(self.params['max_rotation'], error * 1.5))

            elif state == RETURNING_TO_PATH:
                error = (self.path_heading - self.current_yaw + math.pi) % (2 * math.pi) - math.pi
                if abs(error) < 0.1:
                    state = WALKING
                else:
                    msg.angular.z = max(-self.params['max_rotation'], min(self.params['max_rotation'], error * 1.5))

            elif state == COMPLETED:
                msg.linear.x = 0.0
                msg.angular.z = 0.0
                ####self._send_sit()

            self.publisher_.publish(msg)

            if now - self.last_log_time > 0.5:
                print(f"[{ts}] State: {state:15} | Dist: {self.distance_walked:.2f}m | Lidar: {self.lidar.lidar_str}")
                self.last_log_time = now

def main(args=None):
    rclpy.init(args=args)
    params = dict(DEFAULT_PARAMS)

    # Instantiate Nodes
    lidar = LidarViewer()
    follower = Following()
    ui = UserInterface(params)
    obs_det = ObstacleAvoidance(lidar, follower, params)
    mover = Go2Mover(lidar, follower, obs_det, params)

    executor = MultiThreadedExecutor()
    nodes = [lidar, follower, ui, obs_det, mover]
    for node in nodes:
        executor.add_node(node)

    import threading
    move_thread = threading.Thread(target=mover.move, daemon=True)
    move_thread.start()

    try:
        executor.spin()
    except KeyboardInterrupt:
        print("\nShutdown requested...")
    finally:
        for node in nodes:
            node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
