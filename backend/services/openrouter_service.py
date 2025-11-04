"""
OpenRouter 服务模块
提供与 OpenRouter API 交互的功能，支持流式和非流式响应
"""

import asyncio
from typing import AsyncGenerator, Optional, Dict, Any
from openai import AsyncOpenAI
import logging

from backend.config import get_settings

logger = logging.getLogger(__name__)


class OpenRouterService:
    """OpenRouter API 客户端服务"""

    def __init__(self):
        """初始化 OpenRouter 客户端"""
        self.settings = get_settings()
        self.client = AsyncOpenAI(
            base_url=self.settings.openrouter_base_url,
            api_key=self.settings.openrouter_api_key,
        )
        self.model = self.settings.openrouter_model
        logger.info(f"OpenRouter service initialized with model: {self.model}")

    async def generate_response(
        self,
        message: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        生成非流式响应

        Args:
            message: 用户消息
            system_prompt: 系统提示词
            temperature: 温度参数
            max_tokens: 最大 token 数

        Returns:
            生成的响应文本
        """
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": message})

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature or self.settings.llm_temperature,
                max_tokens=max_tokens or self.settings.llm_max_tokens,
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            raise

    async def generate_streaming_response(
        self,
        message: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """
        生成流式响应

        Args:
            message: 用户消息
            system_prompt: 系统提示词
            temperature: 温度参数
            max_tokens: 最大 token 数

        Yields:
            响应文本的增量片段
        """
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": message})

            logger.info(f"Generating streaming response for message: {message[:50]}...")

            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature or self.settings.llm_temperature,
                max_tokens=max_tokens or self.settings.llm_max_tokens,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"Error generating streaming response: {e}")
            raise

    async def generate_with_conversation_history(
        self,
        messages: list[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = True,
    ) -> AsyncGenerator[str, None] | str:
        """
        根据对话历史生成响应

        Args:
            messages: 对话历史列表 [{"role": "user", "content": "..."}, ...]
            temperature: 温度参数
            max_tokens: 最大 token 数
            stream: 是否流式返回

        Returns:
            流式生成器或完整响应文本
        """
        try:
            if stream:
                stream_response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature or self.settings.llm_temperature,
                    max_tokens=max_tokens or self.settings.llm_max_tokens,
                    stream=True,
                )

                async for chunk in stream_response:
                    if chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
            else:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature or self.settings.llm_temperature,
                    max_tokens=max_tokens or self.settings.llm_max_tokens,
                )
                return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Error generating response with history: {e}")
            raise


# 创建全局服务实例
_openrouter_service: Optional[OpenRouterService] = None


def get_openrouter_service() -> OpenRouterService:
    """获取 OpenRouter 服务实例（单例模式）"""
    global _openrouter_service
    if _openrouter_service is None:
        _openrouter_service = OpenRouterService()
    return _openrouter_service


# 测试代码
async def test_openrouter_service():
    """测试 OpenRouter 服务"""
    service = get_openrouter_service()

    print("\n" + "="*60)
    print("Testing OpenRouter Service")
    print("="*60)

    # 测试流式响应
    print("\nTesting streaming response...")
    message = "Tell me a short joke about AI."

    async for chunk in service.generate_streaming_response(message):
        print(chunk, end="", flush=True)

    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(test_openrouter_service())
