"""
MCP Client Service
Manages connection and communication with MCP servers via stdio
"""

import asyncio
import json
import logging
import sys
import time
import random
from typing import Optional, Dict, Any, List
from enum import Enum
from contextlib import AsyncExitStack
from pathlib import Path

logger = logging.getLogger(__name__)


# ============================================================================
# Error Definitions
# ============================================================================

class MCPErrorCode(Enum):
    """MCP错误码"""
    # JSON-RPC标准错误码
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603

    # MCP自定义错误码
    CONNECTION_ERROR = -32000
    TIMEOUT_ERROR = -32001
    TOOL_NOT_FOUND = -32002
    TOOL_EXECUTION_ERROR = -32003
    INITIALIZATION_ERROR = -32004
    PROTOCOL_ERROR = -32005


class MCPErrorSeverity(Enum):
    """错误严重程度"""
    TRANSIENT = "transient"      # 瞬时错误，可重试
    RECOVERABLE = "recoverable"  # 可恢复错误，需要修复后重试
    PERMANENT = "permanent"      # 永久错误，不可重试


class MCPError(Exception):
    """MCP错误基类"""

    def __init__(
        self,
        code: MCPErrorCode,
        message: str,
        severity: MCPErrorSeverity,
        data: Optional[dict] = None,
        cause: Optional[Exception] = None
    ):
        self.code = code
        self.message = message
        self.severity = severity
        self.data = data or {}
        self.cause = cause
        super().__init__(message)

    def to_json_rpc_error(self) -> dict:
        """转换为JSON-RPC错误格式"""
        return {
            "code": self.code.value,
            "message": self.message,
            "data": {
                "severity": self.severity.value,
                **self.data
            }
        }

    def is_retryable(self) -> bool:
        """判断是否可重试"""
        return self.severity == MCPErrorSeverity.TRANSIENT


class MCPTransientError(MCPError):
    """瞬时错误(网络超时、临时不可用等)"""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            code=MCPErrorCode.TIMEOUT_ERROR,
            message=message,
            severity=MCPErrorSeverity.TRANSIENT,
            **kwargs
        )


class MCPRecoverableError(MCPError):
    """可恢复错误(参数错误、工具未找到等)"""
    def __init__(self, code: MCPErrorCode, message: str, **kwargs):
        super().__init__(
            code=code,
            message=message,
            severity=MCPErrorSeverity.RECOVERABLE,
            **kwargs
        )


class MCPPermanentError(MCPError):
    """永久错误(协议错误、初始化失败等)"""
    def __init__(self, code: MCPErrorCode, message: str, **kwargs):
        super().__init__(
            code=code,
            message=message,
            severity=MCPErrorSeverity.PERMANENT,
            **kwargs
        )


# ============================================================================
# Retry Strategy
# ============================================================================

class ExponentialBackoff:
    """指数退避重试策略"""

    def __init__(
        self,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        multiplier: float = 2.0,
        jitter: float = 0.1,
        max_retries: int = 5
    ):
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.multiplier = multiplier
        self.jitter = jitter
        self.max_retries = max_retries
        self._attempt = 0

    def get_delay(self) -> float:
        """计算下次重试延迟"""
        if self._attempt >= self.max_retries:
            raise Exception(f"Exceeded maximum retries: {self.max_retries}")

        delay = min(
            self.initial_delay * (self.multiplier ** self._attempt),
            self.max_delay
        )

        # 添加随机抖动
        jitter_amount = delay * self.jitter * (2 * random.random() - 1)
        delay += jitter_amount

        self._attempt += 1
        return delay

    def reset(self):
        """重置重试计数"""
        self._attempt = 0


# ============================================================================
# MCP Client Service
# ============================================================================

