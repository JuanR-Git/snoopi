#Autonomous walking with obstacle detection
#this is one of the final drafts of the project we want to use. it focuses on the movement of the robot using lidar PointCloud for obstacle detection
#Last Modified: Mar 9th
#Author: Mihir Patel and John Mann

#!/usr/bin/env python3
import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from geometry_msgs.msg import Twist
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from sensor_msgs.msg import PointCloud2, BatteryState  #adding this to read sensor data for obstacle detection
import time
import sensor_msgs_py.point_cloud2 as pc2
from rcl_interfaces.srv import SetParameters
from rclpy.parameter import Parameter
import math
from tf2_ros import Buffer, TransformListener
from tf2_sensor_msgs.tf2_sensor_msgs import do_transform_cloud
import json
from nav_msgs.msg import Odometry
import asyncio
import threading
from go2_webrtc_connect import Go2WebRTCConnection, WebRTCConnectionMethod

import os
import subprocess

import serial
import re
from datetime import datetime

#adding constants to reprersent states for state machine
FORWARD = "forward"
BACKWARD = "backward"
TURNING = "turning"
STOPPED = "stopped"
FORWARD_SAFE = "forward_safe"
STOPPED_SAFE = "stopped_safe"
state = STOPPED
turning_start = None
TURN_MIN_TIME = 0.10 #turn at least 0.1 seconds 
TURN_MAX_TIME = 1.0 #make sure it doesnt turn forever
OBSTACLE_DIST = 0.75 #0.75
OBSTACLE_DIST_SAFE = 0.50
TURN_ANGLE_DEG = 15.0
TURN_SPEED = 0.7
TURN_DURATION = math.radians(TURN_ANGLE_DEG) / TURN_SPEED


class Following(Node):   # or Following(Node) if you are in ROS2 and import Node
    # Regex is constant, can live at class level
    DIST_RE = re.compile(r"distance\[cm\]=(-?\d+)")

    def __init__(self, ports=None, baudrate=115200, base=30):
        # --- CONFIGURATION ---
        # Allow overriding from outside
        self.PORTS = ports or {
            "anchor_1": "/dev/ttyUSB0",
            "anchor_2": "/dev/ttyUSB1",
        }
        self.BAUDRATE = baudrate
        self.base = base  # distance between anchors in cm
        self.dist = None

        # Per‑instance state
        self.latest_ranges = {}
        self.data_lock = threading.Lock()
        self._threads = []
        self._stop_event = threading.Event()

    def reader(self, name, port):
        """Thread function: read one serial port and update latest_ranges."""
        try:
            ser = serial.Serial(port, self.BAUDRATE, timeout=1)
            print(f"[*] Started listening to {name} on {port}")
        except Exception as e:
            print(f"[!] Could not open {port}: {e}")
            return

        while not self._stop_event.is_set():
            try:
                line = ser.readline().decode(errors="ignore").strip()
                if not line:
                    continue

                m = self.DIST_RE.search(line)
                if m:
                    dist_cm = int(m.group(1))
                    with self.data_lock:
                        self.latest_ranges[name] = {
                            "time": datetime.now().strftime("%H:%M:%S"),
                            "dist": dist_cm,
                            "raw": line,
                        }
            except Exception as e:
                print(f"[!] Error reading {name}: {e}")
                break

        ser.close()
        print(f"[*] Stopped listening to {name}")

    def start_readers(self):
        """Spawn reader threads for all configured ports."""
        for name, port in self.PORTS.items():
            t = threading.Thread(
                target=self.reader,
                args=(name, port),
                daemon=True
            )
            t.start()
            self._threads.append(t)

    def stop(self):
        """Signal threads to stop and wait for them."""
        self._stop_event.set()
        for t in self._threads:
            t.join(timeout=1.0)

    def run_monitor(self):
        """Main monitoring loop: prints distances and triangulated X/Y."""
        self.start_readers()

        print("--- UWB Distance Monitor ---")
        print("Press Ctrl+C to stop.\n")

        try:
            while True:
                print(f"\r[{datetime.now().strftime('%H:%M:%S')}] Monitoring...", end="")

                with self.data_lock:
                    if len(self.latest_ranges) >= 2:
                        print("\n" + "-" * 50)
                        (name1, data1), (name2, data2) = list(self.latest_ranges.items())[:2]

                        status1 = "OK" if data1["dist"] > 0 else "INVALID/NEG"
                        print(
                            f"{name1.upper():<10} | Dist: {data1['dist']:>4} cm | "
                            f"Status: {status1:<10} | Last Update: {data1['time']}"
                        )

                        status2 = "OK" if data2["dist"] > 0 else "INVALID/NEG"
                        print(
                            f"{name2.upper():<10} | Dist: {data2['dist']:>4} cm | "
                            f"Status: {status2:<10} | Last Update: {data2['time']}"
                        )

                        # Absolute distance triangulation
                        d1 = data1["dist"]
                        d2 = data2["dist"]
                        base = self.base

                        x = (d1**2 - d2**2 + base**2) / (2 * base)
                        y = math.sqrt(abs(d1**2 - x**2))

                        x_center = x - base / 2.0
                        y_center = y
                        r_center = (math.sqrt(x_center**2 + y_center**2)) / 100 ###turn to m as well

                        print(f"Target is at X: {x:.2f} cm, Y: {y:.2f} cm")
                    
                        if len(q) < 11:
                            q.append(r_center)
                            print(f"Waiting for more values...")
                        else:
                            q.pop(0)
                            q.append(r_center)
                            self.dist= sum(q)/len(q)
                            print(f"Target (center frame) {self.dist:.2f}m")

                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\nStopping monitor...")
        finally:
            self.stop()





