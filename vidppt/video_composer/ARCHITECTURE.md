# 视频合成工具架构文档

## 整体架构

```mermaid
graph TB
    subgraph 主程序
        A[composer.py] --> B[扫描目录]
        A --> C[处理视频段]
        A --> D[拼接视频]
    end

    subgraph 核心模块
        C --> E[TTSGenerator]
        C --> F[FaceVideoGenerator]
        C --> G[视频合成]
    end

    subgraph TTS策略模块
        E --> E1[TextProcessor 基类]
        E1 --> E2[ExplicitPauseProcessor]
        E1 --> E3[PinyinAnnotationProcessor]
        E1 --> E4[SSMLProcessor]
        E1 --> E5[JiebaSegmentProcessor]
        E1 --> E6[CompositeProcessor]
        E --> E7[ProcessorFactory]
    end

    subgraph Provider模块
        F --> H[ProviderRegistry]
        H --> I[BaseFaceVideoProvider]
        I --> J[SadTalkerProvider]
        I --> K[HeyGenProvider]
        I --> L[自定义Provider...]
    end

    subgraph 视频处理
        G --> M[圆形遮罩]
        G --> N[位置计算]
        G --> O[转场效果]
    end
```

## 调用流程

```mermaid
sequenceDiagram
    participant User
    participant Main as composer.py
    participant Scan as scan_directory
    participant TTS as TTSGenerator
    participant Face as FaceVideoGenerator
    participant Provider as Provider
    participant Compose as 视频合成

    User->>Main: 启动 (input_dirs, face_image)
    Main->>Scan: 扫描目录
    Scan-->>Main: SegmentConfig

    loop 每个目录
        alt 有文本
            Main->>TTS: generate(text)
            TTS->>TTS: 解析标记语法
            TTS->>TTS: edge-tts API
            TTS-->>Main: audio_path
            Main->>Face: generate(audio, text)
            Face->>Provider: generate(face_image, text, audio)
            Provider->>Provider: 调用厂商API
            Provider-->>Face: video_path
        else 无文本
            Main->>Main: 创建静态图片片段
        end
        Main->>Compose: 合成视频段
    end

    Main->>Main: 添加转场效果
    Main->>Main: 输出最终视频
    Main-->>User: 完成
```

## Provider 模块架构

```mermaid
classDiagram
    class BaseFaceVideoProvider {
        <<abstract>>
        +name: str
        +description: str
        +config: Dict
        +generate(face_image, text, output_path, **kwargs) FaceVideoResult
        +get_required_params() list
        +get_optional_params() list
        +_validate_config()
    end

    class ProviderRegistry {
        -_providers: Dict
        +register(name, provider_class)
        +unregister(name) bool
        +get(name, config) BaseFaceVideoProvider
        +list_providers() Dict
        +is_registered(name) bool
    end

    class SadTalkerProvider {
        +name = "sadtalker"
        +API_BASE: str
        +generate()
        +get_required_params()
        +get_optional_params()
        -_build_command()
        -_run_command()
    end

    class HeyGenProvider {
        +name = "heygen"
        +API_BASE: str
        +generate()
        +get_required_params()
        +get_optional_params()
        -_create_video()
        -_poll_status()
        -_download_video()
    end

    class FaceVideoGenerator {
        -face_image_path: Path
        -provider: BaseFaceVideoProvider
        +generate(audio_path, output_path, text) Path
    end

    ProviderRegistry --> BaseFaceVideoProvider : 管理
    BaseFaceVideoProvider <|-- SadTalkerProvider
    BaseFaceVideoProvider <|-- HeyGenProvider
    FaceVideoGenerator --> BaseFaceVideoProvider : 使用
    FaceVideoGenerator --> ProviderRegistry : 获取Provider
```

## 模块依赖关系

```mermaid
graph LR
    subgraph 入口
        A[composer.py]
    end

    subgraph providers模块
        B[providers/__init__.py]
        C[providers/base.py]
        D[providers/registry.py]
        E[providers/sadtalker.py]
        F[providers/heygen.py]
    end

    subgraph 外部依赖
        G[edge-tts]
        H[moviepy]
        I[jieba 可选]
    end

    A --> B
    B --> C
    B --> D
    B --> E
    B --> F

    E -.本地.-> E
    F -.HTTP.-> F

    A --> G
    A --> H
    A -.可选.-> I
```

## 数据流

