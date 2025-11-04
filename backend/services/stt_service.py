"""
AssemblyAI STT (Speech-to-Text) 服务模块
提供实时语音转文本功能，支持 WebSocket 音频流
"""

import asyncio
import logging
from typing import Callable, Optional, AsyncGenerator
from assemblyai.streaming.v3 import (
    BeginEvent,
    StreamingClient,
    StreamingClientOptions,
    StreamingError,
    StreamingEvents,
    StreamingParameters,
    StreamingSessionParameters,
    TerminationEvent,
    TurnEvent,
)

from backend.config import get_settings

logger = logging.getLogger(__name__)


class STTService:
    """AssemblyAI 实时语音转文本服务"""

    def __init__(self):
        """初始化 STT 服务"""
        self.settings = get_settings()
        self.client: Optional[StreamingClient] = None
        self.is_connected = False
        self.transcript_callback: Optional[Callable] = None
        logger.info("STT service initialized")

    def create_client(self) -> StreamingClient:
        """创建 AssemblyAI streaming 客户端"""
        client = StreamingClient(
            StreamingClientOptions(
                api_key=self.settings.assemblyai_api_key,
                api_host=self.settings.assemblyai_api_host,
            )
        )
        return client

    async def start_streaming(
        self,
        on_transcript: Callable[[str, bool], None],
        on_error: Optional[Callable[[str], None]] = None,
    ):
        """
        启动实时转录服务

        Args:
            on_transcript: 转录回调函数 (text: str, is_final: bool)
            on_error: 错误回调函数
        """
        try:
            self.transcript_callback = on_transcript
            self.client = self.create_client()

            # 注册事件处理器
            self.client.on(StreamingEvents.Begin, self._on_begin)
            self.client.on(StreamingEvents.Turn, self._on_turn)
            self.client.on(StreamingEvents.Termination, self._on_terminated)
            self.client.on(StreamingEvents.Error, self._on_error)

            # 连接到服务
            self.client.connect(
                StreamingParameters(
                    sample_rate=self.settings.assemblyai_sample_rate,
                    format_turns=True
                )
            )

            self.is_connected = True
            logger.info("STT streaming started successfully")

        except Exception as e:
            logger.error(f"Error starting STT streaming: {e}")
            if on_error:
                on_error(str(e))
            raise

    def _on_begin(self, client, event: BeginEvent):
        """处理会话开始事件"""
        logger.info(f"STT session started: {event.id}")

    def _on_turn(self, client, event: TurnEvent):
        """处理转录事件"""
        if event.transcript and self.transcript_callback:
            logger.debug(f"Transcript: {event.transcript} (final: {event.end_of_turn})")
            self.transcript_callback(event.transcript, event.end_of_turn)

        # 请求格式化的转录结果
        if event.end_of_turn and not event.turn_is_formatted:
            params = StreamingSessionParameters(format_turns=True)
            client.set_params(params)

    def _on_terminated(self, client, event: TerminationEvent):
        """处理会话终止事件"""
        logger.info(f"STT session terminated: {event.audio_duration_seconds}s processed")
        self.is_connected = False

    def _on_error(self, client, error: StreamingError):
        """处理错误事件"""
        logger.error(f"STT error: {error}")

    async def send_audio(self, audio_data: bytes):
        """
        发送音频数据到 AssemblyAI

        Args:
            audio_data: 音频数据（PCM 格式）
        """
        if not self.is_connected or not self.client:
            raise RuntimeError("STT service is not connected")

        try:
            self.client.send_audio(audio_data)
        except Exception as e:
            logger.error(f"Error sending audio: {e}")
            raise

    async def stop_streaming(self):
        """停止转录服务"""
        if self.client and self.is_connected:
            try:
                self.client.disconnect(terminate=True)
                self.is_connected = False
                logger.info("STT streaming stopped")
            except Exception as e:
                logger.error(f"Error stopping STT streaming: {e}")


class STTServiceManager:
    """STT 服务管理器，用于 WebSocket 连接"""

    def __init__(self):
        """初始化服务管理器"""
        self.active_services: dict[str, STTService] = {}
        logger.info("STT service manager initialized")

    async def create_service(self, session_id: str) -> STTService:
        """
        创建新的 STT 服务实例

        Args:
            session_id: 会话 ID

        Returns:
            STT 服务实例
        """
        if session_id in self.active_services:
            logger.warning(f"Service already exists for session {session_id}")
            return self.active_services[session_id]

        service = STTService()
        self.active_services[session_id] = service
        logger.info(f"Created STT service for session {session_id}")
        return service

    async def remove_service(self, session_id: str):
        """
        移除 STT 服务实例

        Args:
            session_id: 会话 ID
        """
        if session_id in self.active_services:
            service = self.active_services[session_id]
            await service.stop_streaming()
            del self.active_services[session_id]
            logger.info(f"Removed STT service for session {session_id}")

    async def get_service(self, session_id: str) -> Optional[STTService]:
        """
        获取 STT 服务实例

        Args:
            session_id: 会话 ID

        Returns:
            STT 服务实例或 None
        """
        return self.active_services.get(session_id)


# 创建全局服务管理器实例
_stt_service_manager: Optional[STTServiceManager] = None


def get_stt_service_manager() -> STTServiceManager:
    """获取 STT 服务管理器实例（单例模式）"""
    global _stt_service_manager
    if _stt_service_manager is None:
        _stt_service_manager = STTServiceManager()
    return _stt_service_manager


if __name__ == "__main__":
    # 基础测试
    logging.basicConfig(level=logging.INFO)
    service = STTService()
    print("STT Service created successfully")
