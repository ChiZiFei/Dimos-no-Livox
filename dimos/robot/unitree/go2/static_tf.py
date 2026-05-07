# Copyright 2026 Dimensional Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

from dimos.core.core import rpc
from dimos.core.module import Module
from dimos.core.stream import Out
from dimos.msgs.geometry_msgs import Quaternion, Transform, Vector3
from dimos.msgs.sensor_msgs.PointCloud2 import PointCloud2


class Mid360StaticTF(Module):
    """Publishes a static base_link → lidar_link transform for Unitree Go2 expansion dock Mid-360.

    Default values are from Unitree official documentation:
    - Translation in body IMU frame: (0.1870, 0, 0.0803) meters
    - Rotation: 13° around Y-axis (pitch)

    Reference: Unitree SLAM Navigation Service Interface v2026-01-20
    """

    lidar: Out[PointCloud2]  # dummy port so autoconnect can wire if needed

    def __init__(
        self,
        x: float = 0.1870,
        y: float = 0.0,
        z: float = 0.0803,
        roll: float = 0.0,
        pitch: float = 0.226893,  # 13 degrees in radians
        yaw: float = 0.0,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._static_tf = Transform(
            translation=Vector3(x, y, z),
            rotation=Quaternion.from_euler(Vector3(roll, pitch, yaw)),
            frame_id="base_link",
            child_frame_id="lidar_link",
        )

    @rpc
    def start(self) -> None:
        super().start()
        self.tf.publish(self._static_tf)


mid360_static_tf = Mid360StaticTF.blueprint

__all__ = ["Mid360StaticTF", "mid360_static_tf"]
