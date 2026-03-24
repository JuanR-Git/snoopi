"""
Command bridge: translates dashboard string commands to robot actions.

Subscribes to /snoopi/command (std_msgs/String) from the dashboard via rosbridge.
Translates commands to:
  - "estop" -> publishes zero velocity to /cmd_vel_out (immediate safety stop)
  - "sit"   -> publishes WebRtcReq with api_id=1005 to /webrtc_req
  - "stand" -> publishes WebRtcReq with api_id=1004 to /webrtc_req
"""
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from geometry_msgs.msg import Twist
from go2_interfaces.msg import WebRtcReq


class CommandBridge(Node):
    def __init__(self):
        super().__init__('command_bridge')

        # Subscribe to dashboard commands (via rosbridge)
        self.create_subscription(String, '/snoopi/command', self._on_command, 10)

        # Publisher for emergency stop — zero velocity to /cmd_vel_out
        self._cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel_out', 10)

        # Publisher for sit/stand via go2_ros2_sdk WebRTC interface
        self._webrtc_pub = self.create_publisher(WebRtcReq, '/webrtc_req', 10)

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
        """Publish zero velocity to /cmd_vel_out."""
        stop = Twist()  # all fields default to 0.0
        self._cmd_vel_pub.publish(stop)
        self.get_logger().info('E-STOP: published zero velocity to /cmd_vel_out')

    def _execute_sit(self):
        """Send sit command via WebRtcReq (api_id=1005)."""
        msg = WebRtcReq()
        msg.api_id = 1005
        msg.topic = 'rt/api/sport/request'
        msg.parameter = ''
        msg.priority = 0
        self._webrtc_pub.publish(msg)
        self.get_logger().info('SIT: published WebRtcReq api_id=1005')

    def _execute_stand(self):
        """Send stand command via WebRtcReq (api_id=1004)."""
        msg = WebRtcReq()
        msg.api_id = 1004
        msg.topic = 'rt/api/sport/request'
        msg.parameter = ''
        msg.priority = 0
        self._webrtc_pub.publish(msg)
        self.get_logger().info('STAND: published WebRtcReq api_id=1004')


def main():
    rclpy.init()
    node = CommandBridge()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
