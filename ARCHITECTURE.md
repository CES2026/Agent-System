# 系统架构文档

## 📐 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                          前端客户端                              │
│                    (浏览器/移动应用/桌面)                         │
└────────────────────────┬────────────────────────────────────────┘
                         │ WebSocket 连接
                         │ ws://localhost:8000/ws
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│                       FastAPI 后端服务                            │
│  ┌────────────────────────────────────────────────────────┐     │
│  │              WebSocket Handler                          │     │
│  │  - 连接管理                                             │     │
│  │  - 消息路由                                             │     │
│  │  - 会话管理                                             │     │
│  └───────────┬──────────────────────────┬─────────────────┘     │
│              │                          │                        │
│              ↓                          ↓                        │
│  ┌──────────────────┐      ┌───────────────────────┐           │
│  │  STT Service     │      │  LangGraph System     │           │
│  │  (AssemblyAI)    │      │  ┌─────────────────┐  │           │
│  │  - 音频流处理    │      │  │  Agent Graph    │  │           │
│  │  - 实时转录      │─────>│  │  - 状态管理     │  │           │
│  │  - 格式化输出    │      │  │  - 工作流控制   │  │           │
│  └──────────────────┘      │  └────────┬────────┘  │           │
│                            │           │            │           │
│                            │           ↓            │           │
│                            │  ┌─────────────────┐  │           │
│                            │  │  LLAMA Agent    │  │           │
│                            │  │  - 意图理解     │  │           │
│                            │  │  - 响应生成     │  │           │
│                            │  │  - 上下文管理   │  │           │
│                            │  └────────┬────────┘  │           │
│                            │           │            │           │
│                            │           ↓            │           │
│                            │  ┌─────────────────┐  │           │
│                            │  │ OpenRouter API  │  │           │
│                            │  │ LLAMA 3 70B     │  │           │
│                            │  └─────────────────┘  │           │
│                            └───────────────────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

## 🔧 核心组件

### 1. FastAPI 主应用 (`backend/main.py`)

**职责**:
- 应用生命周期管理
- HTTP 端点定义 (健康检查、配置等)
- WebSocket 端点路由
- CORS 配置
- 全局错误处理

**关键功能**:
```python
@app.websocket("/ws")      # WebSocket 端点
@app.get("/health")        # 健康检查
@app.get("/config")        # 配置信息
```

### 2. 配置管理 (`backend/config.py`)

**职责**:
- 加载环境变量
- 管理 API keys
- 应用配置参数
- 配置验证

**配置项**:
- AssemblyAI API key
- OpenRouter API key
- LLM 参数 (temperature, max_tokens)
- WebSocket 超时设置
- CORS 来源

### 3. WebSocket 处理器 (`backend/websocket/handler.py`)

**职责**:
- 管理 WebSocket 连接生命周期
- 路由不同类型的消息
- 协调 STT 和 Agent 服务
- 流式响应管理

**消息类型**:
```python
{
    "type": "text",        # 文本消息
    "type": "audio",       # 音频数据 (二进制)
    "type": "control"      # 控制命令
}
```

**处理流程**:
```
接收消息 → 类型判断 →
├─ 文本: 直接发送到 Agent
├─ 音频: 发送到 STT → 转录 → 发送到 Agent
└─ 控制: 执行控制命令 (start/stop/reset)
```

### 4. STT 服务 (`backend/services/stt_service.py`)

**职责**:
- 管理 AssemblyAI Streaming 连接
- 处理实时音频流
- 转录结果回调
- 多会话管理

**核心类**:
- `STTService`: 单个 STT 会话
- `STTServiceManager`: 管理多个并发会话

**音频格式**:
- 格式: PCM
- 采样率: 16kHz
- 声道: 单声道

### 5. OpenRouter 服务 (`backend/services/openrouter_service.py`)

**职责**:
- OpenRouter API 客户端封装
- 支持流式和非流式响应
- 对话历史管理
- 错误处理

**API 模式**:
```python
# 非流式
response = await service.generate_response(message)

# 流式
async for chunk in service.generate_streaming_response(message):
    process(chunk)
```

### 6. Agent 基类 (`backend/agents/base.py`)

