#!/usr/bin/env python3
"""ROS2 bridge for Unitree official SLAM service.

Subscribes to official SLAM topics from expansion dock PC (192.168.123.18)
and publishes to DimOS internal LCM topics.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from dimos.core.core import rpc
from dimos.core.module import Module
from dimos.core.stream import Out
from dimos.msgs.geometry_msgs import Point, Pose, PoseStamped, Quaternion, Vector3
from dimos.msgs.nav_msgs import Odometry
from dimos.msgs.sensor_msgs import PointCloud2, PointField
from dimos.msgs.std_msgs import Header

if TYPE_CHECKING:
    import numpy as np


class UnitreeSlamBridge(Module):
    """Bridge between Unitree official ROS2 SLAM and DimOS.

    Subscribes to:
    - /uslam/frontend/odom -> publishes to self.odometry
    - /uslam/frontend/cloud_world_ds -> publishes to self.pointcloud
    - /utlidar/robot_pose -> publishes to self.pose

    Configuration:
    - slam_ip: IP of expansion dock PC (default: 192.168.123.18)
    """

    odometry: Out[Odometry]
    pointcloud: Out[PointCloud2]
    pose: Out[PoseStamped]

    def __init__(
        self,
        slam_ip: str = "192.168.123.18",
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.slam_ip = slam_ip
        self._ros2_thread: threading.Thread | None = None
        self._shutdown = threading.Event()

    def _ros2_loop(self) -> None:
        """ROS2 spin loop in separate thread."""
        try:
            import rclpy
            from rclpy.node import Node
            from sensor_msgs.msg import PointCloud2 as RosPointCloud2
            from nav_msgs.msg import Odometry as RosOdometry
            from geometry_msgs.msg import PoseStamped as RosPoseStamped

            rclpy.init()
            node = Node("dimos_slam_bridge")

            # Subscribe to odometry
            node.create_subscription(
                RosOdometry,
                "/uslam/frontend/odom",
                self._on_odometry,
                10,
            )

            # Subscribe to point cloud
            node.create_subscription(
                RosPointCloud2,
                "/uslam/frontend/cloud_world_ds",
                self._on_pointcloud,
                10,
            )

            # Subscribe to pose
            node.create_subscription(
                RosPoseStamped,
                "/utlidar/robot_pose",
                self._on_pose,
                10,
            )

            self.logger.info(f"ROS2 bridge connected to SLAM at {self.slam_ip}")

            while not self._shutdown.is_set():
                rclpy.spin_once(node, timeout_sec=0.1)

            node.destroy_node()
            rclpy.shutdown()

        except ImportError as e:
            self.logger.error(f"ROS2 not available: {e}")
            self.logger.error("Please install: pip install rclpy")
        except Exception as e:
            self.logger.error(f"ROS2 bridge error: {e}")

    def _on_odometry(self, msg) -> None:
        """Convert ROS2 Odometry to DimOS format."""
        try:
            odom = Odometry(
                header=Header(
                    stamp=msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
                    frame_id=msg.header.frame_id,
                ),
                child_frame_id=msg.child_frame_id,
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
                twist=msg.twist.twist,
            )
            self.odometry.publish(odom)
        except Exception as e:
            self.logger.warning(f"Failed to convert odometry: {e}")

    def _on_pointcloud(self, msg) -> None:
        """Convert ROS2 PointCloud2 to DimOS format."""
        try:
            # Convert ROS PointCloud2 to numpy array
            import numpy as np

            # Parse point cloud data
            dtype = np.dtype([
                ('x', np.float32),
                ('y', np.float32),
                ('z', np.float32),
            ])

            # Extract points from ROS message
            points = np.frombuffer(msg.data, dtype=dtype, count=msg.width * msg.height)

            # Create DimOS PointCloud2
            pc = PointCloud2(
                header=Header(
                    stamp=msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
                    frame_id=msg.header.frame_id,
                ),
                height=msg.height,
                width=msg.width,
                fields=[
                    PointField(name="x", offset=0, datatype=PointField.FLOAT32, count=1),
                    PointField(name="y", offset=4, datatype=PointField.FLOAT32, count=1),
                    PointField(name="z", offset=8, datatype=PointField.FLOAT32, count=1),
                ],
                is_bigendian=msg.is_bigendian,
                point_step=12,
                row_step=msg.row_step,
                data=points.tobytes(),
                is_dense=msg.is_dense,
            )
            self.pointcloud.publish(pc)
        except Exception as e:
            self.logger.warning(f"Failed to convert pointcloud: {e}")

    def _on_pose(self, msg) -> None:
        """Convert ROS2 PoseStamped to DimOS format."""
        try:
            pose = PoseStamped(
                header=Header(
                    stamp=msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
                    frame_id=msg.header.frame_id,
                ),
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
            self.pose.publish(pose)
        except Exception as e:
            self.logger.warning(f"Failed to convert pose: {e}")

    @rpc
    def start(self) -> None:
        super().start()
        self._shutdown.clear()
        self._ros2_thread = threading.Thread(target=self._ros2_loop, daemon=True)
        self._ros2_thread.start()

    @rpc
    def stop(self) -> None:
        self._shutdown.set()
        if self._ros2_thread:
            self._ros2_thread.join(timeout=2.0)
        super().stop()


unitree_slam_bridge = UnitreeSlamBridge.blueprint

__all__ = ["UnitreeSlamBridge", "unitree_slam_bridge"]
