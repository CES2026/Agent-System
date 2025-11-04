"""
LLAMA 3 Agent 实现
使用 OpenRouter 的 LLAMA 3 70B 模型
"""

import logging
from typing import AsyncGenerator
from backend.agents.base import BaseAgent, AgentState
from backend.services.openrouter_service import get_openrouter_service

logger = logging.getLogger(__name__)


class LlamaAgent(BaseAgent):
    """LLAMA 3 70B Agent"""

    def __init__(
        self,
        name: str = "Llama3Agent",
        system_prompt: str = None
    ):
        """
        初始化 LLAMA Agent

        Args:
            name: Agent 名称
            system_prompt: 系统提示词
        """
        default_prompt = """You are a helpful AI assistant powered by LLAMA 3 70B.
You are part of a multi-agent system that processes voice input from users.

Your role is to:
1. Understand and respond to user queries accurately
2. Provide helpful, relevant, and concise responses
3. Maintain context across the conversation
4. Be friendly and professional

Always respond in a clear and natural way that would work well when read aloud."""

        super().__init__(
            name=name,
            system_prompt=system_prompt or default_prompt
        )
        self.openrouter_service = get_openrouter_service()
        logger.info(f"LLAMA Agent initialized: {self.name}")

    async def process(self, state: AgentState) -> AgentState:
        """
        处理用户输入并生成响应

        Args:
            state: 当前状态

        Returns:
            更新后的状态
        """
        try:
            current_input = state.get("current_input", "")

            if not current_input:
                logger.warning("No input to process")
                state["error"] = "No input provided"
                return state

            logger.info(f"Processing input: {current_input[:100]}...")

            # 设置处理状态
            state["processing_state"] = "processing"

            # 获取上下文消息
            context_messages = self.get_context_messages(state)

            # 添加当前用户输入
            context_messages.append({
                "role": "user",
                "content": current_input
            })

            # 生成响应（非流式）
            response = await self.openrouter_service.generate_response(
                message=current_input,
                system_prompt=self.system_prompt,
            )

            # 更新状态
            state["agent_response"] = response
            state["processing_state"] = "responding"

            # 更新对话历史
            state["conversation_history"] = self.update_conversation_history(
                state, current_input, response
            )

            # 添加消息到消息历史
            state["messages"].append(self.create_message(current_input, "human"))
            state["messages"].append(self.create_message(response, "ai"))

            logger.info(f"Generated response: {response[:100]}...")

            return state

        except Exception as e:
            logger.error(f"Error in LLAMA Agent processing: {e}", exc_info=True)
            state["error"] = str(e)
            state["processing_state"] = "error"
            return state

    async def process_streaming(
        self,
        state: AgentState
    ) -> AsyncGenerator[tuple[str, AgentState], None]:
        """
        处理用户输入并生成流式响应

        Args:
            state: 当前状态

        Yields:
            (响应片段, 更新后的状态) 元组
        """
        try:
            current_input = state.get("current_input", "")

            if not current_input:
                logger.warning("No input to process")
                state["error"] = "No input provided"
                yield "", state
                return

            logger.info(f"Processing streaming input: {current_input[:100]}...")

            # 设置处理状态
            state["processing_state"] = "processing"

            # 获取上下文消息
            context_messages = self.get_context_messages(state)

            # 添加当前用户输入
            context_messages.append({
                "role": "user",
                "content": current_input
            })

            # 收集完整响应
            full_response = ""

            # 生成流式响应
            async for chunk in self.openrouter_service.generate_streaming_response(
                message=current_input,
                system_prompt=self.system_prompt,
            ):
                full_response += chunk
                state["agent_response"] = full_response
                state["processing_state"] = "responding"
                yield chunk, state

            # 更新对话历史
            state["conversation_history"] = self.update_conversation_history(
                state, current_input, full_response
            )

            # 添加消息到消息历史
            state["messages"].append(self.create_message(current_input, "human"))
            state["messages"].append(self.create_message(full_response, "ai"))

            state["processing_state"] = "idle"
            logger.info(f"Streaming response complete: {full_response[:100]}...")

        except Exception as e:
            logger.error(f"Error in LLAMA Agent streaming: {e}", exc_info=True)
            state["error"] = str(e)
            state["processing_state"] = "error"
            yield "", state


# 创建全局 Agent 实例
_llama_agent = None


def get_llama_agent() -> LlamaAgent:
    """获取 LLAMA Agent 实例（单例模式）"""
    global _llama_agent
    if _llama_agent is None:
        _llama_agent = LlamaAgent()
    return _llama_agent


if __name__ == "__main__":
    # 测试 Agent 创建
    agent = get_llama_agent()
    print(f"LLAMA Agent created: {agent.name}")
