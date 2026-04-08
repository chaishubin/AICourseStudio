# 迁移指南：从旧版到新架构

## 概述

新架构（v0.2.0）相比旧版本（v0.1.0）进行了全面重构，提供了更好的可扩展性和模块化设计。

## 主要变化

### 1. 项目结构

**旧版本：**
```
vidppt/
├── extract_ppt.py      # 单一脚本，所有功能耦合在一起
└── run.sh
```

**新版本：**
```
vidppt/
├── vidppt/             # 模块化包结构
│   ├── core/           # 核心抽象
│   ├── processors/     # 文档处理器（可扩展）
│   ├── engines/        # 各种引擎（TTS、OCR等）
│   ├── utils/          # 工具类
│   ├── pipeline.py     # 主流程
│   └── cli.py          # CLI 入口
├── extract_ppt.py      # 保留兼容性
└── run.sh              # 更新为使用新CLI
```

### 2. 命令行接口

**旧版本：**
```bash
# 使用旧脚本
uv run python extract_ppt.py input.pptx -o outputs --voice zh-CN-YunyangNeural
```

**新版本：**
```bash
# 新的 CLI 命令（推荐）
uv run vidppt input.pptx -o outputs --voice zh-CN-YunyangNeural

# 或使用更新后的 run.sh
./run.sh input.pptx outputs --voice zh-CN-YunyangNeural

# 旧命令仍然可用（兼容性）
uv run python extract_ppt.py input.pptx -o outputs
```

### 3. 编程接口

**旧版本：**
```python
# 直接调用函数
from extract_ppt import process_ppt

process_ppt(
    ppt_path="input.pptx",
    output_root="outputs",
    tts=True,
    voice="zh-CN-XiaoxiaoNeural",
    rate="+0%",
    video=True,
)
```

**新版本：**
```python
# 使用配置对象和流程管道
from pathlib import Path
from vidppt import Pipeline, ProcessConfig

config = ProcessConfig(
    input_path=Path("input.pptx"),
    output_dir=Path("outputs"),
    enable_tts=True,
    enable_video=True,
    save_intermediate=True,  # 新增：控制中间文件
    tts_voice="zh-CN-XiaoxiaoNeural",
    tts_rate="+0%",
)

pipeline = Pipeline(config)
pipeline.run()
```

### 4. 新增功能

#### 中间文件控制

**新版本新增：**
```bash
# 不保存中间文件，仅生成最终视频
vidppt input.pptx --no-intermediate
```

```python
config = ProcessConfig(
    input_path=Path("input.pptx"),
    output_dir=Path("outputs"),
    save_intermediate=False,  # 新增选项
)
```

#### 可扩展架构

**支持添加新文档格式：**
```python
from vidppt import DocumentProcessor, register_processor

@register_processor
class WordProcessor(DocumentProcessor):
    @classmethod
    def supported_extensions(cls):
        return ['.doc', '.docx']
    
    # 实现接口方法...
```

**支持添加新 TTS 引擎：**
```python
from vidppt.core.interfaces import TTSEngine

class MyTTSEngine(TTSEngine):
    async def convert_async(self, text, output_path, voice, rate):
        # 实现自定义 TTS 逻辑
        pass
```

## 兼容性说明

### 保留的功能

✅ 旧的 `extract_ppt.py` 脚本仍然可用  
✅ 旧的命令行参数保持兼容  
✅ 输出目录结构保持一致（当 `save_intermediate=True` 时）  
✅ 所有原有功能均已保留

### 不兼容的变化

⚠️ **Python API 完全重写**
- 如果你在代码中直接导入 `extract_ppt` 模块的函数，需要迁移到新 API
- 建议使用新的 `Pipeline` 和 `ProcessConfig`

⚠️ **依赖变化**
- 添加了可选依赖分组（pdf、ocr、api）
- 需要重新运行 `uv sync`

## 迁移步骤

### 命令行用户

如果你只是通过命令行使用，几乎无需改变：

