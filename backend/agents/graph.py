"""
LangGraph 工作流定义
简化的3节点线性流程 + Function Calling
"""

import logging
from typing import AsyncGenerator
from langgraph.graph import StateGraph, END
from backend.agents.base import AgentState, create_initial_state
from backend.agents.llama_agent import get_llama_agent

logger = logging.getLogger(__name__)


class AgentGraph:
    """简化的Agent系统工作流图（3节点线性流程）"""

    def __init__(self):
        """初始化 Agent 图"""
        self.llama_agent = get_llama_agent()
        self.graph = self._build_graph()
        logger.info("Agent graph initialized with Function Calling")

    def _build_graph(self) -> StateGraph:
        """
        构建简化的3节点线性LangGraph工作流

        Returns:
            StateGraph 实例
        """
        workflow = StateGraph(AgentState)

        # 添加3个节点
        workflow.add_node("validate_input", self._validate_input_node)
        workflow.add_node("llama_agent", self._llama_agent_node)
        workflow.add_node("finalize", self._finalize_node)

        # 设置入口点
        workflow.set_entry_point("validate_input")

        # 添加线性边
        workflow.add_edge("validate_input", "llama_agent")
        workflow.add_edge("llama_agent", "finalize")
        workflow.add_edge("finalize", END)

        return workflow

    async def _validate_input_node(self, state: AgentState) -> AgentState:
        """输入验证节点"""
        logger.info("Validate input node")

        if not state.get("current_input"):
            state["error"] = "No input provided"
            state["processing_state"] = "error"
            state["agent_response"] = "未收到输入"
            return state

        input_text = state["current_input"].strip()

        if len(input_text) == 0:
            state["error"] = "Empty input after trimming"
            state["processing_state"] = "error"
            state["agent_response"] = "输入为空"
            return state

        if len(input_text) > 1000:
            state["error"] = "Input too long (max 1000 characters)"
            state["processing_state"] = "error"
            state["agent_response"] = "输入过长（最多1000字符）"
            return state

        state["current_input"] = input_text
        state["processing_state"] = "listening"
        return state

    async def _llama_agent_node(self, state: AgentState) -> AgentState:
        """LLAMA Agent节点（使用Function Calling处理所有请求）"""
        logger.info("LLAMA Agent node with Function Calling")

        if state.get("error"):
            return state

        try:
            # 调用LlamaAgent处理（内部会根据需要调用工具）
            state = await self.llama_agent.process(state)

        except Exception as e:
            logger.error(f"Error in LLAMA agent: {e}", exc_info=True)
            state["error"] = str(e)
            state["agent_response"] = f"抱歉，处理您的请求时出错: {str(e)}"
            state["processing_state"] = "error"

        return state

    async def _finalize_node(self, state: AgentState) -> AgentState:
        """最终化节点"""
        logger.info("Finalize node")

        # 如果没有错误，设置为空闲状态
        if not state.get("error"):
            state["processing_state"] = "idle"

        # 更新对话历史
        if state.get("current_input") and state.get("agent_response"):
            history = state.get("conversation_history", [])
            history.append({
                "role": "user",
                "content": state["current_input"]
            })
            history.append({
                "role": "assistant",
                "content": state["agent_response"]
            })

            # 限制历史长度
            max_history = 20
            if len(history) > max_history:
                history = history[-max_history:]

            state["conversation_history"] = history

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
            state["agent_response"] = f"系统错误: {str(e)}"
            return state


class StreamingAgentGraph:
    """简化的流式Agent图（使用Function Calling）"""

    def __init__(self):
        """初始化流式Agent图"""
        self.llama_agent = get_llama_agent()
        logger.info("Streaming agent graph initialized with Function Calling")

    async def process_streaming(
        self,
        state: AgentState
    ) -> AsyncGenerator[tuple[str, AgentState], None]:
        """
        执行流式处理工作流（简化版）

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
                state["agent_response"] = "未收到输入"
                yield "", state
                return

            input_text = state["current_input"].strip()
            if len(input_text) == 0:
                state["error"] = "Empty input"
                state["processing_state"] = "error"
                state["agent_response"] = "输入为空"
                yield "", state
                return

            if len(input_text) > 1000:
                state["error"] = "Input too long"
                state["processing_state"] = "error"
                state["agent_response"] = "输入过长（最多1000字符）"
                yield "", state
                return

            # 设置处理状态
            state["processing_state"] = "listening"

            # 调用LlamaAgent流式处理（内部会自动使用Function Calling调用工具）
            logger.info(f"Streaming: processing with Function Calling")
            async for chunk, updated_state in self.llama_agent.process_streaming(state):
                yield chunk, updated_state

            # 设置为空闲状态
            state["processing_state"] = "idle"

        except Exception as e:
            logger.error(f"Error in streaming graph: {e}", exc_info=True)
            state["error"] = str(e)
            state["processing_state"] = "error"
            state["agent_response"] = f"系统错误: {str(e)}"
            yield "", state


# 创建全局实例
_agent_graph = None
_streaming_agent_graph = None


def get_agent_graph() -> AgentGraph:
    """获取Agent图实例（单例模式）"""
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = AgentGraph()
    return _agent_graph


def get_streaming_agent_graph() -> StreamingAgentGraph:
    """获取流式Agent图实例（单例模式）"""
    global _streaming_agent_graph
    if _streaming_agent_graph is None:
        _streaming_agent_graph = StreamingAgentGraph()
    return _streaming_agent_graph


async def test_agent_graph():
    """测试Agent图"""
    print("\n" + "=" * 70)
    print("Testing Agent Graph with Function Calling")
    print("=" * 70)

    # 测试1: 导航请求
    print("\n[Test 1: Navigation Request]")
    state1 = create_initial_state("test_session_1")
    state1["current_input"] = "去厨房"

    graph = get_agent_graph()
    result1 = await graph.invoke(state1)

    print(f"Input: {result1['current_input']}")
    print(f"Response: {result1['agent_response']}")

    # 测试2: 通用查询
    print("\n[Test 2: General Query]")
    state2 = create_initial_state("test_session_2")
    state2["current_input"] = "今天天气怎么样?"

    result2 = await graph.invoke(state2)

    print(f"Input: {result2['current_input']}")
    print(f"Response: {result2['agent_response']}")

    # 测试3: 流式响应
    print("\n[Test 3: Streaming Response]")
    state3 = create_initial_state("test_session_3")
    state3["current_input"] = "讲个笑话"

    streaming_graph = get_streaming_agent_graph()

    print("Streaming response: ", end="")
    async for chunk, updated_state in streaming_graph.process_streaming(state3):
        print(chunk, end="", flush=True)
    print("\n")

    print("=" * 70 + "\n")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_agent_graph())
