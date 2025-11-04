"""
FastAPI 主应用
多 Agent 系统的入口点和 API 定义
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import get_settings, print_config_status
from backend.websocket.handler import websocket_endpoint

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    settings = get_settings()
    logger.info("="*60)
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info("="*60)

    # 打印配置状态
    print_config_status()

    # 验证 API keys
    valid, missing = settings.validate_api_keys()
    if not valid:
        logger.warning(f"⚠️  Missing API keys: {', '.join(missing)}")
        logger.warning("Some features may not work correctly!")
    else:
        logger.info("✓ All API keys validated")

    logger.info("FastAPI application started successfully")
    logger.info(f"WebSocket endpoint available at: ws://{settings.host}:{settings.port}/ws")
    logger.info("="*60)

    yield

    # 关闭时执行
    logger.info("Shutting down application...")


# 创建 FastAPI 应用
settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Multi-Agent System with AssemblyAI STT and LangGraph",
    lifespan=lifespan
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== HTTP 端点 ==========

@app.get("/")
async def root():
    """根端点 - 返回 API 信息"""
    return JSONResponse({
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "description": "Multi-Agent System API",
        "endpoints": {
            "websocket": "/ws",
            "health": "/health",
            "config": "/config"
        }
    })


@app.get("/health")
async def health_check():
    """健康检查端点"""
    valid, missing = settings.validate_api_keys()

    return JSONResponse({
        "status": "healthy" if valid else "degraded",
        "api_keys_configured": valid,
        "missing_keys": missing if not valid else [],
        "services": {
            "assemblyai": bool(settings.assemblyai_api_key),
            "openrouter": bool(settings.openrouter_api_key)
        }
    })


@app.get("/config")
async def get_config():
    """获取配置信息（不包含敏感信息）"""
    return JSONResponse({
        "app_name": settings.app_name,
        "version": settings.app_version,
        "debug": settings.debug,
        "openrouter_model": settings.openrouter_model,
        "llm_temperature": settings.llm_temperature,
        "llm_max_tokens": settings.llm_max_tokens,
        "llm_streaming": settings.llm_streaming,
        "websocket_timeout": settings.websocket_timeout
    })


# ========== WebSocket 端点 ==========

@app.websocket("/ws")
async def websocket_route(websocket: WebSocket):
    """
    WebSocket 端点
    处理实时音频流和 Agent 交互

    消息格式:

    客户端 -> 服务器:
    1. 音频数据: 二进制数据 (PCM 16kHz)
    2. 文本消息: {"type": "text", "content": "你的消息"}
    3. 控制命令: {"type": "control", "command": "start_stt"|"stop_stt"|"reset_conversation"}

    服务器 -> 客户端:
    1. 连接: {"type": "connection", "status": "connected", "session_id": "..."}
    2. 转录: {"type": "transcript", "text": "...", "is_final": true/false}
    3. Agent 状态: {"type": "agent_status", "status": "processing"|"completed"}
    4. Agent 响应: {"type": "agent_response", "chunk": "...", "is_streaming": true/false}
    5. 错误: {"type": "error", "message": "..."}
    """
    await websocket_endpoint(websocket)


# ========== 错误处理 ==========

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理器"""
    logger.error(f"Global exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc) if settings.debug else "An error occurred"
        }
    )


# ========== 运行应用 ==========

def run_server():
    """运行服务器"""
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run_server()
