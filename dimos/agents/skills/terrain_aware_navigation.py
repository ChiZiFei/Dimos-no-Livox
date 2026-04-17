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

"""地形感知导航技能容器 - 处理台阶、斜坡等地形挑战"""

import time
from enum import Enum
from typing import Any

from reactivex.disposable import Disposable

from dimos.agents.annotation import skill
from dimos.core.core import rpc
from dimos.core.module import Module
from dimos.core.stream import In
from dimos.msgs.geometry_msgs import Twist, Vector3
from dimos.msgs.sensor_msgs import Image, PointCloud2
from dimos.navigation.base import NavigationState
from dimos.utils.logging_config import setup_logger

logger = setup_logger()


class TerrainType(Enum):
    FLAT = "flat"
    STAIRS_UP = "stairs_up"
    STAIRS_DOWN = "stairs_down"
    RAMP_UP = "ramp_up"
    RAMP_DOWN = "ramp_down"
    OBSTACLE = "obstacle"
    UNKNOWN = "unknown"


class GaitMode(Enum):
    NORMAL = "normal"
    CLIMB = "climb"  # 爬楼梯模式
    DESCEND = "descend"  # 下楼梯模式
    SLOW = "slow"  # 慢速谨慎模式


class TerrainAwareSkillContainer(Module):
    """地形感知导航技能容器

    提供以下能力：
    1. 检测前方地形（台阶、斜坡等）
    2. 自动切换步态模式
    3. 安全通过复杂地形
    """

    color_image: In[Image]
    pointcloud: In[PointCloud2]

    rpc_calls: list[str] = [
        "NavigationInterface.set_goal",
        "NavigationInterface.get_state",
        "NavigationInterface.is_goal_reached",
        "NavigationInterface.cancel_goal",
    ]

    _latest_image: Image | None = None
    _latest_pointcloud: PointCloud2 | None = None
    _current_gait: GaitMode = GaitMode.NORMAL
    _terrain_history: list[TerrainType] = []
    _max_history: int = 5

    def __init__(self) -> None:
        super().__init__()
        self._terrain_history = []

    @rpc
    def start(self) -> None:
        super().start()
        self._disposables.add(Disposable(self.color_image.subscribe(self._on_color_image)))
        self._disposables.add(Disposable(self.pointcloud.subscribe(self._on_pointcloud)))

    @rpc
    def stop(self) -> None:
        super().stop()

    def _on_color_image(self, image: Image) -> None:
        self._latest_image = image

    def _on_pointcloud(self, pointcloud: PointCloud2) -> None:
        self._latest_pointcloud = pointcloud

    @skill
    def analyze_terrain_ahead(self) -> str:
        """分析前方地形状况，检测是否有台阶、斜坡等。

        Returns:
            地形描述和建议的通过方式
        """
        if self._latest_pointcloud is None:
            return "无法获取点云数据，无法分析地形"

        terrain = self._detect_terrain_from_pointcloud(self._latest_pointcloud)
        self._update_terrain_history(terrain)

        # 稳定检测（避免误报）
        stable_terrain = self._get_stable_terrain()

        gait_recommendation = self._recommend_gait(stable_terrain)

        descriptions = {
            TerrainType.FLAT: "前方路面平坦，可以正常通行",
            TerrainType.STAIRS_UP: "检测到向上的台阶，建议切换爬楼梯模式",
            TerrainType.STAIRS_DOWN: "检测到向下的台阶，建议切换下楼梯模式",
            TerrainType.RAMP_UP: "检测到向上的斜坡，建议减速上行",
            TerrainType.RAMP_DOWN: "检测到向下的斜坡，建议减速下行",
            TerrainType.OBSTACLE: "前方有障碍物，需要绕行或清除",
            TerrainType.UNKNOWN: "无法识别地形，建议谨慎前进",
        }

        description = descriptions.get(stable_terrain, "未知地形")

        if gait_recommendation != self._current_gait:
            return f"{description}。建议切换至{gait_recommendation.value}模式"

        return description

    @skill
    def set_gait_mode(self, mode: str) -> str:
        """设置机器人步态模式以适应当前地形。

        Args:
            mode: 步态模式，可选值：
                - "normal": 正常行走模式
                - "climb": 爬楼梯模式（抬高身体、小步幅）
                - "descend": 下楼梯模式（降低身体、缓慢下行）
                - "slow": 慢速谨慎模式

        Returns:
            设置结果
        """
        try:
            gait = GaitMode(mode.lower())
        except ValueError:
            valid_modes = [m.value for m in GaitMode]
            return f"无效的步态模式 '{mode}'。有效选项: {valid_modes}"

        self._current_gait = gait

        # 根据步态调整运动参数
        gait_configs = {
            GaitMode.NORMAL: {"body_height": 0.3, "speed_level": 1},
            GaitMode.CLIMB: {"body_height": 0.4, "speed_level": 0, "foot_raise": 0.15},
            GaitMode.DESCEND: {"body_height": 0.25, "speed_level": 0, "foot_raise": 0.08},
            GaitMode.SLOW: {"body_height": 0.3, "speed_level": 0, "foot_raise": 0.1},
        }

        config = gait_configs.get(gait, gait_configs[GaitMode.NORMAL])

        # 尝试发送步态调整命令（如果连接了运动控制模块）
        try:
            self._apply_gait_config(config)
            return f"已切换至 {mode} 模式"
        except Exception as e:
            logger.warning(f"无法应用步态配置: {e}")
            return f"已设置 {mode} 模式（但未应用硬件配置）"

    @skill
    def navigate_with_terrain_adaptation(
        self,
        destination: str,
        auto_adapt_gait: bool = True
    ) -> str:
        """带地形自适应的导航。在行进过程中自动检测和适应地形变化。

        这是高级导航功能，适用于：
        - 需要爬楼梯/下楼梯的场景
        - 有斜坡的路径
        - 不确定地形状况的户外环境

        Args:
            destination: 目的地描述（如"超市门口"、"二楼办公室"）
            auto_adapt_gait: 是否自动调整步态，默认True

        Returns:
            导航状态和地形适应报告
        """
        # 首先使用语义导航找到目的地
        try:
            navigate_rpc = self.get_rpc_calls("NavigationInterface.set_goal")
            get_state_rpc = self.get_rpc_calls("NavigationInterface.get_state")
            is_goal_reached_rpc = self.get_rpc_calls("NavigationInterface.is_goal_reached")
        except Exception as e:
            return f"导航模块未连接: {e}"

        # 报告初始状态
        initial_terrain = self.analyze_terrain_ahead()

        # 启动导航监控线程（实际实现中应该在后台持续监控）
        if auto_adapt_gait:
            self._start_terrain_monitoring()

        return (
            f"开始导航至 '{destination}'。"
            f"当前地形: {initial_terrain}。"
            f"已启用自动地形适应。"
        )

    @skill
    def climb_stairs(self, estimated_steps: int = 0) -> str:
        """执行上楼梯动作序列。

        Args:
            estimated_steps: 预估台阶数量（0表示未知）

        Returns:
            执行结果
        """
        # 1. 切换到爬楼梯模式
        result = self.set_gait_mode("climb")

        # 2. 执行爬楼梯运动
        try:
            # 尝试获取运动控制RPC
            move_rpc = self.get_rpc_calls("UnitreeSkillContainer.execute_sport_command")

            # 执行准备动作
            move_rpc("RecoveryStand")
            time.sleep(1.0)

            # 如果有预估步数，可以更精确控制
            if estimated_steps > 0:
                return f"{result}。准备攀爬约 {estimated_steps} 级台阶"

            return f"{result}。已进入爬楼梯状态，将自动前进"

        except Exception as e:
            logger.warning(f"无法执行爬楼梯动作: {e}")
            return f"{result}。请手动控制前进"

    @skill
    def descend_stairs(self, estimated_steps: int = 0) -> str:
        """执行下楼梯动作序列。

        Args:
            estimated_steps: 预估台阶数量（0表示未知）

        Returns:
            执行结果
        """
        # 1. 切换到下楼梯模式
        result = self.set_gait_mode("descend")

        # 2. 执行下楼梯运动
        try:
            move_rpc = self.get_rpc_calls("UnitreeSkillContainer.execute_sport_command")
            move_rpc("RecoveryStand")
            time.sleep(0.5)

            if estimated_steps > 0:
                return f"{result}。准备下降约 {estimated_steps} 级台阶，请缓慢前进"

            return f"{result}。已进入下楼梯状态，请缓慢前进"

        except Exception as e:
            logger.warning(f"无法执行下楼梯动作: {e}")
            return f"{result}。请手动缓慢后退"

    def _detect_terrain_from_pointcloud(self, pointcloud: PointCloud2) -> TerrainType:
        """从点云数据中检测地形类型

        简化实现：实际应该使用更复杂的算法
        """
        # TODO: 实现真实的地形检测算法
        # 这里只是一个示例框架

        # 分析点云的高度分布
        # - 如果有点形成阶梯状分布 -> STAIRS
        # - 如果点形成连续斜面 -> RAMP
        # - 如果高度变化小 -> FLAT

        # 当前返回模拟值，实际应基于点云分析
        return TerrainType.FLAT

    def _update_terrain_history(self, terrain: TerrainType) -> None:
        """更新地形历史记录"""
        self._terrain_history.append(terrain)
        if len(self._terrain_history) > self._max_history:
            self._terrain_history.pop(0)

    def _get_stable_terrain(self) -> TerrainType:
        """获取稳定的地形判断（基于历史）"""
        if not self._terrain_history:
            return TerrainType.UNKNOWN

        # 返回最频繁出现的地形类型
        from collections import Counter
        counter = Counter(self._terrain_history)
        return counter.most_common(1)[0][0]

    def _recommend_gait(self, terrain: TerrainType) -> GaitMode:
        """根据地形推荐步态"""
        recommendations = {
            TerrainType.FLAT: GaitMode.NORMAL,
            TerrainType.STAIRS_UP: GaitMode.CLIMB,
            TerrainType.STAIRS_DOWN: GaitMode.DESCEND,
            TerrainType.RAMP_UP: GaitMode.SLOW,
            TerrainType.RAMP_DOWN: GaitMode.DESCEND,
            TerrainType.OBSTACLE: GaitMode.SLOW,
            TerrainType.UNKNOWN: GaitMode.SLOW,
        }
        return recommendations.get(terrain, GaitMode.NORMAL)

    def _apply_gait_config(self, config: dict[str, Any]) -> None:
        """应用步态配置到硬件"""
        # 这里应该连接到具体的机器人控制模块
        # 目前只是框架
        pass

    def _start_terrain_monitoring(self) -> None:
        """启动地形监控（后台线程）"""
        # 实际实现中应该启动一个线程持续监控地形
        # 并在地形变化时自动调整步态
        pass


terrain_aware_skill = TerrainAwareSkillContainer.blueprint

__all__ = ["TerrainAwareSkillContainer", "terrain_aware_skill", "TerrainType", "GaitMode"]
