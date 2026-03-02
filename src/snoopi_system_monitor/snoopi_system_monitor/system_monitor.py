"""
Publishes RPi5 system stats to /snoopi/system_stats as JSON.
Reads CPU load via psutil, temperature from /sys/class/thermal,
and fan status from /sys/class/thermal/cooling_device0.
"""
import json
from pathlib import Path

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

try:
    import psutil
except ImportError:
    psutil = None


class SystemMonitor(Node):
    def __init__(self):
        super().__init__('system_monitor')
        self._pub = self.create_publisher(String, '/snoopi/system_stats', 10)
        self.create_timer(2.0, self._publish)
        self.get_logger().info('System monitor started')

    def _read_temp(self) -> float:
        try:
            raw = Path('/sys/class/thermal/thermal_zone0/temp').read_text().strip()
            return int(raw) / 1000.0
        except Exception:
            return 0.0

    def _read_fan(self) -> bool:
        try:
            raw = Path('/sys/class/thermal/cooling_device0/cur_state').read_text().strip()
            return int(raw) > 0
        except Exception:
            return False

    def _publish(self):
        cpu = psutil.cpu_percent(interval=None) if psutil else 0.0
        msg = String()
        msg.data = json.dumps({
            'cpu_percent': cpu,
            'temperature': self._read_temp(),
            'fan_on': self._read_fan(),
        })
        self._pub.publish(msg)


def main():
    rclpy.init()
    node = SystemMonitor()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
