"""
Command bridge: translates dashboard string commands to robot actions.

Subscribes to /snoopi/command (std_msgs/String) from the dashboard via rosbridge.
Translates commands to:
  - "estop" -> publishes zero velocity to /cmd_vel (immediate safety stop)
  - "sit"   -> calls go2_ros2_sdk sit interface (TBD -- see TODO below)
  - "stand" -> calls go2_ros2_sdk stand interface (TBD -- see TODO below)
"""
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from geometry_msgs.msg import Twist


class CommandBridge(Node):
    def __init__(self):
        super().__init__('command_bridge')

        # Subscribe to dashboard commands (via rosbridge)
        self.create_subscription(String, '/snoopi/command', self._on_command, 10)

        # Publisher for emergency stop — zero velocity to /cmd_vel
        self._cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel_out', 10)

        self.get_logger().info('Command bridge started -- listening on /snoopi/command')

    def _on_command(self, msg: String):
        cmd = msg.data.strip().lower()
        self.get_logger().info(f'Received command: "{cmd}"')

        if cmd == 'estop':
            self._execute_estop()
        elif cmd == 'sit':
            self._execute_sit()
        elif cmd == 'stand':
            self._execute_stand()
        else:
            self.get_logger().warn(f'Unknown command: "{cmd}"')

    def _execute_estop(self):
        """Publish zero velocity to /cmd_vel -- works regardless of SDK interface."""
        stop = Twist()  # all fields default to 0.0
        self._cmd_vel_pub.publish(stop)
        self.get_logger().info('E-STOP: published zero velocity to /cmd_vel')

    def _execute_sit(self):
        """
        TODO: Wire to go2_ros2_sdk sit interface.

        STEPS TO COMPLETE IN LAB:
        1. Run: ros2 topic list
        2. Run: ros2 service list
        3. Find the sit/stand command interface
        4. Run: ros2 topic info <topic> -v  (or ros2 service info)
        5. Replace this TODO with the actual publish/service call

        Expected: the SDK may use a topic like /go2_state or a
        service for mode changes. Check the go2_ros2_sdk README.
        """
        self.get_logger().info('SIT command received -- SDK interface TBD (see TODO in source)')

    def _execute_stand(self):
        """
        TODO: Wire to go2_ros2_sdk stand interface.
        Same discovery steps as _execute_sit() above.
        """
        self.get_logger().info('STAND command received -- SDK interface TBD (see TODO in source)')


def main():
    rclpy.init()
    node = CommandBridge()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
