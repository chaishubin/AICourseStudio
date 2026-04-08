# VidPPT 架构设计文档

## 设计目标

1. **可扩展性**：支持轻松添加新的文档格式、TTS 引擎、OCR 引擎等
2. **模块化**：不同功能模块分离，便于维护和测试
3. **灵活配置**：支持多种配置选项，满足不同场景需求
4. **插件化**：通过注册机制动态加载处理器

## 核心架构

### 1. 分层设计

```
┌─────────────────────────────────────────┐
│         CLI / API Layer                 │  命令行/API 接口
├─────────────────────────────────────────┤
│         Pipeline Layer                  │  流程控制层
├─────────────────────────────────────────┤
│    Processors  │  Engines  │  Utils     │  处理器/引擎/工具层
├────────────────┴───────────┴────────────┤
│         Core Abstractions               │  核心抽象层
├─────────────────────────────────────────┤
│         Data Models                     │  数据模型层
└─────────────────────────────────────────┘
```

### 2. 核心抽象接口

#### DocumentProcessor（文档处理器）

所有文档处理器的基类，定义统一的处理流程：

```python
class DocumentProcessor(ABC):
    @classmethod
    @abstractmethod
    def supported_extensions(cls) -> list[str]:
        """返回支持的文件扩展名"""
        
    @abstractmethod
    def extract_content(self, config: ProcessConfig) -> DocumentContent:
        """提取文档内容（文字、图片等）"""
        
    @abstractmethod
    def render_pages(self, config: ProcessConfig) -> list[Path]:
        """渲染页面为图像"""
    
    def process(self, config: ProcessConfig) -> DocumentContent:
        """完整处理流程（模板方法）"""
```

**设计要点**：
- 使用模板方法模式，`process()` 定义标准流程
- 子类实现 `extract_content()` 和 `render_pages()`
- 通过 `supported_extensions()` 声明支持的格式

#### TTSEngine（文字转语音引擎）

支持多种 TTS 实现：

```python
class TTSEngine(ABC):
    @abstractmethod
    async def convert_async(
        self,
        text: str,
        output_path: Path,
        voice: str,
        rate: str,
    ) -> None:
        """异步转换单个文本为音频"""
    
    async def batch_convert(
        self,
        texts: list[tuple[int, str, Path]],
        voice: str,
        rate: str,
        batch_size: int = 5,
    ) -> None:
        """批量转换（内置并发控制）"""
```

**设计要点**：
- 使用异步设计提高效率
- 内置批量处理和并发控制
- 易于对接不同的 TTS 服务

#### OCREngine（OCR 引擎）

支持多种 OCR 实现：

```python
class OCREngine(ABC):
    @abstractmethod
    def extract_text(self, image_path: Path) -> str:
        """从图像中提取文字"""
    
    @abstractmethod
    def extract_text_batch(self, image_paths: list[Path]) -> list[str]:
        """批量提取"""
```

#### ImageConverter（图像转换器）

支持多种图像转换方式：

```python
class ImageConverter(ABC):
    @abstractmethod
    def convert_to_image(
        self,
        source_path: Path,
        output_path: Path,
        page_number: Optional[int] = None,
    ) -> Path:
        """转换单页"""
    
    @abstractmethod
    def convert_all_pages(
        self,
        source_path: Path,
        output_dir: Path,
    ) -> list[Path]:
        """转换所有页"""
```

### 3. 注册机制

使用装饰器模式实现处理器自动注册：

```python
@register_processor
class PPTProcessor(DocumentProcessor):
    @classmethod
    def supported_extensions(cls) -> list[str]:
        return ['.ppt', '.pptx']
```

**工作原理**：
1. 导入处理器模块时，`@register_processor` 装饰器被执行
2. 处理器类注册到 `ProcessorRegistry`
3. 根据文件扩展名自动路由到对应处理器

**优势**：
- 零配置：添加新处理器只需实现接口和添加装饰器
- 动态加载：无需修改主流程代码
- 易于扩展：支持第三方插件

### 4. 数据流

```
输入文档
   ↓
[DocumentProcessor]
   ├─→ extract_content()  → DocumentContent
   │                          ├─ pages[]
   │                          │   ├─ text
   │                          │   ├─ images[]
   │                          │   └─ metadata
   │                          └─ metadata
   └─→ render_pages()      → slide_images[]
   ↓
[TTSEngine]
   └─→ batch_convert()     → audio_files[]
   ↓
[VideoComposer]
   └─→ compose()           → final_video.mp4
```