**职责**:
- 定义 Agent 状态结构
- 提供基础 Agent 功能
- 管理对话历史
- 消息创建和转换

**状态结构**:
```python
AgentState = {
    "messages": [],              # 消息历史
    "current_input": "",         # 当前输入
    "agent_response": "",        # Agent 响应
    "conversation_history": [],  # 对话历史
    "session_id": "",           # 会话 ID
    "processing_state": ""      # 处理状态
}
```

### 7. LLAMA Agent (`backend/agents/llama_agent.py`)

**职责**:
- 实现具体的 Agent 逻辑
- 调用 OpenRouter 服务
- 管理对话上下文
- 生成响应

**功能**:
- `process()`: 非流式处理
- `process_streaming()`: 流式处理

### 8. LangGraph 工作流 (`backend/agents/graph.py`)

**职责**:
- 定义 Agent 执行图
- 管理节点和边
- 编排处理流程
- 支持流式和非流式执行

**工作流节点**:
```
入口 → 输入处理 → LLAMA Agent → 最终化 → 结束
```

## 🔄 数据流

### 文本对话流程

```
1. 客户端发送文本消息
   ↓
2. WebSocket Handler 接收
   ↓
3. 创建 Agent State
   ↓
4. LangGraph 处理
   ├─ 输入验证
   ├─ LLAMA Agent 处理
   │   ├─ 加载对话历史
   │   ├─ 调用 OpenRouter
   │   └─ 生成响应 (流式)
   └─ 最终化
   ↓
5. 流式返回响应给客户端
```

### 语音对话流程

```
1. 客户端发送音频流
   ↓
2. WebSocket Handler 接收
   ↓
3. 转发到 STT Service
   ↓
4. AssemblyAI 实时转录
   ↓
5. 转录完成回调
   ↓
6. 触发 Agent 处理 (同文本流程)
   ↓
7. 流式返回响应给客户端
```

## 🔐 安全考虑

### API Key 管理
- 使用 `.env` 文件存储
- 不提交到版本控制 (`.gitignore`)
- 启动时验证

### WebSocket 安全
- 会话隔离 (UUID)
- 超时机制
- 错误处理和日志

### 数据隐私
- 对话历史限制 (最近 10 轮)
- 会话结束后清理
- 不持久化敏感数据

## 📊 性能优化

### 异步处理
- 全面使用 `async/await`
- 非阻塞 I/O
- 并发处理多个会话

### 流式响应
- 降低首字节时间 (TTFB)
- 改善用户体验
- 减少内存占用

### 连接池
- OpenRouter 客户端复用
- STT 服务复用
- Agent 实例复用

## 🧪 测试策略

### 单元测试
```bash
# 测试各个模块
python backend/config.py
python backend/services/openrouter_service.py
python backend/agents/graph.py
```

### 集成测试
```bash
# 测试完整流程
python test_client.py --auto
```

### 端到端测试
```bash
# 1. 启动服务器
python run_server.py

# 2. 运行测试客户端
python test_client.py
```

## 🚀 扩展性

### 添加新 Agent

1. 创建新 Agent 类 (继承 `BaseAgent`)
2. 实现处理逻辑
3. 在 LangGraph 中添加节点
4. 更新工作流

### 添加新服务

1. 在 `backend/services/` 创建服务类
2. 实现服务接口
3. 在 `config.py` 添加配置
4. 在 WebSocket Handler 中集成

### 前端集成

WebSocket 客户端示例 (JavaScript):
```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    // 处理不同类型的消息
};

ws.send(JSON.stringify({
    type: "text",
    content: "Hello!"
}));
```

## 📈 监控和日志

### 日志级别
- INFO: 正常操作
- WARNING: 潜在问题
- ERROR: 错误和异常

### 监控指标
- WebSocket 连接数
- 请求处理时间
- API 调用成功率
- 错误率

## 🔮 未来改进

### 短期 (1-2 周)
- [ ] 添加用户认证
- [ ] 实现对话持久化
- [ ] 添加更多 Agent

### 中期 (1-2 月)
- [ ] 添加 TTS 支持
- [ ] 实现多语言支持
- [ ] 性能优化和缓存

### 长期 (3-6 月)
- [ ] 分布式部署
- [ ] Agent 协作机制
- [ ] 高级分析和报告
