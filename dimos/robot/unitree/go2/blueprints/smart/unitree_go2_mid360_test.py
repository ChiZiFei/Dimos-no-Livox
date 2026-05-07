#!/usr/bin/env python3
"""Test blueprint for Go2 + Mid-360 with debug output and no voxel mapper.

This is a test version that:
1. Enables debug logging for SLAM odometry
2. Disables voxel mapper to test pure official SLAM
3. Shows raw odometry data from official SLAM service
"""

import platform
from typing import Any

from dimos.constants import DEFAULT_CAPACITY_COLOR_IMAGE
from dimos.core.blueprints import autoconnect
from dimos.core.global_config import global_config
from dimos.core.transport import pSHMTransport
from dimos.mapping.costmapper import cost_mapper
from dimos.msgs.sensor_msgs import Image
from dimos.navigation.frontier_exploration import wavefront_frontier_explorer
from dimos.navigation.replanning_a_star.module import replanning_a_star_planner
from dimos.protocol.pubsub.impl.lcmpubsub import LCM
from dimos.protocol.service.system_configurator import ClockSyncConfigurator
from dimos.robot.unitree.go2.connection import go2_connection
from dimos.robot.unitree.go2.slam_odom_bridge import slam_odom_bridge
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
    },
    "static": {
        "world/tf/base_link": _static_base_link,
    },
}

# Create base blueprint
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

# Base blueprint with LiDAR enabled for visualization
unitree_go2_basic = (
    autoconnect(
        with_vis,
        go2_connection(enable_internal_lidar=True),
        websocket_vis(),
    )
    .global_config(n_workers=4, robot_model="unitree_go2", log_level="DEBUG")
    .configurators(ClockSyncConfigurator())
)

# Test blueprint - NO VOXEL MAPPER, debug SLAM odometry
unitree_go2_mid360_test = autoconnect(
    unitree_go2_basic,
    # Official Mid-360 mount pose
    mid360_static_tf(),
    # SLAM odometry bridge with debug output
    slam_odom_bridge(topic="/uslam/frontend/odom"),
    # Cost mapper only (no voxel mapper)
    cost_mapper(),
    # Navigation
    replanning_a_star_planner(),
    wavefront_frontier_explorer(),
).global_config(
    n_workers=6,
    robot_model="unitree_go2_mid360_test",
    log_level="DEBUG",  # Enable debug logging
)

__all__ = ["unitree_go2_mid360_test"]
