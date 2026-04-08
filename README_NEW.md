# VidPPT - 文档到视频转换工具

将 PPT、PDF、Word 等文档自动转换为配音讲解视频的可扩展框架。

## 特性

- 支持多种文档格式（PPT/PPTX，PDF 和 Word 支持即将推出）
- 可扩展的架构设计：
  - 插件式文档处理器
  - 多种 TTS 引擎支持（Edge TTS、API 调用等）
  - 灵活的 OCR 引擎
  - 可配置的图像转换器
- 自动提取文字、图片
- 文字转语音（多种中文声音）
- 合成视频
- 可选的中间文件保存

## 项目结构

```
vidppt/
├── vidppt/                    # 主包
│   ├── core/                  # 核心抽象层
│   │   ├── interfaces.py      # 接口定义（处理器、引擎等）
│   │   ├── models.py          # 数据模型
│   │   └── registry.py        # 处理器注册中心
│   ├── processors/            # 文档处理器
│   │   ├── ppt_processor.py   # PPT 处理器
│   │   └── pdf_processor.py   # PDF 处理器（示例）
│   ├── engines/               # 各种引擎
│   │   ├── tts/               # 文字转语音引擎
│   │   │   ├── edge_tts_engine.py    # Edge TTS
│   │   │   └── api_tts_engine.py     # API TTS（示例）
│   │   ├── ocr/               # OCR 引擎
│   │   │   └── ocr_engines.py
│   │   └── image_converter/   # 图像转换器
│   │       └── converters.py
│   ├── utils/                 # 工具类
│   │   └── video_composer.py  # 视频合成
│   ├── pipeline.py            # 主处理流程
│   └── cli.py                 # 命令行入口
├── extract_ppt.py             # 旧版入口（保留兼容）
└── run.sh                     # 一键运行脚本
```

## 快速开始

### 安装

```bash
# 克隆仓库
git clone <repo-url>
cd vidppt

# 安装依赖
uv sync

# 或使用 pip
pip install -e .
```

### 基本使用

```bash
# 方式 1: 使用脚本（推荐）
./run.sh datas/example.pptx

# 方式 2: 直接使用命令
uv run vidppt datas/example.pptx

# 方式 3: 安装后直接调用
vidppt datas/example.pptx
```

### 常用选项

```bash
# 指定输出目录
vidppt input.pptx -o my_output

# 不保存中间文件（仅保留最终视频）
vidppt input.pptx --no-intermediate

# 使用不同的声音
vidppt input.pptx --voice zh-CN-YunyangNeural

# 调整语速
vidppt input.pptx --rate +20%

# 跳过某些步骤
vidppt input.pptx --no-tts        # 跳过语音合成
vidppt input.pptx --no-video      # 跳过视频合成
```

### 可用的 TTS 声音

Edge TTS 支持的中文声音：

- `zh-CN-XiaoxiaoNeural` - 女声·温暖（默认）
- `zh-CN-YunyangNeural` - 男声·专业
- `zh-CN-YunxiNeural` - 男声·活泼
- `zh-CN-XiaoyiNeural` - 女声·活泼

## 扩展开发

### 1. 添加新的文档处理器

创建一个新的处理器来支持其他文档格式：

```python
# vidppt/processors/word_processor.py
from vidppt import DocumentProcessor, register_processor
from vidppt.core.models import DocumentContent, ProcessConfig

@register_processor
class WordProcessor(DocumentProcessor):
    @classmethod
    def supported_extensions(cls) -> list[str]:
        return ['.doc', '.docx']
    
    def extract_content(self, config: ProcessConfig) -> DocumentContent:
        # 实现文档内容提取
        pass
    
    def render_pages(self, config: ProcessConfig) -> list[Path]:
        # 实现页面渲染
        pass
```

### 2. 添加新的 TTS 引擎

实现自定义 TTS 引擎（如云服务 API）：

