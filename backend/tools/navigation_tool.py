"""
Navigation Tool - LangChain tool for robot navigation via MCP
Wraps Sonnet 4.5 for command parsing + MCP for execution
"""

import logging
from typing import Type, Optional, Dict, Any
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
from langchain_openai import ChatOpenAI

from backend.services.mcp_client_service import (
    MCPClientService,
    MCPError,
    MCPTransientError,
    MCPRecoverableError,
    MCPPermanentError
)
from backend.config import get_settings

logger = logging.getLogger(__name__)

# ============================================================================
# Input Schema
# ============================================================================

class NavigationInput(BaseModel):
    """导航工具的输入参数"""
    command: str = Field(
        description="自然语言导航命令，例如：'去厨房'、'前进2米'、'向左转90度'"
    )


# ============================================================================
# Navigation Tool
# ============================================================================

class NavigationTool(BaseTool):
    """
    机器人导航工具

    使用Sonnet 4.5理解自然语言命令，通过MCP协议控制机器人导航
    """

    name: str = "robot_navigation"
    description: str = (
        "控制机器人导航的工具。用于处理用户的导航相关请求，如：\n"
        "- 移动到特定位置（例如：'去厨房'、'去客厅'）\n"
        "- 基础运动控制（例如：'前进2米'、'后退1米'、'向左转90度'）\n"
        "- 跟随指令（例如：'跟着我'）\n"
        "输入应该是用户的自然语言导航命令。"
    )
    args_schema: Type[BaseModel] = NavigationInput

    # MCP client (singleton per tool instance)
    _mcp_client: Optional[MCPClientService] = None
    _mcp_connected: bool = False

    # Sonnet LLM for command parsing
    _sonnet_llm: Optional[ChatOpenAI] = None

    def __init__(self, **kwargs):
        """初始化导航工具"""
        super().__init__(**kwargs)

        # Initialize Sonnet LLM
        settings = get_settings()
        self._sonnet_llm = ChatOpenAI(
            base_url=settings.openrouter_base_url,
            api_key=settings.openrouter_api_key,
            model=settings.navigation_command_parser_model,  # Sonnet 4.5
            temperature=0.2,
        )

        logger.info("NavigationTool initialized")

    async def _ensure_mcp_connected(self):
        """确保MCP客户端已连接"""
        if not self._mcp_connected:
            if self._mcp_client is None:
                settings = get_settings()
                self._mcp_client = MCPClientService(
                    server_module=settings.mcp_server_module,
                    connection_timeout=settings.mcp_connection_timeout,
                    tool_call_timeout=settings.mcp_tool_call_timeout,
                    heartbeat_interval=settings.mcp_heartbeat_interval,
                    heartbeat_timeout=settings.mcp_heartbeat_timeout,
                    heartbeat_max_failures=settings.mcp_heartbeat_max_failures
                )

            logger.info("Connecting to MCP server...")
            await self._mcp_client.connect()
            self._mcp_connected = True
            logger.info("MCP connection established")

    async def _analyze_with_sonnet(self, user_command: str) -> Dict[str, Any]:
        """
        使用Sonnet 4.5分析自然语言导航命令

        Args:
            user_command: 用户的自然语言命令

        Returns:
            包含工具名称和参数的字典
        """
        system_prompt = """You are a robot navigation command parser. Your task is to convert user's natural language commands into structured navigation instructions.

Available navigation tools:
1. navigate_to_location - Navigate to semantic location
   Parameters: {"location": "location_name"}
   Examples: "go to kitchen" / "去厨房" -> {"tool": "navigate_to_location", "params": {"location": "kitchen"}}
   Examples: "go to living room" / "去客厅" -> {"tool": "navigate_to_location", "params": {"location": "living_room"}}

2. navigate_to_pose - Navigate to specified coordinates and orientation
   Parameters: {"x": X_coordinate(meters), "y": Y_coordinate(meters), "yaw": orientation(radians,optional)}
   Examples: "move forward 2 meters" / "前进2米" -> {"tool": "navigate_to_pose", "params": {"x": 2.0, "y": 0.0, "yaw": 0.0}}
   Examples: "move left 1 meter" / "向左移动1米" -> {"tool": "navigate_to_pose", "params": {"x": 0.0, "y": 1.0, "yaw": 0.0}}
   Examples: "move backward 1.5 meters" / "后退1.5米" -> {"tool": "navigate_to_pose", "params": {"x": -1.5, "y": 0.0, "yaw": 0.0}}
   Note: Rotation commands also use this tool, turn left 90 degrees = yaw: 1.57, turn right 90 degrees = yaw: -1.57

3. get_navigation_status - Get current navigation status
   Parameters: {}
   Examples: "what's the navigation status" / "导航状态如何" -> {"tool": "get_navigation_status", "params": {}}
   Examples: "where is the robot" / "机器人在哪里" -> {"tool": "get_navigation_status", "params": {}}

4. cancel_navigation - Cancel current navigation task
   Parameters: {}
   Examples: "stop" / "停止" -> {"tool": "cancel_navigation", "params": {}}
   Examples: "cancel navigation" / "取消导航" -> {"tool": "cancel_navigation", "params": {}}

Semantic location mapping (Chinese/English):
- 厨房/kitchen = kitchen
- 客厅/living room = living_room
- 卧室/bedroom = bedroom
- 书房/study = study
- 餐厅/dining room = dining_room
- 门口/entrance = entrance

Angle to radians: 90° = 1.57 radians, 180° = 3.14 radians, 270° = 4.71 radians

Return structured instruction in JSON format based on user command. If command is unclear, return error explanation.

Return format:
{
  "tool": "tool_name",
  "params": {parameter_dict},
  "understood": true/false,
  "clarification": "if clarification needed, put question here"
}
"""

        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Command: {user_command}"}
            ]

            response = await self._sonnet_llm.agenerate([
                [{"role": msg["role"], "content": msg["content"]} for msg in messages]
            ])

            analysis_text = response.generations[0][0].text

            # 尝试解析JSON
            import json
            try:
                # 提取JSON（处理markdown代码块）
                if "```json" in analysis_text:
                    json_start = analysis_text.find("```json") + 7
                    json_end = analysis_text.find("```", json_start)
                    analysis_text = analysis_text[json_start:json_end].strip()
                elif "```" in analysis_text:
                    json_start = analysis_text.find("```") + 3
                    json_end = analysis_text.find("```", json_start)
                    analysis_text = analysis_text[json_start:json_end].strip()

                analysis = json.loads(analysis_text)
                return analysis
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Sonnet response as JSON: {e}")
                return {
                    "tool": None,
                    "params": {},
                    "understood": False,
                    "clarification": "Cannot understand this command, please rephrase"
                }

        except Exception as e:
            logger.error(f"Error analyzing command with Sonnet: {e}", exc_info=True)
            return {
                "tool": None,
                "params": {},
                "understood": False,
                "clarification": f"Command analysis failed: {str(e)}"
            }

    async def _arun(self, command: str) -> str:
        """
        异步执行导航命令

        Args:
            command: 用户的自然语言导航命令

        Returns:
            执行结果的文本描述
        """
        try:
            # Step 1: 使用Sonnet分析命令
            logger.info(f"Analyzing navigation command: {command}")
            analysis = await self._analyze_with_sonnet(command)

            # 检查是否理解命令
            if not analysis.get("understood", False):
                clarification = analysis.get("clarification", "Cannot understand this command")
                logger.warning(f"Command not understood: {clarification}")
                return f"❓ {clarification}"

            tool_name = analysis.get("tool")
            params = analysis.get("params", {})

            if not tool_name:
                return "❓ Cannot determine navigation operation to execute, please rephrase the command"

            logger.info(f"Parsed command -> tool: {tool_name}, params: {params}")

            # Step 2: 确保MCP连接
            await self._ensure_mcp_connected()

            # Step 3: 调用MCP工具
            logger.info(f"Calling MCP tool: {tool_name}")
            result = await self._mcp_client.call_tool(tool_name, params)

            # Step 4: 格式化结果
            return self._format_result(result, tool_name, params)

        except MCPTransientError as e:
            # 瞬时错误 - 提示用户重试
            logger.warning(f"Transient MCP error: {e.message}")
            return f"⚠️ Navigation system is temporarily busy, please try again later.\nError: {e.message}"

        except MCPRecoverableError as e:
            # 可恢复错误 - 提示用户调整命令
            logger.warning(f"Recoverable MCP error: {e.message}")
            return f"❌ Cannot execute this command.\nReason: {e.message}\nPlease adjust the command and retry."

        except MCPPermanentError as e:
            # 永久错误 - 系统问题
            logger.error(f"Permanent MCP error: {e.message}")
            return f"❌ Navigation system error.\nError: {e.message}\nPlease contact technical support."

        except MCPError as e:
            # 通用MCP错误
            logger.error(f"MCP error: {e.message}")
            return f"❌ Navigation error: {e.message}"

        except Exception as e:
            # 未预期的错误
            logger.error(f"Unexpected error in navigation tool: {e}", exc_info=True)
            return f"❌ Unexpected error occurred while executing navigation command: {str(e)}"

    def _format_result(self, result: Dict[str, Any], tool_name: str, params: Dict[str, Any]) -> str:
        """
        格式化MCP执行结果为用户友好的文本

        Args:
            result: MCP调用结果
            tool_name: 工具名称
            params: 工具参数

        Returns:
            格式化的文本结果
        """
        if not result.get("success", False):
            error = result.get("error", "Unknown error")
            return f"❌ Navigation failed: {error}"

        # 获取结果数据
        result_data = result.get("result", {})

        # 根据不同工具类型格式化输出
        if tool_name == "navigate_to_location":
            location = params.get("location", "target location")
            status = result_data.get("status", "unknown")

            if status == "success":
                return f"✅ Navigating to {location}..."
            elif status == "in_progress":
                progress = result_data.get("progress", 0)
                return f"🚶 Navigating... ({progress}%)"
            else:
                return f"⚠️ Encountered problem navigating to {location}"

        elif tool_name == "navigate_to_pose":
            x = params.get("x", 0)
            y = params.get("y", 0)
            yaw = params.get("yaw", 0)
            status = result_data.get("status", "unknown")

            # 生成友好的描述
            if x > 0 and abs(y) < 0.1:
                desc = f"Moving forward {x:.1f}m"
            elif x < 0 and abs(y) < 0.1:
                desc = f"Moving backward {abs(x):.1f}m"
            elif y > 0 and abs(x) < 0.1:
                desc = f"Moving left {y:.1f}m"
            elif y < 0 and abs(x) < 0.1:
                desc = f"Moving right {abs(y):.1f}m"
            elif abs(yaw) > 0.1:
                angle_deg = abs(yaw) * 57.3  # 弧度转角度
                direction = "left" if yaw > 0 else "right"
                desc = f"Rotating {direction} {angle_deg:.0f}°"
            else:
                desc = f"Moving to coordinates ({x:.1f}, {y:.1f})"

            if status == "success":
                return f"✅ {desc}"
            else:
                return f"⚠️ {desc} encountered problem"

        elif tool_name == "get_navigation_status":
            status = result_data.get("status", "unknown")
            current_pose = result_data.get("current_pose", {})

            if status == "idle":
                return f"🤖 Robot is idle\nPosition: ({current_pose.get('x', 0):.2f}, {current_pose.get('y', 0):.2f})"
            elif status == "navigating":
                goal = result_data.get("goal_pose", {})
                return f"🚶 Navigating to ({goal.get('x', 0):.2f}, {goal.get('y', 0):.2f})"
            else:
                return f"📍 Current status: {status}"

        elif tool_name == "cancel_navigation":
            if result_data.get("status") == "success":
                return f"✅ Navigation task cancelled"
            else:
                return f"⚠️ Failed to cancel navigation"

        # 默认格式化
        return f"✅ Navigation command executed\nResult: {result_data}"

    def _run(self, command: str) -> str:
        """同步运行方法（不推荐使用）"""
        import asyncio
        return asyncio.run(self._arun(command))

    async def cleanup(self):
        """清理资源"""
        if self._mcp_client and self._mcp_connected:
            logger.info("Disconnecting MCP client...")
            await self._mcp_client.disconnect()
            self._mcp_connected = False


# ============================================================================
# Singleton Factory
# ============================================================================

_navigation_tool_instance: Optional[NavigationTool] = None


def get_navigation_tool() -> NavigationTool:
    """获取导航工具实例（单例模式）"""
    global _navigation_tool_instance
    if _navigation_tool_instance is None:
        _navigation_tool_instance = NavigationTool()
    return _navigation_tool_instance
