#!/usr/bin/env python3
# Copyright 2025-2026 Dimensional Inc.
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

"""Go2 with Unitree official expansion dock Mid-360 SLAM.

This blueprint uses Unitree's official SLAM service running on
the expansion dock PC (192.168.123.18).

Data flow:
- Official SLAM (dock PC 192.168.123.18) -> Go2 body (WebRTC) -> DimOS

Official mount pose (from Unitree SDK2 docs 2026-01-20):
- Translation in body IMU frame: (0.1870, 0, 0.0803) meters
- Rotation: 13° around Y-axis (pitch)

Key features:
1. Uses official Unitree SLAM service (no local FastLio2 needed)
2. Data arrives via WebRTC from Go2 body
3. Mid360StaticTF publishes official base_link -> lidar_link transform
4. enable_internal_lidar=False disables built-in LiDAR

Network setup:
- Connect your PC to Go2 WiFi (192.168.12.x)
- Connect ethernet to expansion dock (192.168.123.x) for direct SLAM access
"""

import platform
from typing import Any

from dimos.constants import DEFAULT_CAPACITY_COLOR_IMAGE
from dimos.core.blueprints import autoconnect
from dimos.core.global_config import global_config
from dimos.core.transport import pSHMTransport
from dimos.mapping.costmapper import cost_mapper
from dimos.mapping.voxels import voxel_mapper
from dimos.msgs.sensor_msgs import Image
from dimos.navigation.frontier_exploration import wavefront_frontier_explorer
from dimos.navigation.replanning_a_star.module import replanning_a_star_planner
from dimos.protocol.pubsub.impl.lcmpubsub import LCM
from dimos.protocol.service.system_configurator import ClockSyncConfigurator
from dimos.robot.unitree.go2.connection import go2_connection
from dimos.robot.unitree.go2.static_tf import mid360_static_tf
from dimos.visualization.rerun.bridge import _resolve_viewer_mode, rerun_bridge
from dimos.web.websocket_vis.websocket_vis_module import websocket_vis

# Mac transport config
_mac_transports: dict[tuple[str, type], pSHMTransport[Image]] = {
    ("color_image", Image): pSHMTransport(
        "color_image", default_capacity=DEFAULT_CAPACITY_COLOR_IMAGE
    ),
}

_transports_base = (
    autoconnect() if platform.system() == "Linux" else autoconnect().transports(_mac_transports)
)


def _convert_camera_info(camera_info: Any) -> Any:
    return camera_info.to_rerun(
        image_topic="/world/color_image",
        optical_frame="camera_optical",
    )


def _convert_global_map(grid: Any) -> Any:
    return grid.to_rerun(voxel_size=0.1, mode="boxes")


def _convert_navigation_costmap(grid: Any) -> Any:
    return grid.to_rerun(
        colormap="Accent",
        z_offset=0.015,
        opacity=0.2,
        background="#484981",
    )


def _static_base_link(rr: Any) -> list[Any]:
    return [
        rr.Boxes3D(
            half_sizes=[0.35, 0.155, 0.2],
            colors=[(0, 255, 127)],
            fill_mode="wireframe",
        ),
        rr.Transform3D(parent_frame="tf#/base_link"),
    ]


def _go2_rerun_blueprint() -> Any:
    import rerun.blueprint as rrb
    return rrb.Blueprint(
        rrb.Horizontal(
            rrb.Spatial2DView(origin="world/color_image", name="Camera"),
            rrb.Spatial3DView(origin="world", name="3D"),
            column_shares=[1, 2],
        ),
    )


rerun_config = {
    "blueprint": _go2_rerun_blueprint,
    "pubsubs": [LCM()],
    "visual_override": {
        "world/camera_info": _convert_camera_info,
        "world/global_map": _convert_global_map,
        "world/navigation_costmap": _convert_navigation_costmap,
    },
    "static": {
        "world/tf/base_link": _static_base_link,
    },
}

# Create base blueprint with disabled internal lidar
if global_config.viewer == "foxglove":
    from dimos.robot.foxglove_bridge import foxglove_bridge

    with_vis = autoconnect(
        _transports_base,
        foxglove_bridge(shm_channels=["/color_image#sensor_msgs.Image"]),
    )
elif global_config.viewer.startswith("rerun"):
    with_vis = autoconnect(
        _transports_base, rerun_bridge(viewer_mode=_resolve_viewer_mode(), **rerun_config)
    )
else:
    with_vis = _transports_base

# Base blueprint with disabled internal LiDAR
# Official SLAM data arrives via WebRTC from Go2 body
unitree_go2_basic_no_lidar = (
    autoconnect(
        with_vis,
        go2_connection(enable_internal_lidar=False),
        websocket_vis(),
    )
    .global_config(n_workers=4, robot_model="unitree_go2")
    .configurators(ClockSyncConfigurator())
)

# Main blueprint
unitree_go2_mid360 = (
    autoconnect(
        unitree_go2_basic_no_lidar,
        # Official Mid-360 mount pose from Unitree SDK2 docs
        mid360_static_tf(),
        # Navigation modules
        voxel_mapper(voxel_size=0.1),
        cost_mapper(),
        replanning_a_star_planner(),
        wavefront_frontier_explorer(),
    )
    .global_config(
        n_workers=8,
        robot_model="unitree_go2_mid360",
    )
)

__all__ = ["unitree_go2_mid360"]