```mermaid
flowchart LR
    subgraph 输入
        A1[目录列表]
        A2[背景图片]
        A3[文本文件]
        A4[人脸图片]
    end

    subgraph 处理
        B1[目录扫描] --> B2[TTS转换]
        B2 --> B3[人脸视频生成]
        B3 --> B4[圆形遮罩处理]
        B4 --> B5[视频合成]
    end

    subgraph 输出
        C1[音频文件]
        C2[人脸视频]
        C3[视频片段]
        C4[最终视频]
    end

    A1 --> B1
    A2 --> B1
    A3 --> B2
    A4 --> B3

    B2 --> C1
    C1 --> B3
    B3 --> C2
    C2 --> B4
    B4 --> C3
    B5 --> C4
```

## 扩展 Provider

添加新的 Provider 只需：

```mermaid
flowchart TD
    A[创建 providers/my_provider.py] --> B[继承 BaseFaceVideoProvider]
    B --> C[实现 generate 方法]
    C --> D[定义必需/可选参数]
    D --> E[在 __init__.py 中导入]
    E --> F[自动注册到 Registry]
```

示例代码结构：

```python
# providers/my_provider.py
from .base import BaseFaceVideoProvider, FaceVideoResult
from .registry import register_provider

@register_provider("my_provider")
class MyProvider(BaseFaceVideoProvider):
    name = "my_provider"
    description = "我的 Provider"

    def get_required_params(self):
        return ["api_key"]

    def generate(self, face_image, text, output_path, **kwargs):
        # 实现生成逻辑
        ...
        return FaceVideoResult(video_path=output_path)
```

## TTS 文本处理策略模式

```mermaid
classDiagram
    class TextProcessor {
        <<abstract>>
        +name: str
        +description: str
        +process(text: str) str
    }

    class ExplicitPauseProcessor {
        +name = "explicit_pause"
        +pause_duration: str
        +process(text) str
    }

    class PinyinAnnotationProcessor {
        +name = "pinyin_annotation"
        +process(text) str
    }

    class SSMLProcessor {
        +name = "ssml"
        +process(text) str
    }

    class JiebaSegmentProcessor {
        +name = "jieba_segment"
        +pause_duration: str
        +process(text) str
    }

    class CompositeProcessor {
        +name = "composite"
        +processors: List~TextProcessor~
        +add_processor(processor)
        +process(text) str
    }

    class ProcessorFactory {
        -_registry: Dict
        +register(processor_class)
        +get(name, **kwargs) TextProcessor
        +list_all() Dict
    }

    class TTSGenerator {
        -voice: str
        -processor: TextProcessor
        +generate(text, output_path) Path
        +generate_async(text, output_path) Path
    }

    TextProcessor <|-- ExplicitPauseProcessor
    TextProcessor <|-- PinyinAnnotationProcessor
    TextProcessor <|-- SSMLProcessor
    TextProcessor <|-- JiebaSegmentProcessor
    TextProcessor <|-- CompositeProcessor

    CompositeProcessor o-- TextProcessor : 包含
    ProcessorFactory --> TextProcessor : 创建
    TTSGenerator --> TextProcessor : 使用
```

### 策略使用示例

```python
# 方式1: 默认策略（显式停顿 + 拼音标注）
tts = TTSGenerator()

# 方式2: 单一策略
tts = TTSGenerator(processor_name="jieba_segment")

# 方式3: 组合策略
tts = TTSGenerator(processor=CompositeProcessor()
    .add_processor(ProcessorFactory.get("jieba_segment"))
    .add_processor(ProcessorFactory.get("explicit_pause"))
    .add_processor(ProcessorFactory.get("pinyin_annotation")))
```

### 处理效果

| 策略 | 输入 | 输出 |
|------|------|------|
| explicit_pause | `武汉市\|长江二桥` | `武汉市<break time="200ms"/>长江二桥` |
| pinyin_annotation | `市[shi4]` | `<phoneme ph="shi4">市</phoneme>` |
| ssml | `<break time="500ms"/>` | `<break time="500ms"/>` (原样) |
| jieba_segment | `武汉市长江二桥` | `武汉市<break time="200ms"/>长江二桥` |

## 配置层级

```mermaid
graph TD
    A[VideoConfig] --> B[视频尺寸/帧率]
    A --> C[人脸位置/大小]
    A --> D[转场时长]
    A --> E[TTS语音]

    F[ProviderConfig] --> G[SadTalker: device/preprocess]
    F --> H[HeyGen: api_key/avatar_id]

    I[SegmentConfig] --> J[背景图片]
    I --> K[文本文件]
    I --> L[区域图片]
```
