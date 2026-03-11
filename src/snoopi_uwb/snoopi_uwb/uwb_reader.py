#!/usr/bin/env python3
"""UWB anchor reader node.

Reads distance data from two USB-connected UWB anchors via serial,
publishes combined status + distance as JSON to /snoopi/uwb_status.
"""

import json
import math
import re
import threading
import time
from collections import deque
from datetime import datetime

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

import serial

DIST_RE = re.compile(r"distance\[cm\]=(-?\d+)")

ANCHOR_PORTS = {
    "anchor_1": "/dev/ttyACM0",
    "anchor_2": "/dev/ttyACM1",
}
BAUDRATE = 115200
BASE_CM = 30  # distance between anchors in cm
PUBLISH_INTERVAL = 0.5  # seconds
STALE_TIMEOUT = 3.0  # seconds before marking tag as not detected
RETRY_INTERVAL = 2.0  # seconds between reconnection attempts
ROLLING_WINDOW = 10


class AnchorState:
    """Tracks state for a single UWB anchor."""

    def __init__(self, name: str, port: str):
        self.name = name
        self.port = port
        self.connected = False
        self.tag_detected = False
        self.distance_cm = -1
        self.last_reading_time = 0.0
        self.lock = threading.Lock()


class UwbReaderNode(Node):
    def __init__(self):
        super().__init__('uwb_reader')
        self.publisher_ = self.create_publisher(String, '/snoopi/uwb_status', 10)

        self.anchors = {
            name: AnchorState(name, port)
            for name, port in ANCHOR_PORTS.items()
        }

        self._stop_event = threading.Event()
        self._rolling = deque(maxlen=ROLLING_WINDOW)
        self._threads = []

        # Start a reader thread per anchor
        for anchor in self.anchors.values():
            t = threading.Thread(target=self._reader_loop, args=(anchor,), daemon=True)
            t.start()
            self._threads.append(t)

        # Publish timer
        self.create_timer(PUBLISH_INTERVAL, self._publish_status)

    def _reader_loop(self, anchor: AnchorState):
        """Continuously read serial for one anchor, reconnecting on failure."""
        while not self._stop_event.is_set():
            ser = None
            try:
                ser = serial.Serial(anchor.port, BAUDRATE, timeout=1)
                with anchor.lock:
                    anchor.connected = True
                self.get_logger().info(f'Opened {anchor.name} on {anchor.port}')

                while not self._stop_event.is_set():
                    line = ser.readline().decode(errors='ignore').strip()
                    if not line:
                        continue
                    m = DIST_RE.search(line)
                    if m:
                        dist_cm = int(m.group(1))
                        with anchor.lock:
                            anchor.distance_cm = dist_cm
                            anchor.last_reading_time = time.monotonic()
                            anchor.tag_detected = dist_cm > 0

            except Exception as e:
                self.get_logger().warn(f'{anchor.name} ({anchor.port}): {e}')
            finally:
                with anchor.lock:
                    anchor.connected = False
                    anchor.tag_detected = False
                if ser and ser.is_open:
                    ser.close()

            if not self._stop_event.is_set():
                time.sleep(RETRY_INTERVAL)

    def _publish_status(self):
        now = time.monotonic()

        # Check stale data
        for anchor in self.anchors.values():
            with anchor.lock:
                if anchor.tag_detected and (now - anchor.last_reading_time) > STALE_TIMEOUT:
                    anchor.tag_detected = False

        a1 = self.anchors['anchor_1']
        a2 = self.anchors['anchor_2']

        with a1.lock:
            a1_connected = a1.connected
            a1_tag = a1.tag_detected
            a1_dist_cm = a1.distance_cm if a1.tag_detected else -1
        with a2.lock:
            a2_connected = a2.connected
            a2_tag = a2.tag_detected
            a2_dist_cm = a2.distance_cm if a2.tag_detected else -1

        # Triangulation
        tri_dist = -1.0
        if a1_tag and a2_tag and a1_dist_cm > 0 and a2_dist_cm > 0:
            d1 = a1_dist_cm
            d2 = a2_dist_cm
            base = BASE_CM
            x = (d1**2 - d2**2 + base**2) / (2 * base)
            y_sq = d1**2 - x**2
            y = math.sqrt(abs(y_sq))
            x_center = x - base / 2.0
            r_center = math.sqrt(x_center**2 + y**2) / 100.0  # cm → m
            self._rolling.append(r_center)
            if len(self._rolling) >= 3:
                tri_dist = sum(self._rolling) / len(self._rolling)
        else:
            self._rolling.clear()

        status = {
            'anchor_1_connected': a1_connected,
            'anchor_2_connected': a2_connected,
            'anchor_1_tag_detected': a1_tag,
            'anchor_2_tag_detected': a2_tag,
            'anchor_1_distance_m': round(a1_dist_cm / 100.0, 2) if a1_dist_cm > 0 else -1,
            'anchor_2_distance_m': round(a2_dist_cm / 100.0, 2) if a2_dist_cm > 0 else -1,
            'triangulated_distance_m': round(tri_dist, 2) if tri_dist > 0 else -1,
        }

        msg = String()
        msg.data = json.dumps(status)
        self.publisher_.publish(msg)

        # Terminal log
        ts = datetime.now().strftime('%H:%M:%S')
        a1_str = f'{a1_dist_cm / 100:.2f}m (OK)' if a1_tag and a1_dist_cm > 0 else '--- (DISCONNECTED)' if not a1_connected else '--- (NO TAG)'
        a2_str = f'{a2_dist_cm / 100:.2f}m (OK)' if a2_tag and a2_dist_cm > 0 else '--- (DISCONNECTED)' if not a2_connected else '--- (NO TAG)'
        tri_str = f'{tri_dist:.2f}m' if tri_dist > 0 else '---'
        tags = (1 if a1_tag else 0) + (1 if a2_tag else 0)
        self.get_logger().info(
            f'[UWB {ts}] A1: {a1_str} | A2: {a2_str} | Dist: {tri_str} | Tags: {tags}/2'
        )

    def destroy_node(self):
        self._stop_event.set()
        for t in self._threads:
            t.join(timeout=2.0)
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = UwbReaderNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
