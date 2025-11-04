"""
配置管理模块
加载和管理所有环境变量和应用配置
"""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# 加载环境变量
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)


class Settings(BaseSettings):
    """应用配置类"""

    # API Keys
    assemblyai_api_key: str = os.getenv("ASSEMBLYAI_API_KEY", "")
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")

    # OpenRouter 配置
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "meta-llama/llama-3-70b-instruct"

    # AssemblyAI 配置
    assemblyai_sample_rate: int = 16000
    assemblyai_api_host: str = "streaming.assemblyai.com"

    # FastAPI 配置
    app_name: str = "Multi-Agent System"
    app_version: str = "1.0.0"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000

    # WebSocket 配置
    websocket_timeout: int = 300  # 5 分钟

    # CORS 配置
    cors_origins: list = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
    ]

    # LLM 配置
    llm_temperature: float = 0.7
    llm_max_tokens: int = 2000
    llm_streaming: bool = True

    # 日志配置
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = False

    def validate_api_keys(self) -> tuple[bool, list[str]]:
        """验证必需的 API keys 是否已配置"""
        missing_keys = []

        if not self.assemblyai_api_key:
            missing_keys.append("ASSEMBLYAI_API_KEY")

        if not self.openrouter_api_key:
            missing_keys.append("OPENROUTER_API_KEY")

        return len(missing_keys) == 0, missing_keys


# 创建全局配置实例
settings = Settings()


def get_settings() -> Settings:
    """获取配置实例"""
    return settings


def print_config_status():
    """打印配置状态（用于调试）"""
    valid, missing = settings.validate_api_keys()

    print("\n" + "="*60)
    print("Configuration Status")
    print("="*60)
    print(f"App Name: {settings.app_name}")
    print(f"Version: {settings.app_version}")
    print(f"Debug Mode: {settings.debug}")
    print(f"Host: {settings.host}:{settings.port}")
    print("-"*60)
    print(f"AssemblyAI API Key: {'✓ Configured' if settings.assemblyai_api_key else '✗ Missing'}")
    print(f"OpenRouter API Key: {'✓ Configured' if settings.openrouter_api_key else '✗ Missing'}")
    print(f"OpenRouter Model: {settings.openrouter_model}")
    print("-"*60)

    if not valid:
        print(f"⚠️  Missing API Keys: {', '.join(missing)}")
    else:
        print("✓ All API keys configured")

    print("="*60 + "\n")


if __name__ == "__main__":
    # 测试配置加载
    print_config_status()
