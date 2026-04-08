# 使用示例

## 1. 基本使用

### 转换 PPT 为视频

```bash
# 最简单的用法
vidppt presentation.pptx

# 指定输出目录
vidppt presentation.pptx -o my_videos

# 使用男声
vidppt presentation.pptx --voice zh-CN-YunyangNeural

# 加速 20%
vidppt presentation.pptx --rate +20%
```

### 不保存中间文件

如果只需要最终视频，不需要保存文本、图片等中间文件：

```bash
vidppt presentation.pptx --no-intermediate
```

## 2. 编程使用

### 基础示例

```python
from pathlib import Path
from vidppt import Pipeline, ProcessConfig

# 创建配置
config = ProcessConfig(
    input_path=Path("input.pptx"),
    output_dir=Path("outputs"),
    enable_tts=True,
    enable_video=True,
    save_intermediate=True,
)

# 运行流程
pipeline = Pipeline(config)
pipeline.run()
```

### 自定义配置

```python
from vidppt import ProcessConfig, Pipeline

config = ProcessConfig(
    input_path=Path("presentation.pptx"),
    output_dir=Path("videos"),
    
    # 功能开关
    enable_tts=True,
    enable_video=True,
    save_intermediate=False,  # 不保存中间文件
    
    # TTS 配置
    tts_engine="edge-tts",
    tts_voice="zh-CN-YunyangNeural",  # 男声
    tts_rate="+15%",  # 加速 15%
    
    # 视频配置
    video_fps=30,
    video_codec="libx264",
    audio_codec="aac",
)

pipeline = Pipeline(config)
pipeline.run()
```

### 仅提取内容（不生成视频）

```python
config = ProcessConfig(
    input_path=Path("input.pptx"),
    output_dir=Path("outputs"),
    enable_tts=False,
    enable_video=False,
    save_intermediate=True,
)

pipeline = Pipeline(config)
pipeline.run()
```

## 3. 扩展开发示例

### 添加自定义文档处理器

假设要支持 Jupyter Notebook (.ipynb) 转视频：

```python
# vidppt/processors/notebook_processor.py
import json
from pathlib import Path
from vidppt import DocumentProcessor, register_processor
from vidppt.core.models import DocumentContent, PageContent, ProcessConfig

@register_processor
class NotebookProcessor(DocumentProcessor):
    """Jupyter Notebook 处理器"""
    
    @classmethod
    def supported_extensions(cls) -> list[str]:
        return ['.ipynb']
    
    def extract_content(self, config: ProcessConfig) -> DocumentContent:
        """提取 Notebook 内容"""
        with open(config.input_path, 'r', encoding='utf-8') as f:
            notebook = json.load(f)
        
        pages = []
        for i, cell in enumerate(notebook['cells'], start=1):
            if cell['cell_type'] == 'markdown':
                text = ''.join(cell['source'])
                page = PageContent(page_number=i, text=text)
                
                if config.save_intermediate:
                    page_dir = config.output_dir / str(i)
                    page_dir.mkdir(parents=True, exist_ok=True)
                    (page_dir / "text.txt").write_text(text, encoding='utf-8')
                
                pages.append(page)
        
        return DocumentContent(pages=pages)
    
    def render_pages(self, config: ProcessConfig) -> list[Path]:
        """渲染 Notebook 页面"""
        # 可以使用 nbconvert 转换为 HTML 再截图
        # 或使用 Pillow 直接渲染文本
        from PIL import Image, ImageDraw, ImageFont
        
        slide_images = []
        content = self.extract_content(config)
        
        for page in content.pages:
            # 创建空白图像
            img = Image.new('RGB', (1920, 1080), color='white')
            draw = ImageDraw.Draw(img)
            
            # 绘制文本（简化示例）
            draw.text((50, 50), page.text, fill='black')
            
            # 保存
            if config.save_intermediate:
                page_dir = config.output_dir / str(page.page_number)
                page_dir.mkdir(parents=True, exist_ok=True)
                out_path = page_dir / "slide.png"
            else:
                out_path = config.output_dir / f"_temp_slide_{page.page_number}.png"
            
            img.save(out_path)
            slide_images.append(out_path)
        
        return slide_images
```

