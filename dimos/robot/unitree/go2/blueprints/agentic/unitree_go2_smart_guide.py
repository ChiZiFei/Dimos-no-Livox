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

"""Unitree Go2 智能引导模式 Blueprint

这个 Blueprint 整合了：
- 基础连接和导航
- 地形感知和自适应
- 智能引导功能
- LLM Agent

使用场景：
- 引导视障人士通过复杂环境
- 带领访客到达目的地
- 自动处理台阶、斜坡等地形挑战
"""

from dimos.agents.agent import agent
from dimos.agents.skills.gps_nav_skill import gps_nav_skill
from dimos.agents.skills.navigation import navigation_skill
from dimos.agents.skills.person_follow import person_follow_skill
from dimos.agents.skills.smart_guide import smart_guide_skill
from dimos.agents.skills.speak_skill import speak_skill
from dimos.agents.skills.terrain_aware_navigation import terrain_aware_skill
from dimos.agents.system_prompt_advanced import ADVANCED_SYSTEM_PROMPT
from dimos.core.blueprints import autoconnect
from dimos.perception.detection.module3D import detection_3d_module
from dimos.robot.unitree.go2.blueprints.smart.unitree_go2_spatial import (
    unitree_go2_spatial,
)
from dimos.robot.unitree.unitree_skill_container import unitree_skills

# 智能引导所需的基础模块
_guide_common = autoconnect(
    unitree_skills(),  # 基础运动控制
    speak_skill(),  # 语音输出
    navigation_skill(),  # 导航技能
    gps_nav_skill(),  # GPS导航
)

# 高级地形感知模块
_terrain_modules = autoconnect(
    terrain_aware_skill(),  # 地形感知
    detection_3d_module(),  # 3D检测用于地形分析
)

# 智能引导完整模块
_smart_guide = autoconnect(
    smart_guide_skill(),  # 智能引导核心
    person_follow_skill(),  # 人员跟随
)

# 完整的智能引导 Blueprint
# 使用方式: dimos run unitree-go2-smart-guide
unitree_go2_smart_guide = autoconnect(
    unitree_go2_spatial,  # 基础机器人连接（相机、激光雷达、导航）
    _guide_common,  # 引导和语音
    _terrain_modules,  # 地形感知
    _smart_guide,  # 智能引导
    agent(system_prompt=ADVANCED_SYSTEM_PROMPT),  # LLM Agent with advanced prompt
)

# 导出
__all__ = ["unitree_go2_smart_guide"]
