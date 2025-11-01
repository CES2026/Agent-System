# AssemblyAI Streaming Examples

这个目录包含了 AssemblyAI 实时语音转录的示例代码。

## 文件说明

- `assemblyai_streaming.py` - 基础示例代码
- `test_streaming.py` - 可直接测试的服务脚本（推荐使用）

## 安装依赖

```bash
cd Agent-System
pip install assemblyai python-dotenv pyaudio
```

**macOS 特别说明**：
如果安装 `pyaudio` 遇到问题，先安装 portaudio：
```bash
brew install portaudio
pip install pyaudio
```

## 配置

API key 已在 `.env` 文件中配置：
```
ASSEMBLYAI_API_KEY=your_api_key_here
```

## 运行测试

```bash
cd Agent-System
python examples/test_streaming.py
```

## 使用说明

1. 运行脚本后，程序会自动启动麦克风
2. 对着麦克风说话，实时转录结果会显示在终端
3. 按 `Ctrl+C` 停止转录

## 功能特性

- ✅ 自动加载 .env 配置
- ✅ 实时语音转录
- ✅ 友好的终端输出界面
- ✅ 错误处理和日志记录
- ✅ macOS 麦克风权限自动处理

## 故障排除

### 麦克风权限
首次运行时，macOS 会提示授予麦克风权限，请点击"允许"。

### 没有声音输入
检查系统偏好设置 > 安全性与隐私 > 隐私 > 麦克风，确保终端或 Python 有权限访问麦克风。

### API 错误
确保 `.env` 文件中的 `ASSEMBLYAI_API_KEY` 配置正确。
