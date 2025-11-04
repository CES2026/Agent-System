# 快速入门指南

这是一个简单的 5 分钟快速入门指南，帮助你快速运行多 Agent 系统。

## 第 1 步：安装依赖 (1 分钟)

```bash
# 安装所有 Python 依赖
pip install -r requirements.txt
```

> **macOS 用户**: 如果 pyaudio 安装失败，先运行: `brew install portaudio`

## 第 2 步：配置 API Keys (2 分钟)

编辑 `.env` 文件，替换你的 API keys：

```bash
# AssemblyAI API Configuration
ASSEMBLYAI_API_KEY=你的_assemblyai_api_key

# OpenRouter API Configuration
OPENROUTER_API_KEY=你的_openrouter_api_key
```

**获取 API Keys:**
- AssemblyAI: https://www.assemblyai.com/dashboard/signup (注册后在仪表板获取)
- OpenRouter: https://openrouter.ai/keys (注册后创建 API key)

## 第 3 步：启动服务器 (30 秒)

```bash
python run_server.py
```

你应该看到类似这样的输出：

```
🚀 Starting Multi-Agent System Server
============================================================
Starting Multi-Agent System v1.0.0
============================================================
...
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

## 第 4 步：测试系统 (1.5 分钟)

打开**新的终端窗口**，运行测试客户端：

```bash
python test_client.py
```

然后输入一些测试消息：

```
💬 You: Hello, who are you?
```

你应该看到 Agent 的流式响应！

## 常见问题

### Q: 服务器无法启动

**A**: 检查 `.env` 文件中的 API keys 是否配置正确

### Q: 端口 8000 被占用

**A**: 修改 `backend/config.py` 中的 `port` 配置，或者终止占用端口的进程

### Q: Agent 没有响应

**A**: 确保 OpenRouter API key 有效且有足够的额度

## 下一步

- 阅读完整的 [README.md](README.md) 了解更多功能
- 查看 WebSocket API 文档学习如何集成前端
- 探索 `backend/agents/` 目录学习如何添加新的 Agent

## 测试检查清单

- [ ] 依赖安装成功
- [ ] API keys 配置完成
- [ ] 服务器启动成功
- [ ] 测试客户端连接成功
- [ ] Agent 响应正常

如果所有步骤都完成，恭喜你！系统已经准备就绪。
