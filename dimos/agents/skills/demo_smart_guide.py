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

"""演示脚本：展示智能引导功能的用法

运行方式:
    python -m dimos.agents.skills.demo_smart_guide

这个脚本演示了如何使用智能引导技能完成复杂任务。
"""

import time

from dimos.agents.skills.smart_guide import SmartGuideSkillContainer
from dimos.agents.skills.terrain_aware_navigation import (
    GaitMode,
    TerrainAwareSkillContainer,
    TerrainType,
)


def demo_terrain_analysis():
    """演示地形分析功能"""
    print("=== 地形分析演示 ===\n")

    terrain_skill = TerrainAwareSkillContainer()

    # 模拟地形检测结果
    terrains = [
        TerrainType.FLAT,
        TerrainType.STAIRS_UP,
        TerrainType.RAMP_UP,
        TerrainType.STAIRS_DOWN,
    ]

    for terrain in terrains:
        print(f"检测到地形: {terrain.value}")

        # 获取推荐的步态
        gait = terrain_skill._recommend_gait(terrain)
        print(f"  推荐步态: {gait.value}")

        # 获取描述
        descriptions = {
            TerrainType.FLAT: "前方路面平坦，可以正常通行",
            TerrainType.STAIRS_UP: "检测到向上的台阶，建议切换爬楼梯模式",
            TerrainType.STAIRS_DOWN: "检测到向下的台阶，建议切换下楼梯模式",
            TerrainType.RAMP_UP: "检测到向上的斜坡，建议减速上行",
            TerrainType.RAMP_DOWN: "检测到向下的斜坡，建议减速下行",
            TerrainType.OBSTACLE: "前方有障碍物，需要绕行或清除",
            TerrainType.UNKNOWN: "无法识别地形，建议谨慎前进",
        }
        print(f"  描述: {descriptions.get(terrain, '未知')}")
        print()


def demo_guide_scenario():
    """演示引导场景"""
    print("=== 引导场景演示 ===\n")

    guide_skill = SmartGuideSkillContainer()

    # 场景1: 简单的目的地解析
    destinations = [
        "超市门口",
        "二楼会议室",
        "37.8059,-122.4290",
        "最近的洗手间",
    ]

    print("目的地解析测试:")
    for dest in destinations:
        parsed = guide_skill._parse_destination(dest)
        if guide_skill._is_gps_coordinates(dest):
            print(f"  '{dest}' -> GPS坐标: {guide_skill._parse_gps_coordinates(dest)}")
        else:
            print(f"  '{dest}' -> 类型: {parsed.get('type', 'unknown') if parsed else '解析失败'}")

    print()

    # 场景2: 模拟引导流程
    print("模拟引导流程:")
    print("  1. 用户: '带我去超市门口'")
    print("  2. Agent: guide_to('超市门口', '')")
    print("  3. 语音: '好的，我带您去超市门口。请跟我来。'")
    print("  4. 启动导航线程，持续监控地形...")

    # 模拟地形变化
    print("  5. 检测到地形变化:")
    terrain_sequence = [
        ("平坦路面", "正常前进"),
        ("向上台阶", "切换爬楼梯模式"),
        ("平坦路面", "恢复正常模式"),
        ("到达目的地", "引导结束"),
    ]

    for terrain, action in terrain_sequence:
        print(f"     - {terrain}: {action}")
        time.sleep(0.5)

    print("\n  6. 语音: '我们已经到达超市门口。还有什么可以帮助您的吗？'")


def demo_gait_modes():
    """演示步态模式"""
    print("\n=== 步态模式演示 ===\n")

    gait_configs = {
        GaitMode.NORMAL: {"body_height": 0.3, "speed_level": 1, "description": "正常行走"},
        GaitMode.CLIMB: {
            "body_height": 0.4,
            "speed_level": 0,
            "foot_raise": 0.15,
            "description": "爬楼梯 - 抬高身体、高举脚",
        },
        GaitMode.DESCEND: {
            "body_height": 0.25,
            "speed_level": 0,
            "foot_raise": 0.08,
            "description": "下楼梯 - 降低身体、小步幅",
        },
        GaitMode.SLOW: {
            "body_height": 0.3,
            "speed_level": 0,
            "foot_raise": 0.1,
            "description": "慢速 - 谨慎通过",
        },
    }

    for gait, config in gait_configs.items():
        print(f"{gait.value.upper()} 模式:")
        print(f"  描述: {config['description']}")
        print(f"  配置: {config}")
        print()


def demo_complex_scenario():
    """演示完整复杂场景"""
    print("\n=== 复杂场景演示: 带用户上二楼会议室 ===\n")

    scenario = [
        ("用户", "带我去二楼会议室，走楼梯"),
        ("Agent", "解析意图: guide_to('二楼会议室', '走楼梯')"),
        ("Agent", "查询地图，规划经楼梯的路线"),
        ("语音", "好的，我带您去二楼会议室，我们走楼梯。请跟我来。"),
        ("系统", "开始导航，监控地形..."),
        ("地形", "检测到前方有向上的台阶"),
        ("Agent", "handle_stairs_encountered('up')"),
        ("语音", "前面有向上的台阶，我来爬楼梯，请小心跟随。"),
        ("系统", "切换步态模式: climb"),
        ("系统", "调整身体高度到0.4m，抬高脚部到0.15m"),
        ("系统", "正在爬楼梯..."),
        ("系统", "已通过楼梯，恢复normal模式"),
        ("语音", "已到二楼，继续前往会议室。"),
        ("系统", "到达目的地附近"),
        ("语音", "我们已经到达二楼会议室。还有什么可以帮助您的吗？"),
    ]

    for role, action in scenario:
        print(f"[{role:8s}] {action}")
        time.sleep(0.3)


def main():
    """主函数"""
    print("=" * 60)
    print("DimOS 智能引导功能演示")
    print("=" * 60)
    print()

    demo_terrain_analysis()
    demo_guide_scenario()
    demo_gait_modes()
    demo_complex_scenario()

    print("\n" + "=" * 60)
    print("演示结束")
    print("=" * 60)
    print()
    print("要运行真实的智能引导，请使用:")
    print("  dimos run unitree-go2-smart-guide --robot-ip <IP>")


if __name__ == "__main__":
    main()
