"""
人脸视频生成 Provider 模块

支持的 Provider：
- sadtalker: SadTalker 本地模型
- heygen: HeyGen Cloud API

使用示例：
```python
from providers import get_provider, list_providers

# 查看可用 Provider
print(list_providers())
# {'sadtalker': 'SadTalker...', 'heygen': 'HeyGen...'}

# 获取 SadTalker Provider
provider = get_provider("sadtalker", {
    "checkpoint_path": "/path/to/checkpoint",
    "device": "cuda"
})

# 生成视频
result = provider.generate(
    face_image="face.jpg",
    text="你好",
    output_path="output.mp4",
    audio_path="audio.mp3"
)
```

添加自定义 Provider：
```python
from providers import BaseFaceVideoProvider, register_provider

@register_provider("my_provider")
class MyProvider(BaseFaceVideoProvider):
    name = "my_provider"
    description = "My custom provider"

    def generate(self, face_image, text, output_path, **kwargs):
        # 实现生成逻辑
        pass
```
"""

from .base import BaseFaceVideoProvider, FaceVideoResult
from .registry import (
    ProviderRegistry,
    registry,
    register_provider,
    get_provider,
    list_providers,
)

# 自动导入并注册所有内置 Provider
from . import sadtalker
from . import heygen

__all__ = [
    # 基类
    "BaseFaceVideoProvider",
    "FaceVideoResult",
    # 注册中心
    "ProviderRegistry",
    "registry",
    "register_provider",
    # 便捷函数
    "get_provider",
    "list_providers",
]
