#!/usr/bin/env python3
"""
Wheeltec Navigation MCP Server
模拟版本 - 使用OpenRouter Llama 70B处理自然语言
"""

import asyncio
import json
from typing import Any, Dict
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

from backend.navigation.mock_navigation_client import MockNavigationClient
from backend.services.openrouter_service import get_openrouter_service


# 创建MCP服务器实例
app = Server("wheeltec-navigation-simulator")

# 全局实例
nav_client: MockNavigationClient = None
llm_service = None  # OpenRouterService instance


async def parse_navigation_intent(instruction: str) -> Dict[str, Any]:
    """
    使用LLM解析自然语言导航指令

    Args:
        instruction: 自然语言指令

    Returns:
        解析结果字典，包含action和相关参数
    """
    if llm_service is None:
        return {"action": "error", "message": "LLM service not available"}

    system_prompt = """You are a robot navigation instruction parser. Convert user's natural language instructions into structured navigation commands.

Supported action types:
- navigate_to_pose: Navigate to specified coordinates (requires x, y, yaw parameters)
- navigate_to_location: Navigate to semantic location (requires location parameter)
- get_status: Get navigation status
- cancel: Cancel navigation
- unknown: Cannot understand the instruction

Please return JSON format: {"action": "action_type", "x": number, "y": number, "yaw": number, "location": "location_name"}

Examples:
"go to kitchen" / "去厨房" -> {"action": "navigate_to_location", "location": "kitchen"}
"move forward 2 meters" / "前进2米" -> {"action": "navigate_to_pose", "x": 2.0, "y": 0.0, "yaw": 0.0}
"stop" / "停止" -> {"action": "cancel"}
"""

    try:
        response = await llm_service.generate_response(
            message=instruction,
            system_prompt=system_prompt,
            temperature=0.2
        )

        # 提取JSON
        import json
        if "```json" in response:
            json_start = response.find("```json") + 7
            json_end = response.find("```", json_start)
            response = response[json_start:json_end].strip()
        elif "```" in response:
            json_start = response.find("```") + 3
            json_end = response.find("```", json_start)
            response = response[json_start:json_end].strip()

        result = json.loads(response)
        return result
    except Exception as e:
        return {"action": "error", "message": f"Failed to parse: {str(e)}"}


@app.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """列出所有可用工具"""
    return [
        types.Tool(
            name="navigate_to_pose",
            description="Navigate robot to a specified pose with coordinates (x, y) and orientation (yaw)",
            inputSchema={
                "type": "object",
                "properties": {
                    "x": {
                        "type": "number",
                        "description": "Target X coordinate in meters"
                    },
                    "y": {
                        "type": "number",
                        "description": "Target Y coordinate in meters"
                    },
                    "yaw": {
                        "type": "number",
                        "description": "Target orientation in radians (optional, default 0.0)"
                    },
                    "wait": {
                        "type": "boolean",
                        "description": "Wait for navigation to complete (default true)"
                    }
                },
                "required": ["x", "y"]
            }
        ),
        types.Tool(
            name="navigate_to_location",
            description="Navigate to a semantic location by name (kitchen, bedroom, living_room, charging_station, door, window)",
            inputSchema={
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "Location name",
                        "enum": ["kitchen", "bedroom", "living_room", "charging_station", "door", "window"]
                    },
                    "wait": {
                        "type": "boolean",
                        "description": "Wait for navigation to complete"
                    }
                },
                "required": ["location"]
            }
        ),
        types.Tool(
            name="navigate_through_waypoints",
            description="Navigate through a sequence of waypoints",
            inputSchema={
                "type": "object",
                "properties": {
                    "waypoints": {
                        "type": "array",
                        "description": "List of waypoints",
                        "items": {
                            "type": "object",
                            "properties": {
                                "x": {"type": "number"},
                                "y": {"type": "number"},
                                "yaw": {"type": "number"}
                            },
                            "required": ["x", "y"]
                        }
                    },
                    "loop": {
                        "type": "boolean",
                        "description": "Loop through waypoints continuously"
                    }
                },
                "required": ["waypoints"]
            }
        ),
        types.Tool(
            name="get_navigation_status",
            description="Get current navigation status, including position, target, and progress",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="cancel_navigation",
            description="Cancel the current navigation task",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="set_initial_pose",
            description="Set robot initial pose for localization",
            inputSchema={
                "type": "object",
                "properties": {
                    "x": {"type": "number", "description": "X coordinate"},
                    "y": {"type": "number", "description": "Y coordinate"},
                    "yaw": {"type": "number", "description": "Orientation in radians"}
                },
                "required": ["x", "y", "yaw"]
            }
        ),
        types.Tool(
            name="get_semantic_locations",
            description="Get all available semantic locations",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="add_semantic_location",
            description="Add a new semantic location",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Location name"},
                    "x": {"type": "number", "description": "X coordinate"},
                    "y": {"type": "number", "description": "Y coordinate"},
                    "yaw": {"type": "number", "description": "Orientation in radians (optional)"}
                },
                "required": ["name", "x", "y"]
            }
        ),
        types.Tool(
            name="natural_language_navigate",
            description="Navigate using natural language instructions (powered by Llama 70B). Examples: 'go to kitchen', 'move to coordinates (2, 3)', 'patrol the house'",
            inputSchema={
                "type": "object",
                "properties": {
                    "instruction": {
                        "type": "string",
                        "description": "Natural language navigation instruction in Chinese or English"
                    }
                },
                "required": ["instruction"]
            }
        )
    ]


