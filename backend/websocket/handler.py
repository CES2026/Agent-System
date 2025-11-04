"""
WebSocket 处理器
处理客户端 WebSocket 连接，整合 STT 和 Agent 系统
"""

import asyncio
import json
import logging
import uuid
from typing import Optional
from fastapi import WebSocket, WebSocketDisconnect

from backend.services.stt_service import get_stt_service_manager, STTService
from backend.agents.base import create_initial_state
from backend.agents.graph import get_streaming_agent_graph

logger = logging.getLogger(__name__)


class WebSocketHandler:
    """WebSocket 连接处理器"""

    def __init__(self, websocket: WebSocket):
        """
        初始化 WebSocket 处理器

        Args:
            websocket: FastAPI WebSocket 对象
        """
        self.websocket = websocket
        self.session_id = str(uuid.uuid4())
        self.stt_service: Optional[STTService] = None
        self.agent_graph = get_streaming_agent_graph()
        self.stt_manager = get_stt_service_manager()
        self.is_processing_agent = False
        self.pending_transcript = ""
        logger.info(f"WebSocket handler created for session: {self.session_id}")

    async def connect(self):
        """建立 WebSocket 连接"""
        await self.websocket.accept()
        logger.info(f"WebSocket connected: {self.session_id}")

        # 发送连接成功消息
        await self.send_message({
            "type": "connection",
            "status": "connected",
            "session_id": self.session_id,
            "message": "Connected to Multi-Agent System"
        })

    async def disconnect(self):
        """断开 WebSocket 连接"""
        try:
            # 停止 STT 服务
            if self.stt_service:
                await self.stt_service.stop_streaming()
                await self.stt_manager.remove_service(self.session_id)

            logger.info(f"WebSocket disconnected: {self.session_id}")

        except Exception as e:
            logger.error(f"Error during disconnect: {e}")

    async def send_message(self, data: dict):
        """
        发送消息到客户端

        Args:
            data: 消息数据
        """
        try:
            await self.websocket.send_json(data)
        except Exception as e:
            logger.error(f"Error sending message: {e}")

    async def on_transcript(self, text: str, is_final: bool):
        """
        处理 STT 转录结果

        Args:
            text: 转录文本
            is_final: 是否为最终结果
        """
        try:
            # 发送转录结果到客户端
            await self.send_message({
                "type": "transcript",
                "text": text,
                "is_final": is_final
            })

            # 如果是最终结果且不在处理中，触发 Agent 处理
            if is_final and not self.is_processing_agent:
                self.pending_transcript = text
                await self.process_with_agent(text)

        except Exception as e:
            logger.error(f"Error handling transcript: {e}")

    async def process_with_agent(self, text: str):
        """
        使用 Agent 处理转录文本

        Args:
            text: 转录文本
        """
        try:
            self.is_processing_agent = True

            # 通知客户端开始处理
            await self.send_message({
                "type": "agent_status",
                "status": "processing",
                "message": "Agent is processing your request..."
            })

            # 创建 Agent 状态
            state = create_initial_state(self.session_id)
            state["current_input"] = text

            # 流式处理并发送响应
            full_response = ""

            async for chunk, updated_state in self.agent_graph.process_streaming(state):
                if chunk:
                    full_response += chunk
                    # 发送响应片段到客户端
                    await self.send_message({
                        "type": "agent_response",
                        "chunk": chunk,
                        "is_streaming": True
                    })

            # 发送完成消息
            await self.send_message({
                "type": "agent_response",
                "chunk": "",
                "is_streaming": False,
                "full_response": full_response,
                "status": "completed"
            })

            logger.info(f"Agent processing completed: {full_response[:100]}...")

        except Exception as e:
            logger.error(f"Error processing with agent: {e}", exc_info=True)
            await self.send_message({
                "type": "error",
                "message": f"Agent processing error: {str(e)}"
            })

        finally:
            self.is_processing_agent = False

    async def handle_audio_message(self, audio_data: bytes):
        """
        处理音频数据消息

        Args:
            audio_data: 音频数据
        """
        try:
            # 如果 STT 服务未启动，先启动
            if not self.stt_service:
                self.stt_service = await self.stt_manager.create_service(self.session_id)
                await self.stt_service.start_streaming(
                    on_transcript=self.on_transcript
                )

            # 发送音频数据到 STT 服务
            await self.stt_service.send_audio(audio_data)

        except Exception as e:
            logger.error(f"Error handling audio message: {e}")
            await self.send_message({
                "type": "error",
                "message": f"Audio processing error: {str(e)}"
            })

    async def handle_text_message(self, text: str):
        """
        处理文本消息（直接发送到 Agent，不经过 STT）

        Args:
            text: 文本内容
        """
        try:
            logger.info(f"Received text message: {text[:100]}...")
            await self.process_with_agent(text)

        except Exception as e:
            logger.error(f"Error handling text message: {e}")
            await self.send_message({
                "type": "error",
                "message": f"Text processing error: {str(e)}"
            })

    async def handle_control_message(self, control: dict):
        """
        处理控制消息

        Args:
            control: 控制命令
        """
        try:
            command = control.get("command")

            if command == "start_stt":
                # 启动 STT 服务
                if not self.stt_service:
                    self.stt_service = await self.stt_manager.create_service(self.session_id)
                    await self.stt_service.start_streaming(
                        on_transcript=self.on_transcript
                    )
                    await self.send_message({
                        "type": "control",
                        "status": "stt_started"
                    })

            elif command == "stop_stt":
                # 停止 STT 服务
                if self.stt_service:
                    await self.stt_service.stop_streaming()
                    await self.stt_manager.remove_service(self.session_id)
                    self.stt_service = None
                    await self.send_message({
                        "type": "control",
                        "status": "stt_stopped"
                    })

            elif command == "reset_conversation":
                # 重置对话历史
                await self.send_message({
                    "type": "control",
                    "status": "conversation_reset"
                })

        except Exception as e:
            logger.error(f"Error handling control message: {e}")
            await self.send_message({
                "type": "error",
                "message": f"Control command error: {str(e)}"
            })

    async def handle_message(self, message):
        """
        处理接收到的消息

        Args:
            message: 消息内容（可以是 JSON 或二进制）
        """
        try:
            # 如果是二进制数据，假定为音频
            if isinstance(message, bytes):
                await self.handle_audio_message(message)
                return

            # 如果是 JSON 字符串，解析并处理
            if isinstance(message, str):
                data = json.loads(message)
                message_type = data.get("type")

                if message_type == "text":
                    await self.handle_text_message(data.get("content", ""))

                elif message_type == "control":
                    await self.handle_control_message(data)

                else:
                    logger.warning(f"Unknown message type: {message_type}")

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            await self.send_message({
                "type": "error",
                "message": "Invalid JSON format"
            })

        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            await self.send_message({
                "type": "error",
                "message": str(e)
            })

    async def run(self):
        """
        运行 WebSocket 处理循环
        """
        try:
            await self.connect()

            while True:
                # 接收消息
                message = await self.websocket.receive()

                # 处理不同类型的消息
                if "text" in message:
                    await self.handle_message(message["text"])
                elif "bytes" in message:
                    await self.handle_message(message["bytes"])

        except WebSocketDisconnect:
            logger.info(f"Client disconnected: {self.session_id}")
            await self.disconnect()

        except Exception as e:
            logger.error(f"WebSocket error: {e}", exc_info=True)
            await self.disconnect()


async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 端点处理函数

    Args:
        websocket: FastAPI WebSocket 对象
    """
    handler = WebSocketHandler(websocket)
    await handler.run()