```bash
# 步骤 1: 拉取最新代码
git pull

# 步骤 2: 同步依赖
uv sync

# 步骤 3: 使用新命令（推荐）或继续使用旧命令
vidppt input.pptx  # 新命令
# 或
./run.sh input.pptx  # 更新后的脚本
# 或
uv run python extract_ppt.py input.pptx  # 旧命令仍可用
```

### Python API 用户

如果你在代码中使用了旧 API，需要迁移：

**迁移前：**
```python
from extract_ppt import process_ppt

process_ppt(
    ppt_path="input.pptx",
    output_root="outputs",
    tts=True,
    voice="zh-CN-XiaoxiaoNeural",
    rate="+10%",
    video=True,
)
```

**迁移后：**
```python
from pathlib import Path
from vidppt import Pipeline, ProcessConfig

config = ProcessConfig(
    input_path=Path("input.pptx"),
    output_dir=Path("outputs"),
    enable_tts=True,
    enable_video=True,
    tts_voice="zh-CN-XiaoxiaoNeural",
    tts_rate="+10%",
)

pipeline = Pipeline(config)
pipeline.run()
```

### 批量处理脚本迁移

**迁移前：**
```python
import os
from extract_ppt import process_ppt

for file in os.listdir("inputs"):
    if file.endswith(".pptx"):
        process_ppt(
            ppt_path=f"inputs/{file}",
            output_root=f"outputs/{file[:-5]}",
        )
```

**迁移后：**
```python
from pathlib import Path
from vidppt import Pipeline, ProcessConfig

input_dir = Path("inputs")
for ppt_file in input_dir.glob("*.pptx"):
    config = ProcessConfig(
        input_path=ppt_file,
        output_dir=Path("outputs") / ppt_file.stem,
        save_intermediate=False,  # 批量处理时建议关闭
    )
    
    pipeline = Pipeline(config)
    pipeline.run()
```

## 新特性亮点

### 1. 模块化架构
- 清晰的职责分离
- 易于测试和维护
- 支持第三方扩展

### 2. 插件式处理器
- 通过装饰器自动注册
- 支持多种文档格式
- 轻松添加新格式支持

### 3. 多引擎支持
- TTS：Edge TTS、API TTS（可扩展）
- OCR：Tesseract、API OCR（可扩展）
- 图像转换：Spire、API（可扩展）

### 4. 灵活配置
- 统一的配置模型
- 类型提示支持
- 环境变量配置

### 5. 更好的开发体验
- 完整的类型提示
- 详细的文档
- 丰富的示例代码

## 获取帮助

### 文档

- [README_NEW.md](README_NEW.md) - 新版使用指南
- [ARCHITECTURE.md](ARCHITECTURE.md) - 架构设计文档
- [EXAMPLES.md](EXAMPLES.md) - 详细示例代码

### 命令行帮助

```bash
vidppt --help
```

### 问题反馈

如果遇到问题，请：
1. 查看文档
2. 检查日志输出
3. 提交 Issue

## 常见问题

### Q: 旧脚本还能用吗？
A: 可以，`extract_ppt.py` 保持向后兼容。

### Q: 必须迁移到新 API 吗？
A: 命令行用户不需要，Python API 用户建议迁移以获得更好的扩展性。

### Q: 输出格式有变化吗？
A: 没有，当 `save_intermediate=True` 时，输出结构与旧版完全一致。

### Q: 性能有提升吗？
A: 核心逻辑相同，但新架构提供了更好的批量处理支持和异步优化空间。

### Q: 如何贡献代码？
A: 查看 [ARCHITECTURE.md](ARCHITECTURE.md) 了解如何添加新处理器或引擎。

## 总结

新架构在保持向后兼容的同时，提供了：
- ✅ 更好的可扩展性
- ✅ 更清晰的代码结构
- ✅ 更丰富的功能
- ✅ 更好的开发体验

推荐逐步迁移到新 API 以享受这些优势！
