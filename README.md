# Multi-Agent System with LangGraph

基于 LangGraph 的多 Agent 系统，集成了 AssemblyAI 实时语音转文本 (STT) 和 OpenRouter LLAMA 3 70B 模型。

## 🌟 特性

- **实时语音转文本**: 使用 AssemblyAI Streaming API 进行实时语音识别
- **多 Agent 架构**: 基于 LangGraph 的灵活 Agent 系统
- **LLAMA 3 70B**: 通过 OpenRouter 使用强大的 LLAMA 3 70B 模型
- **WebSocket 通信**: 支持实时双向通信
- **流式响应**: Agent 响应以流式方式返回，提供更好的用户体验
- **FastAPI 后端**: 现代化、高性能的 API 框架

## 🏗️ 系统架构

```
用户前端（语音）
    ↓
WebSocket 连接
    ↓
FastAPI 后端
    ↓
AssemblyAI STT（实时流式）
    ↓
LangGraph Agent System
    ↓
LLAMA 3 70B Agent (OpenRouter)
    ↓
WebSocket 返回（文本响应流）
```

## 📦 技术栈

- **后端框架**: FastAPI
- **实时通信**: WebSocket
- **语音转文本**: AssemblyAI Streaming API
- **Agent 框架**: LangGraph
- **LLM 模型**: OpenRouter (LLAMA 3 70B)
- **异步处理**: asyncio

## 📁 项目结构

```
Agent-System/
├── backend/
│   ├── __init__.py
│   ├── main.py                    # FastAPI 主应用
│   ├── config.py                  # 配置管理
│   ├── websocket/
│   │   ├── __init__.py
│   │   └── handler.py             # WebSocket 处理器
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py                # Agent 基类
│   │   ├── llama_agent.py         # LLAMA 3 Agent
│   │   └── graph.py               # LangGraph 定义
│   └── services/
│       ├── __init__.py
│       ├── stt_service.py         # AssemblyAI STT 服务
│       └── openrouter_service.py  # OpenRouter 客户端
├── examples/                       # 示例代码
│   ├── assemblyai_streaming.py
│   └── test_streaming.py
├── requirements.txt                # Python 依赖
├── .env                           # 环境变量（需要配置）
├── run_server.py                  # 服务器启动脚本
├── test_client.py                 # 测试客户端
└── README.md
```

## 🚀 快速开始

### 1. 安装依赖

```bash
# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # macOS/Linux
# 或
venv\Scripts\activate     # Windows

# 安装依赖
pip install -r requirements.txt
```

**macOS 特别说明**：如果安装 `pyaudio` 遇到问题，先安装 portaudio：
```bash
brew install portaudio
pip install pyaudio
```

### 2. 配置 API Keys

编辑 `.env` 文件，添加你的 API keys：

```bash
# AssemblyAI API Configuration
ASSEMBLYAI_API_KEY=your_assemblyai_api_key_here

# OpenRouter API Configuration
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

**获取 API Keys:**
- AssemblyAI: https://www.assemblyai.com/dashboard/signup
- OpenRouter: https://openrouter.ai/keys

### 3. 启动服务器

```bash
# 方式 1: 使用启动脚本
python run_server.py

# 方式 2: 直接运行
python -m backend.main

# 方式 3: 使用 uvicorn
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

服务器将在 `http://localhost:8000` 启动

### 4. 测试连接

#### 方法 1: 使用测试客户端

```bash
# 交互式模式
python test_client.py

# 自动化测试
python test_client.py --auto
```

#### 方法 2: 访问 API 端点

打开浏览器访问：
- API 信息: http://localhost:8000
- 健康检查: http://localhost:8000/health
- 配置信息: http://localhost:8000/config

## 📡 WebSocket API

### 连接

```
WebSocket URL: ws://localhost:8000/ws
```

### 消息格式

#### 客户端 → 服务器

1. **文本消息**（直接发送到 Agent，不经过 STT）:
```json
{
    "type": "text",
    "content": "你的消息内容"
}
```

2. **音频数据**（实时语音流）:
```
直接发送二进制音频数据（PCM 格式，16kHz 采样率）
```