```python
# vidppt/engines/tts/my_tts_engine.py
from pathlib import Path
from vidppt.core.interfaces import TTSEngine

class MyTTSEngine(TTSEngine):
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    async def convert_async(
        self,
        text: str,
        output_path: Path,
        voice: str,
        rate: str,
    ) -> None:
        # 实现 API 调用
        # 1. 发送请求到 TTS API
        # 2. 接收音频数据
        # 3. 保存到 output_path
        pass
```

然后在 `pipeline.py` 中注册：

```python
def _create_tts_engine(self):
    if self.config.tts_engine == "my-tts":
        return MyTTSEngine(api_key="your-key")
    # ...
```

### 3. 添加 OCR 引擎

```python
# vidppt/engines/ocr/my_ocr_engine.py
from vidppt.core.interfaces import OCREngine

class MyOCREngine(OCREngine):
    def extract_text(self, image_path: Path) -> str:
        # 实现 OCR 识别
        pass
```

### 4. 使用自定义处理流程

```python
from vidppt import Pipeline, ProcessConfig
from pathlib import Path

# 创建配置
config = ProcessConfig(
    input_path=Path("input.pptx"),
    output_dir=Path("outputs"),
    enable_tts=True,
    enable_video=True,
    save_intermediate=False,  # 不保存中间文件
    tts_voice="zh-CN-YunyangNeural",
    tts_rate="+10%",
)

# 运行流程
pipeline = Pipeline(config)
pipeline.run()
```

## 输出结构

### 保存中间文件时 (默认)

```
outputs/
├── example.mp4              # 最终视频
├── 1/
│   ├── text.txt            # 页面文字
│   ├── slide.png           # 整页截图
│   ├── audio.mp3           # 配音
│   └── image_*.png         # 内嵌图片（如果有）
├── 2/
│   └── ...
└── ...
```

### 不保存中间文件时 (`--no-intermediate`)

```
outputs/
└── example.mp4              # 仅最终视频
```

## 依赖说明

### 核心依赖

- `python-pptx` - PPT 解析
- `spire.presentation` - PPT 渲染
- `edge-tts` - 文字转语音
- `moviepy` - 视频合成
- `Pillow` - 图像处理

### 可选依赖

```bash
# PDF 支持
uv sync --extra pdf
# 或
pip install vidppt[pdf]

# OCR 支持
uv sync --extra ocr
# 或
pip install vidppt[ocr]

# API 调用支持
uv sync --extra api
# 或
pip install vidppt[api]
```

## 开发计划

- [ ] 完善 PDF 处理器实现
- [ ] 添加 Word 文档处理器
- [ ] 支持更多 TTS 引擎（阿里云、腾讯云等）
- [ ] 添加视频转场效果
- [ ] 支持自定义字幕样式
- [ ] Web UI 界面

## 常见问题

### 1. Edge TTS 连接失败

Edge TTS 需要访问微软服务器，请检查网络连接。如果无法使用，可以切换到其他 TTS 引擎。

### 2. 如何添加自定义 TTS API？

参考 `vidppt/engines/tts/api_tts_engine.py` 中的示例代码，实现 `TTSEngine` 接口即可。

### 3. PDF 支持何时完善？

PDF 处理器框架已搭建完成，需要根据具体需求实现。可以使用 `pdfplumber` 提取文本，`pdf2image` 转换图像。

## 许可证

MIT

## 贡献

欢迎提交 Issue 和 Pull Request！

## API 调用示例

### MiniMax TTS（参考）

```bash
curl --request POST \
  --url https://api.minimaxi.com/v1/t2a_v2 \
  --header 'Authorization: Bearer sk-cp-xxx' \
  --header 'Content-Type: application/json' \
  --data '{
    "model": "speech-2.8-hd",
    "text": "今天是不是很开心呀",
    "stream": false,
    "voice_setting": {
      "voice_id": "male-qn-qingse",
      "speed": 1,
      "vol": 1,
      "pitch": 0,
      "emotion": "happy"
    },
    "audio_setting": {
      "sample_rate": 32000,
      "bitrate": 128000,
      "format": "mp3",
      "channel": 1
    }
  }'
```

提取音频：
```bash
jq '.data.audio' response.json | xxd -r -p > output.mp3
```
