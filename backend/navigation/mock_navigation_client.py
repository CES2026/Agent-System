#!/usr/bin/env python3
"""
Mock Navigation Client - Simulates robot navigation without ROS2
模拟导航客户端 - 无需ROS2硬件
"""

import asyncio
import math
import time
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum


class NavigationStatus(Enum):
    """导航状态枚举"""
    IDLE = "IDLE"
    NAVIGATING = "NAVIGATING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


@dataclass
class Pose:
    """位姿数据类"""
    x: float
    y: float
    z: float = 0.0
    yaw: float = 0.0

    def distance_to(self, other: 'Pose') -> float:
        """计算到另一个位姿的距离"""
        return math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'x': self.x,
            'y': self.y,
            'z': self.z,
            'yaw': self.yaw,
            'yaw_deg': math.degrees(self.yaw)
        }


class MockNavigationClient:
    """
    模拟导航客户端
    模拟机器人在虚拟环境中的移动
    """

    def __init__(self):
        # 当前状态
        self.current_pose = Pose(0.0, 0.0, 0.0, 0.0)
        self.target_pose: Optional[Pose] = None
        self.status = NavigationStatus.IDLE

        # 导航参数
        self.max_linear_speed = 0.5  # m/s
        self.max_angular_speed = 1.0  # rad/s
        self.position_tolerance = 0.1  # m
        self.yaw_tolerance = 0.1  # rad

        # 反馈信息
        self.feedback = {
            'distance_remaining': 0.0,
            'navigation_time': 0.0,
            'estimated_time_remaining': 0.0,
            'number_of_recoveries': 0
        }

        # 语义位置映射
        self.semantic_locations = {
            "kitchen": Pose(2.5, 1.0, 0.0, 0.0),
            "living_room": Pose(5.0, 3.0, 0.0, 1.57),
            "bedroom": Pose(3.0, 5.0, 0.0, 3.14),
            "charging_station": Pose(0.0, 0.0, 0.0, 0.0),
            "door": Pose(1.5, 0.5, 0.0, 1.57),
            "window": Pose(4.0, 2.0, 0.0, 0.0)
        }

        # 任务控制
        self._cancel_flag = False
        self._current_task: Optional[asyncio.Task] = None

    async def initialize(self):
        """初始化客户端"""
        print("✅ Mock Navigation Client initialized")
        print(f"📍 Starting position: ({self.current_pose.x}, {self.current_pose.y})")
        print(f"🗺️  Available locations: {', '.join(self.semantic_locations.keys())}")

    async def navigate_to_pose(
        self,
        x: float,
        y: float,
        yaw: float = 0.0,
        wait: bool = True
    ) -> Dict:
        """
        导航到指定位姿

        Args:
            x: 目标X坐标（米）
            y: 目标Y坐标（米）
            yaw: 目标朝向（弧度）
            wait: 是否等待完成

        Returns:
            包含导航结果的字典
        """
        self.target_pose = Pose(x, y, 0.0, yaw)
        self.status = NavigationStatus.NAVIGATING
        self._cancel_flag = False

        start_time = time.time()
        start_pose = Pose(self.current_pose.x, self.current_pose.y, 0.0, self.current_pose.yaw)
        total_distance = start_pose.distance_to(self.target_pose)

        print(f"\n🚀 Navigation started")
        print(f"   From: ({start_pose.x:.2f}, {start_pose.y:.2f})")
        print(f"   To:   ({x:.2f}, {y:.2f})")
        print(f"   Distance: {total_distance:.2f}m")

        if not wait:
            # 异步执行，立即返回
            self._current_task = asyncio.create_task(self._simulate_navigation())
            return {
                'success': True,
                'message': 'Navigation started',
                'distance': total_distance
            }

        # 同步等待完成
        try:
            await self._simulate_navigation()
            elapsed_time = time.time() - start_time

            if self.status == NavigationStatus.SUCCEEDED:
                print(f"✅ Navigation succeeded in {elapsed_time:.1f}s")
                return {
                    'success': True,
                    'message': 'Navigation completed successfully',
                    'distance': total_distance,
                    'time': elapsed_time
                }
            elif self.status == NavigationStatus.CANCELED:
                print(f"⚠️  Navigation canceled after {elapsed_time:.1f}s")
                return {
                    'success': False,
                    'message': 'Navigation was canceled',
                    'distance': start_pose.distance_to(self.current_pose),
                    'time': elapsed_time
                }
            else:
                print(f"❌ Navigation failed")
                return {
                    'success': False,
                    'message': 'Navigation failed',
                    'time': elapsed_time
                }

        except Exception as e:
            self.status = NavigationStatus.FAILED
            print(f"❌ Navigation error: {e}")
            return {
                'success': False,
                'message': f'Navigation error: {str(e)}'
            }

    async def navigate_to_location(self, location_name: str, wait: bool = True) -> Dict:
        """
        导航到语义位置

        Args:
            location_name: 位置名称（如 "kitchen", "bedroom"）
            wait: 是否等待完成
        """
        if location_name not in self.semantic_locations:
            return {
                'success': False,
                'message': f'Unknown location: {location_name}',
                'available_locations': list(self.semantic_locations.keys())
            }

        pose = self.semantic_locations[location_name]
        print(f"🎯 Navigating to location: {location_name}")

        result = await self.navigate_to_pose(pose.x, pose.y, pose.yaw, wait)
        result['location'] = location_name
        return result

    async def navigate_waypoints(
        self,
        waypoints: List[Dict],
        loop: bool = False
    ) -> Dict:
        """
        通过多个路径点

        Args:
            waypoints: 路径点列表 [{"x": 1.0, "y": 2.0, "yaw": 0.0}, ...]
            loop: 是否循环
        """
        completed = []
        failed = []

        print(f"\n🛤️  Starting waypoint navigation: {len(waypoints)} points")

        for i, wp in enumerate(waypoints):
            print(f"\n📍 Waypoint {i+1}/{len(waypoints)}")
            result = await self.navigate_to_pose(
                wp['x'],
                wp['y'],
                wp.get('yaw', 0.0),
                wait=True
            )

            if result['success']:
                completed.append(i)
            else:
                failed.append(i)
                if not loop:
                    break

            # 短暂停留
            await asyncio.sleep(0.5)

        return {
            'success': len(failed) == 0,
            'completed': completed,
            'failed': failed,
            'total': len(waypoints)
        }

    async def _simulate_navigation(self):
        """模拟导航过程"""
        if not self.target_pose:
            return

        # 计算总距离和时间
        total_distance = self.current_pose.distance_to(self.target_pose)
        estimated_time = total_distance / self.max_linear_speed

        # 模拟移动过程
        steps = 20  # 分20步完成
        for step in range(steps + 1):
            if self._cancel_flag:
                self.status = NavigationStatus.CANCELED
                return

            # 线性插值更新位置
            progress = step / steps
            self.current_pose.x = self.current_pose.x + (self.target_pose.x - self.current_pose.x) * (1 / (steps - step + 1)) if step < steps else self.target_pose.x
            self.current_pose.y = self.current_pose.y + (self.target_pose.y - self.current_pose.y) * (1 / (steps - step + 1)) if step < steps else self.target_pose.y
            self.current_pose.yaw = self.current_pose.yaw + (self.target_pose.yaw - self.current_pose.yaw) * (1 / (steps - step + 1)) if step < steps else self.target_pose.yaw

            # 更新反馈
            remaining_distance = self.current_pose.distance_to(self.target_pose)
            elapsed_time = estimated_time * progress

            self.feedback = {
                'distance_remaining': remaining_distance,
                'navigation_time': elapsed_time,
                'estimated_time_remaining': estimated_time - elapsed_time,
                'number_of_recoveries': 0,
                'progress_percentage': progress * 100
            }

            # 每步延迟，模拟真实移动
            await asyncio.sleep(estimated_time / steps)

        # 检查是否到达目标
        if self.current_pose.distance_to(self.target_pose) <= self.position_tolerance:
            self.status = NavigationStatus.SUCCEEDED
        else:
            self.status = NavigationStatus.FAILED

    async def cancel(self) -> Dict:
        """取消当前导航"""
        if self.status != NavigationStatus.NAVIGATING:
            return {
                'success': False,
                'message': 'No active navigation to cancel'
            }

        self._cancel_flag = True
        if self._current_task:
            self._current_task.cancel()

        # 等待任务完成取消
        await asyncio.sleep(0.1)

        print("⛔ Navigation canceled")
        return {
            'success': True,
            'message': 'Navigation canceled'
        }

    async def get_status(self) -> Dict:
        """获取当前导航状态"""
        return {
            'status': self.status.value,
            'current_pose': self.current_pose.to_dict(),
            'target_pose': self.target_pose.to_dict() if self.target_pose else None,
            'distance_remaining': self.feedback['distance_remaining'],
            'navigation_time': self.feedback['navigation_time'],
            'estimated_time_remaining': self.feedback['estimated_time_remaining'],
            'number_of_recoveries': self.feedback['number_of_recoveries'],
            'progress': self.feedback.get('progress_percentage', 0.0)
        }

    async def set_initial_pose(self, x: float, y: float, yaw: float):
        """设置初始位姿"""
        self.current_pose = Pose(x, y, 0.0, yaw)
        print(f"📍 Initial pose set to: ({x:.2f}, {y:.2f}, {math.degrees(yaw):.1f}°)")

    async def get_current_pose(self) -> Dict:
        """获取当前位姿"""
        return self.current_pose.to_dict()

    async def get_feedback(self) -> Dict:
        """获取导航反馈"""
        return self.feedback.copy()

    def get_semantic_locations(self) -> Dict[str, Dict]:
        """获取所有语义位置"""
        return {
            name: pose.to_dict()
            for name, pose in self.semantic_locations.items()
        }

    def add_semantic_location(self, name: str, x: float, y: float, yaw: float = 0.0):
        """添加新的语义位置"""
        self.semantic_locations[name] = Pose(x, y, 0.0, yaw)
        print(f"➕ Added location '{name}' at ({x}, {y})")
