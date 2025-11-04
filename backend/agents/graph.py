"""
LangGraph 工作流定义
定义多 Agent 系统的执行图和工作流
"""

import logging
from typing import AsyncGenerator
from langgraph.graph import StateGraph, END
from backend.agents.base import AgentState, create_initial_state
from backend.agents.llama_agent import get_llama_agent

logger = logging.getLogger(__name__)


class AgentGraph:
    """Agent 系统工作流图"""

    def __init__(self):
        """初始化 Agent 图"""
        self.llama_agent = get_llama_agent()
        self.graph = self._build_graph()
        logger.info("Agent graph initialized")

    def _build_graph(self) -> StateGraph:
        """
        构建 LangGraph 工作流

        Returns:
            StateGraph 实例
        """
        # 创建状态图
        workflow = StateGraph(AgentState)

        # 添加节点
        workflow.add_node("process_input", self._process_input_node)
        workflow.add_node("llama_agent", self._llama_agent_node)
        workflow.add_node("finalize", self._finalize_node)

        # 设置入口点
        workflow.set_entry_point("process_input")

        # 添加边（定义流程）
        workflow.add_edge("process_input", "llama_agent")
        workflow.add_edge("llama_agent", "finalize")
        workflow.add_edge("finalize", END)

        return workflow

    async def _process_input_node(self, state: AgentState) -> AgentState:
        """
        处理输入节点
        验证和预处理用户输入

        Args:
            state: 当前状态

        Returns:
            更新后的状态
        """
        logger.info("Processing input node")

        # 验证输入
        if not state.get("current_input"):
            state["error"] = "No input provided"
            state["processing_state"] = "error"
            return state

        # 设置处理状态
        state["processing_state"] = "listening"

        return state

    async def _llama_agent_node(self, state: AgentState) -> AgentState:
        """
        LLAMA Agent 处理节点

        Args:
            state: 当前状态

        Returns:
            更新后的状态
        """
        logger.info("LLAMA Agent node")

        # 如果有错误，跳过处理
        if state.get("error"):
            return state

        # 调用 LLAMA Agent 处理
        state = await self.llama_agent.process(state)

        return state

    async def _finalize_node(self, state: AgentState) -> AgentState:
        """
        最终化节点
        完成处理并准备响应

        Args:
            state: 当前状态

        Returns:
            更新后的状态
        """
        logger.info("Finalize node")

        # 如果没有错误，设置为完成状态
        if not state.get("error"):
            state["processing_state"] = "idle"

        return state

    async def invoke(self, state: AgentState) -> AgentState:
        """
        执行完整的工作流

        Args:
            state: 初始状态

        Returns:
            最终状态
        """
        try:
            # 编译并运行图
            app = self.graph.compile()
            result = await app.ainvoke(state)
            return result
        except Exception as e:
            logger.error(f"Error invoking graph: {e}", exc_info=True)
            state["error"] = str(e)
            state["processing_state"] = "error"
            return state


class StreamingAgentGraph:
    """支持流式响应的 Agent 图"""

    def __init__(self):
        """初始化流式 Agent 图"""
        self.llama_agent = get_llama_agent()
        logger.info("Streaming agent graph initialized")

    async def process_streaming(
        self,
        state: AgentState
    ) -> AsyncGenerator[tuple[str, AgentState], None]:
        """
        执行流式处理工作流

        Args:
            state: 初始状态

        Yields:
            (响应片段, 更新后的状态) 元组
        """
        try:
            # 验证输入
            if not state.get("current_input"):
                state["error"] = "No input provided"
                state["processing_state"] = "error"
                yield "", state
                return

            # 设置处理状态
            state["processing_state"] = "listening"

            # 调用 LLAMA Agent 流式处理
            async for chunk, updated_state in self.llama_agent.process_streaming(state):
                yield chunk, updated_state

            # 设置为空闲状态
            state["processing_state"] = "idle"

        except Exception as e:
            logger.error(f"Error in streaming graph: {e}", exc_info=True)
            state["error"] = str(e)
            state["processing_state"] = "error"
            yield "", state


# 创建全局实例
_agent_graph = None
_streaming_agent_graph = None


def get_agent_graph() -> AgentGraph:
    """获取 Agent 图实例（单例模式）"""
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = AgentGraph()
    return _agent_graph


def get_streaming_agent_graph() -> StreamingAgentGraph:
    """获取流式 Agent 图实例（单例模式）"""
    global _streaming_agent_graph
    if _streaming_agent_graph is None:
        _streaming_agent_graph = StreamingAgentGraph()
    return _streaming_agent_graph


async def test_agent_graph():
    """测试 Agent 图"""
    print("\n" + "="*60)
    print("Testing Agent Graph")
    print("="*60)

    # 创建测试状态
    state = create_initial_state("test_session_123")
    state["current_input"] = "Hello, how are you?"

    # 测试非流式
    graph = get_agent_graph()
    result = await graph.invoke(state)

    print(f"\nInput: {result['current_input']}")
    print(f"Response: {result['agent_response']}")
    print(f"State: {result['processing_state']}")

    # 测试流式
    print("\n" + "-"*60)
    print("Testing Streaming Agent Graph")
    print("-"*60)

    state2 = create_initial_state("test_session_456")
    state2["current_input"] = "Tell me a short joke."

    streaming_graph = get_streaming_agent_graph()

    print("\nStreaming response: ", end="")
    async for chunk, updated_state in streaming_graph.process_streaming(state2):
        print(chunk, end="", flush=True)
    print("\n")

    print("="*60 + "\n")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_agent_graph())