##########################3claass to dtereming wht to do with dat input from lidar viewer

class ObstacleDetection(Node):
    def __init__(self, lidar_viewer, following_dist):
        self.lidar = lidar_viewer
        self.follow_dist = following_dist
        self.obstacle_detected_left = False
        self.obstacle_detected_right = False
        self.obstacle_detected_front = False
        super().__init__('param_controller')
        # Create a client for the SetParameters service of the Go2 node
        self.cli = self.create_client(SetParameters, '/go2_driver_node/set_parameters')
        while not self.cli.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('Waiting for /go2_driver_node/set_parameters service...')
        
    #detectinh with state machine    
    def detect_obstacle(self):
        #rclpy.spin_once(self.lidar, timeout_sec=0.05) ##have to call self.lidar to get the new value for min_dist
        global state
        self.obstacle_detected_left = False
        self.obstacle_detected_right = False
       
        # use the atan2 to figure out if the obstacle is on thr right or left side
        # alse used for the maxc point to determine which way to turn if obstacle is right in front
        #####replacing angle with constant y values
        if self.lidar.min_dist < OBSTACLE_DIST: 
            print(self.lidar.min_dist)
            state = TURNING
            #cur_angle = math.atan2(self.lidar.y, self.lidar.x)
            #if cur_angle > 0.2:
            if self.lidar.y < 0.12 and self.lidar.y >=0:
                self.obstacle_detected_left = True
            #elif cur_angle < -0.2:     
            elif self.lidar.y > -0.16 and self.lidar.y < 0:
                self.obstacle_detected_right = True
            else: #obstacle is in front, decide to turn left or right
                #cur_angle_max = math.atan2(self.lidar.y_max, self.lidar.x_max) # angle of furthest point
                #if cur_angle_max > 0.2:
                if self.lidar.y_max <= 0:
                    self.obstacle_detected_right = True
                else:
                    self.obstacle_detected_left = True
        elif self.follow_dist.dist < 1.25: 
            if state != STOPPED_SAFE and state != FORWARD_SAFE:
                state = FORWARD
        elif self.follow_dist.dist < 0.2:
            state = STOPPED


#########################lidar viewer class to read sensor values output information to other clases

class LidarViewer(Node):
    def __init__(self):
        super().__init__('closest_point_checker')
        #initialize variables here when using it in other classes
        self.min_dist = float('inf')#min dist to detect object
        self.max_dist = -float('inf')#max dist to find availabl path to turn ##make sure its negative inf
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
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.best_safe_angle = 0.0

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
        self.subscription
    
    def pointcloud_callback(self, msg):
        #need to recall these to reset the variables for the distance checks, else it will be the same min and max foprever 
        self.min_dist = float('inf')#min dist to detect object
        self.max_dist = -float('inf')#max dist to find availabl path to turn
        self.x = float('inf')
        self.y = float('inf')
        self.x_max = float('inf')
        self.y_max = float('inf')
        try:
            transform = self.tf_buffer.lookup_transform(
                'base_link',              # target frame
                msg.header.frame_id,      # source frame: odom
                rclpy.time.Time(),
                timeout=rclpy.duration.Duration(seconds=0.1)
            )
        except Exception as e:
            self.get_logger().warn(f"TF transform failed: {e}")
            return
        
        # Transform into base_link
        cloud = do_transform_cloud(msg, transform)   #converting point cloud data into xyz coordinates
        obstacle_detected = False

        bins = 21
        angle_min = -math.radians(45)
        angle_max = math.radians(45)

        bin_amount = [0.0001] * bins
        bin_width = (angle_max - angle_min) / bins

        points = pc2.read_points(cloud, field_names=('x', 'y', 'z'), skip_nans=True)
        #min_dist = float('inf')
        closest_point = None

        for x, y, z in points:

            if x <= 0:
                continue  # keep only objects in front

            
            angle_lim = math.radians(45) #30 deg range of viewing in front
            # if (abs(math.atan2(y,x))) > angle_lim :
            #     continue
            is_in_path = (-0.16 <= y <= 0.12)
            is_in_vision = (-1.0 <= y <= 1.0) # Allow seeing 1m to each side for pathfinding

            if not is_in_vision:
                continue

            if z <= -0.1 or z >=0.1 :
                continue #ignnores the detection of floor, can be adjusted

            if self.angle_match == False:
                 self.target_angle = math.atan2(y, x)
                 self.cur_angle = math.atan2(y, x)

            #self.target_angle = math.atan2(y, x)
            
            if self.target_angle < angle_min or self.target_angle > angle_max:
                continue

            bin_index = int((self.target_angle - angle_min) / bin_width)
            bin_index = min(max(bin_index, 0), bins - 1)
            
            

            dist = math.sqrt(x*x + y*y + z*z) - 0.32
            bin_amount[bin_index] += 1.0 / max(dist, 0.1)
            
            
            if dist < self.min_dist:
                self.min_dist = dist####seems like the 0.32 is detected even when touching the lidar
                closest_point = (x, y, z)
                self.x = closest_point[0]   ### for some reason this is not the same as x??? using this to extract the correct value
                self.y = closest_point[1]
                # z_val = closest_point[2]
                
            if dist > self.max_dist:
                furthest_point = (x, y, z)
                self.max_dist = dist
                self.x_max = furthest_point[0]
                self.y_max = furthest_point[1] #point of farthest obstacle ### may need to turn into avrage to get more accurate values

        # Find the minimum density value
        min_density = min(bin_amount)

        # Find all bins that share this minimum value (likely all the empty ones)
        candidate_indices = [i for i, val in enumerate(bin_amount) if val == min_density]

        # Pick the candidate closest to the center (bins // 2)
        # This prevents the robot from choosing index 0 just because it's the first empty bin
        center_idx = bins // 2
        least_dense_index = min(candidate_indices, key=lambda x: abs(x - center_idx))

        # Calculate best_safe_angle
        best_angle = angle_min + (least_dense_index + 0.5) * bin_width
        self.best_safe_angle = best_angle

        current_time = time.time()
        if current_time - self.last_update_time >= 4.0:
            self.delayed_angle = self.cur_angle
            self.last_update_time = current_time
            self.get_logger().info(f"--- 5s Snapshot: Updated delayed_angle to {self.delayed_angle:.2f} ---")



