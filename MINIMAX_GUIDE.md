# MiniMax TTS 集成指南

本指南说明如何在 VidPPT 中使用 MiniMax TTS 引擎进行高质量的文字转语音。

## 📋 目录

1. [功能特性](#功能特性)
2. [安装](#安装)
3. [配置](#配置)
4. [使用方法](#使用方法)
5. [高级功能](#高级功能)
6. [故障排查](#故障排查)

## 功能特性

### MiniMax TTS 支持的功能

- ✅ **高质量语音合成** - 清晰、自然的语音输出
- ✅ **多语音选择** - 支持男声、女声等多种语音
- ✅ **情感控制** - 支持 happy, sad, angry, neutral, peaceful 等情感
- ✅ **灵活的语速调整** - 支持 0.5x - 2.0x 的语速范围
- ✅ **发音字典** - 支持自定义发音规则
- ✅ **多种音频格式** - MP3, WAV 等格式
- ✅ **批量处理** - 支持批量异步转换

### 支持的语音 ID

#### 男声
- `male-qn-qingse` - 清晰男声（推荐）

#### 女声
- `female-qn-nana` - 娜娜女声

#### 其他语音
根据 MiniMax API 文档，可能还有其他语音 ID

## 安装

### 1. 安装依赖

```bash
# 使用 pip
pip install httpx>=0.25.0

# 或使用 uv
uv pip install httpx>=0.25.0

# 或安装项目的 API 依赖
pip install -e ".[api]"
```

### 2. 获取 API 密钥

访问 [MiniMax API 官网](https://api.minimaxi.com) 注册并获取 API 密钥。

## 配置

### 方式 1：配置文件方式

```python
from pathlib import Path
from vidppt import Pipeline, ProcessConfig

# 创建配置
config = ProcessConfig(
    input_path=Path("presentation.pptx"),
    output_dir=Path("output"),
    enable_tts=True,
    tts_engine="minimax",  # 使用 MiniMax
    tts_voice="male-qn-qingse",  # 语音选择
    tts_rate="+0%",  # 语速
    tts_options={
        "api_key": "sk-cp-your-api-key",  # 必填：API 密钥
        "api_url": "https://api.minimaxi.com/v1/t2a_v2",
        "model": "speech-2.8-hd",  # 使用的模型
        "sample_rate": 32000,  # 采样率
        "bitrate": 128000,  # 比特率
        "audio_format": "mp3",  # 音频格式
        "channel": 1,  # 声道数
        "emotion": "neutral",  # 情感类型
    }
)

# 运行流程
pipeline = Pipeline(config)
pipeline.run()
```

### 方式 2：环境变量方式

```bash
# 设置 API 密钥环境变量
export MINIMAX_API_KEY="sk-cp-your-api-key"
```

```python
import os
from pathlib import Path
from vidppt import Pipeline, ProcessConfig

config = ProcessConfig(
    input_path=Path("presentation.pptx"),
    output_dir=Path("output"),
    tts_engine="minimax",
    tts_options={
        "api_key": os.getenv("MINIMAX_API_KEY"),
    }
)

pipeline = Pipeline(config)
pipeline.run()
```

### 方式 3：命令行方式

```bash
vidppt presentation.pptx \
  --tts-engine minimax \
  --tts-voice male-qn-qingse \
  --tts-options api_key=sk-cp-your-api-key
```

## 使用方法

### 基本使用

```python
from pathlib import Path
from vidppt.engines.tts.api_tts_engine import MiniMaxTTSEngine
import asyncio

# 创建引擎
engine = MiniMaxTTSEngine(
    api_key="sk-cp-your-api-key",
    model="speech-2.8-hd"
)

# 转换单个文本
async def convert_single():
    await engine.convert_async(
        text="欢迎使用 VidPPT",
        output_path=Path("output.mp3"),
        voice="male-qn-qingse",
        rate="+0%"
    )

asyncio.run(convert_single())
```

### 高级用法

#### 1. 使用不同的情感

```python
from pathlib import Path
from vidppt.engines.tts.api_tts_engine import MiniMaxTTSEngine
import asyncio

engine = MiniMaxTTSEngine(
    api_key="sk-cp-your-api-key",
    emotion="happy"  # 设置默认情感为开心
)

async def convert_with_emotion():
    # 使用预设的开心情感
    await engine.convert_async(
        text="今天天气真好！",
        output_path=Path("happy.mp3"),
        voice="male-qn-qingse",
        rate="+0%"
    )
    
    # 覆盖默认情感
    await engine.convert_async(
        text="这真是令人失望。",
        output_path=Path("sad.mp3"),
        voice="male-qn-qingse",
        rate="+0%",
        emotion="sad"
    )

asyncio.run(convert_with_emotion())
```

#### 2. 使用发音字典

```python
pronunciation_dict = {
    "tone": [
        "处理/(chu3)(li3)",  # 自定义"处理"的发音
        "危险/dangerous"     # 英文词汇发音
    ]
}

async def convert_with_pronunciation():
    await engine.convert_async(
        text="这个系统如何处理危险情况？",
        output_path=Path("output.mp3"),
        voice="male-qn-qingse",
        rate="+0%",
        pronunciation_dict=pronunciation_dict
    )

asyncio.run(convert_with_pronunciation())
```

#### 3. 自定义音频设置

```python
engine = MiniMaxTTSEngine(
    api_key="sk-cp-your-api-key",
    model="speech-2.8-hd",
    sample_rate=44100,  # 更高的采样率
    bitrate=256000,     # 更高的比特率
    audio_format="wav"  # WAV 格式
)
```

#### 4. 调整语速

```python
# 支持的语速格式
speeds = [
    "+50%",   # 快速
    "+20%",   # 稍快
    "+0%",    # 正常
    "-10%",   # 稍慢
    "-30%",   # 慢速
    "1.5",    # 直接倍数
]

for speed in speeds:
    await engine.convert_async(
        text="测试语速",
        output_path=Path(f"speed_{speed.replace('+', 'plus').replace('-', 'minus')}.mp3"),
        voice="male-qn-qingse",
        rate=speed
    )
```

## 高级功能

### 批量处理多页文档

```python
from pathlib import Path
from vidppt import Pipeline, ProcessConfig

config = ProcessConfig(
    input_path=Path("presentation.pptx"),
    output_dir=Path("output"),
    enable_tts=True,
    enable_video=True,
    tts_engine="minimax",
    tts_voice="male-qn-qingse",
    tts_options={
        "api_key": "sk-cp-your-api-key",
        "model": "speech-2.8-hd",
    }
)

# 自动批量处理所有页面
pipeline = Pipeline(config)
pipeline.run()
```

### 使用混合情感

```python
from vidppt.engines.tts.api_tts_engine import MiniMaxTTSEngine
import asyncio

engine = MiniMaxTTSEngine(api_key="sk-cp-your-api-key")

async def convert_mixed_emotions():
    """为不同的页面使用不同的情感"""
    pages = [
        (1, "欢迎来到今天的演示！", "happy"),
        (2, "今年的挑战比较大。", "sad"),
        (3, "但我们已经做好准备。", "neutral"),
        (4, "让我们一起前进！", "peaceful"),
    ]
    
    for page_num, text, emotion in pages:
        await engine.convert_async(
            text=text,
            output_path=Path(f"page_{page_num}.mp3"),
            voice="male-qn-qingse",
            rate="+0%",
            emotion=emotion
        )

asyncio.run(convert_mixed_emotions())
```

## 故障排查

### 问题 1：ImportError: No module named 'httpx'

**解决方案**：
```bash
pip install httpx
# 或
pip install -e ".[api]"
```

### 问题 2：ValueError: API Key 未配置

**解决方案**：
确保在 `tts_options` 中设置 `api_key`：
```python
config = ProcessConfig(
    tts_engine="minimax",
    tts_options={
        "api_key": "sk-cp-your-api-key"
    }
)
```

### 问题 3：API 返回错误

检查以下几点：
- API 密钥是否正确
- 网络连接是否正常
- API 配额是否充足
- 文本内容是否有效

```python
import logging

# 启用调试日志
logging.basicConfig(level=logging.DEBUG)

# 运行时会输出详细信息
```

### 问题 4：音频质量不佳

尝试调整以下参数：
```python
engine = MiniMaxTTSEngine(
    api_key="sk-cp-your-api-key",
    sample_rate=44100,  # 提高采样率
    bitrate=256000,     # 提高比特率
)
```

### 问题 5：语速设置不生效

确保使用正确的格式：
```python
# 正确
await engine.convert_async(
    text="文本",
    output_path=Path("output.mp3"),
    voice="male-qn-qingse",
    rate="+20%"  # 格式: "+XXX%" 或 "-XXX%" 或 "X.X"
)
```

## 最佳实践

### 1. API 密钥管理

```python
# 使用环境变量
import os

api_key = os.getenv("MINIMAX_API_KEY")
if not api_key:
    raise ValueError("MINIMAX_API_KEY 环境变量未设置")

engine = MiniMaxTTSEngine(api_key=api_key)
```

### 2. 错误处理

```python
import asyncio
from pathlib import Path

async def safe_convert():
    engine = MiniMaxTTSEngine(api_key="sk-cp-your-api-key")
    
    try:
        await engine.convert_async(
            text="文本",
            output_path=Path("output.mp3"),
            voice="male-qn-qingse",
            rate="+0%"
        )
    except ImportError as e:
        print(f"缺少依赖: {e}")
    except ValueError as e:
        print(f"API 密钥错误: {e}")
    except Exception as e:
        print(f"转换失败: {e}")

asyncio.run(safe_convert())
```

### 3. 性能优化

```python
# 使用批量处理
engine = MiniMaxTTSEngine(api_key="sk-cp-your-api-key")

pages = [
    (1, "第一页", Path("page1.mp3")),
    (2, "第二页", Path("page2.mp3")),
    (3, "第三页", Path("page3.mp3")),
]

# 转换为 batch_convert 格式
texts = [(page_num, text, path) for page_num, text, path in pages]

import asyncio
asyncio.run(engine.batch_convert(
    texts,
    voice="male-qn-qingse",
    rate="+0%",
    batch_size=3  # 每次处理 3 个
))
```

## 支持的情感类型

| 情感 | 描述 | 适用场景 |
|-----|------|--------|
| `happy` | 开心 | 正面内容、庆祝、激励 |
| `sad` | 悲伤 | 沉重话题、反思 |
| `angry` | 愤怒 | 强调问题、警告 |
| `neutral` | 中立 | 默认、中性内容（推荐） |
| `peaceful` | 平和 | 放松、总结、结束 |

## 参考资源

- [MiniMax API 文档](https://api.minimaxi.com)
- [VidPPT 文档](../README_NEW.md)
- [TTS 引擎架构](../ARCHITECTURE.md)

## 常见问题

### Q: MiniMax 和 Edge TTS 有什么区别？

A: 
- **MiniMax**: 
  - 需要 API 密钥
  - 支持情感和发音字典
  - 音质更高
  - 需要付费

- **Edge TTS**:
  - 免费
  - 不需要密钥
  - 基本功能
  - 依赖微软服务

### Q: 可以同时使用两种引擎吗？

A: 可以在不同的处理流程中使用，但单个 Pipeline 只能选择一个引擎。

### Q: 如何处理大量文本？

A: 使用批量处理 `batch_convert` 方法，并调整 `batch_size` 参数。

## 贡献

如果你发现任何问题或有改进建议，欢迎提交 Issue 或 PR。

---

**最后更新**: 2026-04-09  
**版本**: 1.0
