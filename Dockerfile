# Base image: official ROS2 Humble on Ubuntu 22.04 (Jammy)
# Multi-arch manifest — Docker auto-pulls linux/arm64 on RPi5.
# After first successful build, pin to a digest for reproducibility:
#   docker inspect --format='{{index .RepoDigests 0}}' ros:humble-ros-base-jammy
#   Then: FROM ros:humble-ros-base-jammy@sha256:<digest>
FROM ros:humble-ros-base-jammy

# Suppress interactive prompts during apt installs
ENV DEBIAN_FRONTEND=noninteractive

# Layer 1: system tools not included in ros-base
# ros:humble-ros-base-jammy already provides: build-essential, git, curl,
# python3-colcon-common-extensions, python3-rosdep, python3-vcstool
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# Layer 2: ROS2 binary packages (pre-compiled for arm64 from packages.ros.org)
# These install into /opt/ros/humble/ alongside the base install.
# - navigation2 + nav2-bringup: autonomous navigation stack (path planning,
#   costmaps, obstacle avoidance, AMCL localization)
# - slam-toolbox: generates 2D occupancy grid maps from LiDAR during
#   teleoperation mapping phase (Milestone 4)
# - rosbridge-suite: WebSocket bridge between ROS2 and the React/FastAPI UI
# - rmw-cyclonedds-cpp: DDS middleware required by go2_ros2_sdk for
#   communicating with the Go2 Air over Ethernet
# - vision-msgs, image-tools: required dependencies of go2_ros2_sdk
# - teleop-twist-keyboard: manual robot driving for SLAM mapping
# - xacro, robot-state-publisher, joint-state-publisher: robot model (URDF)
#   publishing, needed by Nav2 for footprint and tf transforms
RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-humble-navigation2 \
    ros-humble-nav2-bringup \
    ros-humble-slam-toolbox \
    ros-humble-rosbridge-suite \
    ros-humble-rmw-cyclonedds-cpp \
    ros-humble-vision-msgs \
    ros-humble-image-tools \
    ros-humble-teleop-twist-keyboard \
    ros-humble-xacro \
    ros-humble-robot-state-publisher \
    ros-humble-joint-state-publisher \
    && rm -rf /var/lib/apt/lists/*

# Layer 3: clone go2_ros2_sdk into a dedicated workspace at /opt/go2_ws/
# Separate from /ros2_ws/ (your custom nodes) so the SDK is baked into the
# image once and never rebuilt during day-to-day development.
WORKDIR /opt/go2_ws
RUN mkdir src && \
    git clone --recursive https://github.com/abizovnuralem/go2_ros2_sdk.git src/go2_ros2_sdk

# Layer 4: SDK Python dependencies (WebRTC, MQTT, crypto, etc.)
# Uses our curated ARM64-compatible list instead of the SDK's full
# requirements.txt, which includes open3d (no arm64 wheel) and
# torch/torchvision (not needed for MVP). See docker/requirements-arm64.txt
# for the full exclusion rationale.
COPY docker/requirements-arm64.txt /tmp/requirements-arm64.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements-arm64.txt \
    && rm /tmp/requirements-arm64.txt

# Layer 5: build the SDK workspace with colcon
# --symlink-install: allows source edits without rebuild (dev convenience)
# CMAKE_BUILD_TYPE=Release: strips debug symbols, reduces image size
# --packages-skip: exclude packages not needed for MVP:
#   lidar_processor_cpp — requires pcl_ros; the SDK already publishes
#     LaserScan directly, which Nav2/SLAM Toolbox consume as-is
#   coco_detector — requires torch (excluded from ARM64 pip deps);
#     object detection is not in MVP scope
RUN /bin/bash -c "source /opt/ros/humble/setup.bash && \
    colcon build \
    --symlink-install \
    --packages-skip lidar_processor_cpp coco_detector \
    --cmake-args -DCMAKE_BUILD_TYPE=Release"

# Layer 6: patch SDK to publish battery/BMS data on /snoopi/battery
# The SDK receives bms_state in rt/lf/lowstate but discards it — this patch
# extracts it and publishes as a JSON String so the dashboard can display
# battery %, voltage, and temperature.  Rebuilds only go2_robot_sdk.
COPY docker/patches/ /tmp/patches/
RUN python3 /tmp/patches/add_battery_publisher.py && \
    /bin/bash -c "source /opt/ros/humble/setup.bash && \
    cd /opt/go2_ws && colcon build --symlink-install --packages-select go2_robot_sdk" && \
    rm -rf /tmp/patches/

# Create the user workspace mount point
# ./src on the host is volume-mounted here at runtime via docker-compose
RUN mkdir -p /ros2_ws/src

# Copy entrypoint script (sources ROS2 base, SDK, and user workspaces)
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Source ROS2 workspaces in .bashrc so interactive shells (docker exec)
# have ros2 commands available without manually sourcing.
# NOTE: Only source workspace setup files here — NOT the full entrypoint.
# The entrypoint launches services; .bashrc is for interactive shells only.
RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc && \
    echo "source /opt/go2_ws/install/setup.bash" >> /root/.bashrc && \
    echo '[ -f /ros2_ws/install/setup.bash ] && source /ros2_ws/install/setup.bash' >> /root/.bashrc

# Set CycloneDDS as the ROS2 middleware (required by go2_ros2_sdk)
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
# CYCLONEDDS_URI: points to the DDS config file, volume-mounted at runtime
# via docker-compose. Without the volume, CycloneDDS falls back to defaults.
ENV CYCLONEDDS_URI=/ros2_ws/cyclonedds.xml

WORKDIR /ros2_ws

ENTRYPOINT ["/entrypoint.sh"]
# Default: keep container alive for interactive use via docker exec
CMD ["tail", "-f", "/dev/null"]
