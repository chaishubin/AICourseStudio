"""
人脸视频生成 API 基类

所有厂商实现都需要继承此基类并实现 generate 方法
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass


@dataclass
class FaceVideoResult:
    """人脸视频生成结果"""
    video_path: Path              # 生成的视频路径
    audio_path: Optional[Path] = None  # 音频路径（如果有）
    duration: float = 0.0         # 视频时长
    metadata: Dict[str, Any] = None    # 额外元数据


class BaseFaceVideoProvider(ABC):
    """
    人脸视频生成 API 基类

    子类需要实现：
    - generate(): 核心生成逻辑
    - validate_config(): 验证配置参数
    - get_required_params(): 返回必需参数列表

    使用示例：
    ```python
    class SadTalkerProvider(BaseFaceVideoProvider):
        def get_required_params(self):
            return ["checkpoint_path"]

        def generate(self, face_image, text, output_path, **kwargs):
            # 实现生成逻辑
            pass
    ```
    """

    # 厂商名称，子类需要覆盖
    name: str = "base"
    # 厂商描述
    description: str = "Base face video provider"

    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化 Provider

        Args:
            config: 厂商特定配置（如 API key、模型路径等）
        """
        self.config = config or {}
        self._validate_config()

    def _validate_config(self) -> None:
        """
        验证配置参数

        子类可以覆盖此方法添加特定验证逻辑
        """
        required = self.get_required_params()
        missing = [p for p in required if p not in self.config]
        if missing:
            raise ValueError(
                f"[{self.name}] 缺少必需参数: {missing}\n"
                f"必需参数: {required}\n"
                f"可选参数: {self.get_optional_params()}"
            )

    @abstractmethod
    def generate(
        self,
        face_image: Path,
        text: str,
        output_path: Path,
        **kwargs
    ) -> FaceVideoResult:
        """
        生成人脸视频

        Args:
            face_image: 人脸图像路径
            text: 文本内容（用于生成语音或驱动口型）
            output_path: 输出视频路径
            **kwargs: 额外参数（如音频路径、表情控制等）

        Returns:
            FaceVideoResult: 生成结果
        """
        pass

    def get_required_params(self) -> list:
        """
        返回必需的配置参数

        Returns:
            参数名列表
        """
        return []

    def get_optional_params(self) -> list:
        """
        返回可选的配置参数

        Returns:
            参数名列表
        """
        return []

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.name}>"
