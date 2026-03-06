# Lab Setup Guide — Connecting Pi to Go2 Air

> **Purpose:** Step-by-step instructions for connecting the RPi5 to the Go2 Air
> robot in the lab and verifying the full telemetry pipeline.

---

## Placeholder Values

**Fill these in when you're in the lab.** All placeholders are marked with angle brackets.

| Placeholder | Expected Value | Actual Value |
|---|---|---|
| `<ROBOT_IP>` | `192.168.123.161` (from SDK docs) | __________ |
| `<ROBOT_SUBNET>` | `192.168.123.0/24` | __________ |
| `<PI_ROBOT_SUBNET_IP>` | `192.168.123.100` (pick any unused) | __________ |
| `<PI_ETH_INTERFACE>` | `eth0` or `enx...` (run `ip link show`) | __________ |
| `<PI_WIFI_IP>` | `192.168.0.41` (current home network) | __________ |

---

## Prerequisites

- RPi5 powered on and accessible via SSH over WiFi
- Go2 Air powered on (wait for startup sound to finish)
- Ethernet cable connecting Pi to Go2 Air
- Windows laptop on the same WiFi network as the Pi

---

## Step 1: Identify the Pi's Ethernet Interface

```bash
[PI] ip link show
```

Look for an interface that is NOT `lo` (loopback) or `wlan0` (WiFi). It will likely be `eth0` or `enxXXXXXX`. This is your `<PI_ETH_INTERFACE>`.

---

## Step 2: Configure Static IP on the Robot's Subnet

The Go2 Air uses the `192.168.123.0/24` subnet. The Pi needs an IP on this subnet to communicate.

```bash
[PI] sudo ip addr add <PI_ROBOT_SUBNET_IP>/24 dev <PI_ETH_INTERFACE>
[PI] sudo ip link set <PI_ETH_INTERFACE> up
```

**Example (with expected values):**
```bash
[PI] sudo ip addr add 192.168.123.100/24 dev eth0
[PI] sudo ip link set eth0 up
```

> **Note:** This is temporary — it resets on reboot. To make it permanent,
> create a netplan config (documented at the end of this guide).

---

## Step 3: Verify Connectivity

```bash
[PI] ping <ROBOT_IP> -c 3
```

**Expected:** 3 replies with low latency (<1ms for Ethernet).

**If ping fails:**
- Check cable is plugged in on both ends
- Run `ip addr show <PI_ETH_INTERFACE>` — confirm IP is assigned
- Try `arp -a` to see what devices are on the network
- The robot IP might differ from expected — check go2_ros2_sdk docs

---

## Step 4: Update CycloneDDS Peer (if needed)

If `<ROBOT_IP>` differs from `192.168.123.161`, edit the DDS config:

```bash
[PI] nano ~/snoopi/docker/cyclonedds.xml
```

Change the peer address to match the actual robot IP:
```xml
<Peer Address="<ROBOT_IP>"/>
```

---

## Step 5: Rebuild and Start the Container

```bash
[PI] cd ~/snoopi
[PI] git pull
[PI] docker compose build
[PI] docker compose up -d
```

Wait 30-60 seconds for all services to start, then check logs:

```bash
[PI] docker logs snoopi-ros2
```

**Expected:** Messages showing rosbridge, system_monitor, command_bridge, and go2_sdk all starting. The SDK may show errors if the robot connection isn't established yet — that's normal, it will retry.

---

## Step 6: Verify ROS2 Topic Discovery

```bash
[PI] docker exec -it snoopi-ros2 ros2 topic list
```

**Expected topics from the robot:**
```
/utlidar/battery
/imu/data
/joint_states
/scan
/cloud
/camera/image_raw
/odometry/filtered
```

**Expected topics from snoopi nodes:**
```
/snoopi/system_stats
/snoopi/command
/cmd_vel
```

**If robot topics are missing:**
- Check `docker logs snoopi-ros2` for SDK errors
- Verify Ethernet ping still works: `ping <ROBOT_IP>`
- Check DDS config: `docker exec snoopi-ros2 cat /ros2_ws/cyclonedds.xml`
- Try restarting: `docker compose restart`

---

## Step 7: Verify Topic Data

```bash
[PI - container] ros2 topic echo /utlidar/battery --once
[PI - container] ros2 topic echo /imu/data --once
[PI - container] ros2 topic echo /snoopi/system_stats --once
```

Each should print one message. If `/utlidar/battery` shows real battery data (not the mock's 100% drain pattern), the real robot is connected.

---

## Step 8: Start the Backend and Frontend

```bash
# Terminal 2
[PI] cd ~/snoopi/backend && source venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000

# Terminal 3
[PI] cd ~/snoopi/ui && npm install && npm run dev -- --host 0.0.0.0
```

---

## Step 9: Verify Dashboard

```
[BROWSER] http://<PI_WIFI_IP>:5173
Login: john / snoopi-john-2026
```

**Check each card:**

| Card | Expected |
|---|---|
| Battery | Real battery % (should be 80-100% if robot is charged) |
| Temperature | Real robot internal temp |
| IMU | Z-acceleration ~9.81 m/s² (if robot is standing still) |
| System Health | Pi CPU %, Pi temperature, fan status |
| Telemetry graphs | All 4 graphs accumulating data points |
| rosbridge indicator | Connected (green) |

---

## Step 10: Document Findings

Run these commands and save the output:

```bash
[PI - container] ros2 topic list > /ros2_ws/logs/topic_list.txt
[PI - container] ros2 topic info /utlidar/battery -v > /ros2_ws/logs/battery_info.txt
[PI - container] ros2 service list > /ros2_ws/logs/service_list.txt
```

**Important for command_bridge:** Note any topics or services that look like they control robot mode (sit/stand). Look for:
- `/go2_state` or similar
- Any service with "mode" or "command" in the name
- Check: `ros2 service type <service_name>` for the message type

---

## Appendix: Make Static IP Permanent (Netplan)

To survive reboots, create a netplan config:

```bash
[PI] sudo nano /etc/netplan/99-robot-ethernet.yaml
```

```yaml
network:
  version: 2
  ethernets:
    <PI_ETH_INTERFACE>:
      addresses:
        - <PI_ROBOT_SUBNET_IP>/24
      # No gateway — robot subnet is local only, internet goes through WiFi
```

```bash
[PI] sudo netplan apply
```

---

## Troubleshooting

| Problem | Likely Cause | Fix |
|---|---|---|
| No robot topics in `ros2 topic list` | DDS can't discover robot | Check Ethernet, ping, CycloneDDS peer config |
| SDK launch crashes | Robot not reachable or firmware mismatch | Check logs: `cat /ros2_ws/logs/go2_sdk.log` |
| System monitor shows 0 CPU | psutil not installed | Rebuild image: `docker compose build` |
| System monitor shows 0 temp | /sys not mounted | Check `docker inspect snoopi-ros2` for volumes |
| Dashboard shows dashes | rosbridge not connected | Check `ws://<PI_WIFI_IP>:9090` is reachable |
| Graphs not updating | Data not flowing through rosbridge | Check `ros2 topic echo` inside container first |