使用：

```python
# 在 cli.py 中导入以注册
from vidppt.processors.notebook_processor import NotebookProcessor

# 然后就可以直接使用
vidppt notebook.ipynb
```

### 添加自定义 TTS 引擎

假设要对接讯飞语音：

```python
# vidppt/engines/tts/xunfei_tts_engine.py
from pathlib import Path
from vidppt.core.interfaces import TTSEngine
import httpx

class XunfeiTTSEngine(TTSEngine):
    """讯飞语音 TTS 引擎"""
    
    def __init__(self, app_id: str, api_key: str, api_secret: str):
        self.app_id = app_id
        self.api_key = api_key
        self.api_secret = api_secret
    
    async def convert_async(
        self,
        text: str,
        output_path: Path,
        voice: str,
        rate: str,
    ) -> None:
        """调用讯飞 API 进行语音合成"""
        # 1. 构造请求参数
        params = {
            "app_id": self.app_id,
            "text": text,
            "voice_name": voice,
            "speed": self._parse_rate(rate),
        }
        
        # 2. 调用 API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.xfyun.cn/v1/service/v1/tts",
                json=params,
                headers=self._build_headers(),
                timeout=30.0,
            )
            response.raise_for_status()
        
        # 3. 保存音频
        audio_data = response.content
        output_path.write_bytes(audio_data)
    
    def _parse_rate(self, rate: str) -> float:
        """将 "+10%" 转换为引擎需要的格式"""
        if rate.startswith('+'):
            return 1.0 + float(rate[1:-1]) / 100
        elif rate.startswith('-'):
            return 1.0 - float(rate[1:-1]) / 100
        return 1.0
    
    def _build_headers(self):
        """构造认证头"""
        # 实现签名逻辑
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
```

在 `pipeline.py` 中注册：

```python
def _create_tts_engine(self):
    if self.config.tts_engine == "edge-tts":
        return EdgeTTSEngine()
    elif self.config.tts_engine == "xunfei":
        return XunfeiTTSEngine(
            app_id=os.getenv("XUNFEI_APP_ID"),
            api_key=os.getenv("XUNFEI_API_KEY"),
            api_secret=os.getenv("XUNFEI_API_SECRET"),
        )
    else:
        raise ValueError(f"不支持的 TTS 引擎: {self.config.tts_engine}")
```

使用：

```bash
export XUNFEI_APP_ID="your-app-id"
export XUNFEI_API_KEY="your-api-key"
export XUNFEI_API_SECRET="your-api-secret"

vidppt input.pptx --tts-engine xunfei
```

### 自定义处理流程

如果需要在标准流程中添加自定义步骤：

```python
from vidppt import Pipeline, ProcessConfig

class CustomPipeline(Pipeline):
    """自定义处理流程"""
    
    def run(self):
        # 1. 预处理
        self._preprocess()
        
        # 2. 标准流程
        super().run()
        
        # 3. 后处理
        self._postprocess()
    
    def _preprocess(self):
        """预处理步骤"""
        print("执行自定义预处理...")
        # 例如：检查文件完整性、备份等
    
    def _postprocess(self):
        """后处理步骤"""
        print("执行自定义后处理...")
        # 例如：上传到云存储、发送通知等
        self._upload_to_cloud()
    
    def _upload_to_cloud(self):
        """上传视频到云存储"""
        video_path = (
            self.config.output_dir 
            / f"{self.config.input_path.stem}.mp4"
        )
        
        if video_path.exists():
            print(f"上传视频到云存储: {video_path}")
            # 实现上传逻辑
            # upload_file(video_path, bucket="my-videos")

# 使用
config = ProcessConfig(
    input_path=Path("input.pptx"),
    output_dir=Path("outputs"),
)

custom_pipeline = CustomPipeline(config)
custom_pipeline.run()
```

## 4. 批量处理

