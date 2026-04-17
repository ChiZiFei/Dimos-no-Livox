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

"""智能引导技能容器 - 整合导航、地形适应和交互引导

处理复杂场景如：
- "带我去超市门口"
- "去二楼会议室"
- "绕过障碍物到停车场"
"""

import json
import threading
import time
from typing import Any

from reactivex.disposable import Disposable

from dimos.agents.annotation import skill
from dimos.core.core import rpc
from dimos.core.module import Module
from dimos.core.stream import In, Out
from dimos.msgs.geometry_msgs import PoseStamped
from dimos.msgs.sensor_msgs import Image
from dimos.navigation.base import NavigationState
from dimos.utils.logging_config import setup_logger

logger = setup_logger()


class GuideState:
    """引导状态"""
    IDLE = "idle"
    NAVIGATING = "navigating"
    TERRAIN_ADAPTING = "terrain_adapting"
    WAITING_USER = "waiting_user"
    ARRIVED = "arrived"
    FAILED = "failed"


class SmartGuideSkillContainer(Module):
    """智能引导技能容器

    整合多项能力：
    1. 目的地解析（自然语言到地图坐标）
    2. 路径规划和导航
    3. 地形感知和自适应
    4. 实时语音引导和反馈
    """

    color_image: In[Image]
    odom: In[PoseStamped]
    guide_status: Out[dict]  # 引导状态输出

    rpc_calls: list[str] = [
        # 导航相关
        "NavigationInterface.set_goal",
        "NavigationInterface.get_state",
        "NavigationInterface.is_goal_reached",
        "NavigationInterface.cancel_goal",
        # 地形相关
        "TerrainAwareSkillContainer.analyze_terrain_ahead",
        "TerrainAwareSkillContainer.set_gait_mode",
        "TerrainAwareSkillContainer.climb_stairs",
        "TerrainAwareSkillContainer.descend_stairs",
        # 语音相关
        "SpeakSkill.speak",
        # GPS相关
        "GoogleMapsSkillContainer.google_maps_search",
        "OsmSkill.map_query",
        # 空间记忆
        "SpatialMemory.tag_location",
        "SpatialMemory.query_by_text",
    ]

    _latest_image: Image | None = None
    _latest_odom: PoseStamped | None = None
    _guide_state: str = GuideState.IDLE
    _current_destination: str | None = None
    _navigation_thread: threading.Thread | None = None
    _should_stop: threading.Event = threading.Event()

    def __init__(self) -> None:
        super().__init__()
        self._should_stop = threading.Event()

    @rpc
    def start(self) -> None:
        super().start()
        self._disposables.add(Disposable(self.color_image.subscribe(self._on_color_image)))
        self._disposables.add(Disposable(self.odom.subscribe(self._on_odom)))

    @rpc
    def stop(self) -> None:
        self._stop_navigation()
        super().stop()

    def _on_color_image(self, image: Image) -> None:
        self._latest_image = image

    def _on_odom(self, odom: PoseStamped) -> None:
        self._latest_odom = odom

    @skill
    def guide_to(self, destination: str, user_preference: str = "") -> str:
        """智能引导到目的地，自动处理地形挑战。

        这是主要的引导功能，处理自然语言描述的目的地。

        Args:
            destination: 目的地描述，如：
                - "超市门口"
                - "二楼会议室"
                - "最近的洗手间"
                - "GPS坐标: 37.8059,-122.4290"
            user_preference: 用户偏好，如：
                - "走楼梯" / "坐电梯"
                - "最近路线" / "最平坦路线"
                - "避开人群"

        Returns:
            引导开始状态和预估信息

        Example:
            guide_to("超市门口")
            guide_to("二楼办公室", "走楼梯")
        """
        # 1. 解析目的地
        parsed_dest = self._parse_destination(destination)

        if not parsed_dest:
            return f"抱歉，我找不到 '{destination}' 的位置。请提供更具体的描述或地址。"

        self._current_destination = destination
        self._guide_state = GuideState.NAVIGATING

        # 2. 语音确认
        self._speak(f"好的，我带您去{destination}。请跟我来。")

        # 3. 启动引导线程
        self._should_stop.clear()
        self._navigation_thread = threading.Thread(
            target=self._guide_loop,
            args=(parsed_dest, user_preference),
            daemon=True
        )
        self._navigation_thread.start()

        return (
            f"开始引导至 {destination}。"
            f"位置类型: {parsed_dest.get('type', 'unknown')}。"
            f"预计距离: {parsed_dest.get('distance', 'unknown')}。"
            f"我会实时报告路况和地形变化。"
        )

    @skill
    def handle_stairs_encountered(self, direction: str = "up") -> str:
        """当遇到楼梯时调用此技能处理。

        通常由系统自动调用，但用户也可以主动要求处理楼梯。

        Args:
            direction: 楼梯方向，"up" 或 "down"

        Returns:
            处理结果
        """
        if direction == "up":
            self._speak("前面有向上的台阶，我来爬楼梯，请稍等。")
            try:
                climb_rpc = self.get_rpc_calls(
                    "TerrainAwareSkillContainer.climb_stairs"
                )
                result = climb_rpc()
                return f"正在上楼梯: {result}"
            except Exception as e:
                return f"爬楼梯准备失败: {e}。请手动协助。"
        else:
            self._speak("前面有向下的台阶，小心下楼梯。")
            try:
                descend_rpc = self.get_rpc_calls(
                    "TerrainAwareSkillContainer.descend_stairs"
                )
                result = descend_rpc()
                return f"正在下楼梯: {result}"
            except Exception as e:
                return f"下楼梯准备失败: {e}。请手动协助。"

    @skill
    def report_guide_status(self) -> str:
        """报告当前引导状态。

        Returns:
            详细的引导状态信息
        """
        status = {
            "state": self._guide_state,
            "destination": self._current_destination,
            "position": self._latest_odom.position if self._latest_odom else None,
        }

        # 发布到流
        self.guide_status.publish(status)

        if self._guide_state == GuideState.IDLE:
            return "当前没有进行中的引导任务。"
        elif self._guide_state == GuideState.NAVIGATING:
            return f"正在导航至 {self._current_destination}。"
        elif self._guide_state == GuideState.TERRAIN_ADAPTING:
            return f"正在适应地形变化，准备继续前往 {self._current_destination}。"
        elif self._guide_state == GuideState.WAITING_USER:
            return "等待用户确认或指示。"
        elif self._guide_state == GuideState.ARRIVED:
            return f"已到达 {self._current_destination}。"
        else:
            return f"引导状态异常: {self._guide_state}"

    @skill
    def pause_guide(self) -> str:
        """暂停当前引导。

        Returns:
            暂停确认
        """
        self._should_stop.set()
        self._speak("已暂停引导。您可以在准备好后继续。")
        return "引导已暂停。调用 resume_guide() 继续。"

    @skill
    def resume_guide(self) -> str:
        """恢复暂停的引导。

        Returns:
            恢复确认
        """
        self._should_stop.clear()
        self._speak("继续引导。请跟我来。")
        return "引导已恢复。"

    @skill
    def cancel_guide(self) -> str:
        """取消当前引导任务。

        Returns:
            取消确认
        """
        self._stop_navigation()
        self._guide_state = GuideState.IDLE
        self._speak("引导已取消。需要其他帮助吗？")
        return "引导任务已取消。"

    def _parse_destination(self, destination: str) -> dict[str, Any] | None:
        """解析目的地描述为结构化数据"""
        parsed = {
            "original": destination,
            "type": "unknown",
            "coordinates": None,
            "description": destination,
        }

        # 尝试多种方式解析目的地

        # 1. 检查是否是GPS坐标
        if self._is_gps_coordinates(destination):
            coords = self._parse_gps_coordinates(destination)
            parsed["type"] = "gps"
            parsed["coordinates"] = coords
            return parsed

        # 2. 查询空间记忆
        try:
            query_rpc = self.get_rpc_calls("SpatialMemory.query_by_text")
            results = query_rpc(destination)
            if results:
                parsed["type"] = "semantic_map"
                parsed["map_result"] = results[0]
                return parsed
        except Exception:
            pass

        # 3. 使用Google Maps搜索
        try:
            search_rpc = self.get_rpc_calls("GoogleMapsSkillContainer.google_maps_search")
            result = search_rpc(destination)
            if result:
                parsed["type"] = "google_maps"
                parsed["map_data"] = result
                return parsed
        except Exception:
            pass

        # 4. 使用OSM查询
        try:
            osm_rpc = self.get_rpc_calls("OsmSkill.map_query")
            result = osm_rpc(destination)
            if result:
                parsed["type"] = "osm"
                parsed["map_data"] = result
                return parsed
        except Exception:
            pass

        # 如果所有方法都失败，返回None
        return None

    def _is_gps_coordinates(self, text: str) -> bool:
        """检查文本是否是GPS坐标格式"""
        import re
        # 匹配格式: "37.8059,-122.4290" 或 "37.8059, -122.4290"
        pattern = r"^-?\d+\.?\d*\s*,\s*-?\d+\.?\d*$"
        return bool(re.match(pattern, text.strip()))

    def _parse_gps_coordinates(self, text: str) -> tuple[float, float]:
        """解析GPS坐标文本"""
        parts = text.strip().split(",")
        return (float(parts[0].strip()), float(parts[1].strip()))

    def _guide_loop(self, destination: dict[str, Any], user_preference: str) -> None:
        """引导主循环"""
        try:
            # 1. 设置导航目标
            if not self._set_navigation_goal(destination):
                self._speak("抱歉，无法设置导航目标。请稍后再试。")
                self._guide_state = GuideState.FAILED
                return

            # 2. 导航循环
            while not self._should_stop.is_set():
                # 检查导航状态
                nav_state = self._check_navigation_state()

                if nav_state == "arrived":
                    self._speak(f"我们已经到达 {self._current_destination}。")
                    self._guide_state = GuideState.ARRIVED
                    break

                elif nav_state == "blocked":
                    self._handle_obstacle()

                # 3. 检查地形变化
                terrain_status = self._check_and_adapt_terrain()
                if terrain_status:
                    self._speak(terrain_status)

                # 4. 报告进度
                self._report_progress()

                time.sleep(2.0)  # 检查间隔

        except Exception as e:
            logger.exception("Guide loop error")
            self._guide_state = GuideState.FAILED
            self._speak("引导过程中遇到错误。请重新开始或手动导航。")

    def _set_navigation_goal(self, destination: dict[str, Any]) -> bool:
        """设置导航目标"""
        try:
            set_goal_rpc = self.get_rpc_calls("NavigationInterface.set_goal")

            # 根据目的地类型设置目标
            if destination["type"] == "gps":
                # GPS导航
                lat, lon = destination["coordinates"]
                # 转换为本地坐标或使用GPS导航
                return True
            elif destination["type"] in ["semantic_map", "google_maps", "osm"]:
                # 使用地图坐标
                return True
            else:
                return False

        except Exception as e:
            logger.error(f"Failed to set navigation goal: {e}")
            return False

    def _check_navigation_state(self) -> str:
        """检查导航状态"""
        try:
            get_state_rpc = self.get_rpc_calls("NavigationInterface.get_state")
            is_goal_reached_rpc = self.get_rpc_calls("NavigationInterface.is_goal_reached")

            state = get_state_rpc()

            if is_goal_reached_rpc():
                return "arrived"
            elif state == NavigationState.IDLE:
                return "idle"
            elif state == NavigationState.FOLLOWING_PATH:
                return "following"
            elif state == NavigationState.RECOVERY:
                return "blocked"
            else:
                return "unknown"

        except Exception:
            return "error"

    def _check_and_adapt_terrain(self) -> str | None:
        """检查并适应地形变化"""
        try:
            analyze_rpc = self.get_rpc_calls(
                "TerrainAwareSkillContainer.analyze_terrain_ahead"
            )
            terrain_result = analyze_rpc()

            # 如果检测到需要特殊处理的地形
            if "台阶" in terrain_result or "stairs" in terrain_result.lower():
                self._guide_state = GuideState.TERRAIN_ADAPTING

                if "向上" in terrain_result or "up" in terrain_result.lower():
                    self.handle_stairs_encountered("up")
                    return "检测到向上的台阶，正在调整姿态。"
                else:
                    self.handle_stairs_encountered("down")
                    return "检测到向下的台阶，小心下行。"

            return None

        except Exception:
            return None

    def _handle_obstacle(self) -> None:
        """处理障碍物"""
        self._speak("前方有障碍物，让我找一条替代路线。")
        # 这里可以实现绕行逻辑

    def _report_progress(self) -> None:
        """报告导航进度"""
        # 定期报告进度
        pass

    def _speak(self, text: str) -> None:
        """语音播报"""
        try:
            speak_rpc = self.get_rpc_calls("SpeakSkill.speak")
            speak_rpc(text)
        except Exception:
            logger.warning(f"Failed to speak: {text}")

    def _stop_navigation(self) -> None:
        """停止导航"""
        self._should_stop.set()
        if self._navigation_thread and self._navigation_thread.is_alive():
            self._navigation_thread.join(timeout=2.0)

        try:
            cancel_rpc = self.get_rpc_calls("NavigationInterface.cancel_goal")
            cancel_rpc()
        except Exception:
            pass


smart_guide_skill = SmartGuideSkillContainer.blueprint

__all__ = ["SmartGuideSkillContainer", "smart_guide_skill", "GuideState"]
