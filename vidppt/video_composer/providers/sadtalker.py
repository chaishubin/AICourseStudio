"""
SadTalker Provider 实现

SadTalker: https://github.com/OpenTalker/SadTalker

配置参数：
- checkpoint_path: 模型检查点路径
- device: 运行设备 (cuda/cpu)
- preprocess: 预处理模式 (crop/extensive)
"""

import subprocess
from pathlib import Path
from typing import Any, Dict

from .base import BaseFaceVideoProvider, FaceVideoResult
from .registry import register_provider


@register_provider("sadtalker")
class SadTalkerProvider(BaseFaceVideoProvider):
    """SadTalker 人脸视频生成"""

    name = "sadtalker"
    description = "SadTalker: Learning Realistic 3D Motion Coefficients for Stylized Audio-Driven Single Image Talking Face Animation"

    def get_required_params(self) -> list:
        return []  # 基础参数都有默认值

    def get_optional_params(self) -> list:
        return [
            "checkpoint_path",    # 模型路径
            "device",             # cuda/cpu
            "preprocess",         # crop/extensive
            "facerender",         # face render 模式
            "bg_user",            # 背景图片
            "still",              # 是否静止模式
            "expression_scale",   # 表情强度
        ]

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
            text: 文本内容（需要配合 TTS 使用）
            output_path: 输出路径
            **kwargs:
                - audio_path: 已生成的音频路径（必需）
        """
        audio_path = kwargs.get("audio_path")
        if audio_path is None:
            raise ValueError("SadTalker 需要 audio_path 参数")

        # 构建命令
        cmd = self._build_command(face_image, audio_path, output_path)

        # 执行生成
        self._run_command(cmd)

        return FaceVideoResult(
            video_path=output_path,
            audio_path=Path(audio_path),
        )

    def _build_command(
        self,
        face_image: Path,
        audio_path: Path,
        output_path: Path
    ) -> list:
        """构建 SadTalker 命令"""
        # 默认参数
        checkpoint = self.config.get("checkpoint_path", "checkpoints/SadTalker_V0.0.2_256.pth")
        device = self.config.get("device", "cuda")
        preprocess = self.config.get("preprocess", "crop")
        facerender = self.config.get("facerender", "facevid2vid_256")

        cmd = [
            "python", "inference.py",
            "--source", str(face_image),
            "--driving", str(audio_path),
            "--output", str(output_path),
            "--checkpoint", checkpoint,
            "--device", device,
            "--preprocess", preprocess,
            "--facerender", facerender,
        ]

        # 添加可选参数
        if self.config.get("still"):
            cmd.append("--still")
        if "expression_scale" in self.config:
            cmd.extend(["--expression_scale", str(self.config["expression_scale"])])

        return cmd

    def _run_command(self, cmd: list) -> None:
        """执行命令"""
        print(f"[SadTalker] 执行: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"SadTalker 执行失败:\n{result.stderr}")
