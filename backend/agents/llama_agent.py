"""
LLAMA 3 Agent 实现
使用 OpenRouter 的 LLAMA 3 70B 模型 + LangChain Function Calling
"""

import logging
from typing import AsyncGenerator, List
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import BaseTool

from backend.agents.base import BaseAgent, AgentState
from backend.tools.navigation_tool import get_navigation_tool
from backend.config import get_settings

logger = logging.getLogger(__name__)


class LlamaAgent(BaseAgent):
    """LLAMA 3 70B Agent"""

    def __init__(
        self,
        name: str = "Llama3Agent",
        system_prompt: str = None
    ):
        """
        初始化 LLAMA Agent with Function Calling

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
5. Use the available tools when appropriate (especially for robot navigation requests)

When users ask about navigation or movement (like "去厨房", "前进2米", "向左转"), use the robot_navigation tool.

Always respond in a clear and natural way that would work well when read aloud."""

        super().__init__(
            name=name,
            system_prompt=system_prompt or default_prompt
        )

        # 获取配置
        settings = get_settings()

        # 初始化 ChatOpenAI with OpenRouter
        self.llm = ChatOpenAI(
            base_url=settings.openrouter_base_url,
            api_key=settings.openrouter_api_key,
            model=settings.openrouter_model,
            temperature=settings.llm_temperature,
            streaming=True,
        )

        # 注册工具
        self.tools: List[BaseTool] = [
            get_navigation_tool()
        ]

        # 创建提示模板
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        # 创建 Function Calling Agent
        self.agent = create_openai_functions_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=self.prompt
        )

        # 创建 AgentExecutor
        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=3,
        )

        logger.info(f"LLAMA Agent initialized with {len(self.tools)} tools: {self.name}")

    async def process(self, state: AgentState) -> AgentState:
        """
        处理用户输入并生成响应（使用Function Calling）

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

            logger.info(f"Processing input with Function Calling: {current_input[:100]}...")

            # 设置处理状态
            state["processing_state"] = "processing"

            # 获取对话历史（转换为LangChain格式）
            chat_history = []
            for msg in state.get("conversation_history", []):
                if msg["role"] == "user":
                    chat_history.append(("human", msg["content"]))
                elif msg["role"] == "assistant":
                    chat_history.append(("ai", msg["content"]))

            # 使用AgentExecutor执行
            result = await self.agent_executor.ainvoke({
                "input": current_input,
                "chat_history": chat_history
            })

            response = result.get("output", "")

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
            state["agent_response"] = f"Sorry, an error occurred while processing your request: {str(e)}"
            return state

    async def process_streaming(
        self,
        state: AgentState
    ) -> AsyncGenerator[tuple[str, AgentState], None]:
        """
        处理用户输入并生成流式响应（使用Function Calling + Streaming）

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

            logger.info(f"Processing streaming input with Function Calling: {current_input[:100]}...")

            # 设置处理状态
            state["processing_state"] = "processing"

            # 获取对话历史（转换为LangChain格式）
            chat_history = []
            for msg in state.get("conversation_history", []):
                if msg["role"] == "user":
                    chat_history.append(("human", msg["content"]))
                elif msg["role"] == "assistant":
                    chat_history.append(("ai", msg["content"]))

            # 收集完整响应
            full_response = ""
            tool_called = False

            # 使用astream_events来获取流式输出
            async for event in self.agent_executor.astream_events(
                {
                    "input": current_input,
                    "chat_history": chat_history
                },
                version="v1"
            ):
                kind = event.get("event")

                # 处理工具调用事件
                if kind == "on_tool_start":
                    tool_name = event.get("name", "")
                    logger.info(f"Tool called: {tool_name}")
                    tool_called = True
                    # 可以选择性地向用户通知工具正在执行
                    # yield f"[正在执行: {tool_name}]", state

                # 处理LLM输出流
                elif kind == "on_chat_model_stream":
                    content = event.get("data", {}).get("chunk", {}).content
                    if content:
                        full_response += content
                        state["agent_response"] = full_response
                        state["processing_state"] = "responding"
                        yield content, state

                # 捕获最终输出（用于工具调用后的响应）
                elif kind == "on_chain_end":
                    # 检查是否是AgentExecutor的最终输出
                    if event.get("name") == "AgentExecutor":
                        output_data = event.get("data", {}).get("output", {})

                        # 如果还没有收到流式响应，从最终输出中获取
                        if not full_response:
                            if isinstance(output_data, dict):
                                final_output = output_data.get("output", "")
                            else:
                                final_output = str(output_data)

                            if final_output:
                                full_response = final_output
                                state["agent_response"] = full_response
                                state["processing_state"] = "responding"
                                yield full_response, state
                                logger.info(f"Got final output from chain end: {full_response[:100]}...")

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
            state["agent_response"] = f"Sorry, an error occurred while processing your request: {str(e)}"
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