3. **控制命令**:
```json
{
    "type": "control",
    "command": "start_stt" | "stop_stt" | "reset_conversation"
}
```

#### 服务器 → 客户端

1. **连接确认**:
```json
{
    "type": "connection",
    "status": "connected",
    "session_id": "uuid",
    "message": "Connected to Multi-Agent System"
}
```

2. **转录结果**:
```json
{
    "type": "transcript",
    "text": "转录的文本",
    "is_final": true/false
}
```

3. **Agent 状态**:
```json
{
    "type": "agent_status",
    "status": "processing" | "completed",
    "message": "状态消息"
}
```

4. **Agent 响应**（流式）:
```json
{
    "type": "agent_response",
    "chunk": "响应片段",
    "is_streaming": true/false,
    "full_response": "完整响应（仅在结束时）",
    "status": "completed"
}
```

5. **错误消息**:
```json
{
    "type": "error",
    "message": "错误描述"
}
```

## 🧪 测试

### 测试单个模块

```bash
# 测试配置
python backend/config.py

# 测试 OpenRouter 服务
python backend/services/openrouter_service.py

# 测试 Agent 系统
python backend/agents/graph.py
```

### 端到端测试

```bash
# 1. 启动服务器
python run_server.py

# 2. 在另一个终端运行测试客户端
python test_client.py
```

## 🔧 配置选项

在 `backend/config.py` 中可以配置以下选项：

- `openrouter_model`: LLAMA 模型选择（默认: `meta-llama/llama-3-70b-instruct`）
- `llm_temperature`: 温度参数（默认: 0.7）
- `llm_max_tokens`: 最大 token 数（默认: 2000）
- `assemblyai_sample_rate`: 音频采样率（默认: 16000）
- `websocket_timeout`: WebSocket 超时时间（默认: 300 秒）
- `cors_origins`: 允许的 CORS 来源

## 🎯 使用场景

### 场景 1: 文本对话

客户端发送文本消息，Agent 直接处理并返回响应：

```javascript
// 发送文本消息
ws.send(JSON.stringify({
    type: "text",
    content: "Hello, how can you help me?"
}));

// 接收流式响应
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === "agent_response") {
        console.log(data.chunk);
    }
};
```

### 场景 2: 语音输入

客户端发送实时音频流，系统自动进行 STT 并处理：

```javascript
// 发送音频数据
navigator.mediaDevices.getUserMedia({ audio: true })
    .then(stream => {
        const mediaRecorder = new MediaRecorder(stream);
        mediaRecorder.ondataavailable = (event) => {
            ws.send(event.data);  // 发送音频块
        };
        mediaRecorder.start(100);  // 每 100ms 发送一次
    });
```

## 📝 开发指南

### 添加新的 Agent

1. 在 `backend/agents/` 创建新的 Agent 类
2. 继承 `BaseAgent` 类
3. 实现 `process()` 和 `process_streaming()` 方法
4. 在 `backend/agents/graph.py` 中添加到工作流

### 扩展 WebSocket 处理

在 `backend/websocket/handler.py` 中添加新的消息类型处理器

## 🐛 故障排除

### 问题: API Key 未配置

**错误**: `Missing API keys: OPENROUTER_API_KEY`

**解决**: 确保在 `.env` 文件中配置了正确的 API keys

### 问题: pyaudio 安装失败 (macOS)

**错误**: `fatal error: 'portaudio.h' file not found`

**解决**:
```bash
brew install portaudio
pip install pyaudio
```

### 问题: WebSocket 连接失败

**检查**:
1. 服务器是否正在运行
2. 端口 8000 是否被占用
3. 防火墙是否阻止连接

### 问题: STT 无响应

**检查**:
1. AssemblyAI API key 是否正确
2. 网络连接是否正常
3. 音频格式是否为 PCM 16kHz

## 📚 相关文档

- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [LangGraph 文档](https://langchain-ai.github.io/langgraph/)
- [AssemblyAI 文档](https://www.assemblyai.com/docs)
- [OpenRouter 文档](https://openrouter.ai/docs)

## 🤝 贡献

欢迎提交 Issues 和 Pull Requests！

## 📄 许可证

MIT License