### 5. 配置管理

统一的配置模型：

```python
@dataclass
class ProcessConfig:
    # 输入输出
    input_path: Path
    output_dir: Path
    
    # 功能开关
    enable_tts: bool = True
    enable_video: bool = True
    save_intermediate: bool = True
    
    # 引擎选择
    tts_engine: str = "edge-tts"
    ocr_engine: str = "builtin"
    image_converter: str = "builtin"
    
    # 引擎参数
    tts_voice: str = "zh-CN-XiaoxiaoNeural"
    tts_rate: str = "+0%"
    video_fps: int = 24
    # ...
```

**设计要点**：
- 使用 `dataclass` 提供类型提示
- 集中管理所有配置项
- 提供合理的默认值

## 扩展指南

### 添加新文档处理器

1. 在 `vidppt/processors/` 创建新文件
2. 继承 `DocumentProcessor`
3. 实现必需方法
4. 添加 `@register_processor` 装饰器
5. 在 `cli.py` 中导入以触发注册

示例：支持 Markdown

```python
@register_processor
class MarkdownProcessor(DocumentProcessor):
    @classmethod
    def supported_extensions(cls) -> list[str]:
        return ['.md', '.markdown']
    
    def extract_content(self, config: ProcessConfig) -> DocumentContent:
        # 解析 Markdown 文件
        # 可以按标题拆分为多页
        pass
    
    def render_pages(self, config: ProcessConfig) -> list[Path]:
        # 使用 Pillow/reportlab 渲染
        # 或调用 pandoc 转换
        pass
```

### 添加新 TTS 引擎

1. 在 `vidppt/engines/tts/` 创建新文件
2. 继承 `TTSEngine`
3. 实现 `convert_async()`
4. 在 `Pipeline._create_tts_engine()` 中注册

示例：阿里云 TTS

```python
class AliyunTTSEngine(TTSEngine):
    def __init__(self, access_key: str, access_secret: str):
        self.client = AliyunClient(access_key, access_secret)
    
    async def convert_async(self, text: str, output_path: Path, 
                           voice: str, rate: str) -> None:
        response = await self.client.synthesize(
            text=text,
            voice=voice,
            speed=self._parse_rate(rate),
        )
        output_path.write_bytes(response.audio_data)
```

### 添加新 OCR 引擎

1. 在 `vidppt/engines/ocr/` 创建或修改文件
2. 继承 `OCREngine`
3. 实现文字提取方法

### 自定义处理流程

如果标准流程不满足需求，可以重写 `DocumentProcessor.process()`：

```python
class CustomProcessor(DocumentProcessor):
    def process(self, config: ProcessConfig) -> DocumentContent:
        # 自定义流程
        content = self.extract_content(config)
        
        # 添加自定义步骤
        self.preprocess_images(content)
        self.enhance_text(content)
        
        # 继续标准流程
        slide_images = self.render_pages(config)
        for i, page in enumerate(content.pages):
            page.slide_image = slide_images[i]
        
        return content
```

## 最佳实践

### 1. 错误处理

- 在关键操作处添加 try-except
- 提供清晰的错误提示
- 优雅降级（如 TTS 失败时继续处理其他页）

### 2. 资源管理

- 及时释放大对象（如图像、视频片段）
- 使用上下文管理器
- 清理临时文件

### 3. 性能优化

- 使用异步批量处理
- 控制并发数量避免资源耗尽
- 缓存中间结果

### 4. 测试

- 为每个处理器编写单元测试
- 测试边界条件（空文档、超大文档等）
- 集成测试验证完整流程

## 未来改进

1. **流式处理**：支持处理超大文档，逐页处理而非全部加载
2. **插件系统**：支持从外部加载处理器插件
3. **任务队列**：支持异步任务和进度跟踪
4. **Web API**：提供 RESTful API 接口
5. **分布式处理**：支持多机并行处理大批量文档

## 总结

该架构具有以下优势：

- **开放封闭原则**：对扩展开放，对修改封闭
- **依赖倒置**：依赖抽象而非具体实现
- **单一职责**：每个类专注于单一功能
- **可测试性**：模块化设计便于单元测试
- **可维护性**：清晰的结构和文档

通过这种设计，添加新功能只需实现对应接口，无需修改核心代码。
