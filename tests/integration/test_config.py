"""
测试配置
"""

import os
from pathlib import Path


class TestConfig:
    """测试配置类"""

    # API超时配置
    OPENROUTER_TIMEOUT = 30  # OpenRouter API调用超时(秒)
    MCP_TIMEOUT = 10  # MCP工具调用超时(秒)
    STREAMING_TIMEOUT = 45  # 流式响应超时(秒)

    # 重试配置
    MAX_RETRIES = 2  # 失败重试次数
    RETRY_DELAY = 1  # 重试延迟(秒)

    # 执行配置
    PARALLEL_EXECUTION = False  # 禁用并行执行，串行运行避免MCP冲突
    CONTINUE_ON_ERROR = True  # 出错时继续执行后续测试
    SECTION_DELAY = 1  # 节间延迟(秒)，避免API限流

    # 输出配置
    VERBOSE = True  # 详细日志
    SAVE_REPORT = True  # 保存测试报告
    SAVE_LOGS = True  # 保存详细日志

    # 报告配置
    REPORT_DIR = Path("test_reports")  # 报告目录
    LOG_DIR = Path("test_logs")  # 日志目录

    # 模糊断言配置
    COORDINATE_TOLERANCE = 0.2  # 坐标参数容差(米)
    ANGLE_TOLERANCE = 0.15  # 角度参数容差(弧度, ~8.6度)

    # 环境变量
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

    @classmethod
    def validate(cls):
        """验证配置"""
        errors = []

        if not cls.OPENROUTER_API_KEY:
            errors.append("OPENROUTER_API_KEY not set")

        return errors

    @classmethod
    def setup_directories(cls):
        """创建必要的目录"""
        if cls.SAVE_REPORT:
            cls.REPORT_DIR.mkdir(parents=True, exist_ok=True)
        if cls.SAVE_LOGS:
            cls.LOG_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_summary(cls):
        """获取配置摘要"""
        return {
            "timeouts": {
                "openrouter": cls.OPENROUTER_TIMEOUT,
                "mcp": cls.MCP_TIMEOUT,
                "streaming": cls.STREAMING_TIMEOUT
            },
            "retries": {
                "max": cls.MAX_RETRIES,
                "delay": cls.RETRY_DELAY
            },
            "execution": {
                "parallel": cls.PARALLEL_EXECUTION,
                "continue_on_error": cls.CONTINUE_ON_ERROR
            },
            "tolerance": {
                "coordinate": cls.COORDINATE_TOLERANCE,
                "angle": cls.ANGLE_TOLERANCE
            }
        }