@app.call_tool()
async def handle_call_tool(
    name: str,
    arguments: dict[str, Any]
) -> list[types.TextContent]:
    """处理工具调用"""

    try:
        if name == "navigate_to_pose":
            x = arguments["x"]
            y = arguments["y"]
            yaw = arguments.get("yaw", 0.0)
            wait = arguments.get("wait", True)

            result = await nav_client.navigate_to_pose(x, y, yaw, wait)

            return [types.TextContent(
                type="text",
                text=f"{'✅ Navigation completed' if result['success'] else '❌ Navigation failed'}\n"
                     f"Message: {result['message']}\n"
                     f"Distance: {result.get('distance', 0):.2f}m\n"
                     f"Time: {result.get('time', 0):.1f}s"
            )]

        elif name == "navigate_to_location":
            location = arguments["location"]
            wait = arguments.get("wait", True)

            result = await nav_client.navigate_to_location(location, wait)

            if not result['success'] and 'available_locations' in result:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Unknown location: {location}\n"
                         f"Available locations: {', '.join(result['available_locations'])}"
                )]

            return [types.TextContent(
                type="text",
                text=f"{'✅ Reached' if result['success'] else '❌ Failed to reach'} location: {location}\n"
                     f"Distance: {result.get('distance', 0):.2f}m\n"
                     f"Time: {result.get('time', 0):.1f}s"
            )]

        elif name == "navigate_through_waypoints":
            waypoints = arguments["waypoints"]
            loop = arguments.get("loop", False)

            result = await nav_client.navigate_waypoints(waypoints, loop)

            return [types.TextContent(
                type="text",
                text=f"Waypoint navigation: {len(result['completed'])}/{result['total']} completed\n"
                     f"Completed: {result['completed']}\n"
                     f"Failed: {result['failed']}\n"
                     f"Status: {'✅ Success' if result['success'] else '⚠️ Partial success'}"
            )]

        elif name == "get_navigation_status":
            status = await nav_client.get_status()

            status_emoji = {
                'IDLE': '⏸️',
                'NAVIGATING': '🚀',
                'SUCCEEDED': '✅',
                'FAILED': '❌',
                'CANCELED': '⛔'
            }.get(status['status'], '❓')

            text = f"{status_emoji} Status: {status['status']}\n"
            text += f"📍 Current position: ({status['current_pose']['x']:.2f}, {status['current_pose']['y']:.2f})\n"
            text += f"   Orientation: {status['current_pose']['yaw_deg']:.1f}°\n"

            if status['target_pose']:
                text += f"🎯 Target position: ({status['target_pose']['x']:.2f}, {status['target_pose']['y']:.2f})\n"
                text += f"📏 Distance remaining: {status['distance_remaining']:.2f}m\n"
                text += f"⏱️  Time elapsed: {status['navigation_time']:.1f}s\n"
                text += f"⏳ Estimated remaining: {status['estimated_time_remaining']:.1f}s\n"
                text += f"📊 Progress: {status.get('progress', 0):.1f}%"

            return [types.TextContent(type="text", text=text)]

        elif name == "cancel_navigation":
            result = await nav_client.cancel()
            return [types.TextContent(
                type="text",
                text=f"{'✅' if result['success'] else '❌'} {result['message']}"
            )]

        elif name == "set_initial_pose":
            x, y, yaw = arguments["x"], arguments["y"], arguments["yaw"]
            await nav_client.set_initial_pose(x, y, yaw)
            return [types.TextContent(
                type="text",
                text=f"✅ Initial pose set to:\n"
                     f"   Position: ({x:.2f}, {y:.2f})\n"
                     f"   Orientation: {yaw:.3f} rad ({yaw * 57.3:.1f}°)"
            )]

        elif name == "get_semantic_locations":
            locations = nav_client.get_semantic_locations()
            text = "📍 Available semantic locations:\n\n"
            for name, pose in locations.items():
                text += f"  • {name}: ({pose['x']:.1f}, {pose['y']:.1f}), {pose['yaw_deg']:.0f}°\n"
            return [types.TextContent(type="text", text=text)]

        elif name == "add_semantic_location":
            name_loc = arguments["name"]
            x, y = arguments["x"], arguments["y"]
            yaw = arguments.get("yaw", 0.0)
            nav_client.add_semantic_location(name_loc, x, y, yaw)
            return [types.TextContent(
                type="text",
                text=f"✅ Added location '{name_loc}' at ({x:.2f}, {y:.2f})"
            )]

        elif name == "natural_language_navigate":
            instruction = arguments["instruction"]

            # 使用LLM解析自然语言
            parsed = await parse_navigation_intent(instruction)

            if parsed.get("action") == "unknown":
                return [types.TextContent(
                    type="text",
                    text=f"❓ Cannot understand instruction: {instruction}\n"
                         f"Message: {parsed.get('message', 'Unknown intent')}"
                )]

            if parsed.get("action") == "error":
                return [types.TextContent(
                    type="text",
                    text=f"❌ Error: {parsed.get('message', 'Unknown error')}"
                )]

            # 根据解析结果执行相应的导航命令
            action = parsed["action"]

            if action == "navigate_to_pose":
                result = await nav_client.navigate_to_pose(
                    parsed["x"],
                    parsed["y"],
                    parsed.get("yaw", 0.0)
                )
            elif action == "navigate_to_location":
                result = await nav_client.navigate_to_location(parsed["location"])
            elif action == "navigate_waypoints":
                result = await nav_client.navigate_waypoints(parsed["waypoints"])
            elif action == "cancel":
                result = await nav_client.cancel()
            elif action == "get_status":
                result = await nav_client.get_status()
            elif action == "set_initial_pose":
                await nav_client.set_initial_pose(
                    parsed["x"],
                    parsed["y"],
                    parsed["yaw"]
                )
                result = {"success": True, "message": "Initial pose set"}
            else:
                result = {"success": False, "message": f"Unknown action: {action}"}

            return [types.TextContent(
                type="text",
                text=f"🤖 Understood: {instruction}\n"
                     f"📋 Parsed action: {action}\n"
                     f"{'✅' if result.get('success') else '❌'} {result.get('message', json.dumps(result, ensure_ascii=False))}"
            )]

    except Exception as e:
        return [types.TextContent(
            type="text",
            text=f"❌ Error executing {name}: {str(e)}"
        )]

    raise ValueError(f"Unknown tool: {name}")