class MCPClientService:
    """MCP客户端服务 - 管理与MCP服务器的stdio通信"""

    def __init__(
        self,
        server_module: str = "backend.mcp_servers",
        connection_timeout: float = 10.0,
        tool_call_timeout: float = 30.0,
        heartbeat_interval: float = 30.0,
        heartbeat_timeout: float = 5.0,
        heartbeat_max_failures: int = 3
    ):
        """
        初始化MCP客户端

        Args:
            server_module: MCP服务器模块路径
            connection_timeout: 连接超时(秒)
            tool_call_timeout: 工具调用超时(秒)
            heartbeat_interval: 心跳间隔(秒)
            heartbeat_timeout: 心跳超时(秒)
            heartbeat_max_failures: 心跳最大失败次数
        """
        self.server_module = server_module
        self.connection_timeout = connection_timeout
        self.tool_call_timeout = tool_call_timeout
        self.heartbeat_interval = heartbeat_interval
        self.heartbeat_timeout = heartbeat_timeout
        self.heartbeat_max_failures = heartbeat_max_failures

        self._process: Optional[asyncio.subprocess.Process] = None
        self._connected = False
        self._available_tools: List[Dict] = []
        self._request_id = 0
        self._pending_requests: Dict[int, asyncio.Future] = {}
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._heartbeat_failures = 0
        self._reader_task: Optional[asyncio.Task] = None

        logger.info(f"MCP Client Service initialized for module: {server_module}")

    async def connect(self):
        """连接到MCP服务器"""
        try:
            logger.info("Starting MCP server process...")

            # 启动MCP服务器进程
            self._process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                self.server_module,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            logger.info(f"MCP server process started with PID: {self._process.pid}")

            # 启动读取任务
            self._reader_task = asyncio.create_task(self._read_responses())

            # 初始化握手
            await self._send_initialize()

            # 等待初始化完成
            await asyncio.sleep(0.5)

            # 获取可用工具列表
            await self._fetch_tools()

            self._connected = True

            # 启动心跳
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            logger.info(f"MCP Client connected successfully. Available tools: {len(self._available_tools)}")

        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}", exc_info=True)
            await self._cleanup()
            raise MCPPermanentError(
                code=MCPErrorCode.CONNECTION_ERROR,
                message=f"Failed to connect: {str(e)}",
                cause=e
            )

    async def disconnect(self):
        """断开连接"""
        try:
            logger.info("Disconnecting MCP client...")

            # 停止心跳
            if self._heartbeat_task:
                self._heartbeat_task.cancel()
                try:
                    await self._heartbeat_task
                except asyncio.CancelledError:
                    pass

            await self._cleanup()

            logger.info("MCP Client disconnected")

        except Exception as e:
            logger.error(f"Error disconnecting MCP client: {e}")

    async def _cleanup(self):
        """清理资源"""
        self._connected = False

        # 停止读取任务
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass

        # 关闭进程
        if self._process:
            try:
                # 关闭stdin
                if self._process.stdin:
                    self._process.stdin.close()
                    await self._process.stdin.wait_closed()

                # 等待进程退出
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning("MCP server process did not exit gracefully, terminating...")
                    self._process.terminate()

                    try:
                        await asyncio.wait_for(self._process.wait(), timeout=2.0)
                    except asyncio.TimeoutError:
                        logger.error("MCP server process did not terminate, killing...")
                        self._process.kill()
                        await self._process.wait()
            except Exception as e:
                logger.error(f"Error cleaning up MCP process: {e}")

    async def _send_initialize(self):
        """发送初始化请求"""
        init_request = {
            "jsonrpc": "2.0",
            "id": self._get_next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {
                    "tools": {"listChanged": True}
                },
                "clientInfo": {
                    "name": "agent-system",
                    "version": "1.0.0"
                }
            }
        }

        await self._send_request(init_request)

    async def _fetch_tools(self):
        """获取可用工具列表"""
        request = {
            "jsonrpc": "2.0",
            "id": self._get_next_id(),
            "method": "tools/list",
            "params": {}
        }

        response = await self._send_and_wait(request, timeout=self.connection_timeout)

        if "result" in response and "tools" in response["result"]:
            self._available_tools = response["result"]["tools"]
            logger.info(f"Fetched {len(self._available_tools)} tools from MCP server")
        else:
            logger.warning("No tools found in MCP server response")

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """
        调用MCP工具

        Args:
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            工具执行结果
        """
        if not self._connected:
            raise MCPPermanentError(
                code=MCPErrorCode.CONNECTION_ERROR,
                message="MCP client not connected"
            )

        request = {
            "jsonrpc": "2.0",
            "id": self._get_next_id(),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }

        logger.info(f"Calling MCP tool: {tool_name} with arguments: {arguments}")

        try:
            response = await self._send_and_wait(request, timeout=self.tool_call_timeout)

            if "error" in response:
                error = response["error"]
                raise MCPRecoverableError(
                    code=MCPErrorCode.TOOL_EXECUTION_ERROR,
                    message=error.get("message", "Tool execution failed"),
                    data=error.get("data", {})
                )

            if "result" in response and "content" in response["result"]:
                # 提取文本内容
                text_content = ""
                for content in response["result"]["content"]:
                    if isinstance(content, dict) and "text" in content:
                        text_content += content["text"]

                # 尝试解析JSON结果
                try:
                    result = json.loads(text_content)
                    logger.info(f"Tool {tool_name} executed successfully")
                    return {
                        "success": True,
                        "result": result,
                        "raw": response
                    }
                except json.JSONDecodeError:
                    return {
                        "success": True,
                        "result": text_content,
                        "raw": response
                    }

            return {
                "success": False,
                "error": "No content in response"
            }

        except asyncio.TimeoutError:
            logger.error(f"Tool call timed out: {tool_name}")
            raise MCPTransientError(
                message=f"Tool call timed out after {self.tool_call_timeout}s",
                data={"tool_name": tool_name, "arguments": arguments}
            )
        except MCPError:
            raise
        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}", exc_info=True)
            raise MCPPermanentError(
                code=MCPErrorCode.INTERNAL_ERROR,
                message=f"Unexpected error: {str(e)}",
                cause=e
            )

    async def _send_request(self, request: dict):
        """发送请求到MCP服务器"""
        if not self._process or not self._process.stdin:
            raise MCPPermanentError(
                code=MCPErrorCode.CONNECTION_ERROR,
                message="MCP process not running"
            )

        try:
            request_str = json.dumps(request) + "\n"
            self._process.stdin.write(request_str.encode('utf-8'))
            await self._process.stdin.drain()
        except Exception as e:
            logger.error(f"Error sending request: {e}")
            raise MCPTransientError(
                message="Failed to send request",
                cause=e
            )

    async def _send_and_wait(self, request: dict, timeout: float) -> dict:
        """发送请求并等待响应"""
        request_id = request["id"]

        # 创建Future用于等待响应
        future = asyncio.Future()
        self._pending_requests[request_id] = future

        try:
            # 发送请求
            await self._send_request(request)

            # 等待响应
            response = await asyncio.wait_for(future, timeout=timeout)
            return response

        finally:
            # 清理
            self._pending_requests.pop(request_id, None)

    async def _read_responses(self):
        """读取响应的后台任务"""
        try:
            while self._process and self._process.stdout:
                line = await self._process.stdout.readline()

                if not line:
                    logger.warning("MCP server stdout closed")
                    break

                try:
                    response = json.loads(line.decode('utf-8'))
                    await self._handle_response(response)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse response: {line}, error: {e}")
                except Exception as e:
                    logger.error(f"Error handling response: {e}", exc_info=True)
        except asyncio.CancelledError:
            logger.info("Response reader task cancelled")
        except Exception as e:
            logger.error(f"Error in response reader: {e}", exc_info=True)

    async def _handle_response(self, response: dict):
        """处理服务器响应"""
        if "id" in response:
            request_id = response["id"]
            if request_id in self._pending_requests:
                future = self._pending_requests[request_id]
                if not future.done():
                    future.set_result(response)

    async def _heartbeat_loop(self):
        """心跳循环"""
        try:
            while self._connected:
                await asyncio.sleep(self.heartbeat_interval)

                try:
                    # 使用list_tools作为心跳探测
                    request = {
                        "jsonrpc": "2.0",
                        "id": self._get_next_id(),
                        "method": "tools/list",
                        "params": {}
                    }

                    await asyncio.wait_for(
                        self._send_and_wait(request, timeout=self.heartbeat_timeout),
                        timeout=self.heartbeat_timeout
                    )

                    self._heartbeat_failures = 0

                except asyncio.TimeoutError:
                    self._heartbeat_failures += 1
                    logger.warning(
                        f"Heartbeat timeout ({self._heartbeat_failures}/"
                        f"{self.heartbeat_max_failures})"
                    )

                    if self._heartbeat_failures >= self.heartbeat_max_failures:
                        logger.error("MCP connection dead, attempting reconnect")
                        await self.reconnect()

                except Exception as e:
                    logger.error(f"Heartbeat error: {e}")
                    self._heartbeat_failures += 1

        except asyncio.CancelledError:
            logger.info("Heartbeat task cancelled")

    async def reconnect(self):
        """重新连接"""
        logger.info("Attempting to reconnect to MCP server...")

        await self.disconnect()
        await asyncio.sleep(2.0)

        try:
            await self.connect()
            logger.info("Reconnection successful")
        except Exception as e:
            logger.error(f"Reconnection failed: {e}")
            raise

    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._connected

    def get_available_tools(self) -> List[Dict]:
        """获取可用工具列表"""
        return self._available_tools

    def _get_next_id(self) -> int:
        """获取下一个请求ID"""
        self._request_id += 1
        return self._request_id


# ============================================================================
# Global Instance Management
# ============================================================================

_mcp_client: Optional[MCPClientService] = None


async def get_mcp_client() -> MCPClientService:
    """获取MCP客户端实例（单例）"""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClientService()
        await _mcp_client.connect()
    return _mcp_client


async def call_mcp_tool_with_retry(
    client: MCPClientService,
    tool_name: str,
    arguments: dict,
    max_retries: int = 5
) -> dict:
    """带重试的MCP工具调用"""
    backoff = ExponentialBackoff(max_retries=max_retries)

    while True:
        try:
            result = await client.call_tool(tool_name, arguments)
            backoff.reset()
            return result

        except MCPTransientError as e:
            try:
                delay = backoff.get_delay()
                logger.warning(f"Tool call failed, retrying in {delay:.1f}s: {e}")
                await asyncio.sleep(delay)
            except Exception:
                # 超过最大重试次数
                logger.error(f"Tool call failed after {max_retries} retries")
                raise

        except (MCPRecoverableError, MCPPermanentError):
            # 不可重试的错误，立即失败
            raise
