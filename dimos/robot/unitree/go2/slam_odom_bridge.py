#!/usr/bin/env python3
"""ROS2 bridge for Unitree official SLAM odometry.

Subscribes to official SLAM odometry from expansion dock PC
and publishes to DimOS internal LCM topics.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from dimos.core.core import rpc
from dimos.core.module import Module
from dimos.core.stream import Out
from dimos.msgs.geometry_msgs import Pose, PoseStamped, Quaternion, Point
from dimos.msgs.nav_msgs import Odometry
from dimos.msgs.std_msgs import Header

if TYPE_CHECKING:
    pass


class SlamOdomBridge(Module):
    """Bridge between Unitree official SLAM odometry and DimOS.

    Subscribes to /uslam/frontend/odom or /utlidar/robot_pose from ROS2
    and publishes to DimOS odometry stream.

    This replaces the built-in WebRTC odometry with official SLAM data.
    """

    odometry: Out[Odometry]

    def __init__(
        self,
        topic: str = "/uslam/frontend/odom",  # or "/utlidar/robot_pose"
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.topic = topic
        self._running = False
        self._thread: threading.Thread | None = None

    def _ros2_loop(self) -> None:
        """ROS2 subscription loop."""
        try:
            import rclpy
            from rclpy.node import Node
            from nav_msgs.msg import Odometry as RosOdometry
            from geometry_msgs.msg import PoseStamped as RosPoseStamped

            rclpy.init()
            node = Node("slam_odom_bridge")

            # Subscribe to odometry
            if "odom" in self.topic:
                node.create_subscription(
                    RosOdometry,
                    self.topic,
                    self._on_odometry,
                    10,
                )
            else:
                node.create_subscription(
                    RosPoseStamped,
                    self.topic,
                    self._on_pose,
                    10,
                )

            self.logger.info(f"SLAM odom bridge subscribed to {self.topic}")

            while self._running:
                rclpy.spin_once(node, timeout_sec=0.1)

            node.destroy_node()
            rclpy.shutdown()

        except ImportError as e:
            self.logger.error(f"ROS2 not available: {e}")
        except Exception as e:
            self.logger.error(f"ROS2 bridge error: {e}")

    def _on_odometry(self, msg) -> None:
        """Convert ROS2 Odometry to DimOS format.

        Note: Official SLAM outputs in 'odom' frame, we convert to 'map' frame
        for global consistency in DimOS.
        """
        try:
            # Debug: Log received odometry
            import math

            q = msg.pose.pose.orientation
            # Convert quaternion to Euler angles (yaw)
            yaw = math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))
            yaw_deg = math.degrees(yaw)

            self.logger.debug(
                f"[SLAM ODOM] Received: frame={msg.header.frame_id}, "
                f"pos=({msg.pose.pose.position.x:.3f}, {msg.pose.pose.position.y:.3f}, {msg.pose.pose.position.z:.3f}), "
                f"yaw={yaw_deg:.2f}°"
            )

            # Use 'map' as frame_id for global consistency
            # Official SLAM /uslam/frontend/odom uses 'odom' frame but is actually
            # the global map-aligned pose
            frame_id = "map" if msg.header.frame_id == "odom" else msg.header.frame_id

            odom = Odometry(
                header=Header(
                    stamp=msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
                    frame_id=frame_id,
                ),
                child_frame_id="lidar_link",  # Match our TF tree
                pose=Pose(
                    position=Point(
                        x=msg.pose.pose.position.x,
                        y=msg.pose.pose.position.y,
                        z=msg.pose.pose.position.z,
                    ),
                    orientation=Quaternion(
                        x=msg.pose.pose.orientation.x,
                        y=msg.pose.pose.orientation.y,
                        z=msg.pose.pose.orientation.z,
                        w=msg.pose.pose.orientation.w,
                    ),
                ),
            )
            self.odometry.publish(odom)

            # Debug: Log published odometry
            self.logger.debug(
                f"[SLAM ODOM] Published: frame={frame_id}, "
                f"pos=({odom.pose.position.x:.3f}, {odom.pose.position.y:.3f}), "
                f"yaw={math.degrees(math.atan2(2.0 * (odom.pose.orientation.w * odom.pose.orientation.z + odom.pose.orientation.x * odom.pose.orientation.y), 1.0 - 2.0 * (odom.pose.orientation.y**2 + odom.pose.orientation.z**2))):.2f}°"
            )

        except Exception as e:
            self.logger.warning(f"Failed to convert odometry: {e}")

    def _on_pose(self, msg) -> None:
        """Convert ROS2 PoseStamped to Odometry format."""
        try:
            odom = Odometry(
                header=Header(
                    stamp=msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
                    frame_id=msg.header.frame_id,
                ),
                child_frame_id="base_link",
                pose=Pose(
                    position=Point(
                        x=msg.pose.position.x,
                        y=msg.pose.position.y,
                        z=msg.pose.position.z,
                    ),
                    orientation=Quaternion(
                        x=msg.pose.orientation.x,
                        y=msg.pose.orientation.y,
                        z=msg.pose.orientation.z,
                        w=msg.pose.orientation.w,
                    ),
                ),
            )
            self.odometry.publish(odom)
        except Exception as e:
            self.logger.warning(f"Failed to convert pose: {e}")

    @rpc
    def start(self) -> None:
        super().start()
        self._running = True
        self._thread = threading.Thread(target=self._ros2_loop, daemon=True)
        self._thread.start()

    @rpc
    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        super().stop()


slam_odom_bridge = SlamOdomBridge.blueprint

__all__ = ["SlamOdomBridge", "slam_odom_bridge"]
