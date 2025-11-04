#!/usr/bin/env python3
"""
WebSocket 客户端测试脚本
测试与 Multi-Agent System 的 WebSocket 连接和交互
"""

import asyncio
import json
import sys
import websockets
from typing import Optional


class TestClient:
    """WebSocket 测试客户端"""

    def __init__(self, url: str = "ws://localhost:8000/ws"):
        """
        初始化测试客户端

        Args:
            url: WebSocket URL
        """
        self.url = url
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None

    async def connect(self):
        """建立 WebSocket 连接"""
        print(f"\n🔌 Connecting to {self.url}...")
        try:
            self.websocket = await websockets.connect(self.url)
            print("✓ Connected successfully!")
            return True
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            return False

    async def disconnect(self):
        """断开连接"""
        if self.websocket:
            await self.websocket.close()
            print("\n👋 Disconnected")

    async def send_text_message(self, text: str):
        """
        发送文本消息

        Args:
            text: 文本内容
        """
        if not self.websocket:
            print("✗ Not connected")
            return

        message = {
            "type": "text",
            "content": text
        }

        print(f"\n📤 Sending: {text}")
        await self.websocket.send(json.dumps(message))

    async def send_control_command(self, command: str):
        """
        发送控制命令

        Args:
            command: 控制命令
        """
        if not self.websocket:
            print("✗ Not connected")
            return

        message = {
            "type": "control",
            "command": command
        }

        print(f"\n🎮 Sending control command: {command}")
        await self.websocket.send(json.dumps(message))

    async def receive_messages(self):
        """接收并处理消息"""
        if not self.websocket:
            return

        try:
            async for message in self.websocket:
                data = json.loads(message)
                await self.handle_message(data)

        except websockets.exceptions.ConnectionClosed:
            print("\n🔌 Connection closed by server")
        except Exception as e:
            print(f"\n✗ Error receiving messages: {e}")

    async def handle_message(self, data: dict):
        """
        处理接收到的消息

        Args:
            data: 消息数据
        """
        message_type = data.get("type")

        if message_type == "connection":
            print(f"\n✓ {data.get('message')}")
            print(f"Session ID: {data.get('session_id')}")

        elif message_type == "transcript":
            text = data.get("text")
            is_final = data.get("is_final")
            status = "✓" if is_final else "..."
            print(f"\n📝 Transcript [{status}]: {text}")

        elif message_type == "agent_status":
            status = data.get("status")
            message = data.get("message", "")
            print(f"\n🤖 Agent Status: {status}")
            if message:
                print(f"   {message}")

        elif message_type == "agent_response":
            chunk = data.get("chunk")
            is_streaming = data.get("is_streaming")

            if is_streaming:
                # 流式输出
                print(chunk, end="", flush=True)
            else:
                # 响应完成
                full_response = data.get("full_response")
                print("\n\n✓ Response completed")
                if data.get("status") == "completed":
                    print("Status: Completed")

        elif message_type == "control":
            status = data.get("status")
            print(f"\n🎮 Control: {status}")

        elif message_type == "error":
            error_message = data.get("message")
            print(f"\n✗ Error: {error_message}")

        else:
            print(f"\n❓ Unknown message type: {message_type}")
            print(f"   Data: {data}")

    async def run_interactive_test(self):
        """运行交互式测试"""
        if not await self.connect():
            return

        print("\n" + "="*60)
        print("Interactive WebSocket Client")
        print("="*60)
        print("\nCommands:")
        print("  - Type any text to send to the agent")
        print("  - Type 'quit' or 'exit' to disconnect")
        print("  - Type 'reset' to reset conversation")
        print("="*60)

        # 启动消息接收任务
        receive_task = asyncio.create_task(self.receive_messages())

        try:
            while True:
                # 从标准输入读取
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None, input, "\n💬 You: "
                )

                if user_input.lower() in ['quit', 'exit']:
                    print("\n👋 Exiting...")
                    break

                elif user_input.lower() == 'reset':
                    await self.send_control_command("reset_conversation")

                elif user_input.strip():
                    await self.send_text_message(user_input)
                    print("\n🤖 Agent: ", end="", flush=True)

        except KeyboardInterrupt:
            print("\n\n⏹️  Interrupted by user")

        finally:
            receive_task.cancel()
            await self.disconnect()

    async def run_automated_test(self):
        """运行自动化测试"""
        if not await self.connect():
            return

        print("\n" + "="*60)
        print("Automated Test Sequence")
        print("="*60)

        # 启动消息接收任务
        receive_task = asyncio.create_task(self.receive_messages())

        # 等待连接消息
        await asyncio.sleep(1)

        # 测试消息列表
        test_messages = [
            "Hello! Can you introduce yourself?",
            "What's 2 + 2?",
            "Tell me a short joke.",
        ]

        try:
            for i, message in enumerate(test_messages, 1):
                print(f"\n{'='*60}")
                print(f"Test {i}/{len(test_messages)}")
                print(f"{'='*60}")

                await self.send_text_message(message)
                print("\n🤖 Agent: ", end="", flush=True)

                # 等待响应完成
                await asyncio.sleep(10)

            print(f"\n\n{'='*60}")
            print("All tests completed!")
            print(f"{'='*60}")

        except Exception as e:
            print(f"\n✗ Test error: {e}")

        finally:
            receive_task.cancel()
            await asyncio.sleep(1)
            await self.disconnect()


async def main():
    """主函数"""
    # 解析命令行参数
    if len(sys.argv) > 1:
        if sys.argv[1] == "--auto":
            mode = "auto"
        elif sys.argv[1] == "--url" and len(sys.argv) > 2:
            url = sys.argv[2]
            mode = "interactive"
        else:
            print("Usage:")
            print("  python test_client.py                 # Interactive mode")
            print("  python test_client.py --auto          # Automated test")
            print("  python test_client.py --url <url>     # Custom URL")
            return
    else:
        mode = "interactive"

    # 创建客户端
    client = TestClient()

    # 运行测试
    if mode == "auto":
        await client.run_automated_test()
    else:
        await client.run_interactive_test()


if __name__ == "__main__":
    print("\n🚀 Multi-Agent System WebSocket Test Client")
    print("="*60)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
