"""
工具调用监控器
用于跟踪和验证工具调用
"""

import time
from typing import List, Dict, Any, Optional
import json


class ToolCall:
    """单次工具调用记录"""

    def __init__(self, tool_name: str, params: Dict[str, Any], result: Any = None):
        self.tool_name = tool_name
        self.params = params
        self.result = result
        self.timestamp = time.time()
        self.duration = None  # 工具执行时间（如果记录）

    def set_result(self, result: Any, duration: float = None):
        """设置调用结果"""
        self.result = result
        if duration is not None:
            self.duration = duration

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "tool": self.tool_name,
            "params": self.params,
            "result": self.result,
            "timestamp": self.timestamp,
            "duration": self.duration
        }

    def __repr__(self):
        return f"ToolCall({self.tool_name}, params={self.params})"


class ToolCallMonitor:
    """工具调用监控器"""

    def __init__(self):
        self.calls: List[ToolCall] = []
        self._call_history = []  # 保存所有历史记录

    def record(self, tool_name: str, params: Dict[str, Any], result: Any = None) -> ToolCall:
        """
        记录工具调用

        Args:
            tool_name: 工具名称
            params: 工具参数
            result: 工具返回结果

        Returns:
            ToolCall对象
        """
        call = ToolCall(tool_name, params, result)
        self.calls.append(call)
        self._call_history.append(call)
        return call

    def get_call_count(self, tool_name: Optional[str] = None) -> int:
        """
        获取工具调用次数

        Args:
            tool_name: 工具名称，None则返回总调用次数

        Returns:
            调用次数
        """
        if tool_name is None:
            return len(self.calls)

        return len([c for c in self.calls if c.tool_name == tool_name])

    def get_last_call(self, tool_name: Optional[str] = None) -> Optional[ToolCall]:
        """
        获取最后一次调用

        Args:
            tool_name: 工具名称，None则返回任意工具的最后一次调用

        Returns:
            ToolCall对象或None
        """
        if not self.calls:
            return None

        if tool_name is None:
            return self.calls[-1]

        filtered_calls = [c for c in self.calls if c.tool_name == tool_name]
        return filtered_calls[-1] if filtered_calls else None

    def get_all_calls(self, tool_name: Optional[str] = None) -> List[ToolCall]:
        """
        获取所有调用记录

        Args:
            tool_name: 工具名称，None则返回所有工具的调用

        Returns:
            ToolCall列表
        """
        if tool_name is None:
            return self.calls.copy()

        return [c for c in self.calls if c.tool_name == tool_name]

    def has_tool_call(self, tool_name: str) -> bool:
        """检查是否调用了指定工具"""
        return any(c.tool_name == tool_name for c in self.calls)

    def verify_params(self, tool_name: str, expected_params: Dict[str, Any],
                      tolerance: Dict[str, float] = None) -> bool:
        """
        验证工具参数

        Args:
            tool_name: 工具名称
            expected_params: 预期参数
            tolerance: 数值参数的容差，如 {"x": 0.1, "y": 0.1}

        Returns:
            是否匹配
        """
        last_call = self.get_last_call(tool_name)
        if not last_call:
            return False

        actual_params = last_call.params

        for key, expected_value in expected_params.items():
            if key not in actual_params:
                return False

            actual_value = actual_params[key]

            # 数值类型：使用容差比较
            if isinstance(expected_value, (int, float)) and tolerance and key in tolerance:
                if abs(actual_value - expected_value) > tolerance[key]:
                    return False
            # 其他类型：精确比较
            elif actual_value != expected_value:
                return False

        return True

    def reset(self):
        """重置当前调用记录（不清除历史）"""
        self.calls = []

    def clear_history(self):
        """清除所有历史记录"""
        self.calls = []
        self._call_history = []

    def get_summary(self) -> Dict[str, Any]:
        """获取监控摘要"""
        if not self.calls:
            return {
                "total_calls": 0,
                "tools": {}
            }

        # 统计每个工具的调用次数
        tools_stats = {}
        for call in self.calls:
            if call.tool_name not in tools_stats:
                tools_stats[call.tool_name] = {
                    "count": 0,
                    "params_examples": []
                }

            tools_stats[call.tool_name]["count"] += 1

            # 记录前3个参数示例
            if len(tools_stats[call.tool_name]["params_examples"]) < 3:
                tools_stats[call.tool_name]["params_examples"].append(call.params)

        return {
            "total_calls": len(self.calls),
            "tools": tools_stats
        }

    def export_trace(self) -> str:
        """导出完整调用trace（JSON格式）"""
        return json.dumps(
            [call.to_dict() for call in self.calls],
            indent=2,
            ensure_ascii=False
        )

    def print_trace(self):
        """打印调用trace"""
        if not self.calls:
            print("No tool calls recorded")
            return

        print(f"\nTool Call Trace ({len(self.calls)} calls):")
        print("=" * 70)

        for i, call in enumerate(self.calls, 1):
            print(f"\n{i}. {call.tool_name}")
            print(f"   Params: {json.dumps(call.params, ensure_ascii=False)}")
            if call.result:
                result_str = str(call.result)
                if len(result_str) > 100:
                    result_str = result_str[:100] + "..."
                print(f"   Result: {result_str}")
            if call.duration:
                print(f"   Duration: {call.duration:.2f}s")

        print("\n" + "=" * 70)

    def __len__(self):
        return len(self.calls)

    def __repr__(self):
        return f"ToolCallMonitor({len(self.calls)} calls)"