########################go2 mover class to move the robot

class Go2Mover(Node):
    def __init__(self, obs_det):
        super().__init__('go2_mover')
        self.publisher_ = self.create_publisher(Twist, 'cmd_vel_out', 10) #publisher is for output i think; so output twist velocity of 10
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
        #end_time = self.get_clock().now().nanoseconds / 1e9 + duration
        msg = Twist()
        
        global state, turning_start

        while rclpy.ok():# and self.get_clock().now().nanoseconds / 1e9 < end_time:
            time.sleep(0.01)

            rclpy.spin_once(self.obs.lidar, timeout_sec=0.01)
            self.obs.detect_obstacle() ##run this function to get new value for obstacle_detected
            print("State: ", state)

            if state == FORWARD:

                # if self.obs.obstacle_detected_left == True or self.obs.obstacle_detected_right == True:
                #     state = TURNING
                #     self.turn_end_time = None
                # else:
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
                    # Stop as soon as we are pointed in the right direction
                    msg.angular.z = 0.0
                    self.publisher_.publish(msg) #Immediate
                    print("Min Distance: ", self.obs.lidar.min_dist)
                    if OBSTACLE_DIST < self.obs.lidar.min_dist:
                        self.get_logger().info("Clear! Moving Forward.")
                        self.locked_angle = None
                        state = FORWARD
                    else:
                        self.locked_angle = None
                        state = STOPPED
                else:
                    msg.angular.z = error *1.5

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
                    # Stop as soon as we are pointed in the right direction
                    msg.angular.z = 0.0
                    self.publisher_.publish(msg) #Immediate
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



    #asyncio.run(sit_down())

    print("Moving on...")

    rclpy.init(args=args)
    lidar = LidarViewer()
    follower = Following()
    obs_det = ObstacleDetection(lidar, follower)
    mover = Go2Mover(obs_det)
    
    executor = MultiThreadedExecutor()
    executor.add_node(lidar)
    executor.add_node(follower)
    executor.add_node(obs_det)
    executor.add_node(mover)

    try:
        #param.set_obstacle_avoidance(False)
        # Step forward
        import threading
        move_thread = threading.Thread(target=mover.move, daemon=True)
        move_thread.start()
        executor.spin()
        # Old code below
        # mover.get_logger().info('Moving forward...')
        # mover.move()
        # Old code ends
        #mover.move(linear_x = 0.0, linear_y=0.0, angular_z = 1.5, duration=1.375)  code for 90 deg turn

    except KeyboardInterrupt:
        #making sure the dog stops moving before shutdown
        state = STOPPED  #redudunt call since there is already a keyyboard interupt in the move
        #param.set_obstacle_avoidance(False)
        print("Keyboard Interrupt")
    
    
    #param.set_obstacle_avoidance(False)
    
    mover.get_logger().info('Movement demo complete.')

    mover.destroy_node()
    obs_det.destroy_node()
    lidar.destroy_node()
    

    if rclpy.ok():
        rclpy.shutdown()

if __name__ == '__main__':
    main()

