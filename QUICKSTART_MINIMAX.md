# MiniMax TTS 快速开始

## 5 分钟快速上手 MiniMax TTS

### 第 1 步：安装依赖

```bash
pip install httpx>=0.25.0
# 或
pip install -e ".[api]"
```

### 第 2 步：获取 API 密钥

1. 访问 https://api.minimaxi.com
2. 注册账号
3. 获取 API 密钥（格式：`sk-cp-xxx`）

### 第 3 步：最小化代码示例

```python
from pathlib import Path
from vidppt import Pipeline, ProcessConfig

# 创建配置
config = ProcessConfig(
    input_path=Path("your_presentation.pptx"),
    output_dir=Path("output"),
    tts_engine="minimax",                    # 使用 MiniMax
    tts_voice="male-qn-qingse",             # 男声
    tts_options={
        "api_key": "sk-cp-your-api-key",     # 替换为你的密钥
    }
)

# 运行
pipeline = Pipeline(config)
pipeline.run()
```

## 常见用法

### 快速使用（复制即用）

```python
from pathlib import Path
from vidppt import Pipeline, ProcessConfig
import os

config = ProcessConfig(
    input_path=Path("presentation.pptx"),
    output_dir=Path("output"),
    tts_engine="minimax",
    tts_options={
        "api_key": os.getenv("MINIMAX_API_KEY", "sk-cp-your-key"),
    }
)

Pipeline(config).run()
```

### 调整语速

```python
config = ProcessConfig(
    # ...
    tts_rate="+20%",  # 快 20%
    # 其他选项: "+0%", "-10%", "-30%" 等
)
```

### 更换语音

```python
config = ProcessConfig(
    # ...
    tts_voice="female-qn-nana",  # 女声
    # 或使用男声: "male-qn-qingse"
)
```

### 调整音频质量

```python
config = ProcessConfig(
    # ...
    tts_options={
        "api_key": "sk-cp-xxx",
        "sample_rate": 44100,      # 更高质量
        "bitrate": 256000,         # 更高比特率
    }
)
```

### 添加情感

```python
config = ProcessConfig(
    # ...
    tts_options={
        "api_key": "sk-cp-xxx",
        "emotion": "happy",        # 开心语调
        # 可选: "sad", "angry", "neutral", "peaceful"
    }
)
```

## 环境变量设置

### 推荐：使用环境变量存储密钥

**macOS/Linux**:
```bash
export MINIMAX_API_KEY="sk-cp-your-key"
```

**Windows** (PowerShell):
```powershell
$env:MINIMAX_API_KEY="sk-cp-your-key"
```

然后在代码中：
```python
import os
api_key = os.getenv("MINIMAX_API_KEY")
```

## 完整示例

### 示例 1：基本使用

```python
from pathlib import Path
from vidppt import Pipeline, ProcessConfig

config = ProcessConfig(
    input_path=Path("my_presentation.pptx"),
    output_dir=Path("output"),
    enable_tts=True,
    enable_video=True,
    tts_engine="minimax",
    tts_voice="male-qn-qingse",
    tts_options={
        "api_key": "sk-cp-your-key",
    }
)

pipeline = Pipeline(config)
pipeline.run()
```

### 示例 2：高级配置

```python
config = ProcessConfig(
    input_path=Path("presentation.pptx"),
    output_dir=Path("output"),
    tts_engine="minimax",
    tts_voice="male-qn-qingse",
    tts_rate="+10%",
    tts_options={
        "api_key": "sk-cp-your-key",
        "model": "speech-2.8-hd",
        "sample_rate": 44100,
        "bitrate": 256000,
        "emotion": "neutral",
    }
)

pipeline = Pipeline(config)
pipeline.run()
```

### 示例 3：使用 Edge TTS（对比）

```python
config = ProcessConfig(
    input_path=Path("presentation.pptx"),
    output_dir=Path("output"),
    tts_engine="edge-tts",  # 改为 edge-tts
    tts_voice="zh-CN-XiaoxiaoNeural",
)

pipeline = Pipeline(config)
pipeline.run()
```

## 故障排查

### 问题 1：ModuleNotFoundError: No module named 'httpx'

**解决方案**:
```bash
pip install httpx
```

### 问题 2：ValueError: API Key 未配置

**解决方案**:
```python
tts_options={
    "api_key": "sk-cp-your-api-key",  # 确保填写正确的密钥
}
```

### 问题 3：API 调用超时

**解决方案**:
- 检查网络连接
- 增加 timeout（API 内部）

### 问题 4：音频质量不佳

**解决方案**:
```python
tts_options={
    "api_key": "sk-cp-xxx",
    "sample_rate": 44100,  # 提高采样率
    "bitrate": 256000,     # 提高比特率
}
```

## 支持的参数

| 参数 | 说明 | 示例 |
|-----|------|------|
| `api_key` | MiniMax API 密钥 | `sk-cp-xxx` |
| `model` | 模型名称 | `speech-2.8-hd` |
| `sample_rate` | 采样率 | `32000`, `44100` |
| `bitrate` | 比特率 | `128000`, `256000` |
| `emotion` | 情感类型 | `happy`, `sad`, `neutral` |
| `audio_format` | 音频格式 | `mp3`, `wav` |
| `channel` | 声道数 | `1` (mono), `2` (stereo) |

## 性能提示

- MiniMax API 调用平均耗时：500-2000ms
- 建议批量处理：3-5 个页面为一批
- 总处理时间 = 提取时间 + TTS时间 + 视频合成时间

## 获取帮助

- 📖 完整指南：查看 `MINIMAX_GUIDE.md`
- 🧪 测试示例：查看 `tests/unit/test_minimax_tts.py`
- 🏗️ 架构文档：查看 `ARCHITECTURE.md`

## 下一步

1. ✅ 安装依赖
2. ✅ 获取 API 密钥
3. ✅ 复制示例代码
4. ✅ 运行转换
5. 📚 查看完整指南获取更多功能

---

**提示**: 使用 `tts_rate="+0%"` 来使用正常语速。
