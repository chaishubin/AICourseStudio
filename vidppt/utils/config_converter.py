"""
配置转换器

将配置字典转换为 ProcessConfig 对象。
"""

from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger

from ..core.models import ProcessConfig


class ConfigConverter:
    """配置转换器"""

    @staticmethod
    def to_process_config(config_dict: Dict[str, Any]) -> ProcessConfig:
        """
        将配置字典转换为 ProcessConfig 对象

        参数:
            config_dict: 配置字典

        返回:
            ProcessConfig 对象

        抛出异常:
            ValueError: 配置缺少必填字段或包含无效值
        """
        # 检查必填字段
        if "input" not in config_dict:
            raise ValueError("配置缺少必填字段 'input'")

        input_path = Path(config_dict["input"])
        if not input_path.exists():
            raise ValueError(f"输入文件不存在: {input_path}")

        # 输出目录，默认为 'outputs'
        output_dir = Path(config_dict.get("output", "outputs"))

        # 创建 ProcessConfig
        process_config = ProcessConfig(
            input_path=input_path,
            output_dir=output_dir,
            # 功能开关
            enable_tts=config_dict.get("enable_tts", True),
            enable_video=config_dict.get("enable_video", True),
            save_intermediate=config_dict.get("save_intermediate", True),
            # TTS 配置
            tts_engine=config_dict.get("tts_engine", "edge-tts"),
            tts_voice=config_dict.get("tts_voice", "zh-CN-XiaoxiaoNeural"),
            tts_rate=config_dict.get("tts_rate", "+0%"),
            tts_options=config_dict.get("tts_options", {}),
            # 缓存配置
            enable_audio_cache=config_dict.get("enable_audio_cache", True),
            audio_cache_dir=ConfigConverter._resolve_path(
                config_dict.get("audio_cache_dir")
            ),
            audio_cache_expiry_days=config_dict.get("audio_cache_expiry_days", 30),
            # OCR 配置
            ocr_engine=config_dict.get("ocr_engine", "builtin"),
            # 图像转换配置
            image_converter=config_dict.get("image_converter", "builtin"),
            # 视频配置
            video_fps=config_dict.get("video_fps", 24),
            video_codec=config_dict.get("video_codec", "libx264"),
            audio_codec=config_dict.get("audio_codec", "aac"),
        )

        logger.debug(f"配置转换成功: {input_path.name} -> {output_dir.name}")

        return process_config

    @staticmethod
    def _resolve_path(path_str: Optional[str]) -> Optional[Path]:
        """
        转换路径字符串为 Path 对象

        支持以下格式：
        - ~/xxx - 相对于用户主目录
        - ./xxx - 相对于当前目录
        - /xxx - 绝对路径
        - xxx - 相对于当前目录

        参数:
            path_str: 路径字符串

        返回:
            Path 对象，如果输入为 None 则返回 None
        """
        if path_str is None:
            return None

        path = Path(path_str).expanduser()
        return path
