#!/usr/bin/env python3
"""
basic_mover.py — Interactive R&D tool for Go2 Air movement.

This script lets you send individual movement commands from the terminal
and see how they affect the robot via odometry feedback. Use it to build
intuition about how Twist messages map to real robot motion.

=== How the Go2 Air moves ===

The robot accepts velocity commands on the /cmd_vel_out topic using
geometry_msgs/Twist. A Twist message has 6 fields, but only 3 matter
for the Go2:

  linear.x  → forward (+) / backward (-) speed in meters/second
  linear.y  → left (+) / right (-) strafe speed in meters/second
  angular.z → counter-clockwise (+) / clockwise (-) rotation in radians/second

The other fields (linear.z, angular.x, angular.y) are ignored — the
robot can't fly or tilt on command.

Velocity commands must be sent continuously (this script sends at 20Hz).
If you stop publishing, the robot will coast to a stop.

=== Sit / Stand ===

These are NOT velocity commands. They use a separate WebRTC API:
  - api_id 1004 = stand up
  - api_id 1005 = sit down
Published to /webrtc_req as go2_interfaces/WebRtcReq.

=== Odometry ===

The robot reports its estimated position and orientation on /odom.
Position is (x, y) in meters from where the robot was when the driver
started. Orientation is a quaternion, which we convert to yaw (heading
angle in degrees). Yaw=0 is the starting direction, positive=left turn.

Usage (inside snoopi-ros2 container):
  ros2 run snoopi_control basic_mover

Requires: go2_driver_node to be running.
"""

import math
import time
import threading

import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from go2_interfaces.msg import WebRtcReq

# ------------------------------------------------------------------ #
#  Safety limits — project.md says max 0.5 m/s                       #
# ------------------------------------------------------------------ #
MAX_LINEAR_SPEED = 0.5    # m/s — do not exceed
MAX_ANGULAR_SPEED = 1.0   # rad/s
DEFAULT_SPEED = 0.3       # m/s — conservative starting point
DEFAULT_ANGULAR = 0.5     # rad/s
DEFAULT_DURATION = 2.0    # seconds


def clamp(val, lo, hi):
    """Clamp a value to [lo, hi]."""
    return max(lo, min(hi, val))


