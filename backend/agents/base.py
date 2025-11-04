"""
Agent 基类和状态定义
定义 Agent 系统的基础类型和状态结构
"""

from typing import TypedDict, Annotated, Sequence, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
import operator
import logging

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """
    Agent 状态定义
    用于在 LangGraph 中传递状态信息
    """
    # 消息历史
    messages: Annotated[Sequence[BaseMessage], operator.add]

    # 当前用户输入（来自 STT）
    current_input: str

    # Agent 响应
    agent_response: str

    # 对话历史（用于上下文管理）
    conversation_history: list[dict[str, str]]

    # 会话元数据
    session_id: str
    user_id: Optional[str]

    # 错误信息
    error: Optional[str]

    # 当前处理状态
    processing_state: str  # "idle", "listening", "processing", "responding"


class BaseAgent:
    """Agent 基类"""

    def __init__(self, name: str, system_prompt: str):
        """
        初始化 Agent

        Args:
            name: Agent 名称
            system_prompt: 系统提示词
        """
        self.name = name
        self.system_prompt = system_prompt
        logger.info(f"Initialized agent: {name}")

    async def process(self, state: AgentState) -> AgentState:
        """
        处理 Agent 逻辑（抽象方法）

        Args:
            state: 当前状态

        Returns:
            更新后的状态
        """
        raise NotImplementedError("Subclasses must implement process method")

    def create_message(self, content: str, role: str = "human") -> BaseMessage:
        """
        创建消息对象

        Args:
            content: 消息内容
            role: 消息角色 (human, ai, system)

        Returns:
            消息对象
        """
        if role == "human":
            return HumanMessage(content=content)
        elif role == "ai":
            return AIMessage(content=content)
        elif role == "system":
            return SystemMessage(content=content)
        else:
            raise ValueError(f"Unknown role: {role}")

    def update_conversation_history(
        self,
        state: AgentState,
        user_message: str,
        agent_response: str
    ) -> list[dict[str, str]]:
        """
        更新对话历史

        Args:
            state: 当前状态
            user_message: 用户消息
            agent_response: Agent 响应

        Returns:
            更新后的对话历史
        """
        history = state.get("conversation_history", [])
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": agent_response})

        # 限制历史长度，保留最近的 10 轮对话
        max_history = 20  # 10 轮对话 = 20 条消息
        if len(history) > max_history:
            history = history[-max_history:]

        return history

    def get_context_messages(self, state: AgentState) -> list[dict[str, str]]:
        """
        获取上下文消息（包括系统提示词和历史）

        Args:
            state: 当前状态

        Returns:
            消息列表
        """
        messages = [{"role": "system", "content": self.system_prompt}]

        # 添加对话历史
        if "conversation_history" in state and state["conversation_history"]:
            messages.extend(state["conversation_history"])

        return messages


def create_initial_state(
    session_id: str,
    user_id: Optional[str] = None
) -> AgentState:
    """
    创建初始状态

    Args:
        session_id: 会话 ID
        user_id: 用户 ID

    Returns:
        初始状态
    """
    return AgentState(
        messages=[],
        current_input="",
        agent_response="",
        conversation_history=[],
        session_id=session_id,
        user_id=user_id,
        error=None,
        processing_state="idle"
    )


if __name__ == "__main__":
    # 测试状态创建
    state = create_initial_state("test_session_123")
    print("Initial state created:", state)