@app.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    """列出所有可用资源"""
    return [
        types.Resource(
            uri="robot://current_pose",
            name="Current Robot Pose",
            description="Real-time robot position and orientation",
            mimeType="application/json"
        ),
        types.Resource(
            uri="robot://navigation_feedback",
            name="Navigation Feedback",
            description="Live navigation feedback during active navigation",
            mimeType="application/json"
        ),
        types.Resource(
            uri="robot://semantic_locations",
            name="Semantic Locations",
            description="All available semantic locations",
            mimeType="application/json"
        )
    ]


@app.read_resource()
async def handle_read_resource(uri: str) -> str:
    """读取资源"""
    if uri == "robot://current_pose":
        pose = await nav_client.get_current_pose()
        return json.dumps(pose, indent=2, ensure_ascii=False)

    elif uri == "robot://navigation_feedback":
        feedback = await nav_client.get_feedback()
        return json.dumps(feedback, indent=2, ensure_ascii=False)

    elif uri == "robot://semantic_locations":
        locations = nav_client.get_semantic_locations()
        return json.dumps(locations, indent=2, ensure_ascii=False)

    raise ValueError(f"Unknown resource: {uri}")


async def main():
    """主函数"""
    global nav_client, llm_service

    print("🤖 Wheeltec Navigation MCP Server (Simulator)")
    print("=" * 50)

    # 初始化模拟导航客户端
    nav_client = MockNavigationClient()
    await nav_client.initialize()

    # 初始化LLM服务
    try:
        llm_service = get_openrouter_service()
        print("✅ OpenRouter LLM service initialized (Llama 70B)")
    except Exception as e:
        print(f"⚠️  Warning: {e}")
        print("   Natural language navigation will not be available")
        llm_service = None

    print("=" * 50)
    print("🚀 MCP Server ready!\n")

    # 运行MCP服务器
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="wheeltec-navigation-simulator",
                server_version="1.0.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                )
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
