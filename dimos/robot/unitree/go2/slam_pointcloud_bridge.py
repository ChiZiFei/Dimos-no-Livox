#!/usr/bin/env python3
"""Bridge to subscribe to official SLAM point cloud from Go2.

This module receives point cloud data from the official Unitree SLAM service
via WebRTC/ROS2 and publishes it to DimOS internal topics for visualization.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from dimos.core.core import rpc
from dimos.core.module import Module
from dimos.core.stream import Out
from dimos.msgs.sensor_msgs import PointCloud2, PointField
from dimos.msgs.std_msgs import Header

if TYPE_CHECKING:
    pass


class SlamPointcloudBridge(Module):
    """Bridge between Unitree official SLAM point cloud and DimOS.

    Subscribes to point cloud from GO2Connection (which receives it from
    Go2 body via WebRTC) and republishes to voxel mapper.

    This is a workaround for enable_internal_lidar=False which disables
    the built-in LiDAR stream but we still want to visualize point cloud
    from official SLAM.
    """

    lidar: Out[PointCloud2]  # Output to voxel mapper

    def __init__(
        self,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._running = False
        self._thread: threading.Thread | None = None

    def _bridge_loop(self) -> None:
        """Bridge loop - in this simple version, we rely on GO2Connection
        to receive point cloud and just pass it through.

        Actually, the GO2Connection with enable_internal_lidar=False
        doesn't subscribe to LiDAR, so we need to subscribe to the
        official SLAM topics directly.
        """
        try:
            # For now, this is a placeholder
            # The actual implementation would subscribe to ROS2 topics
            # from the official SLAM and convert to DimOS PointCloud2
            self.logger.info("SLAM point cloud bridge started")

            while self._running:
                # In a real implementation, we would:
                # 1. Subscribe to /uslam/frontend/cloud_world_ds
                # 2. Convert ROS PointCloud2 to DimOS PointCloud2
                # 3. Publish to self.lidar
                import time

                time.sleep(1)

        except Exception as e:
            self.logger.error(f"Bridge error: {e}")

    @rpc
    def start(self) -> None:
        super().start()
        self._running = True
        self._thread = threading.Thread(target=self._bridge_loop, daemon=True)
        self._thread.start()
        self.logger.info("SLAM point cloud bridge started")

    @rpc
    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        super().stop()


slam_pointcloud_bridge = SlamPointcloudBridge.blueprint

__all__ = ["SlamPointcloudBridge", "slam_pointcloud_bridge"]
