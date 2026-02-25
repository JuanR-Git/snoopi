#!/bin/bash
set -e

# Layer 1: ROS2 base
source /opt/ros/humble/setup.bash

# Layer 2: go2_ros2_sdk workspace (baked into image)
source /opt/go2_ws/install/setup.bash

# Layer 3: user workspace (volume-mounted src/, only source if built)
if [ -f /ros2_ws/install/setup.bash ]; then
    source /ros2_ws/install/setup.bash
fi

exec "$@"