```python
from pathlib import Path
from vidppt import Pipeline, ProcessConfig

def batch_convert(input_dir: Path, output_base: Path):
    """批量转换目录下的所有 PPT 文件"""
    ppt_files = list(input_dir.glob("*.pptx")) + list(input_dir.glob("*.ppt"))
    
    for ppt_file in ppt_files:
        print(f"\n处理: {ppt_file.name}")
        
        # 为每个文件创建独立的输出目录
        output_dir = output_base / ppt_file.stem
        
        config = ProcessConfig(
            input_path=ppt_file,
            output_dir=output_dir,
            save_intermediate=False,  # 批量处理时不保存中间文件
        )
        
        try:
            pipeline = Pipeline(config)
            pipeline.run()
            print(f"✓ 完成: {ppt_file.name}")
        except Exception as e:
            print(f"✗ 失败: {ppt_file.name} - {e}")

# 使用
batch_convert(
    input_dir=Path("presentations"),
    output_base=Path("videos")
)
```

## 5. 高级配置示例

### 多语言支持

```python
# 英文演示文稿
config = ProcessConfig(
    input_path=Path("presentation_en.pptx"),
    output_dir=Path("outputs"),
    tts_voice="en-US-JennyNeural",  # 英文声音
    tts_rate="+0%",
)
```

### 高质量视频输出

```python
config = ProcessConfig(
    input_path=Path("presentation.pptx"),
    output_dir=Path("outputs"),
    video_fps=60,  # 更高帧率
    video_codec="libx265",  # H.265 编码
    audio_codec="aac",
)
```

### 仅生成音频（不生成视频）

```python
config = ProcessConfig(
    input_path=Path("presentation.pptx"),
    output_dir=Path("outputs"),
    enable_tts=True,
    enable_video=False,  # 跳过视频合成
    save_intermediate=True,  # 保存音频文件
)
```

## 6. 错误处理

```python
from vidppt import Pipeline, ProcessConfig
from vidppt.core.registry import ProcessorRegistry

def safe_convert(input_path: Path, output_dir: Path):
    """带错误处理的转换"""
    # 检查文件是否存在
    if not input_path.exists():
        print(f"错误：文件不存在 {input_path}")
        return False
    
    # 检查文件格式是否支持
    if not ProcessorRegistry.is_supported(input_path):
        supported = ProcessorRegistry.list_supported_extensions()
        print(f"错误：不支持的格式 {input_path.suffix}")
        print(f"支持的格式: {', '.join(supported)}")
        return False
    
    # 执行转换
    try:
        config = ProcessConfig(
            input_path=input_path,
            output_dir=output_dir,
        )
        pipeline = Pipeline(config)
        pipeline.run()
        return True
    except Exception as e:
        print(f"转换失败: {e}")
        import traceback
        traceback.print_exc()
        return False

# 使用
success = safe_convert(
    input_path=Path("presentation.pptx"),
    output_dir=Path("outputs")
)
```

## 7. 环境变量配置

```bash
# .env 文件
VIDPPT_OUTPUT_DIR=./outputs
VIDPPT_TTS_ENGINE=edge-tts
VIDPPT_TTS_VOICE=zh-CN-XiaoxiaoNeural
VIDPPT_TTS_RATE=+0%
VIDPPT_SAVE_INTERMEDIATE=true
```

```python
import os
from pathlib import Path
from vidppt import ProcessConfig, Pipeline

# 从环境变量读取配置
config = ProcessConfig(
    input_path=Path("input.pptx"),
    output_dir=Path(os.getenv("VIDPPT_OUTPUT_DIR", "outputs")),
    tts_engine=os.getenv("VIDPPT_TTS_ENGINE", "edge-tts"),
    tts_voice=os.getenv("VIDPPT_TTS_VOICE", "zh-CN-XiaoxiaoNeural"),
    tts_rate=os.getenv("VIDPPT_TTS_RATE", "+0%"),
    save_intermediate=os.getenv("VIDPPT_SAVE_INTERMEDIATE", "true").lower() == "true",
)

pipeline = Pipeline(config)
pipeline.run()
```

这些示例涵盖了从基本使用到高级扩展的各种场景，可以根据实际需求选择合适的方式使用。