class BasicMover(Node):
    """ROS2 node for interactive Go2 movement testing."""

    def __init__(self):
        super().__init__('basic_mover')

        # --- Publishers ---
        # /cmd_vel_out is where go2_ros2_sdk reads velocity commands
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel_out', 10)
        # /webrtc_req is where go2_ros2_sdk reads mode commands (sit/stand)
        self.webrtc_pub = self.create_publisher(WebRtcReq, '/webrtc_req', 10)

        # --- Subscribers ---
        # /odom gives us the robot's position and orientation estimate
        self.create_subscription(Odometry, '/odom', self._odom_callback, 10)

        # --- Odometry state ---
        self.odom_x = 0.0
        self.odom_y = 0.0
        self.odom_yaw = 0.0  # radians
        self.odom_received = False

        self.get_logger().info('BasicMover node started')

    def _odom_callback(self, msg):
        """
        Extract position and yaw from odometry.

        The orientation comes as a quaternion (x, y, z, w). For a ground
        robot we only care about yaw (rotation around the vertical axis).
        The formula below extracts yaw from the quaternion.
        """
        self.odom_x = msg.pose.pose.position.x
        self.odom_y = msg.pose.pose.position.y

        q = msg.pose.pose.orientation
        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        self.odom_yaw = math.atan2(siny_cosp, cosy_cosp)
        self.odom_received = True

    # ------------------------------------------------------------------ #
    #  Movement commands                                                  #
    # ------------------------------------------------------------------ #

    def send_velocity(self, linear_x=0.0, linear_y=0.0, angular_z=0.0):
        """Publish a single Twist message to /cmd_vel_out."""
        msg = Twist()
        msg.linear.x = float(linear_x)
        msg.linear.y = float(linear_y)
        msg.angular.z = float(angular_z)
        self.cmd_vel_pub.publish(msg)

    def stop(self):
        """Send zero velocity — robot will stop moving."""
        self.send_velocity(0.0, 0.0, 0.0)

    def move_timed(self, linear_x=0.0, linear_y=0.0, angular_z=0.0, duration=2.0):
        """
        Send velocity at 20Hz for `duration` seconds, then stop.
        Prints odometry before and after so you can measure the effect.
        """
        # Snapshot starting pose
        start_x = self.odom_x
        start_y = self.odom_y
        start_yaw = self.odom_yaw

        print(f"\n  Command: linear.x={linear_x:.2f}  linear.y={linear_y:.2f}  angular.z={angular_z:.2f}")
        print(f"  Duration: {duration:.1f}s")
        print(f"  Start:  x={start_x:.3f}  y={start_y:.3f}  yaw={math.degrees(start_yaw):.1f} deg")

        # Publish velocity at 20Hz
        rate_hz = 20
        iterations = int(duration * rate_hz)
        for _ in range(iterations):
            if not rclpy.ok():
                break
            self.send_velocity(linear_x, linear_y, angular_z)
            time.sleep(1.0 / rate_hz)

        # Stop the robot
        self.stop()
        time.sleep(0.2)  # brief pause for final odom to arrive

        # Report what happened
        end_x = self.odom_x
        end_y = self.odom_y
        end_yaw = self.odom_yaw

        dist = math.sqrt((end_x - start_x) ** 2 + (end_y - start_y) ** 2)
        dyaw = math.degrees(end_yaw - start_yaw)
        dyaw = (dyaw + 180) % 360 - 180  # normalize to [-180, 180]

        print(f"  End:    x={end_x:.3f}  y={end_y:.3f}  yaw={math.degrees(end_yaw):.1f} deg")
        print(f"  Result: moved {dist:.3f}m, turned {dyaw:.1f} deg")

    # ------------------------------------------------------------------ #
    #  Sit / Stand                                                       #
    # ------------------------------------------------------------------ #

    def sit(self):
        """Command the robot to sit down."""
        msg = WebRtcReq()
        msg.api_id = 1005  # 1005 = sit
        msg.topic = 'rt/api/sport/request'
        msg.parameter = ''
        msg.priority = 0
        self.webrtc_pub.publish(msg)
        print("  Sent SIT (api_id=1005)")

    def stand(self):
        """Command the robot to stand up."""
        msg = WebRtcReq()
        msg.api_id = 1004  # 1004 = stand
        msg.topic = 'rt/api/sport/request'
        msg.parameter = ''
        msg.priority = 0
        self.webrtc_pub.publish(msg)
        print("  Sent STAND (api_id=1004)")

    def print_status(self):
        """Print current odometry reading."""
        if not self.odom_received:
            print("  No odometry data yet — is go2_driver_node running?")
            return
        print(f"  Position: x={self.odom_x:.3f}  y={self.odom_y:.3f}")
        print(f"  Yaw: {math.degrees(self.odom_yaw):.1f} deg ({self.odom_yaw:.3f} rad)")


# ------------------------------------------------------------------ #
#  Help text                                                          #
# ------------------------------------------------------------------ #

HELP_TEXT = """
=== Go2 Air — Basic Mover R&D ===

Movement (optional args: speed, duration — defaults: 0.3 m/s, 2.0s):
  forward  [speed] [dur]   walk forward      (linear.x > 0)
  backward [speed] [dur]   walk backward     (linear.x < 0)
  left     [speed] [dur]   strafe left       (linear.y > 0)
  right    [speed] [dur]   strafe right      (linear.y < 0)
  rotl     [speed] [dur]   rotate CCW/left   (angular.z > 0)
  rotr     [speed] [dur]   rotate CW/right   (angular.z < 0)

Raw Twist (set exact values):
  twist <lx> <ly> <az> [dur]   e.g. "twist 0.2 0.0 0.3 3"

Shortcuts: f=forward, b=backward, l=left, r=right, rl=rotl, rr=rotr

Robot state:
  sit        sit down
  stand      stand up
  stop       zero velocity immediately
  status     print current position and yaw from odometry

Other:
  help       show this help
  quit       stop robot and exit

Safety: linear speed capped at 0.5 m/s, angular at 1.0 rad/s
"""


# ------------------------------------------------------------------ #
#  Interactive command loop                                           #
# ------------------------------------------------------------------ #

