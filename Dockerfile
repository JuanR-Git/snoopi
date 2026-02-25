# TODO: pin this to a digest after first successful build on the Pi.
# Run: docker inspect --format='{{index .RepoDigests 0}}' osrf/ros:humble-ros-base
# Then replace with: FROM osrf/ros:humble-ros-base@sha256:<digest>
FROM osrf/ros:humble-ros-base

# Suppress interactive prompts during apt installs
ENV DEBIAN_FRONTEND=noninteractive

# Layer: system build tools and utilities
RUN apt-get update && apt-get install -y \
    clang \
    portaudio19-dev \
    python3-pip \
    python3-colcon-common-extensions \
    python3-rosdep \
    git \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Layer: ROS2 packages
# Each package installs into /opt/ros/humble/ alongside the base install
RUN apt-get update && apt-get install -y \
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

# Layer: clone go2_ros2_sdk into its own workspace at /opt/go2_ws/
# This workspace is separate from /ros2_ws/ (your nodes) so the SDK
# is pre-compiled in the image and never rebuilt during development.
WORKDIR /opt/go2_ws
RUN mkdir src && \
    git clone https://github.com/abizovnuralem/go2_ros2_sdk.git src/go2_ros2_sdk

# Layer: SDK Python dependencies (WebRTC, async libs, etc.)
RUN pip3 install --no-cache-dir \
    -r /opt/go2_ws/src/go2_ros2_sdk/requirements.txt

# Layer: build the SDK workspace with colcon
# This is the slow step (~15-25 min on ARM64 first time).
# source the ROS2 base first so colcon knows about ROS2 message types.
RUN /bin/bash -c "source /opt/ros/humble/setup.bash && \
    colcon build \
    --symlink-install \
    --cmake-args -DCMAKE_BUILD_TYPE=Release"

# Create the user workspace mount point
# ./src on the host is mounted here at runtime via docker-compose volumes
RUN mkdir -p /ros2_ws/src

# Copy entrypoint script
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set ROS middleware to CycloneDDS
# CYCLONEDDS_URI points to the config file (volume-mounted at runtime)
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
# CYCLONEDDS_URI: volume-mounted at runtime via docker-compose.
# Running this image directly with docker run (without the volume) will cause
# CycloneDDS to use defaults rather than this config — use docker-compose instead.
ENV CYCLONEDDS_URI=/ros2_ws/cyclonedds.xml

WORKDIR /ros2_ws

ENTRYPOINT ["/entrypoint.sh"]
# Default: keep container alive so you can docker exec into it
CMD ["tail", "-f", "/dev/null"]