def input_loop(node):
    """Read commands from terminal and execute them on the robot."""
    print(HELP_TEXT)

    while rclpy.ok():
        try:
            raw = input("\nsnoopi> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nShutting down...")
            node.stop()
            return

        if not raw:
            continue

        parts = raw.split()
        cmd = parts[0].lower()

        try:
            if cmd == 'help':
                print(HELP_TEXT)

            elif cmd in ('quit', 'exit', 'q'):
                print("Stopping robot and exiting...")
                node.stop()
                return

            elif cmd == 'stop':
                node.stop()
                print("  Velocity zeroed")

            elif cmd == 'sit':
                node.sit()

            elif cmd == 'stand':
                node.stand()

            elif cmd == 'status':
                node.print_status()

            elif cmd in ('forward', 'fw', 'f'):
                speed = clamp(float(parts[1]), 0, MAX_LINEAR_SPEED) if len(parts) > 1 else DEFAULT_SPEED
                dur = float(parts[2]) if len(parts) > 2 else DEFAULT_DURATION
                node.move_timed(linear_x=speed, duration=dur)

            elif cmd in ('backward', 'bw', 'b'):
                speed = clamp(float(parts[1]), 0, MAX_LINEAR_SPEED) if len(parts) > 1 else DEFAULT_SPEED
                dur = float(parts[2]) if len(parts) > 2 else DEFAULT_DURATION
                node.move_timed(linear_x=-speed, duration=dur)

            elif cmd in ('left', 'l'):
                speed = clamp(float(parts[1]), 0, MAX_LINEAR_SPEED) if len(parts) > 1 else DEFAULT_SPEED
                dur = float(parts[2]) if len(parts) > 2 else DEFAULT_DURATION
                node.move_timed(linear_y=speed, duration=dur)

            elif cmd in ('right', 'r'):
                speed = clamp(float(parts[1]), 0, MAX_LINEAR_SPEED) if len(parts) > 1 else DEFAULT_SPEED
                dur = float(parts[2]) if len(parts) > 2 else DEFAULT_DURATION
                node.move_timed(linear_y=-speed, duration=dur)

            elif cmd in ('rotl', 'rl'):
                speed = clamp(float(parts[1]), 0, MAX_ANGULAR_SPEED) if len(parts) > 1 else DEFAULT_ANGULAR
                dur = float(parts[2]) if len(parts) > 2 else DEFAULT_DURATION
                node.move_timed(angular_z=speed, duration=dur)

            elif cmd in ('rotr', 'rr'):
                speed = clamp(float(parts[1]), 0, MAX_ANGULAR_SPEED) if len(parts) > 1 else DEFAULT_ANGULAR
                dur = float(parts[2]) if len(parts) > 2 else DEFAULT_DURATION
                node.move_timed(angular_z=-speed, duration=dur)

            elif cmd == 'twist':
                if len(parts) < 4:
                    print("  Usage: twist <linear_x> <linear_y> <angular_z> [duration]")
                    print("  Example: twist 0.2 0.0 0.3 3")
                    continue
                lx = clamp(float(parts[1]), -MAX_LINEAR_SPEED, MAX_LINEAR_SPEED)
                ly = clamp(float(parts[2]), -MAX_LINEAR_SPEED, MAX_LINEAR_SPEED)
                az = clamp(float(parts[3]), -MAX_ANGULAR_SPEED, MAX_ANGULAR_SPEED)
                dur = float(parts[4]) if len(parts) > 4 else DEFAULT_DURATION
                node.move_timed(linear_x=lx, linear_y=ly, angular_z=az, duration=dur)

            else:
                print(f"  Unknown command: '{cmd}' — type 'help' for commands")

        except (ValueError, IndexError) as e:
            print(f"  Bad input: {e} — type 'help' for usage")


# ------------------------------------------------------------------ #
#  Entry point                                                        #
# ------------------------------------------------------------------ #

def main(args=None):
    rclpy.init(args=args)
    node = BasicMover()

    # Run ROS2 callbacks (odom) in a background thread
    # so the main thread can read terminal input
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    spin_thread = threading.Thread(target=executor.spin, daemon=True)
    spin_thread.start()

    try:
        input_loop(node)
    except KeyboardInterrupt:
        print("\nKeyboard interrupt — stopping robot")
        node.stop()
    finally:
        executor.shutdown()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
